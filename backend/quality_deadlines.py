"""Quality-only workflow clocks and auditable, transaction-safe timeout processing."""
import json
import logging
import os
import threading
import time
from datetime import datetime
from types import SimpleNamespace
from flask import g, jsonify, request
from psycopg2.extras import Json


def scan_interval_seconds():
    try:
        minutes = int(os.environ.get('QUALITY_DEADLINE_SCAN_MINUTES', '180'))
    except ValueError:
        minutes = 180
    return max(30, min(1440, minutes)) * 60


def policy_snapshot(cur):
    cur.execute('SELECT * FROM quality_deadline_policy WHERE id=1')
    return json.loads(json.dumps(dict(cur.fetchone()), default=lambda value: value.isoformat()))


def responsible_users(cur, core, stage, station_id, region):
    role = {'acceptance': 'station_manager', 'area_pending': 'area_account', 'quality_pending': 'quality_safety'}[stage]
    cur.execute("SELECT id,username,real_name,role,station_id FROM users WHERE role=%s AND account_status='active' ORDER BY id", (role,))
    users = cur.fetchall()
    selected = []
    for user in users:
        if stage == 'acceptance':
            allowed = user['station_id'] == station_id and core.can_sign_inspection_records(cur, user)
        elif stage == 'area_pending':
            from issue_appeals import area_regions
            allowed = core.normalize_station_region_value(region) in area_regions(core, cur, user)
        else:
            allowed = core.has_permission(cur, user, 'review_quality_appeals')
        if allowed:
            selected.append({key: user.get(key) for key in ('id', 'username', 'real_name', 'role')})
    return selected


def log_event(cur, kind, detail, *, inspection_id=None, issue_id=None, appeal_id=None,
              stage=None, started_at=None, deadline_at=None, policy=None, responsible=None, actor=None):
    cur.execute('''INSERT INTO quality_deadline_events
      (kind,detail,inspection_id,issue_id,appeal_id,stage,started_at,deadline_at,policy,responsible,actor)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
      (kind, detail, inspection_id, issue_id, appeal_id, stage, started_at, deadline_at,
       Json(policy or {}), Json(responsible or []), Json(actor or {'name': '系统时限任务'})))


def initialize_appeal_review(cur, core, appeal_id, user=None):
    cur.execute('''SELECT a.*,i.station_id,i.inspection_id,s.region FROM inspection_issue_appeals a
      JOIN issues i ON i.id=a.issue_id JOIN stations s ON s.id=i.station_id WHERE a.id=%s''', (appeal_id,))
    appeal = cur.fetchone()
    policy = policy_snapshot(cur)
    if not appeal or not policy['review_enabled']:
        return
    if appeal['review_started_at'] and appeal['review_started_at'] >= datetime.fromisoformat(policy['review_enabled_at']):
        return
    if appeal['created_at'] < datetime.fromisoformat(policy['review_enabled_at']):
        policy.update(policy['review_enabled_policy'])
    # Old active appeals receive a full grace period from rollout, not a retroactive timeout.
    cur.execute('''UPDATE inspection_issue_appeals SET review_deadline_at=
      GREATEST(created_at,%s::timestamptz) + make_interval(days=>%s),review_policy=%s
      ,review_started_at=GREATEST(created_at,%s::timestamptz)
      WHERE id=%s RETURNING review_deadline_at''', (policy['review_enabled_at'], policy['review_days'], Json(policy), policy['review_enabled_at'], appeal_id))
    deadline = cur.fetchone()['review_deadline_at']
    owners = responsible_users(cur, core, appeal['status'], appeal['station_id'], appeal['region'])
    cur.execute('UPDATE inspection_issue_appeals SET phase_responsible=%s WHERE id=%s',
                (Json({appeal['status']: owners}), appeal_id))
    log_event(cur, 'review_started', '申诉进入共享审核时限；片区通过后不重新计时。',
              inspection_id=appeal['inspection_id'], issue_id=appeal['issue_id'], appeal_id=appeal_id,
              stage=appeal['status'], deadline_at=deadline, policy=policy, responsible=owners,
              actor={key: user.get(key) for key in ('id','username','real_name','role')} if user else None)


def capture_quality_handoff(cur, core, appeal, user):
    cur.execute('SELECT station_id,inspection_id FROM issues WHERE id=%s', (appeal['issue_id'],))
    issue = cur.fetchone()
    owners = responsible_users(cur, core, 'quality_pending', issue['station_id'], appeal['region'])
    cur.execute("UPDATE inspection_issue_appeals SET phase_responsible=phase_responsible || %s::jsonb WHERE id=%s",
                (Json({'quality_pending': owners}), appeal['id']))
    enabled = policy_snapshot(cur)['review_enabled']
    log_event(cur, 'review_handoff', '片区通过，转质安部终审；' + ('继续使用原截止时间。' if enabled else '共享审核时限已关闭，继续人工审核。'),
              inspection_id=issue['inspection_id'], issue_id=appeal['issue_id'], appeal_id=appeal['id'],
              stage='quality_pending', deadline_at=appeal['review_deadline_at'], policy=appeal['review_policy'],
              responsible=owners, actor={key: user.get(key) for key in ('id','username','real_name','role')})


def run_deadline_scan(cur, core, *, scheduled=False):
    # All workers/replicas may start a timer. PostgreSQL elects one scan transaction.
    cur.execute('SELECT pg_try_advisory_xact_lock(66092026) AS acquired')
    if not cur.fetchone()['acquired']:
        return
    if scheduled:
        cur.execute('SELECT next_scan_at>CURRENT_TIMESTAMP AS deferred FROM quality_deadline_worker_state WHERE id=1')
        if cur.fetchone()['deferred']:
            return
    # A switch update waits for an in-flight scan, so no old-policy work commits after it returns.
    cur.execute('SELECT * FROM quality_deadline_policy WHERE id=1 FOR SHARE')
    switches = cur.fetchone()
    cur.execute("SELECT set_config('app.actor_id','',true)")
    cur.execute('''SELECT ins.id FROM inspections ins WHERE is_quality_deadline_table(ins.inspection_table_id)
      AND COALESCE(ins.sign_status,'待签名确认') <> '已签名确认' AND ins.inspector_completion_status='已确认完成'
      AND NOT EXISTS(SELECT 1 FROM issues i WHERE i.inspection_id=ins.id AND COALESCE(i.audit_status,'pending')='pending')
      AND %s AND (ins.quality_accept_started_at IS NULL OR ins.quality_accept_started_at < %s OR ins.quality_accept_deadline_at<=CURRENT_TIMESTAMP
        OR EXISTS(SELECT 1 FROM issues i WHERE i.inspection_id=ins.id AND i.audited_at AT TIME ZONE 'Asia/Shanghai'>ins.quality_accept_started_at))
      ORDER BY ins.id LIMIT 200''', (switches['acceptance_enabled'], switches['acceptance_enabled_at']))
    for candidate in cur.fetchall():
        cur.execute('SELECT refresh_quality_acceptance(%s)', (candidate['id'],))
        cur.execute('''SELECT ins.*,s.region,s.station_name,quality_accept_deadline_at<=CURRENT_TIMESTAMP AS overdue
          FROM inspections ins JOIN stations s ON s.id=ins.station_id WHERE ins.id=%s''', (candidate['id'],))
        ins = cur.fetchone()
        if not ins['overdue'] or ins['sign_status']=='已签名确认':
            continue
        # Lock the issue set before rechecking; concurrent audit/reset cannot slip past acceptance.
        cur.execute('SELECT audit_status FROM issues WHERE inspection_id=%s ORDER BY id FOR UPDATE', (ins['id'],))
        if any(row['audit_status'] not in ('approved','rejected') for row in cur.fetchall()):
            continue
        owners = responsible_users(cur, core, 'acceptance', ins['station_id'], ins['region'])
        owner_names = '、'.join(f"{u.get('real_name') or u['username']}（账号ID {u['id']}）" for u in owners) or '暂无具备权限的有效站点账号，需核查账号配置'
        detail = f"站点未在验收期限内签名，系统自动验收（截止 {ins['quality_accept_deadline_at'].isoformat()}）。待办理账号：{owner_names}。未生成或冒用人员签名；可作为后续考核追溯依据，责任需人工核实。"
        cur.execute("SELECT set_config('app.quality_auto_accept','1',true)")
        cur.execute("""UPDATE inspections SET sign_status='已签名确认',quality_accept_source='automatic',
          station_manager_signed_name='系统自动验收',station_manager_signature_path=NULL,
          station_manager_signed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=%s""", (ins['id'],))
        cur.execute("SELECT set_config('app.quality_auto_accept','',true)")
        cur.execute('''INSERT INTO inspection_issue_flow_history(issue_id,action_type,to_status,result,note,actor_name)
          SELECT id,'inspection_auto_accepted','已验收','系统自动验收',%s,'系统时限任务' FROM issues WHERE inspection_id=%s''', (detail, ins['id']))
        log_event(cur, 'acceptance_timeout', detail, inspection_id=ins['id'], stage='acceptance',
                  started_at=ins['quality_accept_started_at'], deadline_at=ins['quality_accept_deadline_at'],
                  policy=ins['quality_accept_policy'], responsible=owners)

    # Initialize still-pending legacy windows once. The issue trigger preserves them thereafter.
    cur.execute("""UPDATE issues SET quality_appeal_deadline_at=NULL WHERE id IN (
      SELECT i.id FROM issues i JOIN inspections ins ON ins.id=i.inspection_id
      WHERE %s AND ins.sign_status='已签名确认' AND i.audit_status='approved'
      AND i.status='待整改' AND (i.quality_appeal_deadline_at IS NULL OR i.quality_appeal_started_at < %s)
      AND is_quality_deadline_table(i.inspection_table_id) ORDER BY i.id LIMIT 200)""",
      (switches['appeal_enabled'], switches['appeal_enabled_at']))
    cur.execute("""SELECT a.id,a.issue_id FROM inspection_issue_appeals a JOIN issues i ON i.id=a.issue_id
      WHERE %s AND a.status IN ('area_pending','quality_pending') AND is_quality_deadline_table(i.inspection_table_id)
      AND (a.review_deadline_at IS NULL OR a.review_started_at < %s OR a.review_deadline_at<=CURRENT_TIMESTAMP AND a.review_policy->>'timeout_action'<>'manual')
      ORDER BY a.id LIMIT 200""", (switches['review_enabled'], switches['review_enabled_at']))
    for candidate in cur.fetchall():
        cur.execute('SELECT i.*,s.region FROM issues i JOIN stations s ON s.id=i.station_id WHERE i.id=%s FOR UPDATE OF i', (candidate['issue_id'],))
        issue = cur.fetchone()
        cur.execute('SELECT * FROM inspection_issue_appeals WHERE id=%s FOR UPDATE', (candidate['id'],))
        appeal = cur.fetchone()
        if not appeal or appeal['status'] not in ('area_pending','quality_pending') or issue['status']!='申诉中':
            continue
        initialize_appeal_review(cur, core, appeal['id'])
        cur.execute('SELECT *,review_deadline_at<=CURRENT_TIMESTAMP AS overdue FROM inspection_issue_appeals WHERE id=%s', (appeal['id'],))
        appeal = cur.fetchone()
        action = appeal['review_policy']['timeout_action']
        if not appeal['overdue'] or action == 'manual':
            continue
        approved = action == 'approve'
        stage = appeal['status']
        owners = responsible_users(cur, core, stage, issue['station_id'], issue['region'])
        stage_name = '片区初审' if stage == 'area_pending' else '质安部终审'
        result = '系统超时通过申诉' if approved else '系统超时拒绝申诉'
        detail = f'{stage_name}未在共享审核期限内完成。按规则v{appeal["review_policy"]["version"]}{result}，' + ('问题已销毁。' if approved else '恢复站点整改。')
        detail += '截止时具备办理权限的账号：' + ('、'.join(f"{u.get('real_name') or u['username']}（ID {u['id']}）" for u in owners) or '无，需核查权限配置') + '。责任需结合阶段接收记录人工核实。'
        prefix = 'area' if stage == 'area_pending' else 'quality'
        cur.execute(f'''UPDATE inspection_issue_appeals SET status=%s,timeout_at=CURRENT_TIMESTAMP,timeout_stage=%s,
          {prefix}_reason=%s,{prefix}_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=%s''',
          ('approved' if approved else 'rejected',stage,detail,appeal['id']))
        cur.execute("SELECT set_config('app.appeal_event','1',true)")
        if approved:
            cur.execute("""UPDATE issues SET status='已销毁',audit_status='rejected',audited_by=NULL,audited_at=CURRENT_TIMESTAMP,
              is_excellent=false,audit_source='manual',auto_audit_rule_id=NULL,auto_audit_rule_name=NULL,auto_audit_match_summary=NULL WHERE id=%s""", (issue['id'],))
        else:
            cur.execute("UPDATE issues SET status='待整改' WHERE id=%s", (issue['id'],))
        cur.execute('''INSERT INTO inspection_issue_flow_history(issue_id,action_type,from_status,to_status,result,note,actor_name)
          VALUES (%s,%s,'申诉中',%s,%s,%s,'系统时限任务')''',
          (issue['id'],'appeal_timeout_approved' if approved else 'appeal_timeout_rejected','已销毁' if approved else '待整改',result,detail))
        cur.execute("SELECT set_config('app.appeal_event','',true)")
        log_event(cur, 'review_timeout', detail, inspection_id=issue['inspection_id'], issue_id=issue['id'],
                  appeal_id=appeal['id'], stage=stage, started_at=appeal['review_started_at'], deadline_at=appeal['review_deadline_at'],
                  policy=appeal['review_policy'], responsible={'phase_start': appeal['phase_responsible'].get(stage,[]), 'at_timeout': owners})
    cur.execute('''UPDATE quality_deadline_worker_state SET last_success_at=CURRENT_TIMESTAMP,
      next_scan_at=CURRENT_TIMESTAMP+make_interval(secs=>%s) WHERE id=1''', (scan_interval_seconds(),))


def start_deadline_worker(namespace):
    core = SimpleNamespace(**namespace)
    def loop():
        while True:
            conn = cur = None
            try:
                conn = core.get_db_connection()
                cur = conn.cursor()
                cur.execute("SET LOCAL lock_timeout='3s'")
                cur.execute("SET LOCAL statement_timeout='30s'")
                run_deadline_scan(cur, core, scheduled=True)
                conn.commit()
            except Exception:
                if conn:
                    conn.rollback()
                    try:
                        cur.execute('''UPDATE quality_deadline_worker_state SET last_failure_at=CURRENT_TIMESTAMP,
                          next_scan_at=GREATEST(next_scan_at,CURRENT_TIMESTAMP+make_interval(secs=>%s)) WHERE id=1''',
                          (scan_interval_seconds(),))
                        conn.commit()
                    except Exception:
                        conn.rollback()
                logging.exception('Quality deadline scan failed; transaction rolled back, retrying')
            finally:
                core.close_db_resources(cur, conn)
            time.sleep(scan_interval_seconds())
    threading.Thread(target=loop, name='quality-deadlines', daemon=True).start()


def register_quality_deadlines(app, namespace):
    core = SimpleNamespace(**namespace)
    def run(operation):
        user = getattr(g, 'current_user', None)
        if not user:
            return jsonify(error='请先登录。'), 401
        if not core.is_root_user(user):
            return jsonify(error='仅root可管理质安流程时限。'), 403
        conn = cur = None
        try:
            conn = core.get_db_connection()
            cur = conn.cursor()
            result = operation(cur, user)
            conn.commit()
            return result
        except (ValueError, TypeError):
            if conn: conn.rollback()
            return jsonify(error='参数不正确，天数须为1至365的整数。'), 400
        except Exception:
            if conn: conn.rollback()
            app.logger.exception('Quality deadline management failed')
            return jsonify(error='时限管理暂不可用，请联系管理员检查数据库升级。'), 500
        finally:
            core.close_db_resources(cur, conn)

    @app.get('/api/management/quality-deadlines')
    def get_quality_deadlines():
        def operation(cur, user):
            policy = policy_snapshot(cur)
            cur.execute('SELECT last_success_at,last_failure_at,next_scan_at FROM quality_deadline_worker_state WHERE id=1')
            worker = cur.fetchone()
            cur.execute('SELECT COALESCE(real_name,username) AS name FROM users WHERE id=%s', (policy.get('updated_by'),))
            editor = cur.fetchone()
            return jsonify(policy=policy, editor=editor['name'] if editor else '系统默认', worker=worker,
                           scan_interval_minutes=scan_interval_seconds() // 60)
        return run(operation)

    @app.put('/api/management/quality-deadlines')
    def update_quality_deadlines():
        def operation(cur, user):
            data = request.get_json(silent=True) or {}
            stage = data.get('stage')
            if stage not in ('acceptance', 'appeal', 'review'):
                raise ValueError()
            if type(data.get('enabled')) is not bool or type(data.get('days')) is not int or not 1 <= data['days'] <= 365:
                raise ValueError()
            if stage == 'review' and data.get('timeout_action') not in ('manual','approve','reject'):
                raise ValueError()
            cur.execute('SELECT * FROM quality_deadline_policy WHERE id=1 FOR UPDATE')
            previous = cur.fetchone()
            if previous['version'] != data.get('version'):
                return jsonify(error='开关或时限已被其他操作更新，请刷新后重试。'), 409
            cur.execute(f'''UPDATE quality_deadline_policy SET {stage}_enabled=%s,{stage}_days=%s,
              {stage}_enabled_at=CASE WHEN NOT {stage}_enabled AND %s THEN CURRENT_TIMESTAMP ELSE {stage}_enabled_at END,
              {stage}_enabled_policy=CASE WHEN NOT {stage}_enabled AND %s THEN %s ELSE {stage}_enabled_policy END,
              timeout_action=%s,version=version+1,updated_at=CURRENT_TIMESTAMP,updated_by=%s WHERE id=1''',
              (data['enabled'],data['days'],data['enabled'],data['enabled'],
               Json({f'{stage}_days':data['days'],'version':previous['version']+1,**({'timeout_action':data['timeout_action']} if stage == 'review' else {})}),
               data.get('timeout_action') if stage == 'review' else previous['timeout_action'],user['id']))
            policy = policy_snapshot(cur)
            stage_name = {'acceptance':'站点签名验收','appeal':'站点发起申诉','review':'片区与质安部共享审核'}[stage]
            log_event(cur, 'policy_updated', f"root单独调整{stage_name}：{'启用' if data['enabled'] else '关闭'}时限，{data['days']}天。其他开关不变。关闭立即解除该项限制；重新启用给予待办完整期限；仅修改天数或处理方式影响后续新任务。",
                      stage=stage, policy=policy, actor={key: user.get(key) for key in ('id','username','real_name','role')})
            return jsonify(success=True, policy=policy)
        return run(operation)

    @app.get('/api/management/quality-deadlines/events')
    def quality_deadline_events():
        def operation(cur, user):
            page = max(1,int(request.args.get('page',1)))
            where, args = ['TRUE'], []
            kind = request.args.get('kind','')
            if kind:
                where.append('kind=%s'); args.append(kind)
            for key in ('inspection_id','issue_id'):
                if request.args.get(key):
                    where.append(f'{key}=%s'); args.append(int(request.args[key]))
            predicate = ' AND '.join(where)
            cur.execute(f'SELECT count(*) AS n FROM quality_deadline_events WHERE {predicate}',args)
            total = cur.fetchone()['n']
            cur.execute(f'SELECT * FROM quality_deadline_events WHERE {predicate} ORDER BY id DESC LIMIT 20 OFFSET %s',args+[(page-1)*20])
            return jsonify(items=cur.fetchall(),total=total)
        return run(operation)
