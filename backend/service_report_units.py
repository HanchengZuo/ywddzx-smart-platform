"""Chapter-two hierarchy and per-evidence AI memory; statistics stay server-owned."""
from collections import defaultdict
from uuid import uuid4
from report_ai_memory import ReportMemory,current_report_ai_memory,reused_result
from ai_routing import current_model
from safety_report_data import unit_key
from service_report_analysis import run_ai,validate,memory_key

def hierarchy(rows,phrases):
    units=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    for row in sorted(rows,key=lambda r:r['issue_id']):
        stage=phrases.get(row['standard_key']) or row.get('stage') or row['content'] or '未设置环节'
        units[row['unit_name']][row['category']][stage].append(row)
    result=[]
    for unit,categories in sorted(units.items(),key=lambda item:unit_key(item[0])):
        category_rows=[]
        for number,(category,stages) in enumerate(sorted(categories.items(),key=lambda item:(-sum(len(v) for v in item[1].values()),item[0])),1):
            groups=[]
            for stage,issues in sorted(stages.items(),key=lambda item:(-len(item[1]),item[0])):
                groups.append({'key':memory_key('unit_group',[unit,category,stage]),'stage':stage,
                    'count':len(issues),'issue_ids':[r['issue_id'] for r in issues],
                    'station_names':sorted({r['station_name'] for r in issues}),
                    'modes':sorted({r['mode'] for r in issues})})
            category_rows.append({'name':category,'number':number,'count':sum(g['count'] for g in groups),
                'station_names':sorted({name for g in groups for name in g['station_names']}),'groups':groups})
        result.append({'unit_name':unit,'categories':category_rows})
    return result

def evidence_context(entries,by_id):
    return {'kind':'unit_evidence','items':[{'ref':f'G{i+1}','unit':unit,'category':category,'stage':group['stage'],
        'issues':[{'ref':f'I{identifier}','issue_id':identifier,'description':by_id[identifier]['description'],
            'photo':bool(by_id[identifier]['issue_photo']),'photo_path':by_id[identifier]['issue_photo']} for identifier in group['issue_ids']]}
        for i,(unit,category,group) in enumerate(entries)]}

def unit_discoveries(connect,cur,rows,phrases,settings,generate=False,log_usage=None):
    result=hierarchy(rows,phrases);by_id={r['issue_id']:r for r in rows};pending=[]
    contexts={g['key']:evidence_context([(u['unit_name'],c['name'],g)],by_id)
        for u in result for c in u['categories'] for g in c['groups']}
    keys=[memory_key('service_unit_evidence',context) for context in contexts.values()]
    conn=None
    try:
        if cur is None:conn=connect();cur=conn.cursor()
        cur.execute('SELECT cache_key,payload FROM inspection_report_ai_memory WHERE cache_key=ANY(%s)',(keys,))
        cache={r['cache_key']:r['payload'] for r in cur.fetchall()}
    finally:
        if conn:conn.close()
    for unit in result:
        for category in unit['categories']:
            for group in category['groups']:
                entry=(unit['unit_name'],category['name'],group)
                context=contexts[group['key']]
                payload=cache.get(memory_key('service_unit_evidence',context))
                override=settings.get('unit_evidence',{}).get(group['key'],{})
                saved=validate(payload,context)['items']['G1'] if payload else {}
                group.update(summary=override.get('summary',saved.get('summary','')),
                    photo_ids=override.get('photo_ids',[int(ref[1:]) for ref in saved.get('photo_ids',[])]))
                allowed={i for i in group['issue_ids'] if by_id[i]['issue_photo']}
                group['photo_ids']=[i for i in group['photo_ids'] if i in allowed]
                group['ready']=bool(group['summary']) and (not allowed or bool(group['photo_ids']))
                if not group['ready']:pending.append(entry)
    if generate:
        memory=current_report_ai_memory() or ReportMemory(connect,'service-units-'+uuid4().hex,'on_site_service')
        reused=len(contexts)-len(pending)
        if reused:
            memory.record('service_unit_evidence','cache_hit',f'{reused} 个片区环节复用历史分析或人工配置，未重复调用AI。')
            if log_usage:log_usage(reused_result({'groups_reused':reused},current_model()))
        for offset in range(0,len(pending),6):
            batch=pending[offset:offset+6];payload=run_ai(connect,'service_unit_evidence',evidence_context(batch,by_id),log_usage)
            with memory.connection() as cursor:
                for i,entry in enumerate(batch):
                    context=evidence_context([entry],by_id);value=payload['items'][f'G{i+1}']
                    memory.put(cursor,memory_key('service_unit_evidence',context),'service_unit_evidence',entry[2]['issue_ids'],{'items':{'G1':value}},'')
        # Apply overrides to generated defaults through the same read path.
        if pending:return unit_discoveries(connect,None,rows,phrases,settings)
    return result
