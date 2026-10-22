"""Scheduling periods, without changing the quarterly/monthly coverage-map API."""
from datetime import date, timedelta
from scheduling_map import period as coverage_period
from schedule_common import today


def period(source):
    if source.get('mode') != 'annual':
        return coverage_period(source)
    year = source.get('year', today().year)
    if isinstance(year, bool) or not str(year).isdigit() or not 2000 <= int(year) <= 2100:
        raise ValueError('年份须为2000至2100年。')
    year = int(year)
    start, end = date(year, 1, 1), date(year + 1, 1, 1)
    return dict(mode='annual', year=year, annual=1, label=f'{year}年',
                date_from=start.isoformat(), date_to=(end-timedelta(days=1)).isoformat()), start, end


def field_mode(mode):
    return 'offline' if mode == 'annual' else mode
