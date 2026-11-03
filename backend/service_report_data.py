"""Deterministic service report evidence. Counts never come from a language model."""
from collections import Counter, defaultdict
from datetime import timedelta
import re
from safety_report_data import unit_name, unit_key, REGION_ORDER, period_label, is_before

TABLES = {'video': '现场检查明细表（视频）', 'onsite': '现场检查明细表（现场）'}
POLICY = 'service-first-chapter-124-1'


def onsite_category(fields):
    return fields.get('项目') or fields.get('考察类别区域') or ''


def onsite_stage(fields):
    return fields.get('内容') or fields.get('考察类别项目') or ''

def category_label(value):
    # Remove only score suffixes, not meaningful parentheses in the category itself.
    return re.sub(r'\s*[（(]\s*(?:共|总分|满分)?\s*\d+(?:\.\d+)?\s*分\s*[）)]\s*$', '',str(value or '')).strip() or '未设置类别'

def standard_key(row):
    mode = row.get('mode') or ('video' if row.get('checklist_mode')=='online' or row.get('table_name')==TABLES['video'] else 'onsite')
    return mode+':'+str(row.get('external_standard_id') or row.get('standard_id') or '')

def serialize(rows, catalog):
    standards = {item['key']:item for item in catalog}
    result=[]
    for row in rows:
        standard=standards.get(standard_key(row))
        if not standard: continue  # Unknown standards cannot supply a classification.
        data=standard['fields']; mode=standard['mode']
        category=category_label(data.get('检查类别') if mode=='video' else onsite_category(data))
        content=data.get('检查内容','') if mode=='video' else onsite_stage(data)
        result.append({'issue_id':int(row['id']), 'station_id':row['station_id'],
            'station_name':row.get('station_name') or '', 'unit_name':unit_name(row.get('region')),
            'mode':mode,'standard_key':standard['key'],'external_standard_id':standard['external_standard_id'],
            'category':category,'content':content,'description':row.get('description') or '',
            'issue_photo':row.get('issue_photo') or '', 'report_date':str(row.get('report_date') or '')})
    return result

def distribution(rows, key):
    counts=Counter(row[key] for row in rows)
    return [{'name':name,'count':count,'percentage':round(count*100/len(rows),2)}
        for name,count in sorted(counts.items(),key=lambda x:(-x[1],x[0]))]

def chosen(rows,settings):
    ids=settings.get('station_ids')
    return [row for row in rows if ids is None or row['station_id'] in ids]

def scope(issues,visits,mode=None):
    rows=[row for row in issues if mode is None or row['mode']==mode]
    visits=[row for row in visits if mode is None or ('video' if row['checklist_mode']=='online' else 'onsite')==mode]
    units={}
    for row in [*visits,*rows]:
        name=row.get('unit_name') or unit_name(row.get('region'))
        entry=units.setdefault(name,{'stations':{},'issue_count':0})
        entry['stations'][row['station_id']]=row.get('station_name') or ''
        if 'issue_id' in row: entry['issue_count']+=1
    unit_rows=[{'unit_name':name,'station_count':len(v['stations']),'station_names':sorted(v['stations'].values()),
        'issue_count':v['issue_count'],'average_issue_count':round(v['issue_count']/len(v['stations']),2) if v['stations'] else 0}
        for name,v in sorted(units.items(),key=lambda x:unit_key(x[0]))]
    stations={r['station_id'] for r in [*visits,*rows]}
    return {'mode':mode or 'all','units':unit_rows,'station_count':len(stations),'issue_count':len(rows),
        'region_count':sum(name in REGION_ORDER for name in units),'holding_count':sum(name not in REGION_ORDER for name in units),
        'average_issue_count':round(len(rows)/len(stations),2) if stations else 0,
        'categories':distribution(rows,'category'),'stages':distribution(rows,'stage') if rows and all('stage' in r for r in rows) else []}

def historical_status(row,events,end):
    events=[e for e in events if is_before(e.get('created_at'),end)]
    audits=[e for e in events if e['action_type']=='audit_changed']
    if audits: audit=audits[-1]['to_status']
    elif row.get('audited_at') and not is_before(row['audited_at'],end): audit='pending'
    else: audit=row.get('audit_status') or 'pending'
    if audit in ('rejected','审核否决'): return None
    states=[e['to_status'] for e in events if e.get('to_status') in ('待审核','待签名','待整改','待复核','已闭环','站级无法整改','申诉中','已销毁')]
    state=states[-1] if states else '待整改'
    if not states:
        if is_before(row.get('review_at'),end):
            result=row.get('review_result')
            state='已闭环' if result in ('整改通过','已整改') else '站级无法整改' if result in ('通过站级无法整改','站级无法整改') else '待整改'
        elif is_before(row.get('rectification_at'),end): state='待复核'
        elif not row.get('review_at') and not row.get('rectification_at'):
            state=row.get('status') or '待整改'
    if state=='已销毁': return None
    if audit not in ('approved','审核通过'): return '待审核'
    if state=='待整改' and not is_before(row.get('station_manager_signed_at'),end): return '待签名'
    return state

def cumulative(rows,history,end,settings):
    events=defaultdict(list); units={}
    for event in history: events[event['issue_id']].append(event)
    for row in chosen(rows,settings):
        state=historical_status(row,events[row['id']],end)
        if state is None: continue
        name=unit_name(row.get('region'))
        entry=units.setdefault(name,{'unit_name':name,'total_count':0,'rectified_count':0,'unable_count':0,'pending_count':0})
        entry['total_count']+=1
        entry['rectified_count' if state=='已闭环' else 'unable_count' if state=='站级无法整改' else 'pending_count']+=1
    result=sorted(units.values(),key=lambda r:unit_key(r['unit_name']))
    for row in result: row['rate']=row['rectified_count']/row['total_count'] if row['total_count'] else 0
    counts={key:sum(row[key] for row in result) for key in ('total_count','rectified_count','unable_count','pending_count')}
    return {'units':result,**counts,'cutoff':(end-timedelta(days=1)).isoformat(),
        'narrative':f"截至{end-timedelta(days=1):%Y年%m月%d日}，累计发现{counts['total_count']}项问题，已整改（已闭环）{counts['rectified_count']}项、站级无法整改{counts['unable_count']}项，尚未闭环{counts['pending_count']}项。请各片区尽快完成问题的确认和整改。"}

def build_report(start,end,issues,visits,pending,settings,phrases,analysis,examples,behavior_examples):
    rows=[dict(row,stage=phrases.get(row['standard_key']) or row['content'] or '未设置环节') for row in chosen(issues,settings)]
    visits=chosen(visits,settings)
    all_scope=scope(rows,visits); modes=[scope(rows,visits,mode) for mode in ('video','onsite')]
    top=all_scope['categories'][:3]
    label=period_label(start,end)
    narrative=(f"{label}，盛大公司业务督导中心针对加油站现场方面进行了视频+现场巡检，覆盖{all_scope['region_count']}个片区及"
        f"{all_scope['holding_count']}个股权单位共计{all_scope['station_count']}座加油站，发现各类问题{len(rows)}个。")
    return {'month':start.strftime('%Y-%m'),'month_label':label,'title':label+'现场服务检查报告',
        'data_policy_version':POLICY,'target_tables':list(TABLES.values()),'service_settings':settings,
        'summary':{'station_count':all_scope['station_count'],'total_issue_count':len(rows),'unit_count':len(all_scope['units']),
            'video_issue_count':modes[0]['issue_count'],'onsite_issue_count':modes[1]['issue_count'],
            'date_from':start.isoformat(),'date_to':(end-timedelta(days=1)).isoformat()},
        'overview_text':narrative,'focus_text':'问题主要涉及'+('、'.join(r['name'] for r in top) or '暂无对应类别')+'等关键领域，为后续问题整改和服务质量提升提供了精准数据支撑。',
        'scope':all_scope,'mode_summaries':modes,'unit_comparison':all_scope['units'],'cumulative_rectification':pending,
        'service_issues':rows,'category_examples':examples,'behavior_analysis':analysis,'behavior_examples':behavior_examples}
