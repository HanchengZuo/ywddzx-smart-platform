"""Shared transactional outbox; callers own commit and rollback, never network I/O."""
import uuid


def add_recipients(cur, message_id, recipients, only_device=None):
    for uid in sorted(set(recipients)):
        cur.execute('''INSERT INTO web_push_recipients(message_id,user_id,delivery_note)
          SELECT %s,u.id,CASE WHEN NOT COALESCE(p.enabled,TRUE) THEN '账号已暂停推送，仅保留站内通知'
            WHEN NOT EXISTS(SELECT 1 FROM web_push_devices d WHERE d.user_id=u.id AND d.active
              AND d.subscription_cipher IS NOT NULL AND (%s::uuid IS NULL OR d.id=%s::uuid))
              THEN '暂无有效订阅设备，仅保留站内通知' ELSE '已向有效订阅设备入队' END
          FROM users u LEFT JOIN web_push_preferences p ON p.user_id=u.id WHERE u.id=%s''',
          (message_id,only_device,only_device,uid))
    cur.execute('''INSERT INTO web_push_deliveries(message_id,user_id,device_id,device_revision)
      SELECT %s,d.user_id,d.id,d.revision FROM web_push_devices d JOIN users u ON u.id=d.user_id
      LEFT JOIN web_push_preferences p ON p.user_id=u.id WHERE d.user_id=ANY(%s)
      AND d.active AND d.subscription_cipher IS NOT NULL AND u.account_status='active'
      AND COALESCE(p.enabled,TRUE) AND (%s::uuid IS NULL OR d.id=%s::uuid)''',
      (message_id,list(recipients),only_device,only_device))


def enqueue_business(cur, *, event_key, source, entity_id, title, body, recipients, action_path, push_hint):
    identifier=str(uuid.uuid4())
    cur.execute('''INSERT INTO web_push_messages(id,request_id,sender_name,title,body,kind,event_key,source,entity_id,action_path,push_hint)
      VALUES(%s,%s,'系统业务通知',%s,%s,'business',%s,%s,%s,%s,%s)
      ON CONFLICT(event_key) DO NOTHING RETURNING id''',
      (identifier,str(uuid.uuid4()),title,body,event_key,source,entity_id,action_path,push_hint))
    if not cur.fetchone():
        return None
    add_recipients(cur,identifier,recipients)
    return identifier
