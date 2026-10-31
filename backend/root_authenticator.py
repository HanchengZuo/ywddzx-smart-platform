"""Root-only, encrypted OATH-TOTP credentials and explicit enrollment endpoints."""
import base64
import hashlib
import hmac
from io import BytesIO
import json
import re
import secrets
import struct
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet
from flask import Blueprint, g, jsonify, request
import qrcode
from auth_rate_limit import check_password_login_allowed, record_password_login_failure, clear_successful_password_login

ISSUER = 'YWDDZX'
SETUP_SECONDS = 300


def eligible(user):
    return bool(user and user.get('role') == 'root' and user.get('username') == 'root'
        and user.get('account_status') == 'active')


def cipher(key):
    derived = hmac.new(str(key).encode(), b'ywddzx-root-totp-v1', hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def seal(secret, user_id, key):
    return cipher(key).encrypt(json.dumps({'uid': user_id, 'secret': secret}).encode()).decode()


def unseal(value, user_id, key):
    payload = json.loads(cipher(key).decrypt(value.encode()))
    if payload['uid'] != user_id:
        raise ValueError('Authenticator凭据不属于当前账号。')
    return payload['secret']


def hotp(secret, counter):
    digest = hmac.new(base64.b32decode(secret), struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = struct.unpack('>I', digest[offset:offset+4])[0] & 0x7fffffff
    return f'{value % 1000000:06d}'


def matching_counter(secret, code, now, last=-1):
    if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code):
        return None
    current = int(now) // 30
    matches = [step for step in (current-1, current, current+1) if step >= 0
        and hmac.compare_digest(hotp(secret, step), code) and step > last]
    return max(matches) if matches else None


def database_time(cur):
    cur.execute('SELECT EXTRACT(EPOCH FROM clock_timestamp()) AS now')
    return cur.fetchone()['now']


def authenticate(cur, user, code, key):
    if not eligible(user) or not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code):
        return False
    # Row locks serialize consumption across all Gunicorn workers. Caller owns
    # the transaction, including the login audit and session creation metadata.
    cur.execute('SELECT * FROM root_authenticators WHERE user_id=%s FOR UPDATE', (user['id'],))
    row = cur.fetchone()
    if not row or not row['secret_ciphertext']:
        return False
    # A fixed internal scope also limits guesses across changing client IPs.
    check_password_login_allowed(cur,key,'root-authenticator',user['username'])
    step = matching_counter(unseal(row['secret_ciphertext'], user['id'], key), code, database_time(cur), row['last_counter'])
    if step is None:
        record_password_login_failure(cur,key,'root-authenticator',user['username'])
        return False
    cur.execute('UPDATE root_authenticators SET last_counter=%s,last_used_at=clock_timestamp() WHERE user_id=%s', (step,user['id']))
    clear_successful_password_login(cur,key,'root-authenticator',user['username'])
    return True


def register_root_authenticator(app, *, connect, fetch_user, verify_management, audit, invalidate):
    blueprint = Blueprint('root_authenticator', __name__)

    @blueprint.route('/api/auth/root-authenticator', methods=['GET','POST','PUT','DELETE'])
    def manage():
        conn = None
        try:
            user = getattr(g, 'current_user', None)
            if not eligible(user) or getattr(g, 'impersonator', None):
                return jsonify(success=False,error='仅root本人可以管理Microsoft Authenticator。'),403
            conn = connect(); cur = conn.cursor()
            user = fetch_user(cur,user['id'])
            if not eligible(user):
                return jsonify(success=False,error='root账号状态已变化。'),403
            body = request.get_json(silent=True) or {}
            if not isinstance(body,dict):
                raise ValueError('请提交有效的安全设置。')
            if request.method != 'GET':
                # Even a stolen TOTP session cannot enroll a new device or
                # remove this credential without fresh Passkey verification.
                verify_management(body.get('management_token'), user)
            if request.method == 'GET':
                cur.execute('SELECT enabled_at,last_used_at FROM root_authenticators WHERE user_id=%s AND secret_ciphertext IS NOT NULL',(user['id'],))
                row = cur.fetchone()
                return jsonify(success=True,enabled=bool(row),enabled_at=row['enabled_at'].isoformat() if row and row['enabled_at'] else None)
            cur.execute('INSERT INTO root_authenticators(user_id) VALUES (%s) ON CONFLICT DO NOTHING',(user['id'],))
            cur.execute('SELECT * FROM root_authenticators WHERE user_id=%s FOR UPDATE',(user['id'],))
            row = cur.fetchone()
            cur.execute('SELECT id FROM users WHERE id=%s FOR UPDATE',(user['id'],))
            user = fetch_user(cur,user['id'])
            if not eligible(user):
                raise ValueError('root账号状态已变化，请重新登录。')
            verify_management(body.get('management_token'),user)
            now = database_time(cur)
            key = app.config['SECRET_KEY']
            if request.method == 'POST':
                if row['secret_ciphertext']:
                    return jsonify(success=False,error='已绑定Authenticator，请先停用原绑定。'),409
                secret = base64.b32encode(secrets.token_bytes(20)).decode()
                setup_id = secrets.token_urlsafe(32)
                cur.execute('''UPDATE root_authenticators SET pending_ciphertext=%s,pending_id=%s,
                    pending_expires_at=clock_timestamp()+interval '5 minutes',pending_attempts=0 WHERE user_id=%s''',
                    (seal(secret,user['id'],key),setup_id,user['id']))
                uri = 'otpauth://totp/'+quote(ISSUER+':root',safe='')+'?'+urlencode({
                    'secret':secret,'issuer':ISSUER,'algorithm':'SHA1','digits':6,'period':30})
                output = BytesIO(); qrcode.make(uri).save(output,format='PNG')
                audit(cur,user,'root_authenticator_setup','success')
                conn.commit()
                return jsonify(success=True,setup_id=setup_id,secret=secret,expires_in=SETUP_SECONDS,
                    qr_code='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode())
            if request.method == 'PUT':
                setup_id = body.get('setup_id')
                if (row['secret_ciphertext'] or not row['pending_ciphertext'] or row['pending_attempts'] >= 5
                    or not isinstance(setup_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',setup_id)
                    or not hmac.compare_digest(setup_id,row['pending_id'] or '')
                    or row['pending_expires_at'].timestamp() <= float(now)):
                    raise ValueError('绑定已失效，请重新进行Passkey验证并生成二维码。')
                step = matching_counter(unseal(row['pending_ciphertext'],user['id'],key),body.get('code'),now)
                if step is None:
                    cur.execute('UPDATE root_authenticators SET pending_attempts=pending_attempts+1 WHERE user_id=%s',(user['id'],))
                    audit(cur,user,'root_authenticator_enable','failure')
                    conn.commit()
                    return jsonify(success=False,error='验证码无效或已过期，请核对手机时间后重试。'),400
                cur.execute('''UPDATE root_authenticators SET secret_ciphertext=pending_ciphertext,last_counter=%s,
                    enabled_at=clock_timestamp(),pending_ciphertext=NULL,pending_id=NULL,pending_expires_at=NULL,
                    pending_attempts=0 WHERE user_id=%s''',(step,user['id']))
                action = 'root_authenticator_enable'
            else:
                cur.execute('DELETE FROM root_authenticators WHERE user_id=%s',(user['id'],))
                action = 'root_authenticator_disable'
            cur.execute('UPDATE users SET auth_version=auth_version+1,updated_at=CURRENT_TIMESTAMP WHERE id=%s',(user['id'],))
            audit(cur,user,action,'success')
            conn.commit(); invalidate(user['id'])
            message = ('Authenticator已启用，请使用Passkey或等待下一组验证码后重新登录。'
                if request.method == 'PUT' else 'Authenticator已停用，请使用Passkey重新登录。')
            return jsonify(success=True,session_invalidated=True,message=message)
        except ValueError as exc:
            if conn:conn.rollback()
            return jsonify(success=False,error=str(exc)),400
        except Exception:
            if conn:conn.rollback()
            # Do not log exception payloads: secrets/codes must never reach logs.
            app.logger.error('Root Authenticator operation failed')
            return jsonify(success=False,error='Authenticator安全服务暂不可用，请稍后重试。'),503
        finally:
            if conn:conn.close()

    app.register_blueprint(blueprint)
