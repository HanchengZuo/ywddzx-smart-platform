"""Shared inspection completion rule for scheduling and dispatch progress."""


def completed_record_sql(mode, record='ins'):
    # SQL expressions are supplied by the calling query, never by a request.
    return f"({mode} <> 'online' OR {record}.inspector_completion_status = '已确认完成')"


def task_checklist_mode_sql(task='task'):
    # Annual metering video tasks are dispatched to field teams.
    return f"(CASE WHEN {task}.column_key = 'metering_video' THEN 'online' ELSE {task}.mode END)"
