"""Bounded date selection shared by personnel grouping and station dispatch."""
import json
from schedule_common import day_value, today

MAX_BATCH_DAYS = 31


def planning_days(values, *, earliest=None):
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except (ValueError, TypeError) as exc:
            raise ValueError('请选择有效的排班日期。') from exc
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_BATCH_DAYS:
        raise ValueError(f'每批请选择1至{MAX_BATCH_DAYS}个日期。')
    days = [day_value(value) for value in values]
    if len(set(days)) != len(days):
        raise ValueError('排班日期不能重复。')
    if any(day < (earliest or today()) for day in days):
        raise ValueError('只能安排今天或未来日期，过去安排仍保留为历史记录。')
    return sorted(days)


def eligible_dates(cur, names, *, grouped=False, as_of=None):
    if grouped:
        cur.execute('''SELECT t.day,t.revision,jsonb_array_length(t.assignments) AS people_count
          FROM staff_daily_teams t JOIN quality_work_calendar c ON c.day=t.day AND c.working
          WHERE t.day >= %s AND jsonb_array_length(t.assignments)>0 ORDER BY t.day''', (as_of or today(),))
    else:
        cur.execute('''SELECT a.day,COUNT(*) AS people_count,
            COALESCE(MAX(t.revision),0) AS revision
          FROM staff_availability a JOIN quality_work_calendar c ON c.day=a.day AND c.working
          LEFT JOIN staff_daily_teams t ON t.day=a.day
          WHERE a.day >= %s AND a.person_name=ANY(%s)
          GROUP BY a.day HAVING COUNT(DISTINCT a.person_name)=%s
            AND BOOL_AND(a.available IS NOT NULL) ORDER BY a.day''', (as_of or today(), names, len(names)))
    return [dict(day=row['day'].isoformat(), weekday='星期'+'一二三四五六日'[row['day'].weekday()],
                 people_count=row['people_count'], revision=row['revision'], grouped=row['revision']>0)
            for row in cur.fetchall()]
