"""Run after upgrading chinesecalendar when the next official calendar is published."""
from datetime import date, timedelta
import chinese_calendar as calendar
from psycopg2.extras import execute_values


def sync_calendar(cur):
    day = date(min(calendar.holidays).year, 1, 1)
    end = date(max(calendar.holidays).year, 12, 31)
    rows = []
    while day <= end:
        rows.append((day, calendar.is_workday(day), 'chinesecalendar-' + calendar.__version__))
        day += timedelta(days=1)
    # Existing deadline snapshots must not shift silently. Only fill new calendar dates.
    execute_values(cur, '''INSERT INTO quality_work_calendar(day,working,source) VALUES %s
      ON CONFLICT(day) DO NOTHING''', rows)
    return end


if __name__ == '__main__':
    from app import get_db_connection
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            end = sync_calendar(cur)
        conn.commit()
        print(f'Official work calendar available through {end.isoformat()}; existing dates preserved.')
    finally:
        conn.close()
