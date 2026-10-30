"""Broad video risk themes, shared by generation, saved selections and previews."""
import re

VIDEO_POLICY = 'video-risk-themes-v1'
VIDEO_GUIDANCE = (
    '按较高层级的风险控制缺陷再分类，不按措辞、设备名、站点或检查表大类拆分同义问题。'
    '优先沿用统一维度：作业隔离与消防防护不到位；个人劳动防护与着装不规范；'
    '卸油连接与操作流程不规范；作业监护与人员行为不规范；油品验收与质量控制不规范；'
    '设备设施运行维护不到位。仅有实质不同风险时才新增类别，不能照抄原检查内容当再分类。'
    '例如检维修未布置消防隔离、检维修防护隔离缺失、检修现场未设隔离与消防器材、'
    '员工打开加油机、自检、开启卸油口或计量井未放置围栏或消防用具，统一为作业隔离与消防防护不到位。'
    '同一问题有多个表现时只按主要风险归入一类。摘要综合描述该类实际表现，不编造输入没有的作业。'
)


def normalize_video_groups(analysis):
    """Join explicit synonyms across batches; never change issue membership."""
    merged = {}
    for group in analysis.get('groups', []):
        name = group['name'].strip()
        protection = re.search('隔离|围栏|围挡|警戒', name) or (
            '消防' in name and re.search('器材|缺失|摆放|未配|未临战', name))
        if protection and not re.search('个人|着装|安全帽|劳保', name): name = '作业隔离与消防防护不到位'
        entry = merged.setdefault(name, {'name': name, 'summary': group.get('summary') or name, 'issue_ids': []})
        entry['issue_ids'].extend(group['issue_ids'])
        # Keep one evidence-bound, AI-authored summary rather than concatenate
        # near-duplicate descriptions into an unreadable report paragraph.
        if len(group['issue_ids']) > entry.get('_largest', 0):
            entry['summary'] = group.get('summary') or name; entry['_largest'] = len(group['issue_ids'])
    values = [{key: value for key, value in group.items() if key != '_largest'} for group in merged.values()]
    return {**analysis, 'groups': sorted(values, key=lambda g: (-len(g['issue_ids']), g['name']))}


def selected_video_group(issues, analysis, selection=''):
    eligible = {r['issue_id'] for r in issues if r['mode']=='video'}
    choices = []
    for group in normalize_video_groups(analysis).get('groups', []):
        ids = set(group['issue_ids']) & eligible
        if ids: choices.append({**group, 'issue_ids': sorted(ids)})
    choices.sort(key=lambda g: (-len(g['issue_ids']), g['name']))
    return next((g for g in choices if g['name']==selection), choices[0] if choices else None)


def selected_video_issue(issues, group, selection=None):
    """Choose a photo within the active theme; stale/manual IDs never cross themes."""
    members = set((group or {}).get('issue_ids', []))
    photos = sorted((row for row in issues if row['mode']=='video'
        and row['issue_id'] in members and row.get('issue_photo')), key=lambda row:row['issue_id'])
    return next((row for row in photos if row['issue_id']==selection), photos[0] if photos else None)
