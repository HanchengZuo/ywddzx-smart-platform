"""Business events use existing recipients and the station signature badge criterion."""
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from psycopg2.extras import RealDictCursor
from web_push_outbox import enqueue_business

SOURCES = (
    dict(key='appeal_area',menu='申诉空间',name='待片区处理申诉',recipient='站点所属片区的有效片区账号',
         trigger='站点成功提交申诉',rule='按现有片区归属匹配，不扩大数据权限。'),
    dict(key='appeal_quality',menu='申诉空间',name='待质安部处理申诉',recipient='拥有申诉终审权限的有效质安部账号',
         trigger='片区通过并转入质安部（含时限规则自动通过）',rule='只通知具备终审权限的账号。'),
    dict(key='inspection_signature',menu='巡检记录',name='待站经理签名验收',recipient='对应站点的有效站点角色账号',
         trigger='检查人确认完成且所有问题审核结束，记录尚未签名',rule='与菜单红点一致；适用时附上质安验收截止时间。'),
)


def recipient_resolver(*, can_sign, has_permission, normalize_region, region_scope):
    # Only these four domain capabilities are needed, not app globals or an app import.
    policy=SimpleNamespace(can_sign_inspection_records=can_sign,has_permission=has_permission,
        normalize_station_region_value=normalize_region,get_effective_station_region_scope_values=region_scope)
    def resolve(cur, stage, station_id, region):
        from quality_deadlines import responsible_users
        return [user['id'] for user in responsible_users(cur,policy,stage,station_id,region)]
    return resolve


def notify_appeal(cur, appeal_id, stage, recipients):
    cur.execute('''SELECT a.id,a.issue_id,a.status,s.station_name,t.table_name
      FROM inspection_issue_appeals a JOIN issues i ON i.id=a.issue_id
      JOIN stations s ON s.id=i.station_id JOIN inspection_tables t ON t.id=i.inspection_table_id WHERE a.id=%s''',(appeal_id,))
    appeal=cur.fetchone()
    if not appeal or appeal['status']!=stage:
        return
    area=stage=='area_pending'
    label='待片区处理申诉' if area else '待质安部处理申诉'
    enqueue_business(cur,event_key=f'appeal:{appeal_id}:{stage}',source='appeal_area' if area else 'appeal_quality',
        entity_id=appeal_id,title=label,
        body=f"{appeal['station_name']}的问题 #{appeal['issue_id']}（{appeal['table_name']}）"+
             ('已提交申诉，请所属片区及时初审。' if area else '经片区通过，已转入质安部终审，请及时处理。'),
        recipients=recipients,action_path='/inspection/appeals',push_hint=label+'，请登录申诉空间及时处理。')


def signature_record(cur, identifier):
    cur.execute('''SELECT ins.id,ins.station_id,ins.inspection_date,ins.inspection_table_id,
      s.station_name,s.region,t.table_name,
      COALESCE(ins.inspector_completion_status,'待检查人确认')='已确认完成'
        AND COALESCE(ins.sign_status,'待签名确认')<>'已签名确认'
        AND NOT EXISTS(SELECT 1 FROM issues i WHERE i.inspection_id=ins.id AND COALESCE(i.audit_status,'pending')='pending') AS ready
      FROM inspections ins JOIN stations s ON s.id=ins.station_id JOIN inspection_tables t ON t.id=ins.inspection_table_id
      WHERE ins.id=%s''',(identifier,))
    return cur.fetchone()


def process_signature_changes(connect, recipients, limit=50):
    conn=connect()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT pg_try_advisory_xact_lock(12331001) AS acquired')
            if not cur.fetchone()['acquired']:
                conn.commit();return 0
            cur.execute("SET LOCAL lock_timeout='3s'")
            cur.execute("SET LOCAL statement_timeout='15s'")
            # Do not lock invalidations before inspections: audit writers lock in that order.
            cur.execute('''SELECT inspection_id,max(id) AS revision FROM web_push_signature_changes
              GROUP BY inspection_id ORDER BY min(id) LIMIT %s''',(limit,))
            candidates=cur.fetchall()
            for change in sorted(candidates,key=lambda entry:entry['inspection_id']):
                identifier=change['inspection_id']
                cur.execute('SELECT * FROM web_push_signature_state WHERE inspection_id=%s',(identifier,))
                previous=cur.fetchone()
                cur.execute('SELECT id FROM inspections WHERE id=%s FOR UPDATE SKIP LOCKED',(identifier,))
                if not cur.fetchone():
                    continue
                record=signature_record(cur,identifier)
                if not record: continue
                episode=previous['episode'] if previous else 0
                if record['ready'] and (not previous or not previous['ready'] or previous['station_id']!=record['station_id']):
                    episode+=1
                    cur.execute('SELECT refresh_quality_acceptance(%s)',(identifier,))
                    cur.execute('''SELECT CASE WHEN is_quality_deadline_table(inspection_table_id) THEN
                      quality_effective_deadline('acceptance',quality_accept_deadline_at,quality_accept_started_at) END AS deadline
                      FROM inspections WHERE id=%s''',(identifier,))
                    deadline=cur.fetchone()['deadline']
                    suffix=''
                    if deadline:
                        formatted=deadline.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')
                        suffix=f'本记录适用质安签名验收时限，请于北京时间 {formatted} 前完成；逾期系统将自动验收并留痕，可能涉及后续考核。'
                    enqueue_business(cur,event_key=f'inspection:{identifier}:{episode}',source='inspection_signature',
                        entity_id=identifier,title='巡检记录待签名验收',
                        body=f"{record['station_name']} · {record['table_name']} · {record['inspection_date']}，巡检记录 #{identifier} 的问题审核已结束，请前往巡检记录完成签名验收。"+suffix,
                        recipients=recipients(cur,'acceptance',record['station_id'],record['region']),action_path='/inspection/records',
                        push_hint='有巡检记录待签名验收。'+(suffix or '请登录巡检记录及时办理。'))
                cur.execute('''INSERT INTO web_push_signature_state(inspection_id,ready,station_id,episode) VALUES(%s,%s,%s,%s)
                  ON CONFLICT(inspection_id) DO UPDATE SET ready=EXCLUDED.ready,station_id=EXCLUDED.station_id,episode=EXCLUDED.episode''',
                  (identifier,record['ready'],record['station_id'],episode))
                # A concurrently committed change is not consumed by this older snapshot.
                cur.execute('DELETE FROM web_push_signature_changes WHERE inspection_id=%s AND id<=%s',(identifier,change['revision']))
        conn.commit();return len(candidates)
    except Exception:
        conn.rollback();raise
    finally:
        conn.close()


def delivery_allowed(cur, message, user_id, recipients):
    if message['source']=='inspection_signature':
        record=signature_record(cur,message['entity_id'])
        return bool(record and record['ready'] and user_id in recipients(cur,'acceptance',record['station_id'],record['region']))
    if message['source'] in ('appeal_area','appeal_quality'):
        stage='area_pending' if message['source']=='appeal_area' else 'quality_pending'
        cur.execute('''SELECT a.status,i.station_id,s.region FROM inspection_issue_appeals a
          JOIN issues i ON i.id=a.issue_id JOIN stations s ON s.id=i.station_id WHERE a.id=%s''',(message['entity_id'],))
        record=cur.fetchone()
        return bool(record and record['status']==stage and user_id in recipients(cur,stage,record['station_id'],record['region']))
    return False
