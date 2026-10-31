"""Web Push cryptography and validation; no database or thread work at import."""
import base64
import hashlib
import json
import os
import re
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def decode(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}', value):
        raise ValueError('订阅密钥格式无效。')
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def configuration(env=None):
    env = os.environ if env is None else env
    result = {'ready': False, 'public_key': '', 'private_key': '', 'subject': ''}
    if env.get('WEB_PUSH_ENABLED', 'true').lower() in ('false','0','no'):
        return result
    try:
        raw = env.get('WEB_PUSH_VAPID_PRIVATE_KEY', '')
        key = serialization.load_der_private_key(decode(raw), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
            return result
        subject = env.get('WEB_PUSH_SUBJECT', '')
        if not (re.fullmatch(r'mailto:[^\s@]+@[^\s@]+\.[^\s@]+', subject)
                or re.fullmatch(r'https://[a-zA-Z0-9.-]+(?::[0-9]+)?/?', subject)):
            return result
        result.update(ready=True, private_key=raw, subject=subject,
            public_key=b64(key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)))
    except (ValueError, TypeError):
        pass
    return result


def cipher(secret):
    key = HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=b'ywddzx-web-push-v1').derive(secret.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def seal(subscription, secret):
    return cipher(secret).encrypt(json.dumps(subscription).encode()).decode()


def unseal(value, secret):
    return json.loads(cipher(secret).decrypt(value.encode()))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def device_key(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',value):
        raise ValueError('当前设备标识无效，请重新打开通知中心。')
    return digest(value)


def validate_subscription(value):
    if not isinstance(value,dict): raise ValueError('订阅信息无效。')
    endpoint=value.get('endpoint')
    if not isinstance(endpoint,str) or len(endpoint)>4096: raise ValueError('订阅地址无效。')
    url=urlsplit(endpoint)
    # Never allow user-provided arbitrary destinations (SSRF) or HTTP redirects.
    host=(url.hostname or '').lower()
    allowed=(host in ('fcm.googleapis.com','updates.push.services.mozilla.com','push.services.mozilla.com','web.push.apple.com')
        or host.endswith('.notify.windows.com'))
    if url.scheme!='https' or not allowed or url.port not in (None,443) or url.username or url.password or url.fragment:
        raise ValueError('当前浏览器的推送服务暂不支持，请使用系统推荐的浏览器。')
    keys=value.get('keys') or {}
    if not isinstance(keys,dict): raise ValueError('订阅密钥无效。')
    try:
        if len(decode(keys.get('auth'))) != 16: raise ValueError()
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),decode(keys.get('p256dh')))
    except (ValueError, TypeError):
        raise ValueError('订阅密钥无效，请重新授权。') from None
    return {'endpoint':endpoint,'keys':{'p256dh':keys['p256dh'],'auth':keys['auth']}}


def device_labels(ua):
    ua=str(ua or '')[:1000]
    platform=('iOS / iPadOS' if re.search(r'iPhone|iPad|iPod',ua) or ('Macintosh' in ua and 'Mobile/' in ua)
        else 'Android' if 'Android' in ua else 'Windows' if 'Windows' in ua else 'macOS' if 'Macintosh' in ua else '其他设备')
    browser=next((label for token,label in [('MicroMessenger','微信内置浏览器'),('HUAWEI','华为浏览器'),
        ('HuaweiBrowser','华为浏览器'),('Edg','Edge'),('Firefox','Firefox'),('FxiOS','Firefox'),
        ('Chrome','Chrome'),('CriOS','Chrome'),('Safari','Safari')] if token in ua),'其他浏览器')
    return platform,browser


def send(subscription, payload, config):
    from pywebpush import webpush
    import requests
    class NoRedirectSession(requests.Session):
        def request(self,*args,**kwargs):
            kwargs['allow_redirects']=False
            return super().request(*args,**kwargs)
    with NoRedirectSession() as session:
        return webpush(subscription_info=validate_subscription(subscription),data=json.dumps(payload,ensure_ascii=False),
            vapid_private_key=config['private_key'],vapid_claims={'sub':config['subject']},
            ttl=86400,timeout=12,requests_session=session)
