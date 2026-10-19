"""Read-only station coverage by inspection record, independent of issue workflow."""
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import g, jsonify, request


PERMISSION = 'view_scheduling_map'


def period(source, today=None):
    today = today or datetime.now(ZoneInfo('Asia/Shanghai')).date()
    mode = source.get('mode', 'offline')
    if mode not in ('offline', 'online'):
        raise ValueError('请选择现场或视频检查。')

    def number(key, default, low, high):
        value = source.get(key, default)
        if isinstance(value, bool) or not str(value).isdigit() or not low <= int(value) <= high:
            raise ValueError('年份须为2000至2100年，季度为1至4，月份为1至12。')
        return int(value)

    year = number('year', today.year, 2000, 2100)
    if mode == 'offline':
        if source.get('month') not in (None, ''):
            raise ValueError('现场检查按季度统计，请选择年份和季度。')
        selected = number('quarter', (today.month-1)//3+1, 1, 4)
        month = (selected-1)*3+1
        start = date(year, month, 1)
        end = date(year+1, 1, 1) if selected == 4 else date(year, month+3, 1)
        label = f'{year}年第{selected}季度'
    else:
        if source.get('quarter') not in (None, ''):
            raise ValueError('视频检查按月统计，请选择年份和月份。')
        selected = number('month', today.month, 1, 12)
        start = date(year, selected, 1)
        end = date(year+1, 1, 1) if selected == 12 else date(year, selected+1, 1)
        label = f'{year}年{selected}月'
    return dict(mode=mode, year=year, **{'quarter' if mode == 'offline' else 'month': selected},
                label=label, date_from=start.isoformat(), date_to=(end-timedelta(days=1)).isoformat()), start, end


def coverage(cur, chosen, start, end, station_scope, table_scope):
    station_where, station_params = station_scope
    table_where, table_params = table_scope
    cur.execute('''WITH eligible_tables AS MATERIALIZED (
        SELECT t.id FROM inspection_tables t WHERE t.checklist_mode=%s AND ''' + ' AND '.join(table_where or ['TRUE']) + '''
      ), station_scope AS MATERIALIZED (
        SELECT s.id AS station_id,s.station_name,COALESCE(NULLIF(TRIM(s.region),''),'未填写片区') AS region,
          s.address,s.longitude,s.latitude,s.status
        FROM stations s WHERE ''' + ' AND '.join(station_where or ['TRUE']) + '''
      ), covered AS MATERIALIZED (
        SELECT DISTINCT ins.station_id FROM inspections ins
        JOIN eligible_tables t ON t.id=ins.inspection_table_id
        JOIN station_scope s ON s.station_id=ins.station_id
        WHERE ins.inspection_date >= %s AND ins.inspection_date < %s
      ), evaluated AS MATERIALIZED (
        SELECT s.*,c.station_id IS NOT NULL AS checked,
          COALESCE(s.longitude BETWEEN -180 AND 180 AND s.latitude BETWEEN -90 AND 90
            AND NOT (s.longitude=0 AND s.latitude=0),FALSE) AS has_coordinates
        FROM station_scope s LEFT JOIN covered c ON c.station_id=s.station_id
        WHERE EXISTS(SELECT 1 FROM eligible_tables)
      ) SELECT json_build_object(
        'has_tables',EXISTS(SELECT 1 FROM eligible_tables),
        'summary',(SELECT json_build_object('total',COUNT(*),'checked',COUNT(*) FILTER(WHERE checked),
          'remaining',COUNT(*) FILTER(WHERE NOT checked),
          'missing_coordinates',COUNT(*) FILTER(WHERE NOT checked AND NOT has_coordinates)) FROM evaluated),
        'regions',(SELECT COALESCE(json_agg(r ORDER BY region),'[]') FROM (
          SELECT region,COUNT(*) AS total,COUNT(*) FILTER(WHERE checked) AS checked,
            COUNT(*) FILTER(WHERE NOT checked) AS remaining,
            COUNT(*) FILTER(WHERE NOT checked AND NOT has_coordinates) AS missing_coordinates
          FROM evaluated GROUP BY region) r),
        'stations',(SELECT COALESCE(json_agg(r ORDER BY region,station_name,station_id),'[]') FROM (
          SELECT station_id,station_name,region,address,longitude,latitude,status,has_coordinates
          FROM evaluated WHERE NOT checked) r)
      ) AS data''', [chosen['mode']] + table_params + station_params + [start, end])
    return dict(cur.fetchone()['data'], period=chosen,
                generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'))


def register_scheduling_map(app, *, connect, has_permission, scope):
    @app.get('/api/scheduling-map')
    def get_scheduling_map():
        user = getattr(g, 'current_user', None)
        if not user:
            return jsonify(success=False, error='请先登录。'), 401
        conn = cur = None
        try:
            conn = connect()
            cur = conn.cursor()
            if not has_permission(cur, user, PERMISSION):
                return jsonify(success=False, error='当前账号无权查看排班地图。'), 403
            chosen, start, end = period(request.args)
            station_scope, table_scope = scope(cur, user)
            cur.execute("SET LOCAL statement_timeout = '10s'")
            result = coverage(cur, chosen, start, end, station_scope, table_scope)
            response = jsonify(success=True, **result)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        except ValueError as exc:
            return jsonify(success=False, error=str(exc)), 400
        except Exception:
            logging.exception('Scheduling map coverage query failed')
            return jsonify(success=False, error='排班覆盖数据暂时无法读取，请稍后重试。'), 500
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
