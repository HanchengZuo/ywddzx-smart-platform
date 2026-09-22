"""Read-only, scoped operational analytics. No certificate or scoring data."""
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from flask import jsonify, request


PERMISSIONS = {
    'overview': 'view_operations_overview',
    'rectification': 'view_operations_rectification',
    'insights': 'view_operations_insights',
}
OPEN_PHASES = ('待验收', '待整改', '待复核', '申诉中')
PHASES = ('待审核', '待验收', '待整改', '待复核', '申诉中', '已闭环', '站级无法整改', '已销毁', '其他状态')


def parse_period(source, today=None):
    today = today or datetime.now(ZoneInfo('Asia/Shanghai')).date()
    try:
        start = datetime.strptime(source.get('date_from') or today.replace(day=1).isoformat(), '%Y-%m-%d').date()
        end = datetime.strptime(source.get('date_to') or today.isoformat(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValueError('请选择有效的开始和结束日期。') from None
    if end < start or (end - start).days > 365:
        raise ValueError('开始日期不能晚于结束日期，单次分析范围最多366天。')
    return start, end


def issue_cte(core, cur, user, source):
    start, end = parse_period(source)
    where, params = core.build_issue_list_visibility_scope(cur, user)
    where += ['i.created_at >= %s::date', 'i.created_at < %s::date']
    params += [start, end + timedelta(days=1)]
    # These predicates are the same as the issue list, including pending-audit visibility.
    return '''WITH scoped AS MATERIALIZED (
      SELECT i.id, i.station_id, s.station_name, COALESCE(NULLIF(s.region,''),'未分配片区') AS region,
        i.inspection_table_id, t.table_name,
        CASE WHEN t.checklist_mode='offline' THEN '现场' ELSE '视频' END AS mode,
        i.created_at, i.description,
        COALESCE(i.standard_id::text, NULLIF(i.internal_standard_id,''), '未关联规范') AS standard_key,
        LEFT(COALESCE(NULLIF(i.standard_detail_text,''),i.internal_standard_detail_text,''),140) AS standard_text,
        i.audit_status='approved' AND COALESCE(i.status,'')<>'已销毁' AS valid,
        CASE
          WHEN i.audit_status='rejected' OR i.status='已销毁' THEN '已销毁'
          WHEN COALESCE(i.audit_status,'pending')='pending' THEN '待审核'
          WHEN i.status='申诉中' THEN '申诉中'
          WHEN i.status IN ('已闭环','已整改') THEN '已闭环'
          WHEN i.status='站级无法整改' THEN '站级无法整改'
          WHEN i.status='待复核' THEN '待复核'
          WHEN i.status IN ('待整改','未整改','站经无法整改') THEN
            CASE WHEN ins.sign_status='已签名确认' OR ins.station_manager_signed_at IS NOT NULL
              OR NULLIF(TRIM(ins.station_manager_signature_path),'') IS NOT NULL
              OR NULLIF(TRIM(ins.station_manager_signed_name),'') IS NOT NULL
              THEN '待整改' ELSE '待验收' END
          ELSE '其他状态' END AS phase,
        GREATEST(0, (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')::date-i.created_at::date) AS age_days
      FROM issues i JOIN inspections ins ON ins.id=i.inspection_id
      JOIN stations s ON s.id=i.station_id JOIN inspection_tables t ON t.id=i.inspection_table_id
      WHERE ''' + ' AND '.join(where or ['TRUE']) + '''
    ), selected AS MATERIALIZED (SELECT * FROM scoped WHERE (%s='' OR region=%s)) ''' , params + [source.get('region',''), source.get('region','')]


def record_summary(core, cur, user, source):
    """Use record permissions independently, so BI access never widens business scope."""
    where, params = [], []
    if not (core.can_view_all_inspection_records(cur, user) or core.can_view_region_inspection_records(cur, user)):
        if not core.can_view_own_inspection_records(cur, user) or not user.get('station_id'):
            return None
        where.append('ins.station_id=%s')
        params.append(user['station_id'])
    for function, column, key in (
        (core.append_inspection_table_scope_filter, 'ins.inspection_table_id', 'limit_record_inspection_table_scope'),
        (core.append_station_region_scope_filter, 's.region', 'limit_record_station_region_scope'),
    ):
        if not function(cur, user, where, params, column, key):
            where.append('FALSE')
    core.append_pending_audit_inspection_visibility_filter(user, where)
    start, end = parse_period(source)
    where += ['ins.inspection_date >= %s', 'ins.inspection_date <= %s']
    params += [start, end]
    cur.execute('''WITH records AS MATERIALIZED (
        SELECT ins.*,COALESCE(NULLIF(s.region,''),'未分配片区') AS region
        FROM inspections ins JOIN stations s ON s.id=ins.station_id WHERE ''' + ' AND '.join(where) + '''
        ) SELECT COUNT(*) AS records, COUNT(DISTINCT ins.station_id) AS stations,
        COUNT(*) FILTER (WHERE ins.sign_status='已签名确认') AS signed,
        COUNT(*) FILTER (WHERE ins.quality_accept_source='automatic') AS auto_signed,
        (SELECT COALESCE(json_agg(region ORDER BY region),'[]') FROM (SELECT DISTINCT region FROM records) r) AS regions
        FROM records ins WHERE (%s='' OR region=%s)''', params + [source.get('region','')]*2)
    return dict(cur.fetchone())


def dashboard(core, cur, user, mode, source):
    cte, params = issue_cte(core, cur, user, source)
    cur.execute(cte + '''
      SELECT json_build_object(
        'regions', (SELECT COALESCE(json_agg(region ORDER BY region),'[]') FROM (SELECT DISTINCT region FROM scoped) r),
        'summary', (SELECT json_build_object('total',COUNT(*),'valid',COUNT(*) FILTER(WHERE valid),
          'stations',COUNT(DISTINCT station_id) FILTER(WHERE valid),
          'pending_audit',COUNT(*) FILTER(WHERE phase='待审核'),
          'closed',COUNT(*) FILTER(WHERE valid AND phase='已闭环'),
          'unable',COUNT(*) FILTER(WHERE valid AND phase='站级无法整改'),
          'destroyed',COUNT(*) FILTER(WHERE phase='已销毁'),
          'open',COUNT(*) FILTER(WHERE valid AND phase IN ('待验收','待整改','待复核','申诉中')),
          'aged',COUNT(*) FILTER(WHERE valid AND phase IN ('待验收','待整改','待复核','申诉中') AND age_days>=30)
        ) FROM selected),
        'phases', (SELECT COALESCE(json_agg(r ORDER BY phase),'[]') FROM (
          SELECT phase,COUNT(*) AS count FROM selected GROUP BY phase) r),
        'units', (SELECT COALESCE(json_agg(r ORDER BY valid DESC,region),'[]') FROM (
          SELECT region,COUNT(*) FILTER(WHERE valid) AS valid,COUNT(DISTINCT station_id) FILTER(WHERE valid) AS stations,
          COUNT(*) FILTER(WHERE valid AND phase='已闭环') AS closed,
          COUNT(*) FILTER(WHERE valid AND phase IN ('待验收','待整改','待复核','申诉中')) AS open
          FROM selected GROUP BY region) r)
      ) AS payload''', params)
    result = cur.fetchone()['payload']
    if mode == 'overview':
        result['records'] = record_summary(core, cur, user, source)
        # Include zero-problem stations' regions when the initial all-region view is loaded.
        if result['records']:
            result['regions'] = sorted(set(result['regions']) | set(result['records']['regions']))
        cur.execute(cte + '''SELECT created_at::date AS day,COUNT(*) AS registered,
          COUNT(*) FILTER(WHERE valid) AS valid,COUNT(*) FILTER(WHERE phase='已闭环' AND valid) AS closed
          FROM selected GROUP BY created_at::date ORDER BY day''', params)
        result['trend'] = [dict(r, day=r['day'].isoformat()) for r in cur.fetchall()]
        # Highlights reuse the identical issue visibility aliases without joining inspections.
        where, hp = core.build_issue_list_visibility_scope(cur, user)
        start, end = parse_period(source)
        where += ['i.created_at >= %s::date', 'i.created_at < %s::date', "i.audit_status='approved'"]
        hp += [start, end + timedelta(days=1)]
        if source.get('region'):
            where.append("COALESCE(NULLIF(s.region,''),'未分配片区')=%s")
            hp.append(source['region'])
        cur.execute('''SELECT COUNT(*) AS count FROM inspection_highlights i
          JOIN stations s ON s.id=i.station_id CROSS JOIN LATERAL (SELECT i.inspector_id) ins
          WHERE ''' + ' AND '.join(where), hp)
        result['highlights'] = cur.fetchone()['count']
    elif mode == 'rectification':
        cur.execute(cte + '''SELECT CASE WHEN age_days<7 THEN '0–6天' WHEN age_days<15 THEN '7–14天'
          WHEN age_days<30 THEN '15–29天' ELSE '30天及以上' END AS label,
          CASE WHEN age_days<7 THEN 0 WHEN age_days<15 THEN 1 WHEN age_days<30 THEN 2 ELSE 3 END AS rank,
          COUNT(*) AS count FROM selected WHERE valid AND phase IN ('待验收','待整改','待复核','申诉中')
          GROUP BY 1,2 ORDER BY 2''', params)
        result['ages'] = [dict(r) for r in cur.fetchall()]
        cur.execute(cte + '''SELECT station_id,station_name,region,COUNT(*) AS count,MAX(age_days) AS oldest
          FROM selected WHERE valid AND phase IN ('待验收','待整改','待复核','申诉中')
          GROUP BY station_id,station_name,region ORDER BY count DESC,station_id LIMIT 12''', params)
        result['stations'] = [dict(r) for r in cur.fetchall()]
    else:
        cur.execute(cte + '''SELECT inspection_table_id,table_name,mode,COUNT(*) AS count,
          COUNT(DISTINCT station_id) AS stations FROM selected WHERE valid
          GROUP BY inspection_table_id,table_name,mode ORDER BY count DESC,inspection_table_id''', params)
        result['tables'] = [dict(r) for r in cur.fetchall()]
        cur.execute(cte + '''SELECT standard_key,MIN(standard_text) AS detail,COUNT(*) AS count,
          COUNT(DISTINCT station_id) AS stations FROM selected WHERE valid
          GROUP BY standard_key ORDER BY count DESC,standard_key LIMIT 15''', params)
        result['standards'] = [dict(r) for r in cur.fetchall()]
    start, end = parse_period(source)
    result.update(date_from=start.isoformat(), date_to=end.isoformat(), generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat())
    return result


def details(core, cur, user, source):
    cte, params = issue_cte(core, cur, user, source)
    where = ['TRUE']
    if source.get('phase'):
        if source['phase'] not in PHASES:
            raise ValueError('问题阶段不正确。')
        where.append('phase=%s'); params.append(source['phase'])
    if source.get('open') == '1':
        where.append('valid AND phase=ANY(%s)'); params.append(list(OPEN_PHASES))
    for key, column in [('station_id','station_id'), ('table_id','inspection_table_id'), ('standard_key','standard_key')]:
        if source.get(key):
            value = source[key]
            if key.endswith('_id'):
                try: value = int(value)
                except (ValueError, TypeError): raise ValueError('明细筛选参数不正确。') from None
            where.append(f'{column}=%s'); params.append(value)
    if source.get('valid') == '1':
        where.append('valid')
    try: page = max(1, int(source.get('page',1)))
    except (TypeError, ValueError): raise ValueError('页码不正确。') from None
    if page > 100000:
        raise ValueError('页码不正确。')
    # One statement keeps count and rows consistent even if concurrent audits run.
    cur.execute(cte + ', filtered AS (SELECT * FROM selected WHERE ' + ' AND '.join(where) + ''')
      SELECT (SELECT COUNT(*) FROM filtered) AS total,
      COALESCE((SELECT json_agg(r) FROM (SELECT id,station_name,region,table_name,mode,description,phase,
      to_char(created_at,'YYYY-MM-DD HH24:MI') AS created_at FROM filtered
      ORDER BY id DESC LIMIT 20 OFFSET %s) r),'[]') AS rows''', params + [(page-1)*20])
    return dict(cur.fetchone(), page=page, page_size=20)


def register_operations(app, namespace):
    core = SimpleNamespace(**namespace)

    @app.get('/api/operations/<mode>')
    @app.get('/api/operations/<mode>/issues')
    def operations(mode):
        if mode not in PERMISSIONS:
            return jsonify(error='看板不存在。'), 404
        conn = cur = None
        try:
            user = core.get_current_request_user()
            conn = core.get_db_connection(); cur = conn.cursor()
            if not core.has_permission(cur, user, PERMISSIONS[mode]):
                return jsonify(error='当前账号无权查看此运营看板。'), 403
            cur.execute("SET LOCAL statement_timeout='10s'")
            result = details(core, cur, user, request.args) if request.path.endswith('/issues') else dashboard(core, cur, user, mode, request.args)
            return jsonify(success=True, **result)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception:
            logging.exception('Operations dashboard failed')
            return jsonify(error='看板数据暂时不可用，请稍后重试。'), 500
        finally:
            core.close_db_resources(cur, conn)
