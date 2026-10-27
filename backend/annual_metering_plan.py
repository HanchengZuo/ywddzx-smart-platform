"""Shared monthly targets and annual coverage, using either applicable metering record."""
import json
import logging
from collections import Counter
from datetime import date
from flask import g, jsonify, request
from inspection_schedule_catalog import normalized_region, roster_position, OFFLINE_GROUPS
from schedule_common import ScheduleConflict, lock_schedule, today


def plan_state(cur, year, month, *, ignore_plan_day=None, ignore_plan_days=()):
    ignored = list(ignore_plan_days) + ([ignore_plan_day] if ignore_plan_day else [])
    cur.execute('''SELECT p.*,COALESCE(NULLIF(TRIM(u.real_name),''),u.username,'未记录') AS updated_by_name,
      to_char(p.updated_at,'YYYY-MM-DD HH24:MI:SS') AS saved_at
      FROM annual_metering_plans p LEFT JOIN users u ON u.id=p.updated_by WHERE p.year=%s''', (year,))
    saved = cur.fetchone() or {}
    cur.execute('SELECT id,region,station_name,monitoring_status FROM stations WHERE include_offline_plan=TRUE')
    stations = [s for s in cur.fetchall() if roster_position(s,'annual')]
    regions = Counter(normalized_region(s['region']) for s in stations)
    start, end = date(year,month,1), date(year+1,1,1) if month==12 else date(year,month+1,1)
    cur.execute('''SELECT ins.station_id,BOOL_OR(ins.inspection_date>=%s AND ins.inspection_date<%s) AS in_month
      FROM inspections ins JOIN inspection_tables t ON t.id=ins.inspection_table_id
      JOIN stations s ON s.id=ins.station_id
      WHERE t.is_active=TRUE AND (SELECT COUNT(*) FROM inspection_tables definition
        WHERE definition.table_name=t.table_name AND definition.checklist_mode=t.checklist_mode AND definition.is_active=TRUE)=1 AND (
        (t.table_name='计量稽查检查表（现场）' AND t.checklist_mode='offline') OR
        (t.table_name='计量稽查检查表（视频）' AND t.checklist_mode='online' AND s.monitoring_status='未运行'))
      AND ins.inspection_date>=%s AND ins.inspection_date<%s GROUP BY ins.station_id''',
      (start,end,date(year,1,1),date(year+1,1,1)))
    records=cur.fetchall()
    actual = {r['station_id'] for r in records if r['in_month']}
    annual = {r['station_id'] for r in records}
    cur.execute('''SELECT DISTINCT station_id FROM inspection_schedule_cells WHERE mode='annual' AND year=%s
      AND column_key='metering_site' AND jsonb_array_length(inspector_ids)>0
      AND scheduled_date>=%s AND scheduled_date<%s AND scheduled_date>=%s
      AND NOT (scheduled_date=ANY(%s::date[]))''', (year,start,end,today(),ignored))
    reserved = {r['station_id'] for r in cur.fetchall()} - actual
    checked = Counter(normalized_region(s['region']) for s in stations if s['id'] in actual)
    annual_checked = Counter(normalized_region(s['region']) for s in stations if s['id'] in annual)
    held = Counter(normalized_region(s['region']) for s in stations if s['id'] in reserved)
    quotas = saved.get('quotas', {})
    progress = [dict(region=r,total=regions[r],target=quotas.get(str(month),{}).get(r,0),
                     completed=checked[r],annual_completed=annual_checked[r],reserved=held[r],
                     remaining=max(0,quotas.get(str(month),{}).get(r,0)-checked[r]-held[r]))
                for r,_ in OFFLINE_GROUPS if regions[r]]
    return dict(year=year,month=month,quotas=quotas,revision=saved.get('revision',0),regions=progress,
                updated_by_name=saved.get('updated_by_name',''),updated_at=saved.get('saved_at',''))


def validate_quotas(value, regions):
    if not isinstance(value,dict) or any(k not in {str(m) for m in range(1,13)} for k in value):
        raise ValueError('请按1至12月填写片区站点配额。')
    result, totals = {}, Counter()
    limits = {r['region']:r['total'] for r in regions}
    for month, items in value.items():
        if not isinstance(items,dict): raise ValueError('月度计划格式不正确。')
        result[month] = {}
        for region,n in items.items():
            if region not in limits or type(n) is not int or not 0<=n<=limits[region]:
                raise ValueError('片区配额须为不超过已纳入站点数的非负整数。')
            if n: result[month][region]=n
            totals[region]+=n
    if any(n>limits[r] for r,n in totals.items()):
        raise ValueError('同一片区全年的配额合计不能超过其已纳入现场计划的站点数。')
    return {m:items for m,items in result.items() if items}


def register_metering_plan(app, *, connect, has_permission):
    @app.route('/api/inspection-schedule/metering-plan',methods=['GET','PUT'])
    def metering_plan():
        actor=getattr(g,'current_user',None)
        if not actor: return jsonify(success=False,error='请先登录。'),401
        conn=cur=None
        try:
            conn=connect();cur=conn.cursor()
            cur.execute("SET LOCAL lock_timeout='3s'; SET LOCAL statement_timeout='10s'")
            if not has_permission(cur,actor,'view_inspection_schedule'): raise PermissionError('当前账号无权查看巡检排班。')
            can_edit=has_permission(cur,actor,'edit_inspection_schedule')
            data=request.get_json(silent=True) if request.method=='PUT' else request.args
            if data is None or not hasattr(data,'get'): raise ValueError('请提交有效计划。')
            year,month=data.get('year',today().year),data.get('month',today().month)
            if any(isinstance(v,bool) or not str(v).isdigit() for v in (year,month)) or not 2000<=int(year)<=2100 or not 1<=int(month)<=12:
                raise ValueError('请选择有效年份和月份。')
            year,month=int(year),int(month)
            if request.method=='PUT':
                if not can_edit: raise PermissionError('当前账号只有查看权限，不能编辑排班。')
                lock_schedule(cur)
            result=plan_state(cur,year,month)
            if request.method=='PUT':
                if type(data.get('revision')) is not int or data['revision']!=result['revision']:
                    raise ScheduleConflict('计量年度计划已被修改，请重新载入后保存。')
                quotas=validate_quotas(data.get('quotas'),result['regions'])
                cur.execute('''INSERT INTO annual_metering_plans(year,quotas,revision,updated_by) VALUES(%s,%s,1,%s)
                  ON CONFLICT(year) DO UPDATE SET quotas=EXCLUDED.quotas,revision=annual_metering_plans.revision+1,
                  updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP''',(year,json.dumps(quotas),actor['id']))
                cur.execute('''INSERT INTO annual_metering_plan_events(year,before_quotas,after_quotas,actor_id,actor_name)
                  VALUES(%s,%s,%s,%s,%s)''',(year,json.dumps(result['quotas']),json.dumps(quotas),actor['id'],actor.get('real_name') or actor.get('username') or str(actor['id'])))
                result=plan_state(cur,year,month)
            conn.commit()
            response=jsonify(success=True,can_edit=can_edit,**result)
            response.headers['Cache-Control']='private, no-store'
            return response
        except (ValueError,PermissionError) as exc:
            if conn: conn.rollback()
            return jsonify(success=False,error=str(exc)),409 if isinstance(exc,ScheduleConflict) else 403 if isinstance(exc,PermissionError) else 400
        except Exception:
            if conn: conn.rollback()
            logging.exception('Annual metering plan failed')
            return jsonify(success=False,error='计量年度计划暂时无法处理，请稍后重试。'),500
        finally:
            if cur: cur.close()
            if conn: conn.close()
