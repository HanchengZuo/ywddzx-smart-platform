"""Safety report evidence and deterministic, independently counted onsite/video data."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import re

TABLES = {'onsite': '质量安全环保检查表（现场）', 'video': '质量安全环保检查表（视频）'}
UNIT_ORDER = ['浦东', '闵普徐', '松金', '嘉青', '南汇', '宝静', '奉贤', '崇明']
ONSITE_PAGES = [('设备设施', '2. 设备设施类问题', 2), ('污染防治', '3. 污染防治类问题', 1),
    ('能力培训和意识', '4. 能力培训和意识类问题', 1), ('风险合规', '5. 风险合规类问题', 1),
    ('其他隐患类', '6. 其他对生产经营有影响的问题', 1)]
VIDEO_PAGES = [('设备维修作业', '7. 设备检维修作业类问题'), ('卸油作业', '8. 卸油作业类问题'),
    ('现场加油作业', '9. 现场加油作业类问题'), ('油品质量控制', '10. 油品质量控制类问题')]
ALIASES = [('车间站队组织开展危害因素辨识', '危害因素识别'), ('组织开展隐患排查工作', '隐患排查治理'),
    ('QHSE证照齐全且有效', '证照及许可'), ('需持证上岗的人员按有关规定培训取证', '人员持证'),
    ('卸油静电接地报警器、卸油人体静电释放器、接地桩', '卸油区静电管理相关装置'),
    ('办公生活辅助区域', '办公生活辅助区域'), ('环保设施配置齐全', '环保设施'),
    ('固体废物的运输、储存、处置、转移', '固废管理'), ('落实国家和地方排污许可制', '排污管理'),
    ('常用计量器具管理', '液位仪')]


def fields(value):
    """A field starts only at a labelled line; multiline scoring requirements stay intact."""
    result, key = {}, None
    labels = {'序号', '类别', '检查主题', '检查项', '检查内容', '依据', '评分项', '分值', '评分说明',
        '检查方式', '规范ID', '考核标准', '评分标准', '适用范围', '规范标签', '是否禁止项'}
    for line in str(value or '').replace('\\n', '\n').splitlines():
        match = re.match(r'^\s*([^：:]{1,32})[：:](.*)$', line)
        if match and match[1].strip() in labels:
            key = match[1].strip()
            result[key] = match[2].strip()
        elif key:
            result[key] += '\n' + line.strip()
    return result


def unit(row):
    name = str(row.get('region') or '').replace('闵浦徐', '闵普徐').strip()
    # Use the actual archive affiliation, never infer an equity company from a station's name.
    base = name.replace('管理片区', '').replace('片区', '').removesuffix('公司')
    return base or '未设置所属单位'


def unit_key(name):
    return (UNIT_ORDER.index(name) if name in UNIT_ORDER else len(UNIT_ORDER), name)


def serialize(row):
    data = fields(row.get('standard_detail_text'))
    mode = 'video' if row.get('checklist_mode') == 'online' else 'onsite'
    topic = data.get('检查主题') or '未设置检查主题'
    content = data.get('检查内容') or ''
    serial = data.get('序号', '').strip()
    if mode == 'video':
        if serial == '13' or content in ('', '/', '其他') or topic == '其他': content = '其他隐患类'
        content = content.replace('加油站设备维修作业', '设备维修作业')
        topic = content
    else:
        if serial == '50': content = '其他'
        for start, short in ALIASES:
            if content.startswith(start): content = short; break
        if topic == '其他对生产经营有影响的问题隐患': topic = '其他隐患类'
    return {'issue_id': int(row['id']), 'station_id': row['station_id'], 'station_name': row.get('station_name') or '',
        'unit_name': unit(row), 'mode': mode, 'topic': topic, 'category_name': content or '未设置检查内容',
        'external_standard_id': str(row.get('standard_id') or ''), 'standard_detail_text': row.get('standard_detail_text') or '',
        'requirement': data.get('评分说明') or '', 'description': row.get('description') or '',
        'issue_photo': row.get('issue_photo') or '', 'report_date': str(row.get('report_date') or '')}


def distribution(rows, key):
    counts = Counter(row[key] for row in rows)
    total = len(rows)
    return [{'name': name, 'count': count, 'percentage': round(count * 100 / total, 2) if total else 0}
            for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def groups(rows, key):
    result = defaultdict(list)
    for row in rows: result[row[key]].append(row)
    return dict(result)


def period_label(start, end):
    last = end - timedelta(days=1)
    if (start.year, start.month) == (last.year, last.month): return f'{start.year}年{start.month:02d}月'
    return f'{start:%Y年%m月%d日}至{last:%Y年%m月%d日}'


def scope(rows, visits, mode, label):
    mode_rows = [row for row in rows if row['mode'] == mode]
    stations = {row['station_id'] for row in mode_rows}
    mode_visits = [row for row in visits if ('video' if row['checklist_mode'] == 'online' else 'onsite') == mode]
    stations.update(row['station_id'] for row in mode_visits)
    units = {}
    for row in mode_visits:
        units.setdefault(unit(row), {'stations': set(), 'count': 0})['stations'].add(row['station_id'])
    for row in mode_rows:
        group = units.setdefault(row['unit_name'], {'stations': set(), 'count': 0})
        group['stations'].add(row['station_id']); group['count'] += 1
    total = len(mode_rows)
    unit_rows = [{'unit_name': name, 'station_count': len(data['stations']), 'issue_count': data['count'],
        'percentage': round(data['count'] / total * 100, 1) if total else 0,
        'average_issue_count': round(data['count'] / len(data['stations']), 1) if data['stations'] else 0}
        for name, data in sorted(units.items(), key=lambda item: unit_key(item[0]))]
    regions = sum(name in UNIT_ORDER for name in units)
    average = round(total / len(stations), 1) if stations else 0
    title = '现场检查' if mode == 'onsite' else '视频扫站检查'
    intro = f'{label}，对{regions}个管理片区、{len(units)-regions}个合资公司开展{title}，共计检查加油站{len(stations)}座，发现问题{total}项，站均问题{average:.1f}个。'
    details = '；'.join(f"{u['unit_name']}{u['station_count']}个站点，共{u['issue_count']}项，占比{u['percentage']:.1f}%" for u in unit_rows)
    return {'mode': mode, 'label': title, 'table_name': TABLES[mode], 'region_count': regions,
        'holding_unit_count': len(units)-regions, 'station_count': len(stations), 'total_issue_count': total,
        'average_issue_count': average, 'narrative': intro + ('各管理片区及合资公司问题数量如下：' + details + '。' if details else ''),
        'overview': intro, 'unit_text': details, 'units': unit_rows,
        'category_field': '检查主题' if mode == 'onsite' else '检查内容',
        'category_distribution': distribution(mode_rows, 'topic'), 'detail_distribution': distribution(mode_rows, 'category_name')}


def is_before(value, end):
    if value is None: return False
    if isinstance(value, str):
        try: value = datetime.fromisoformat(value)
        except ValueError: return False
    if isinstance(value, datetime):
        if value.tzinfo: value = value.astimezone(ZoneInfo('Asia/Shanghai'))
        value = value.date()
    return isinstance(value, date) and value < end


def pending_at(row, events, end):
    """Reconstruct the cutoff, rather than counting today's state in an old month's report."""
    before = [event for event in events if is_before(event.get('created_at'), end)]
    audits = [e for e in before if e['action_type'] == 'audit_changed']
    approved = audits[-1]['to_status'] == '审核通过' if audits else row.get('audit_status') == 'approved' and (
        not row.get('audited_at') or is_before(row.get('audited_at'), end))
    if not approved: return None
    states = [e['to_status'] for e in before if e.get('to_status') in ('待整改', '待复核', '已闭环', '站级无法整改', '申诉中', '已销毁')]
    state = states[-1] if states else '待整改'
    if not states:
        # Old imports may precede lifecycle logging. Use only dated source facts,
        # never a later closure to rewrite the state of an earlier reporting month.
        if is_before(row.get('review_at'), end):
            result = row.get('review_result')
            state = ('已闭环' if result in ('整改通过', '已整改') else '站级无法整改'
                if result in ('通过站级无法整改', '站级无法整改') else '待整改')
        elif is_before(row.get('rectification_at'), end): state = '待复核'
    if state != '待整改': return None
    signs = [e for e in before if e['action_type'] in ('inspection_signed', 'inspection_auto_accepted', 'inspection_reset')]
    signed = (signs[-1]['action_type'] == 'inspection_auto_accepted' or (
        signs[-1]['action_type'] == 'inspection_signed' and '撤销' not in (signs[-1].get('to_status') or '')
        and '未' not in (signs[-1].get('to_status') or ''))) if signs else is_before(row.get('station_manager_signed_at'), end)
    return '待整改' if signed else '待签名'


def backlog(rows, history, end, station_ids=None):
    events = defaultdict(list)
    for event in history: events[event['issue_id']].append(event)
    result = {'onsite': {}, 'video': {}}
    for row in rows:
        if station_ids is not None and row['station_id'] not in station_ids: continue
        status = pending_at(row, events[row['id']], end)
        if not status: continue
        mode = 'video' if row['checklist_mode'] == 'online' else 'onsite'
        data = result[mode].setdefault(unit(row), {'pending_sign': 0, 'pending_rectification': 0})
        data['pending_sign' if status == '待签名' else 'pending_rectification'] += 1
    return {mode: [{'unit_name': name, **value} for name, value in sorted(data.items(), key=lambda item: unit_key(item[0]))]
            for mode, data in result.items()}


def category_rows(rows, mode, category):
    candidates = [row for row in rows if row['mode'] == mode]
    if category == '__typical__': return candidates
    if category.startswith('content:'): return [row for row in candidates if row['category_name'] == category[8:]]
    if category == '风险合规': return [row for row in candidates if row['topic'] in ('风险隐患', '合规性管理')]
    return [row for row in candidates if row['topic'] == category]
