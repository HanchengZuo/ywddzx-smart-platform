"""Evidence-grounded final chapters, cached independently from PPT rendering."""
from service_report_analysis import run_ai

def context_for(report):
    groups=[{'unit':unit['unit_name'],'category':category['name'],'stage':group['stage'],
        'count':group['count'],'summary':group['summary'],'issue_ids':group['issue_ids']}
        for unit in report.get('unit_discoveries',[]) for category in unit['categories'] for group in category['groups']]
    if report['service_issues'] and (not groups or any(not g['summary'].strip() for g in groups)):
        raise ValueError('请先完成各片区环节问题概括，再生成问题总结与建议。')
    return {'kind':'conclusion','items':[{'ref':'R1','issue_ids':sorted(r['issue_id'] for r in report['service_issues']),
        'categories':report['scope']['categories'],'groups':groups}]}

def validate_conclusion(value,evidence):
    if not isinstance(value,dict):raise ValueError('报告总结格式无效。')
    allowed=set(evidence['issue_ids'])
    def text(item,key,limit):
        value=item.get(key)
        if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError('总结或建议文本为空或超过版面长度限制。')
    for key,count in [('themes',4),('recommendations',3)]:
        items=value.get(key)
        if not isinstance(items,list) or len(items)!=count:raise ValueError('请完整生成4项共性问题和3项下一步建议。')
        for item in items:
            if not isinstance(item,dict):raise ValueError('总结条目格式无效。')
            text(item,'title',26)
            ids=item.get('issue_ids')
            if not isinstance(ids,list) or not ids or any(type(i)is not int or i not in allowed for i in ids) or len(ids)!=len(set(ids)):
                raise ValueError('总结或建议引用了范围外的问题。')
            if key=='themes':
                points=item.get('points')
                if not isinstance(points,list) or not 2<=len(points)<=4:raise ValueError('每项共性问题需要2至4个要点。')
                for point in points:text({'point':point},'point',90)
                if sum(len(point) for point in points)>240:raise ValueError('共性问题要点过长。')
            else:text(item,'content',220)
    return value

def generate_conclusion(connect,report,log_usage=None):
    if not report['service_issues']:
        return {'generated':False,'themes':[{'title':title,'points':points,'issue_ids':[]} for title,points in [
            ('本期暂无审核通过问题',['当前范围没有可用于总结的审核通过问题。','不将暂无问题记录等同于站点不存在风险。']),
            ('共性表现暂无统计依据',['没有足够的问题依据归纳共性表现。','待形成真实检查记录后再进行分析。']),
            ('片区对比暂不形成结论',['本期不据此进行片区间问题表现对比。','不以数据缺失判断某个片区管理水平。']),
            ('亮点推广不作无据评价',['本页不编造已完成成果或亮点案例。','拟推广的措施应先核验实际执行效果。'])]],
            'recommendations':[{'title':title,'content':content,'issue_ids':[]} for title,content in [
                ('保持常态化巡检','持续按现场、视频检查要求开展检查，及时记录实际发现的问题。'),
                ('核验基础管理','结合检查规范开展自查，保持服务标准、现场秩序和工作资料的日常核验。'),
                ('跟进新增问题','对后续审核确认的问题及时开展验收、整改和复核，不将暂无问题等同于无风险。')]]}
    context=context_for(report)
    return dict(run_ai(connect,'service_conclusion',context,log_usage)['items']['R1'],generated=True)
