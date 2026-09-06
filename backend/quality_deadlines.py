"""Quality-only workflow clocks and auditable, transaction-safe timeout processing."""
import json
import logging
import threading
import time
from types import SimpleNamespace
from flask import g, jsonify, request
from psycopg2.extras import Json


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
    if not appeal or appeal['review_deadline_at'] is not None:
        return
    policy = policy_snapshot(cur)
    # Old active appeals receive a full grace period from rollout, not a retroactive timeout.
    cur.execute('''UPDATE inspection_issue_appeals SET review_deadline_at=
      GREATEST(created_at,%s::timestamptz) + make_interval(days=>%s),review_policy=%s
      ,review_started_at=GREATEST(created_at,%s::timestamptz)
      WHERE id=%s RETURNING review_deadline_at''', (policy['activated_at'], policy['review_days'], Json(policy), policy['activated_at'], appeal_id))
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
    log_event(cur, 'review_handoff', '片区通过，转质安部终审；继续使用原截止时间。',
              inspection_id=issue['inspection_id'], issue_id=appeal['issue_id'], appeal_id=appeal['id'],
              stage='quality_pending', deadline_at=appeal['review_deadline_at'], policy=appeal['review_policy'],
              responsible=owners, actor={key: user.get(key) for key in ('id','username','real_name','role')})


def run_deadline_scan(cur, core):
    # All workers/replicas may start a timer. PostgreSQL elects one scan transaction.
    cur.execute('SELECT pg_try_advisory_xact_lock(66092026) AS acquired')
    if not cur.fetchone()['acquired']:
        return
    cur.execute("SELECT set_config('app.actor_id','',true)")
    cur.execute('''SELECT ins.id FROM inspections ins WHERE is_quality_deadline_table(ins.inspection_table_id)
      AND COALESCE(ins.sign_status,'待签名确认') <> '已签名确认' AND ins.inspector_completion_status='已确认完成'
      AND NOT EXISTS(SELECT 1 FROM issues i WHERE i.inspection_id=ins.id AND COALESCE(i.audit_status,'pending')='pending')
      AND (ins.quality_accept_started_at IS NULL OR ins.quality_accept_deadline_at<=CURRENT_TIMESTAMP
        OR EXISTS(SELECT 1 FROM issues i WHERE i.inspection_id=ins.id AND i.audited_at AT TIME ZONE 'Asia/Shanghai'>ins.quality_accept_started_at))
      ORDER BY ins.id LIMIT 200''')
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
    cur.execute("""UPDATE issues i SET quality_appeal_deadline_at=NULL FROM inspections ins
      WHERE ins.id=i.inspection_id AND ins.sign_status='已签名确认' AND i.audit_status='approved'
      AND i.status='待整改' AND i.quality_appeal_deadline_at IS NULL AND is_quality_deadline_table(i.inspection_table_id)""")
    cur.execute("""SELECT a.id,a.issue_id FROM inspection_issue_appeals a JOIN issues i ON i.id=a.issue_id
      WHERE a.status IN ('area_pending','quality_pending') AND is_quality_deadline_table(i.inspection_table_id)
      AND (a.review_deadline_at IS NULL OR a.review_deadline_at<=CURRENT_TIMESTAMP AND a.review_policy->>'timeout_action'<>'manual')
      ORDER BY a.id LIMIT 200""")
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
    cur.execute('UPDATE quality_deadline_worker_state SET last_success_at=CURRENT_TIMESTAMP WHERE id=1')


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
                run_deadline_scan(cur, core)
                conn.commit()
            except Exception:
                if conn:
                    conn.rollback()
                    try:
                        cur.execute('UPDATE quality_deadline_worker_state SET last_failure_at=CURRENT_TIMESTAMP WHERE id=1')
                        conn.commit()
                    except Exception:
                        conn.rollback()
                logging.exception('Quality deadline scan failed; transaction rolled back, retrying')
            finally:
                core.close_db_resources(cur, conn)
            time.sleep(30)
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
            cur.execute('SELECT last_success_at,last_failure_at FROM quality_deadline_worker_state WHERE id=1')
            worker = cur.fetchone()
            cur.execute('SELECT COALESCE(real_name,username) AS name FROM users WHERE id=%s', (policy.get('updated_by'),))
            editor = cur.fetchone()
            return jsonify(policy=policy, editor=editor['name'] if editor else '系统默认', worker=worker)
        return run(operation)

    @app.put('/api/management/quality-deadlines')
    def update_quality_deadlines():
        def operation(cur, user):
            data = request.get_json(silent=True) or {}
            for field in ('acceptance_days','appeal_days','review_days'):
                if type(data.get(field)) is not int or not 1 <= data[field] <= 365:
                    raise ValueError()
            if data.get('timeout_action') not in ('manual','approve','reject'):
                raise ValueError()
            cur.execute('SELECT version FROM quality_deadline_policy WHERE id=1 FOR UPDATE')
            if cur.fetchone()['version'] != data.get('version'):
                return jsonify(error='规则已被其他操作更新，请刷新后重试。'), 409
            cur.execute('''UPDATE quality_deadline_policy SET acceptance_days=%s,appeal_days=%s,review_days=%s,
              timeout_action=%s,version=version+1,updated_at=CURRENT_TIMESTAMP,updated_by=%s WHERE id=1''',
              (data['acceptance_days'],data['appeal_days'],data['review_days'],data['timeout_action'],user['id']))
            policy = policy_snapshot(cur)
            log_event(cur, 'policy_updated', 'root更新时限规则；只影响此后新进入环节的任务，已有期限与处理方式不变。',
                      policy=policy, actor={key: user.get(key) for key in ('id','username','real_name','role')})
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
