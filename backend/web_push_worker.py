"""Durable, leased outbox. Network requests never run in a business transaction."""
import threading
import uuid
from psycopg2.extras import RealDictCursor
from web_push import configuration, send, unseal


def deliver_one(connect, secret, config=None, sender=send):
    config=configuration() if config is None else config
    if not config['ready']: return False
    conn=connect()
    lease=str(uuid.uuid4())
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''SELECT * FROM web_push_deliveries WHERE
              (status='queued' AND available_at<=now()) OR (status='sending' AND lease_until<now())
              ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1''')
            job=cur.fetchone()
            if not job:
                conn.commit();return False
            if job['attempts']>=3:
                cur.execute("UPDATE web_push_deliveries SET status='failed',last_error='超过最大尝试次数',updated_at=now() WHERE id=%s",(job['id'],))
                conn.commit();return True
            cur.execute('''SELECT d.*,COALESCE(p.enabled,TRUE) AS enabled,u.account_status FROM web_push_devices d
              JOIN users u ON u.id=d.user_id LEFT JOIN web_push_preferences p ON p.user_id=d.user_id WHERE d.id=%s''',(job['device_id'],))
            device=cur.fetchone()
            if (not device or not device['active'] or not device['enabled'] or device['account_status']!='active'
                    or device['user_id']!=job['user_id'] or device['revision']!=job['device_revision']):
                cur.execute("UPDATE web_push_deliveries SET status='skipped',last_error='设备、账号或通知偏好已变化',updated_at=now() WHERE id=%s",(job['id'],))
                conn.commit();return True
            cur.execute('''UPDATE web_push_deliveries SET status='sending',attempts=attempts+1,lease=%s,
              lease_until=now()+interval '2 minutes',updated_at=now() WHERE id=%s''',(lease,job['id']))
        conn.commit()
        # Lock-screen payloads contain no problem details, user names or message body.
        payload={'title':'业务督导中心 · 新通知','body':'你有一条系统消息，请登录通知中心查看。',
            'url':'/notifications','tag':'ywddzx-'+str(job['message_id'])}
        code=None;status='failed';error='推送发送失败，请检查密钥、网络及设备设置。';retry=False
        try:
            response=sender(unseal(device['subscription_cipher'],secret),payload,config)
            code=getattr(response,'status_code',None)
            if code in (200,201,202): status='accepted';error=''
            elif code in (404,410): status='expired';error='订阅已失效，请在设备上重新授权。'
            else: retry=code in (408,429) or bool(code and code>=500)
        except Exception as exc:
            # Never persist provider responses: they may contain subscription secrets.
            response=getattr(exc,'response',None)
            code=getattr(exc,'status_code',None) or getattr(response,'status_code',None)
            if code in (404,410): status='expired';error='订阅已失效，请在设备上重新授权。'
            else: retry=code is None or code in (408,429) or code>=500
        if retry and job['attempts']<2: status='queued';error='推送服务暂不可达，将自动重试。'
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''UPDATE web_push_deliveries SET status=%s,http_status=%s,last_error=%s,
              available_at=now()+interval '2 minutes',lease=NULL,lease_until=NULL,updated_at=now()
              WHERE id=%s AND lease=%s AND status='sending' RETURNING id''',(status,code,error,job['id'],lease))
            if cur.fetchone():
                cur.execute('''UPDATE web_push_devices SET last_sent_at=CASE WHEN %s='accepted' THEN now() ELSE last_sent_at END,
                  last_error=%s,active=CASE WHEN %s='expired' THEN FALSE ELSE active END
                  WHERE id=%s AND revision=%s''',(status,error,status,job['device_id'],job['device_revision']))
        conn.commit();return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def start_push_worker(connect, secret, logger):
    """Called after fork only; SKIP LOCKED + leases coordinate Gunicorn workers."""
    def work():
        while True:
            try:
                # Bound each scan; skip startup network calls when keys are absent.
                for _ in range(10):
                    if not deliver_one(connect,secret): break
            except Exception:
                logger.error('Web Push queue scan failed; retrying later')
            threading.Event().wait(30)
    thread=threading.Thread(target=work,name='web-push-outbox',daemon=True)
    thread.start()
    return thread
