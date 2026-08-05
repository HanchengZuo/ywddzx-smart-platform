import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from psycopg2.extras import Json
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)


PASSKEY_CHALLENGE_TTL_SECONDS = 5 * 60
PASSKEY_RP_NAME = os.environ.get(
    "WEBAUTHN_RP_NAME",
    "业务督导中心数智管理平台",
).strip() or "业务督导中心数智管理平台"


class PasskeyError(ValueError):
    pass


class PasskeyConfigurationError(PasskeyError):
    pass


def _enum_value(value):
    return getattr(value, "value", value)


def get_passkey_settings(request_origin=None):
    configured_origin = os.environ.get("WEBAUTHN_ORIGIN", "").strip().rstrip("/")
    configured_rp_id = os.environ.get("WEBAUTHN_RP_ID", "").strip().lower()
    origin = configured_origin or str(request_origin or "").strip().rstrip("/")
    parsed = urlparse(origin)
    hostname = str(parsed.hostname or "").lower()

    if not origin or parsed.scheme not in {"http", "https"} or not hostname:
        raise PasskeyConfigurationError("Passkey服务地址尚未正确配置，请联系系统管理员。")
    if parsed.scheme != "https" and hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise PasskeyConfigurationError("Passkey只能在HTTPS网站中使用，请先为系统启用HTTPS。")
    if configured_origin and request_origin and origin != str(request_origin).strip().rstrip("/"):
        raise PasskeyConfigurationError("当前访问地址与Passkey服务配置不一致，请使用系统正式访问地址。")

    rp_id = configured_rp_id or hostname
    if hostname != rp_id and not hostname.endswith(f".{rp_id}"):
        raise PasskeyConfigurationError("Passkey域名配置与当前网站不一致，请联系系统管理员。")
    return {"rp_id": rp_id, "origin": origin, "rp_name": PASSKEY_RP_NAME}


def stable_passkey_user_id(user_id):
    return hashlib.sha256(f"ywddzx-passkey-user:{int(user_id)}".encode("utf-8")).digest()


def normalize_credential_name(value, fallback="我的Passkey"):
    name = " ".join(str(value or "").strip().split())
    return (name or fallback)[:80]


def _normalize_transports(values):
    valid = {item.value for item in AuthenticatorTransport}
    result = []
    for value in values or []:
        text = str(value or "").strip()
        if text in valid and text not in result:
            result.append(text)
    return result


def _descriptor(row):
    transports = []
    for value in _normalize_transports(row.get("transports") or []):
        try:
            transports.append(AuthenticatorTransport(value))
        except ValueError:
            continue
    return PublicKeyCredentialDescriptor(
        id=bytes(row["credential_id"]),
        transports=transports or None,
    )


def cleanup_expired_challenges(cur):
    cur.execute(
        """
        DELETE FROM webauthn_challenges
        WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day'
           OR used_at < CURRENT_TIMESTAMP - INTERVAL '1 day'
        """
    )


def create_challenge(cur, *, purpose, challenge, user_id=None, auth_version=None):
    cleanup_expired_challenges(cur)
    flow_id = uuid.uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=PASSKEY_CHALLENGE_TTL_SECONDS)
    cur.execute(
        """
        INSERT INTO webauthn_challenges (
            id, user_id, purpose, challenge, auth_version, expires_at, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (str(flow_id), user_id, str(purpose)[:40], bytes(challenge), auth_version, expires_at),
    )
    return str(flow_id)


def lock_active_challenge(cur, flow_id, purpose, *, user_id=None):
    try:
        parsed_id = uuid.UUID(str(flow_id))
    except (TypeError, ValueError) as exc:
        raise PasskeyError("Passkey请求已失效，请重新操作。") from exc
    cur.execute(
        """
        SELECT id, user_id, purpose, challenge, auth_version, expires_at
        FROM webauthn_challenges
        WHERE id = %s
          AND purpose = %s
          AND used_at IS NULL
          AND expires_at > CURRENT_TIMESTAMP
        FOR UPDATE
        """,
        (str(parsed_id), purpose),
    )
    row = cur.fetchone()
    if not row or (user_id is not None and int(row.get("user_id") or 0) != int(user_id)):
        raise PasskeyError("Passkey请求已失效，请重新操作。")
    return row


def mark_challenge_used(cur, flow_id):
    cur.execute(
        """
        UPDATE webauthn_challenges
        SET used_at = CURRENT_TIMESTAMP
        WHERE id = %s AND used_at IS NULL
        """,
        (str(uuid.UUID(str(flow_id))),),
    )
    if cur.rowcount != 1:
        raise PasskeyError("Passkey请求已被使用，请重新操作。")


def fetch_user_passkeys(cur, user_id, *, for_update=False):
    suffix = " FOR UPDATE" if for_update else ""
    cur.execute(
        f"""
        SELECT
            id, user_id, credential_id, credential_public_key, sign_count,
            transports, device_type, backed_up, credential_name,
            TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at,
            TO_CHAR(last_used_at, 'YYYY-MM-DD HH24:MI') AS last_used_at
        FROM user_passkeys
        WHERE user_id = %s
        ORDER BY created_at ASC, id ASC{suffix}
        """,
        (user_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def count_user_passkeys(cur, user_id):
    cur.execute("SELECT COUNT(*) AS count FROM user_passkeys WHERE user_id = %s", (user_id,))
    return int(cur.fetchone()["count"] or 0)


def serialize_passkey(row):
    return {
        "id": int(row["id"]),
        "credential_name": row.get("credential_name") or "我的Passkey",
        "transports": list(row.get("transports") or []),
        "device_type": row.get("device_type") or "single_device",
        "backed_up": bool(row.get("backed_up")),
        "created_at": row.get("created_at") or "-",
        "last_used_at": row.get("last_used_at") or "尚未使用",
    }


def generate_passkey_registration(cur, user, request_origin, *, purpose="registration"):
    settings = get_passkey_settings(request_origin)
    existing = fetch_user_passkeys(cur, user["id"])
    challenge = secrets.token_bytes(32)
    options = generate_registration_options(
        rp_id=settings["rp_id"],
        rp_name=settings["rp_name"],
        user_id=stable_passkey_user_id(user["id"]),
        user_name=str(user.get("username") or user["id"]),
        user_display_name=str(user.get("real_name") or user.get("username") or user["id"]),
        challenge=challenge,
        timeout=PASSKEY_CHALLENGE_TTL_SECONDS * 1000,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            require_resident_key=True,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[_descriptor(item) for item in existing],
    )
    flow_id = create_challenge(
        cur,
        purpose=purpose,
        challenge=challenge,
        user_id=user["id"],
        auth_version=int(user.get("auth_version") or 1),
    )
    return flow_id, json.loads(options_to_json(options))


def verify_and_store_passkey(
    cur,
    user,
    request_origin,
    *,
    flow_id,
    credential,
    credential_name=None,
    purpose="registration",
):
    settings = get_passkey_settings(request_origin)
    challenge_row = lock_active_challenge(cur, flow_id, purpose, user_id=user["id"])
    if int(challenge_row.get("auth_version") or 0) != int(user.get("auth_version") or 1):
        raise PasskeyError("账号安全状态已经变化，请重新开始绑定。")
    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=bytes(challenge_row["challenge"]),
            expected_rp_id=settings["rp_id"],
            expected_origin=settings["origin"],
            require_user_verification=True,
        )
    except Exception as exc:
        raise PasskeyError("Passkey验证失败，请确认设备验证完成后重试。") from exc

    transports = _normalize_transports((credential or {}).get("response", {}).get("transports", []))
    cur.execute(
        """
        INSERT INTO user_passkeys (
            user_id, credential_id, credential_public_key, sign_count,
            transports, device_type, backed_up, credential_name,
            created_at, last_used_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, NULL)
        RETURNING id
        """,
        (
            user["id"],
            verification.credential_id,
            verification.credential_public_key,
            int(verification.sign_count or 0),
            Json(transports),
            str(_enum_value(verification.credential_device_type) or "single_device")[:40],
            bool(verification.credential_backed_up),
            normalize_credential_name(credential_name),
        ),
    )
    passkey_id = int(cur.fetchone()["id"])
    mark_challenge_used(cur, flow_id)
    return passkey_id


def generate_passkey_authentication(cur, request_origin, *, user_id=None, purpose="authentication"):
    settings = get_passkey_settings(request_origin)
    credentials = fetch_user_passkeys(cur, user_id) if user_id is not None else []
    if user_id is not None and not credentials:
        raise PasskeyError("当前账号尚未绑定Passkey。")
    challenge = secrets.token_bytes(32)
    options = generate_authentication_options(
        rp_id=settings["rp_id"],
        challenge=challenge,
        timeout=PASSKEY_CHALLENGE_TTL_SECONDS * 1000,
        allow_credentials=[_descriptor(item) for item in credentials] if user_id is not None else None,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    flow_id = create_challenge(
        cur,
        purpose=purpose,
        challenge=challenge,
        user_id=user_id,
    )
    return flow_id, json.loads(options_to_json(options))


def credential_id_from_response(credential):
    encoded = str((credential or {}).get("id") or "").strip()
    if not encoded or len(encoded) > 2048:
        raise PasskeyError("Passkey凭据格式不正确。")
    try:
        return base64url_to_bytes(encoded)
    except Exception as exc:
        raise PasskeyError("Passkey凭据格式不正确。") from exc


def verify_passkey_authentication(
    cur,
    request_origin,
    *,
    flow_id,
    credential,
    purpose="authentication",
    expected_user_id=None,
):
    settings = get_passkey_settings(request_origin)
    challenge_row = lock_active_challenge(
        cur,
        flow_id,
        purpose,
        user_id=expected_user_id,
    )
    credential_id = credential_id_from_response(credential)
    cur.execute(
        """
        SELECT
            pk.id AS passkey_id, u.id, pk.user_id, pk.credential_id, pk.credential_public_key,
            pk.sign_count, pk.device_type, pk.backed_up,
            u.username, u.role, u.real_name, u.phone, u.station_id,
            u.must_change_password, u.force_change_immediately,
            u.password_changed_at, u.password_policy_version,
            u.password_risk_flags, u.auth_version, u.account_status,
            s.station_name, s.region, s.address, s.hos_station_code
        FROM user_passkeys pk
        JOIN users u ON u.id = pk.user_id
        LEFT JOIN stations s ON s.id = u.station_id
        WHERE pk.credential_id = %s
        FOR UPDATE OF pk
        """,
        (credential_id,),
    )
    row = cur.fetchone()
    if not row or (expected_user_id is not None and int(row["user_id"]) != int(expected_user_id)):
        raise PasskeyError("Passkey验证失败，请重试。")
    if row.get("account_status") != "active":
        raise PasskeyError("Passkey验证失败，请重试。")

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=bytes(challenge_row["challenge"]),
            expected_rp_id=settings["rp_id"],
            expected_origin=settings["origin"],
            credential_public_key=bytes(row["credential_public_key"]),
            credential_current_sign_count=int(row.get("sign_count") or 0),
            require_user_verification=True,
        )
    except Exception as exc:
        raise PasskeyError("Passkey验证失败，请重试。") from exc

    cur.execute(
        """
        UPDATE user_passkeys
        SET sign_count = %s,
            device_type = %s,
            backed_up = %s,
            last_used_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (
            int(verification.new_sign_count or 0),
            str(_enum_value(verification.credential_device_type) or "single_device")[:40],
            bool(verification.credential_backed_up),
            row["passkey_id"],
        ),
    )
    mark_challenge_used(cur, flow_id)
    return dict(row)
