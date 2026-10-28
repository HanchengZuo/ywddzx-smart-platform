"""Execution locks follow current assignees and post-dispatch evidence, not 17:00 UI release."""


def execution_locks(cur, day):
    cur.execute('''SELECT DISTINCT c.mode,c.inspector_ids,c.plan_team
      FROM inspection_schedule_cells c
      LEFT JOIN LATERAL (
        SELECT ev.created_at FROM inspection_schedule_events ev
        WHERE ev.mode=c.mode AND ev.year=c.year AND ev.period_number=c.period_number
          AND ev.station_id=c.station_id AND ev.column_key=c.column_key
          AND ev.after_date=c.scheduled_date AND ev.after_ids<>'[]'::jsonb
          AND (ev.after_team->>'leader_id') IS NOT DISTINCT FROM (c.plan_team->>'leader_id')
          AND (c.mode<>'online' OR ev.after_ids=c.inspector_ids)
          AND (ev.before_ids='[]'::jsonb OR ev.before_date IS DISTINCT FROM ev.after_date
            OR ev.before_team->>'leader_id' IS DISTINCT FROM ev.after_team->>'leader_id'
            OR (c.mode='online' AND ev.before_ids IS DISTINCT FROM ev.after_ids))
        ORDER BY ev.id DESC LIMIT 1
      ) dispatch ON TRUE
      JOIN inspection_schedule_tasks task
        ON task.mode=CASE WHEN c.mode='online' THEN 'online' ELSE 'offline' END
        AND task.year=c.year AND task.period_number=c.period_number
        AND task.station_id=c.station_id AND task.column_key=c.column_key
        AND task.scheduled_date=c.scheduled_date AND task.team_ids=c.inspector_ids
        AND task.status IN ('pending','completed','expired')
      WHERE c.scheduled_date=%s AND c.inspector_ids<>'[]'::jsonb
        AND EXISTS(SELECT 1 FROM inspections ins WHERE ins.station_id=c.station_id AND ins.inspection_table_id=task.table_id
          AND ins.inspection_date>=task.period_start
          AND ins.inspection_date<task.period_start+CASE WHEN c.mode='annual' THEN INTERVAL '1 year'
            WHEN c.mode='offline' THEN INTERVAL '3 months' ELSE INTERVAL '1 month' END
          AND ((c.inspector_ids @> jsonb_build_array(ins.inspector_id) AND ins.created_at>=COALESCE(dispatch.created_at,c.updated_at))
            OR EXISTS(SELECT 1 FROM issues issue WHERE issue.inspection_id=ins.id
              AND c.inspector_ids @> jsonb_build_array(issue.inspector_id)
              AND issue.created_at>=COALESCE(dispatch.created_at,c.updated_at))))''', (day,))
    fields, members, video = set(), set(), set()
    for row in cur.fetchall():
        if row['mode'] == 'online':
            video.update(row['inspector_ids'])
        elif row['plan_team']:
            fields.add(row['plan_team']['leader_id'])
            members.update(row['inspector_ids'])
    return dict(field_leaders=fields, field_members=members, video_members=video)


def change_modes(person):
    # Unassigned people retain existing actuals rules; assigned people use the
    # more precise task evidence supplied by the server's grouping context.
    return set(person['execution_modes']) if 'execution_modes' in person else {
        row['mode'] for row in person.get('actual_modes', [])}
