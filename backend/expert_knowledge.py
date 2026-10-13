"""Global business-only RAG for cockpit-authorized experts. Never model-generated SQL."""
from datetime import date
from functools import lru_cache
import json
from pathlib import Path
import re
import subprocess
import time
import zipfile
from xml.etree import ElementTree

from standard_retrieval import ALIASES, CatalogIndex, excerpt, tokens

MAX_CONTEXT = 24000
MAX_EVIDENCE = 24
SOURCES = ['外部规范', '内部规范', '检查表原件', '培训材料', '巡检问题与流转',
           '亮点', '巡检记录', '巡检计划', '站点与证照', '业务人员', '已生成报告', '系统反馈', '考核与AI用量', '系统流程说明']


def redact(text):
    text = str(text or '')
    text = re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)|(?<!\d)\d{17}[\dXx](?!\d)', '[个人号码已隐藏]', text)
    text = re.sub(r'(?i)(?:sk-[a-z0-9_-]{12,}|bearer\s+[a-z0-9._-]{20,})', '[凭据已隐藏]', text)
    text = re.sub(r'(?i)(?:密码|password|api[_-]?key|secret[_-]?key)\s*[:=：]\s*[^\s，,；;]+', '[凭据已隐藏]', text)
    return text


def normalize_request(data):
    if not isinstance(data, dict):
        raise ValueError('请求格式不正确。')
    question = data.get('question')
    if not isinstance(question, str) or not 2 <= len(question.strip()) <= 1500:
        raise ValueError('请输入2至1500字的问题。')
    start, end = data.get('date_from') or '', data.get('date_to') or ''
    if bool(start) != bool(end):
        raise ValueError('请选择完整的日期范围，或清空日期查询全部历史。')
    try:
        if start and (date.fromisoformat(end) < date.fromisoformat(start)):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('请选择有效的开始和结束日期。') from None
    region = data.get('region') or ''
    if not isinstance(region, str) or len(region) > 100:
        raise ValueError('片区筛选格式不正确。')
    return redact(question.strip()), {'date_from': start, 'date_to': end, 'region': region.strip()}


def source(identifier, kind, title, text, path):
    return {'key': identifier, 'kind': kind, 'title': redact(title)[:160],
            'text': redact(text), 'path': path}


def report_passages(value, parent=''):
    allowed = {'title', 'text', 'content', 'description', 'reason', 'summary', 'analysis',
               'suggestion', 'overview_text', 'finding_summary', 'work_plan', 'work_suggestions',
               'improvement_suggestions', 'next_steps', 'attribution_analysis', 'result_analysis'}
    if isinstance(value, str):
        return [value[:3000]] if parent in allowed else []
    if isinstance(value, dict):
        return [part for key, child in value.items() if key not in ('photo_path', 'photo_paths', 'image', 'image_url', 'base64')
                for part in report_passages(child, key)][:60]
    if isinstance(value, list):
        return [part for child in value[:60] for part in report_passages(child, parent)][:60]
    return []


def period_predicates(options, column, region_column=None):
    where, params = [], []
    if options['date_from']:
        where += [column + ' >= %s::date', column + " < %s::date + INTERVAL '1 day'"]
        params += [options['date_from'], options['date_to']]
    if region_column and options['region']:
        where.append(region_column + ' = %s')
        params.append(options['region'])
    return where, params


def keywords(question):
    # Bound SQL recall, then BM25 re-rank. Common question words are not useful evidence.
    stop = tokens('有什么哪些多少如何请问我们系统问题情况进行查询分析本月数据是否应该')
    terms = [term for term in tokens(question) if term not in stop][:16]
    synonyms = [term for group in ALIASES if any(term in question.lower() for term in group) for term in group]
    return list(dict.fromkeys(terms + synonyms))[:24]


def recall(cur, statement, fields, question, where=(), params=(), limit=160):
    where, params = list(where), list(params)
    terms = keywords(question)
    if terms:
        where.append('(' + ' OR '.join(f"COALESCE({field}::text,'') ILIKE ANY(%s)" for field in fields) + ')')
        patterns = ['%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%' for term in terms]
        params += [patterns] * len(fields)
    else:
        return []
    cur.execute(statement + ' WHERE ' + ' AND '.join(where or ['TRUE']) + ' ORDER BY 1 DESC LIMIT %s', params + [limit])
    return [dict(row) for row in cur.fetchall()]


def business_evidence(core, cur, question, options):
    result = []
    where, params = period_predicates(options, 'i.created_at', 's.region')
    base = '''FROM issues i JOIN inspections ins ON ins.id=i.inspection_id
              JOIN stations s ON s.id=i.station_id JOIN inspection_tables t ON t.id=i.inspection_table_id'''
    # Complete aggregate, not the number of retrieved snippets. Stored workflow states are labelled explicitly.
    cur.execute('''SELECT COUNT(*) AS registered,
        COUNT(*) FILTER(WHERE COALESCE(i.audit_status,'pending')='pending') AS pending_audit,
        COUNT(*) FILTER(WHERE i.audit_status='approved' AND COALESCE(i.status,'')<>'已销毁') AS approved,
        COUNT(*) FILTER(WHERE i.audit_status='rejected' OR i.status='已销毁') AS destroyed,
        COUNT(DISTINCT i.station_id) AS stations ''' + base + ' WHERE ' + ' AND '.join(where or ['TRUE']), params)
    summary = dict(cur.fetchone())
    result.append(source('stats:issues', '数据库统计', '问题登记完整统计',
                         json.dumps({'筛选范围': options, '口径': '按问题登记日期，包含待审核与否决历史；通过数排除已销毁', **summary}, ensure_ascii=False), '/inspection/issues'))
    cur.execute('SELECT station_name FROM stations ORDER BY station_name')
    mentioned = [row['station_name'] for row in cur.fetchall()
                 if len(row['station_name']) >= 2 and row['station_name'] in question][:12]
    if mentioned:
        cur.execute('''SELECT s.station_name,COUNT(*) AS registered,
            COUNT(*) FILTER(WHERE COALESCE(i.audit_status,'pending')='pending') AS pending_audit,
            COUNT(*) FILTER(WHERE i.audit_status='approved' AND COALESCE(i.status,'')<>'已销毁') AS approved ''' + base +
            ' WHERE ' + ' AND '.join(where + ['s.station_name=ANY(%s)']) + ' GROUP BY s.station_name ORDER BY s.station_name', params + [mentioned])
        result.append(source('stats:mentioned_stations', '数据库统计', '提问中明确提及站点的完整登记统计',
                             json.dumps([dict(row) for row in cur.fetchall()], ensure_ascii=False), '/inspection/issues'))
    cur.execute('''SELECT s.region, t.table_name, COALESCE(i.audit_status,'pending') AS audit_status,
        i.status AS stored_status, COUNT(*) AS count ''' + base + ' WHERE ' + ' AND '.join(where or ['TRUE']) +
        ' GROUP BY s.region,t.table_name,i.audit_status,i.status ORDER BY COUNT(*) DESC LIMIT 80', params)
    result.append(source('stats:distribution', '数据库统计', '片区、检查表与状态分布（最多前80组）',
                         json.dumps([dict(row) for row in cur.fetchall()], ensure_ascii=False, default=str), '/operations/overview'))
    rows = recall(cur, '''SELECT i.id,s.station_name,s.region,t.table_name,i.created_at,i.description,
        i.standard_id,i.standard_detail_text,i.audit_status,i.status,i.rectification_result,
        i.rectification_note,i.review_result,i.review_note ''' + base,
        ['i.id', 'i.description', 'i.standard_id', 'i.standard_detail_text', 'i.status', 'i.review_result', 'i.rectification_note', 'i.review_note', 's.station_name', 't.table_name'], question, where, params)
    for row in rows:
        result.append(source('issue:' + str(row['id']), '巡检问题', f"问题 #{row['id']} · {row['station_name']}",
                             json.dumps(row, ensure_ascii=False, default=str), '/inspection/issues'))
    if rows:
        cur.execute('''SELECT id,issue_id,action_type,from_status,to_status,result,note,actor_name,actor_role,created_at
            FROM inspection_issue_flow_history WHERE issue_id=ANY(%s) ORDER BY id DESC LIMIT 100''', [[row['id'] for row in rows]])
        for row in cur.fetchall():
            result.append(source('flow:' + str(row['id']), '问题流转', f"问题 #{row['issue_id']} · 流转事件",
                                 json.dumps(dict(row), ensure_ascii=False, default=str), '/inspection/issues'))
    if '申诉' in question:
        cur.execute('''SELECT a.status,COUNT(*) AS count FROM inspection_issue_appeals a
            JOIN issues i ON i.id=a.issue_id JOIN stations s ON s.id=i.station_id WHERE ''' +
            ' AND '.join(where or ['TRUE']) + ' GROUP BY a.status ORDER BY a.status', params)
        result.append(source('stats:appeals', '数据库统计', '按问题登记日期筛选的申诉完整统计',
                             json.dumps([dict(row) for row in cur.fetchall()], ensure_ascii=False), '/inspection/appeals'))
        for row in recall(cur, '''SELECT a.id,a.issue_id,a.status,a.reason,a.area_reason,a.quality_reason,a.updated_at,s.station_name,s.region
            FROM inspection_issue_appeals a JOIN issues i ON i.id=a.issue_id JOIN stations s ON s.id=i.station_id''',
            ["'申诉'",'a.reason','a.area_reason','a.quality_reason','s.station_name'], question, where, params):
            result.append(source('appeal:' + str(row['id']), '申诉', '问题 #' + str(row['issue_id']) + ' · 申诉',
                                 json.dumps(row, ensure_ascii=False, default=str), '/inspection/appeals'))
    where, params = period_predicates(options, 'i.created_at', 's.region')
    for row in recall(cur, '''SELECT i.id,i.description,i.audit_status,i.created_at,s.station_name,s.region,t.table_name
        FROM inspection_highlights i JOIN stations s ON s.id=i.station_id JOIN inspection_tables t ON t.id=i.inspection_table_id''',
        ['i.description', 's.station_name', 't.table_name', "'HL'||i.id::text"], question, where, params):
        result.append(source('highlight:' + str(row['id']), '亮点', '亮点 HL' + str(row['id']), json.dumps(row, ensure_ascii=False, default=str), '/inspection/highlights'))
    where, params = period_predicates(options, 'ins.inspection_date', 's.region')
    joins = ' FROM inspections ins JOIN stations s ON s.id=ins.station_id JOIN inspection_tables t ON t.id=ins.inspection_table_id'
    cur.execute('SELECT COUNT(*) AS records,COUNT(DISTINCT ins.station_id) AS stations, COUNT(*) FILTER(WHERE ins.sign_status=\'已签名确认\') AS accepted' + joins +
                ' WHERE ' + ' AND '.join(where or ['TRUE']), params)
    result.append(source('stats:records', '数据库统计', '巡检记录完整统计', json.dumps(dict(cur.fetchone()), ensure_ascii=False, default=str), '/inspection/records'))
    for row in recall(cur, '''SELECT ins.id,ins.inspection_date,ins.sign_status,ins.inspector_completion_status,
        ins.quality_accept_source,s.station_name,s.region,t.table_name''' + joins,
        ['s.station_name', 't.table_name', 'ins.id'], question, where, params):
        result.append(source('record:' + str(row['id']), '巡检记录', '巡检记录 #' + str(row['id']), json.dumps(row, ensure_ascii=False, default=str), '/inspection/records'))
    region_where, region_params = (['s.region=%s'], [options['region']]) if options['region'] else ([], [])
    for row in recall(cur, '''SELECT psi.id,pc.period_key,pc.coverage_type,t.table_name,s.station_name,s.region,
        psi.completion_status,psi.note FROM inspection_plan_station_items psi JOIN inspection_plan_configs pc ON pc.id=psi.plan_config_id
        JOIN stations s ON s.id=psi.station_id JOIN inspection_tables t ON t.id=pc.inspection_table_id''',
        ['pc.period_key','t.table_name','s.station_name','psi.note'], question, region_where + ['psi.is_included=TRUE'], region_params):
        result.append(source('plan:' + str(row['id']), '巡检计划', row['station_name'] + ' · ' + row['period_key'], json.dumps(row, ensure_ascii=False, default=str), '/inspection/plan'))
    for row in recall(cur, '''SELECT c.id,c.certificate_name,c.certificate_type,c.expiry_date,c.remark,s.station_name,s.region
        FROM station_certificates c JOIN stations s ON s.id=c.station_id''',
        ['c.certificate_name','c.certificate_type','c.remark','s.station_name'], question, region_where, region_params):
        result.append(source('certificate:' + str(row['id']), '证照', row['station_name'] + ' · ' + row['certificate_name'], json.dumps(row, ensure_ascii=False, default=str), '/inspection/certificates'))
    for row in recall(cur, 'SELECT s.id,s.station_name,s.region,s.address,s.station_type,s.asset_type,s.status,s.station_manager_name FROM stations s',
        ['s.station_name','s.region','s.address'], question, region_where, region_params):
        result.append(source('station:' + str(row['id']), '站点资料', row['station_name'], json.dumps(row, ensure_ascii=False, default=str), '/inspection/station-map'))
    for row in recall(cur, 'SELECT id,title,module,description,feedback_type,created_at FROM system_feedbacks',
        ['title','module','description'], question):
        result.append(source('feedback:' + str(row['id']), '系统反馈', row['title'], json.dumps(row, ensure_ascii=False, default=str), '/feedback'))
    for row in recall(cur, '''SELECT a.id,a.score_month,a.standard_id,a.manual_score,a.note,s.station_name,t.table_name
        FROM station_score_adjustments a JOIN stations s ON s.id=a.station_id JOIN inspection_tables t ON t.id=a.inspection_table_id''',
        ['a.note','a.standard_id','s.station_name','t.table_name'], question, region_where, region_params):
        result.append(source('score:' + str(row['id']), '站点评分人工调整', row['station_name'], json.dumps(row, ensure_ascii=False, default=str), '/assessment/station-score'))
    for row in recall(cur, '''SELECT id,real_name,role FROM users''', ['real_name','role'], question):
        result.append(source('profile:' + str(row['id']), '业务人员', row['real_name'] or '业务账号',
                             json.dumps(row, ensure_ascii=False, default=str), ''))
    for row in recall(cur, 'SELECT id,title,description,deadline_at,status FROM peer_review_tasks', ['title','description'], question):
        result.append(source('peer:' + str(row['id']), '考核互评任务', row['title'], json.dumps(row, ensure_ascii=False, default=str), '/assessment/peer-review'))
    if any(term in question.lower() for term in ['ai', '费用', '调用', 'token']):
        where, params = period_predicates(options, 'created_at')
        cur.execute('''SELECT usage_module, COUNT(*) FILTER(WHERE ai_called) AS calls,
            SUM(total_tokens_est) AS estimated_tokens,SUM(total_cost_est) AS estimated_cost
            FROM ai_usage_logs WHERE ''' + ' AND '.join(where or ['TRUE']) + ' GROUP BY usage_module', params)
        result.append(source('stats:ai', '数据库统计', 'AI使用记录（估算费用，非账单）',
                             json.dumps([dict(row) for row in cur.fetchall()], ensure_ascii=False, default=str), '/management/ai-usage'))
    return result


@lru_cache(maxsize=128)
def file_text(path, stamp, size):
    if size > 50 * 1024 * 1024:
        return '', '文件过大，未提取正文'
    try:
        extension = Path(path).suffix.lower()
        if extension == '.pdf':
            proc = subprocess.run(['pdftotext', '-f', '1', '-l', '80', '-enc', 'UTF-8', path, '-'],
                                  capture_output=True, timeout=6, check=True)
            text = proc.stdout.decode('utf-8', errors='replace')
            note = 'PDF仅检索前80页可提取文字；不识别扫描照片'
        elif extension in ('.pptx', '.docx'):
            with zipfile.ZipFile(path) as archive:
                names = [name for name in archive.namelist() if (re.fullmatch(r'ppt/slides/slide\d+\.xml', name)
                         if extension == '.pptx' else name == 'word/document.xml')]
                text_parts = []
                for name in names[:80]:
                    if archive.getinfo(name).file_size > 2 * 1024 * 1024:
                        continue
                    tree = ElementTree.fromstring(archive.read(name))
                    text_parts.append(' '.join(node.text or '' for node in tree.iter() if node.tag.endswith('}t')))
                text = '\n'.join(text_parts)
            note = 'Office文档仅检索文字，不识别图片或嵌入对象'
        elif extension in ('.txt', '.md', '.csv'):
            with open(path, 'r', encoding='utf-8', errors='replace') as stream:
                text = stream.read(100000)
            note = '文本最多检索前10万字'
        else:
            return '', '此格式暂仅检索标题与文件名，未提取正文'
        return text[:100000], note
    except (OSError, subprocess.SubprocessError, zipfile.BadZipFile, ElementTree.ParseError):
        return '', '无法提取正文，仅检索标题与文件名'


def safe_file(root, relative):
    root = Path(root).resolve()
    path = (root / str(relative).lstrip('/')).resolve()
    if root not in path.parents or path.relative_to(root).parts[0] not in ('inspection_originals', 'training_materials') or not path.is_file():
        return None
    return path


def knowledge_evidence(core, cur):
    result = []
    disabled = core.disabled_standard_ids(cur)
    for identifier, row in core.fetch_external_standard_map(cur).items():
        if identifier not in disabled:
            result.append(source('external:' + str(identifier), '外部规范', f"规范 {identifier} · {row['inspection_table_name']}",
                                 row.get('standard_detail_text', ''), '/inspection/checklist-originals'))
    cur.execute('SELECT internal_standard_id,content,field_values,notes FROM inspection_internal_standards WHERE is_active=TRUE')
    for row in cur.fetchall():
        result.append(source('internal:' + row['internal_standard_id'], '内部规范', '内部规范 ' + row['internal_standard_id'],
                             row['content'] or json.dumps(row['field_values'], ensure_ascii=False), '/inspection/standards'))
    cur.execute('''SELECT f.id,t.table_name AS title,f.file_path FROM inspection_table_original_files f
        JOIN inspection_tables t ON t.id=f.inspection_table_id WHERE t.is_active=TRUE ORDER BY f.id DESC''')
    files = [(dict(row), '检查表原件', '/inspection/checklist-originals') for row in cur.fetchall()]
    cur.execute('SELECT id,title,original_filename,file_path FROM training_materials ORDER BY updated_at DESC')
    files += [(dict(row), '培训材料', '/training/materials') for row in cur.fetchall()]
    notices = []
    if len(files) > 80:
        notices.append(f'文档共{len(files)}份，本次正文索引限最近80份；其余仅检索标题。')
    deadline = time.monotonic() + 18
    skipped = 0
    for index, (row, kind, route) in enumerate(files):
        text, note = '', '仅检索标题'
        path = safe_file(core.STORAGE_ROOT, row['file_path'])
        if path and index < 80 and time.monotonic() < deadline:
            stat = path.stat()
            text, note = file_text(str(path), stat.st_mtime_ns, stat.st_size)
        else:
            skipped += 1
        result.append(source(f"file:{kind}:{row['id']}", kind, row['title'],
                             row['title'] + '\n' + str(row.get('original_filename') or '') + '\n' + note + '\n' + text, route))
    if skipped:
        notices.append(f'{skipped}份文档因数量、提取时限或文件不可用，本次仅检索标题。')
    cur.execute('''SELECT DISTINCT ON(report_type) id,report_type,report_month,report_payload,generated_at
        FROM inspection_report_snapshots ORDER BY report_type,generated_at DESC''')
    for row in cur.fetchall():
        payload = row['report_payload']
        if isinstance(payload, str):
            payload = json.loads(payload)
        # Whitelist authored report text and summary, never image blobs, config secrets or arbitrary JSON.
        summary = {key: value for key, value in (payload.get('summary') or {}).items()
                   if isinstance(value, (int, float, str)) and 'path' not in key and 'url' not in key}
        text = json.dumps(summary, ensure_ascii=False, default=str)
        for key in ('overview_text', 'finding_summary', 'data_scope_note'):
            text += '\n' + str(payload.get(key) or '')[:4000]
        for section in (payload.get('sections') or [])[:40]:
            if isinstance(section, dict):
                text += '\n' + str(section.get('title') or '') + '\n' + str(section.get('content') or '')[:3000]
        text += '\n' + '\n'.join(report_passages(payload.get('deep_analysis') or {}))
        result.append(source('report:' + str(row['id']), '已生成报告', payload.get('title') or row['report_type'],
                             '生成时间：' + str(row['generated_at']) + '\n' + text, '/inspection/reports'))
    readme = Path(__file__).parent / 'assets/expert_knowledge/system_workflow.md'
    if readme.is_file():
        text = readme.read_text(encoding='utf-8')
        for index, section in enumerate(re.split(r'\n(?=## )', text)):
            result.append(source('workflow:' + str(index), '系统流程说明', section.split('\n')[0].lstrip('# '), section, ''))
    return result, notices


def select_evidence(question, records):
    facts = [row for row in records if row['key'].startswith('stats:')]
    candidates = [row for row in records if not row['key'].startswith('stats:')]
    # Long files are ranked on query-local windows, not millions of full-document postings.
    catalog = tuple((row['key'], row['title'], excerpt(row['text'], question, 4000)) for row in candidates)
    index = CatalogIndex(catalog)
    chosen = facts + [candidates[pos] for pos in index.rank(question)[:MAX_EVIDENCE - len(facts)]]
    result, remaining = [], MAX_CONTEXT
    for row in chosen:
        if remaining < 500:
            break
        text = excerpt(row['text'], question, min(1600, remaining - 250))
        item = {**row, 'text': text, 'id': 'S' + str(len(result) + 1)}
        remaining -= len(text) + len(row['title']) + 200
        result.append(item)
    return result


def retrieve(core, cur, question, options):
    business = business_evidence(core, cur, question, options)
    knowledge, notices = knowledge_evidence(core, cur)
    evidence = select_evidence(question, business + knowledge)
    return evidence, {'scope': '全局业务数据（不沿用其他页面的片区/检查表限制）',
                      'options': options, 'candidate_count': len(business) + len(knowledge),
                      'source_count': len(evidence), 'notices': notices,
                      'limits': '问题等明细为关键词候选样本，不能据其数量推断总数。完整统计只以数据库统计来源为准；知识文档不受登记日期筛选。'}
