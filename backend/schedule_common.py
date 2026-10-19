"""Shared scheduling invariants. No application import or startup side effects."""
from datetime import date, datetime
from zoneinfo import ZoneInfo


class ScheduleConflict(ValueError):
    pass


def today():
    return datetime.now(ZoneInfo('Asia/Shanghai')).date()


def day_value(value):
    if not isinstance(value, str):
        raise ValueError('请选择有效日期。')
    try:
        day = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('日期格式须为YYYY-MM-DD。') from exc
    if day.isoformat() != value:
        raise ValueError('日期格式须为YYYY-MM-DD。')
    return day


def lock_schedule(cur):
    # Availability, bulk dispatch and single-cell writes share a cross-worker lock.
    cur.execute('SELECT pg_advisory_xact_lock(9801,1)')


def working_days(cur, start, end):
    cur.execute('SELECT day,working,source FROM quality_work_calendar WHERE day >= %s AND day < %s ORDER BY day', (start, end))
    return [dict(day=row['day'].isoformat(), weekday='星期' + '一二三四五六日'[row['day'].weekday()],
                 source=row['source']) for row in cur.fetchall() if row['working']]


def require_workday(cur, day):
    cur.execute('SELECT working FROM quality_work_calendar WHERE day=%s', (day,))
    row = cur.fetchone()
    if not row:
        raise ValueError('该日期的官方工作日历尚未发布或未同步，暂不能排班。')
    if not row['working']:
        raise ValueError('请选择工作日（含法定调休工作日）。')
    if day < today():
        raise ValueError('过去日期仅查看实绩，不能新增或修改档期与排班。')
