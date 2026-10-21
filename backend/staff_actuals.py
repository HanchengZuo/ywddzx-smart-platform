"""Personnel actuals release at 17:00 Shanghai time; source records stay real-time."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import schedule_common


@dataclass(frozen=True)
class ActualsWindow:
    today: date
    as_of: date
    now: datetime

    def metadata(self):
        cutoff = datetime.combine(self.today,time(17),ZoneInfo('Asia/Shanghai'))
        return dict(actuals_release_at=cutoff.isoformat(),server_now=self.now.isoformat(),
                    actuals_as_of=self.as_of.isoformat(),actuals_pending=self.as_of<self.today)


def actuals_window(day=None):
    now = schedule_common.shanghai_now().astimezone(ZoneInfo('Asia/Shanghai'))
    day = day or now.date()
    return ActualsWindow(day,day if now.hour>=17 else day-timedelta(days=1),now)


def assert_actuals_window(window, day):
    current = actuals_window(day)
    if (current.today,current.as_of) != (window.today,window.as_of):
        raise schedule_common.ScheduleConflict('已到实绩核对时点或日期已变化，请重新读取后再操作。')


def merge_actual_modes(direct, work):
    """Union personal and delegated evidence without counting the same inspection twice."""
    ids = {mode:set(values) for mode,values in work.get('_actual_record_ids',{}).items()}
    counts = {row['mode']:row['count'] for row in work.get('actual_modes',[])}
    for row in direct:
        ids.setdefault(row['mode'],set()).update(row.get('record_ids',[]))
        counts[row['mode']] = max(counts.get(row['mode'],0),row['count'])
    modes = set(ids) | set(counts)
    return [dict(mode=mode,count=max(len(ids.get(mode,())),counts.get(mode,0))) for mode in sorted(modes)
            if ids.get(mode) or counts.get(mode)]
