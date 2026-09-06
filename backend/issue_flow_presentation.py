"""Read-only grouping of legacy duplicate events, without erasing audit evidence."""


def present_flow_rows(rows):
    appeals = [r for r in rows if r.get('action_type', '').startswith('appeal_')]
    result = []
    appeal_attempt = 0
    for row in rows:
        duplicate_of = None
        if row.get('action_type') in ('status_changed', 'audit_changed'):
            for appeal in appeals:
                if (not row.get('occurred_at') or row['occurred_at'] != appeal.get('occurred_at')
                        or row.get('actor_user_id') != appeal.get('actor_user_id')):
                    continue
                state_duplicate = (row['action_type'] == 'status_changed'
                                   and row.get('from_status') == appeal.get('from_status')
                                   and row.get('to_status') == appeal.get('to_status'))
                audit_duplicate = (row['action_type'] == 'audit_changed'
                                   and appeal['action_type'] == 'appeal_quality_approved'
                                   and row.get('result') == '审核否决')
                if state_duplicate or audit_duplicate:
                    duplicate_of = appeal
                    break
        if duplicate_of is not None:
            continue
        item = dict(row)
        item.pop('occurred_at', None)
        if item.get('action_type') == 'appeal_submitted':
            appeal_attempt += 1
        if item.get('action_type', '').startswith('appeal_'):
            item['appeal_attempt'] = max(1, appeal_attempt)
            if appeal_attempt > 1 and item['action_type'] == 'appeal_submitted':
                item['history_notice'] = '旧版本允许重复申诉产生的历史记录；现在每个问题只能申诉一次。'
        result.append(item)
    return result


def flow_event_presentation(event):
    kind = event.get('action_type', '')
    result = event.get('result') or ''
    if kind.startswith('appeal_'):
        event['stage_label'] = '申诉流程'
        if event.get('appeal_attempt', 1) > 1:
            event['stage_label'] = f'历史第{event["appeal_attempt"]}次申诉'
        event['tone'] = 'returned' if kind.endswith('_rejected') or kind == 'appeal_cancelled' else 'success' if kind.endswith('_approved') else 'info'
        if kind == 'appeal_area_approved':
            event['from_label'], event['to_label'] = '片区初审', '质安部终审'
        elif kind == 'appeal_submitted':
            event['from_label'], event['to_label'] = '待整改', '申诉中 · 待片区初审'
        elif kind.startswith('appeal_quality_'):
            event['from_label'] = '申诉中 · 质安部终审'
        elif kind.startswith('appeal_area_'):
            event['from_label'] = '申诉中 · 片区初审'
    elif kind == 'audit_changed':
        event['stage_label'] = '问题审核（非申诉审核）'
        event['tone'] = 'returned' if result == '审核否决' else 'success' if result == '审核通过' else 'info'
        if event.get('from_status') in ('审核通过', '审核否决') and result in ('审核通过', '审核否决') and result != event['from_status']:
            event['action_label'] = f'问题重新判定：{result}'
        elif result in ('审核通过', '审核否决'):
            event['action_label'] = f'{"自动" if event.get("note", "").startswith("自动审核") else "问题"}审核：{result}'
    elif kind in ('rectification_submitted', 'review_submitted'):
        event['stage_label'] = '整改复核'
        event['tone'] = 'returned' if result in ('整改不通过', '驳回站级无法整改') else 'success' if kind == 'review_submitted' else 'info'
    else:
        event['stage_label'] = '巡检流程'
        event['tone'] = 'info'
    event.setdefault('from_label', event.get('from_status'))
    event.setdefault('to_label', event.get('to_status'))
    return event
