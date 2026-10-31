"""Authenticated device ownership, personal inbox and permission-scoped administration."""
import uuid
from datetime import datetime
from flask import Blueprint, g, jsonify, request
from psycopg2.extras import RealDictCursor
from web_push import configuration, device_key, device_labels, digest, seal, validate_subscription
from web_push_outbox import add_recipients
from web_push_business import SOURCES

CAPABILITIES={'supported','unsupported','ios_install_required','insecure','unknown'}
PERMISSIONS={'default','granted','denied','unavailable'}


def public_device(row):
    return {key:(value.isoformat() if isinstance(value,datetime) else str(value)) if value is not None else None for key,value in row.items()
        if key in {'id','platform','browser','capability','permission','last_seen_at','last_sent_at','last_error'}} | {'active':bool(row['active'])}


def enqueue(cur, user, recipients, title, body, kind, request_id, only_device=None):
    try: request_id=str(uuid.UUID(str(request_id)))
    except (ValueError,TypeError,AttributeError): raise ValueError('发送请求标识无效。') from None
    cur.execute('SELECT pg_advisory_xact_lock(%s,%s)',(1230001,user['id']))
    cur.execute('SELECT id,title,body,kind FROM web_push_messages WHERE sender_id=%s AND request_id=%s',(user['id'],request_id))
    existing=cur.fetchone()
    if existing:
        cur.execute('SELECT user_id FROM web_push_recipients WHERE message_id=%s',(existing['id'],))
        if (existing['title']!=title or existing['body']!=body or existing['kind']!=kind
                or {row['user_id'] for row in cur.fetchall()}!=set(recipients)):
            raise ValueError('发送请求标识已被其他消息使用，请重新创建发送请求。')
        return str(existing['id'])
    cur.execute("SELECT count(*) AS n FROM web_push_messages WHERE sender_id=%s AND created_at>now()-interval '1 minute'",(user['id'],))
    if cur.fetchone()['n'] >= 5: raise ValueError('发送过于频繁，请一分钟后再试。')
    message_id=str(uuid.uuid4())
    cur.execute('''INSERT INTO web_push_messages(id,request_id,sender_id,sender_name,title,body,kind)
      VALUES(%s,%s,%s,%s,%s,%s,%s)''',(message_id,request_id,user['id'],user.get('real_name') or user.get('username') or '',title,body,kind))
    add_recipients(cur,message_id,recipients,only_device)
    return message_id


def register_web_push(app, *, connect, has_permission):
    bp=Blueprint('web_push',__name__)

    def run(operation, admin=False):
        conn=None
        try:
            user=getattr(g,'current_user',None)
            if not user: return jsonify(error='请先登录。'),401
            if getattr(g,'impersonator',None): raise PermissionError('代入账号时不能管理设备通知，请返回自己的账号。')
            conn=connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if admin and not has_permission(cur,user,'manage_web_push'):
                    raise PermissionError('当前账号无消息通知管理权限。')
                result=operation(cur,user)
            conn.commit()
            return result
        except PermissionError as exc:
            if conn: conn.rollback()
            return jsonify(error=str(exc)),403
        except (ValueError,TypeError) as exc:
            if conn: conn.rollback()
            return jsonify(error=str(exc)),400
        except Exception:
            if conn: conn.rollback()
            # Subscription endpoints and auth keys must never enter exception logs.
            app.logger.error('Web Push operation failed; check configuration and migration 20261101_003')
            return jsonify(error='消息通知服务暂不可用，请检查配置和数据库升级。'),503
        finally:
            if conn: conn.close()

    def source():
        value=request.get_json(silent=True)
        if not isinstance(value,dict): raise ValueError('请求内容格式无效。')
        return value

    @bp.get('/api/notifications/settings')
    def settings():
        def operation(cur,user):
            cur.execute('SELECT enabled FROM web_push_preferences WHERE user_id=%s',(user['id'],))
            preference=cur.fetchone();config=configuration()
            return jsonify(enabled=preference['enabled'] if preference else True,
                configured=config['ready'],public_key=config['public_key'])
        return run(operation)

    @bp.get('/api/notifications')
    def inbox():
        def operation(cur,user):
            page=max(1,min(100000,int(request.args.get('page',1))))
            cur.execute('SELECT enabled FROM web_push_preferences WHERE user_id=%s',(user['id'],))
            preference=cur.fetchone()
            cur.execute('''SELECT m.id,m.title,m.body,m.kind,m.source,m.action_path,m.sender_name,m.created_at,r.read_at,r.confirmed_at,r.delivery_note,
              (SELECT count(*) FROM web_push_deliveries d WHERE d.message_id=m.id AND d.user_id=r.user_id AND d.status='accepted') AS accepted,
              (SELECT count(*) FROM web_push_deliveries d WHERE d.message_id=m.id AND d.user_id=r.user_id AND d.status IN ('queued','sending')) AS pending,
              (SELECT count(*) FROM web_push_deliveries d WHERE d.message_id=m.id AND d.user_id=r.user_id AND d.status IN ('failed','expired','skipped')) AS failed
              FROM web_push_recipients r JOIN web_push_messages m ON m.id=r.message_id
              WHERE r.user_id=%s ORDER BY m.created_at DESC,m.id LIMIT 20 OFFSET %s''',(user['id'],(page-1)*20))
            items=cur.fetchall()
            cur.execute('SELECT count(*) AS total,count(*) FILTER(WHERE read_at IS NULL) AS unread FROM web_push_recipients WHERE user_id=%s',(user['id'],))
            counts=cur.fetchone()
            config=configuration()
            return jsonify(items=items,**counts,enabled=preference['enabled'] if preference else True,
                configured=config['ready'],public_key=config['public_key'],page=page)
        return run(operation)

    @bp.put('/api/notifications/preference')
    def preference():
        def operation(cur,user):
            enabled=source().get('enabled')
            if type(enabled) is not bool: raise ValueError('请选择通知开关。')
            cur.execute('''INSERT INTO web_push_preferences(user_id,enabled) VALUES(%s,%s)
              ON CONFLICT(user_id) DO UPDATE SET enabled=EXCLUDED.enabled,updated_at=now()''',(user['id'],enabled))
            return jsonify(success=True,enabled=enabled)
        return run(operation)

    @bp.route('/api/notifications/device',methods=['POST','DELETE'])
    def device():
        def operation(cur,user):
            data=source();token=device_key(data.get('device_key'))
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,1230))',(token,))
            cur.execute('SELECT * FROM web_push_devices WHERE device_hash=%s FOR UPDATE',(token,))
            existing=cur.fetchone()
            if request.method=='DELETE' and existing and existing['user_id']!=user['id']:
                raise PermissionError('此设备仍关联其他账号，请先使用原账号停用通知或清除浏览器站点数据。')
            if request.method=='DELETE':
                cur.execute('''UPDATE web_push_devices SET active=FALSE,subscription_cipher=NULL,endpoint_hash=NULL,
                  revision=%s,last_seen_at=now() WHERE device_hash=%s AND user_id=%s''',(str(uuid.uuid4()),token,user['id']))
                return jsonify(success=True)
            capability,permission=data.get('capability'),data.get('permission')
            if capability not in CAPABILITIES or permission not in PERMISSIONS: raise ValueError('设备能力状态无效。')
            subscription=data.get('subscription')
            config=configuration()
            if subscription is not None:
                if not config['ready']: raise ValueError('管理员尚未配置 Web Push 密钥，暂不能订阅。')
                if capability!='supported' or permission!='granted': raise ValueError('请先在浏览器中允许通知。')
                subscription=validate_subscription(subscription)
            platform,browser=device_labels(request.headers.get('User-Agent'))
            encrypted=seal(subscription,app.config['SECRET_KEY']) if subscription else None
            endpoint_hash=digest(subscription['endpoint']) if subscription else None
            if endpoint_hash:
                cur.execute('SELECT * FROM web_push_devices WHERE endpoint_hash=%s AND device_hash<>%s FOR UPDATE',(endpoint_hash,token))
                old=cur.fetchone()
                if old:
                    if old['user_id']!=user['id']: raise ValueError('此浏览器订阅已被其他账号绑定，请停用后重新授权。')
                    if not existing:
                        # A cleared local device key is not a new browser subscription.
                        cur.execute('UPDATE web_push_devices SET device_hash=%s WHERE id=%s',(token,old['id']))
                        existing=old
                    else:
                        cur.execute('''UPDATE web_push_devices SET active=FALSE,subscription_cipher=NULL,endpoint_hash=NULL,
                          revision=%s WHERE id=%s''',(str(uuid.uuid4()),old['id']))
            # Preserve the revision on a routine heartbeat so pending messages remain valid.
            from web_push import unseal
            same=False
            if existing and existing['user_id']==user['id'] and existing['subscription_cipher'] and subscription:
                try: same=unseal(existing['subscription_cipher'],app.config['SECRET_KEY'])==subscription
                except Exception: pass
            revision=str(existing['revision']) if same else str(uuid.uuid4())
            identifier=str(existing['id']) if existing else str(uuid.uuid4())
            cur.execute('''INSERT INTO web_push_devices(id,user_id,device_hash,endpoint_hash,subscription_cipher,revision,platform,browser,capability,permission,active)
              VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT(device_hash) DO UPDATE SET user_id=EXCLUDED.user_id,endpoint_hash=EXCLUDED.endpoint_hash,subscription_cipher=EXCLUDED.subscription_cipher,
              revision=EXCLUDED.revision,platform=EXCLUDED.platform,browser=EXCLUDED.browser,capability=EXCLUDED.capability,
              permission=EXCLUDED.permission,active=EXCLUDED.active,last_seen_at=now(),last_error='' RETURNING *''',
              (identifier,user['id'],token,endpoint_hash,encrypted,revision,platform,browser,capability,permission,bool(subscription)))
            return jsonify(success=True,device=public_device(cur.fetchone()))
        return run(operation)

    @bp.get('/api/notifications/devices')
    def devices():
        def operation(cur,user):
            cur.execute('SELECT * FROM web_push_devices WHERE user_id=%s ORDER BY last_seen_at DESC',(user['id'],))
            return jsonify(items=[public_device(row) for row in cur.fetchall()])
        return run(operation)

    @bp.post('/api/notifications/test')
    def test():
        def operation(cur,user):
            data=source();token=device_key(data.get('device_key'))
            if not configuration()['ready']: raise ValueError('Web Push 尚未配置，暂不能发送测试通知。')
            cur.execute('''SELECT d.id FROM web_push_devices d LEFT JOIN web_push_preferences p ON p.user_id=d.user_id
              WHERE d.device_hash=%s AND d.user_id=%s AND d.active AND COALESCE(p.enabled,TRUE)''',(token,user['id']))
            row=cur.fetchone()
            if not row: raise ValueError('请先开启通知并订阅当前设备。')
            identifier=enqueue(cur,user,[user['id']],'浏览器推送测试','这是当前设备的测试通知。收到系统通知后，请点击下方“确认收到系统推送”。','test',data.get('request_id'),str(row['id']))
            return jsonify(success=True,id=identifier),202
        return run(operation)

    @bp.post('/api/notifications/<uuid:identifier>/read')
    def mark_read(identifier):
        def operation(cur,user):
            data=source()
            cur.execute('''UPDATE web_push_recipients SET read_at=COALESCE(read_at,now()),
              confirmed_at=CASE WHEN %s THEN COALESCE(confirmed_at,now()) ELSE confirmed_at END
              WHERE message_id=%s AND user_id=%s RETURNING message_id''',(data.get('confirm') is True,str(identifier),user['id']))
            if not cur.fetchone(): return jsonify(error='通知不存在或无权查看。'),404
            return jsonify(success=True)
        return run(operation)

    @bp.get('/api/management/notifications')
    def management():
        def operation(cur,user):
            page=max(1,min(100000,int(request.args.get('page',1))))
            log_page=max(1,min(100000,int(request.args.get('log_page',1))))
            query=request.args.get('keyword','').strip()[:100]
            status=request.args.get('status','')
            if status not in ('','enabled','not_enabled','unsupported'): raise ValueError('通知状态无效。')
            cte='''WITH catalog AS (SELECT u.id,u.username,u.real_name,u.role,COALESCE(p.enabled,TRUE) AS enabled,
              count(d.id) AS devices,count(d.id) FILTER(WHERE d.active) AS subscriptions,max(d.last_seen_at) AS last_seen_at,
              CASE WHEN COALESCE(p.enabled,TRUE) AND bool_or(d.active) THEN 'enabled'
                WHEN count(d.id)>0 AND bool_and(d.capability IN ('unsupported','insecure','ios_install_required')) THEN 'unsupported'
                ELSE 'not_enabled' END AS state
              FROM users u LEFT JOIN web_push_preferences p ON p.user_id=u.id
              LEFT JOIN web_push_devices d ON d.user_id=u.id WHERE u.account_status='active'
              GROUP BY u.id,p.enabled)'''
            cur.execute(cte+''' SELECT count(*) AS total,count(*) FILTER(WHERE state='enabled') AS enabled,
              count(*) FILTER(WHERE state='not_enabled') AS not_enabled,count(*) FILTER(WHERE state='unsupported') AS unsupported FROM catalog''')
            summary=cur.fetchone()
            where="WHERE (%s='' OR state=%s) AND (%s='' OR username ILIKE %s OR real_name ILIKE %s)"
            params=[status,status,query,f'%{query}%',f'%{query}%']
            cur.execute(cte+' SELECT count(*) AS n FROM catalog '+where,params)
            total=cur.fetchone()['n']
            cur.execute(cte+' SELECT * FROM catalog '+where+' ORDER BY id LIMIT 30 OFFSET %s',params+[(page-1)*30])
            rows=cur.fetchall()
            if request.args.get('recipients_only')=='1':
                return jsonify(items=rows,total=total,page=page)
            log_source=request.args.get('log_source','')
            if log_source not in ('','manual','test',*[entry['key'] for entry in SOURCES]):
                raise ValueError('消息来源无效。')
            log_where="WHERE (%s='' OR m.source=%s OR m.kind=%s)"
            log_args=[log_source]*3
            cur.execute('SELECT count(*) AS n FROM web_push_messages m '+log_where,log_args)
            records_total=cur.fetchone()['n']
            cur.execute('''SELECT m.id,m.title,m.body,m.sender_name,m.created_at,m.kind,m.source,m.entity_id,m.action_path,
              (SELECT count(*) FROM web_push_recipients r WHERE r.message_id=m.id) AS recipients,
              (SELECT count(*) FROM web_push_recipients r WHERE r.message_id=m.id
                AND NOT EXISTS(SELECT 1 FROM web_push_deliveries d WHERE d.message_id=r.message_id AND d.user_id=r.user_id)) AS inbox_only,
              (SELECT count(*) FROM web_push_recipients r WHERE r.message_id=m.id AND r.confirmed_at IS NOT NULL) AS confirmed,
              (SELECT count(*) FROM web_push_deliveries d WHERE d.message_id=m.id AND status='accepted') AS accepted,
              (SELECT count(*) FROM web_push_deliveries d WHERE d.message_id=m.id AND status IN ('queued','sending')) AS pending,
              (SELECT count(*) FROM web_push_deliveries d WHERE d.message_id=m.id AND status IN ('failed','expired','skipped')) AS failed
              FROM web_push_messages m '''+log_where+' ORDER BY m.created_at DESC,m.id LIMIT 30 OFFSET %s',log_args+[(log_page-1)*30])
            records=cur.fetchall()
            cur.execute("SELECT source,count(*) AS total,max(created_at) AS latest FROM web_push_messages WHERE kind='business' GROUP BY source")
            stats={row['source']:dict(total=row['total'],latest=row['latest']) for row in cur.fetchall()}
            return jsonify(items=rows,total=total,page=page,summary=summary,records=records,
                sources=[dict(entry,**stats.get(entry['key'],dict(total=0,latest=None))) for entry in SOURCES],
                records_total=records_total,records_page=log_page,configured=configuration()['ready'])
        return run(operation,True)

    @bp.get('/api/management/notifications/users/<int:uid>/devices')
    def management_devices(uid):
        def operation(cur,user):
            cur.execute('SELECT * FROM web_push_devices WHERE user_id=%s ORDER BY last_seen_at DESC',(uid,))
            return jsonify(items=[public_device(row) for row in cur.fetchall()])
        return run(operation,True)

    @bp.get('/api/management/notifications/<uuid:identifier>/deliveries')
    def deliveries(identifier):
        def operation(cur,user):
            cur.execute('''SELECT COALESCE(d.status,'inbox_only') AS status,d.attempts,d.http_status,d.last_error,d.updated_at,
              u.real_name,u.username,v.platform,v.browser,r.delivery_note,r.read_at,r.confirmed_at
              FROM web_push_recipients r JOIN users u ON u.id=r.user_id
              LEFT JOIN web_push_deliveries d ON d.message_id=r.message_id AND d.user_id=r.user_id
              LEFT JOIN web_push_devices v ON v.id=d.device_id WHERE r.message_id=%s ORDER BY u.id,d.id LIMIT 1000''',(str(identifier),))
            return jsonify(items=cur.fetchall())
        return run(operation,True)

    @bp.post('/api/management/notifications/send')
    def dispatch():
        def operation(cur,user):
            data=source();ids=data.get('user_ids');title=data.get('title');body=data.get('body')
            if not isinstance(ids,list) or not 1<=len(ids)<=200 or any(type(i)is not int or i<=0 for i in ids): raise ValueError('请选择1至200个有效用户。')
            if not isinstance(title,str) or not 1<=len(title.strip())<=60 or not isinstance(body,str) or not 1<=len(body.strip())<=1500:
                raise ValueError('标题须为1至60字，正文须为1至1500字。')
            if not configuration()['ready']: raise ValueError('Web Push 尚未配置，暂不能推送。')
            ids=sorted(set(ids))
            cur.execute("SELECT id FROM users WHERE id=ANY(%s) AND account_status='active'",(ids,))
            if {row['id'] for row in cur.fetchall()}!=set(ids): raise ValueError('所选用户已失效，请重新读取。')
            identifier=enqueue(cur,user,ids,title.strip(),body.strip(),'manual',data.get('request_id'))
            return jsonify(success=True,id=identifier,message='已加入发送队列；未授权或未订阅的设备无法收到系统推送，仍可查看站内通知。'),202
        return run(operation,True)

    app.register_blueprint(bp)
