import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone


def _bounded_env_int(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


LOGIN_WINDOW_SECONDS = _bounded_env_int("LOGIN_RATE_WINDOW_SECONDS", 900, 60, 86400)
LOGIN_PAIR_FAILURE_LIMIT = _bounded_env_int("LOGIN_PAIR_FAILURE_LIMIT", 5, 2, 50)
LOGIN_IP_FAILURE_LIMIT = _bounded_env_int("LOGIN_IP_FAILURE_LIMIT", 20, 5, 500)
LOGIN_BLOCK_SECONDS = _bounded_env_int("LOGIN_BLOCK_SECONDS", 900, 60, 86400)
PUBLIC_AUTH_WINDOW_SECONDS = _bounded_env_int("PUBLIC_AUTH_RATE_WINDOW_SECONDS", 300, 60, 3600)
PUBLIC_AUTH_REQUEST_LIMIT = _bounded_env_int("PUBLIC_AUTH_REQUEST_LIMIT", 40, 10, 500)
PUBLIC_AUTH_BLOCK_SECONDS = _bounded_env_int("PUBLIC_AUTH_BLOCK_SECONDS", 300, 60, 3600)


class AuthenticationRateLimitExceeded(Exception):
    def __init__(self, retry_after, scope_type=""):
        self.retry_after = max(1, int(retry_after or 1))
        self.scope_type = str(scope_type or "")
        super().__init__("请求过于频繁，请稍后再试。")


def build_rate_limit_key(secret_key, scope_type, scope_value):
    secret = str(secret_key or "").encode("utf-8")
    normalized = f"{scope_type}:{str(scope_value or '').strip().lower()}".encode("utf-8")
    return hmac.new(secret, normalized, hashlib.sha256).hexdigest()


def _normalize_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _load_locked_row(cur, scope_key, scope_type, now):
    cur.execute(
        """
        INSERT INTO authentication_rate_limits (
            scope_key,
            scope_type,
            attempt_count,
            window_started_at,
            blocked_until,
            updated_at
        )
        VALUES (%s, %s, 0, %s, NULL, %s)
        ON CONFLICT (scope_key) DO NOTHING;
        """,
        (scope_key, scope_type, now, now),
    )
    cur.execute(
        """
        SELECT scope_key, attempt_count, window_started_at, blocked_until
        FROM authentication_rate_limits
        WHERE scope_key = %s
        FOR UPDATE;
        """,
        (scope_key,),
    )
    return cur.fetchone()


def _retry_after_seconds(blocked_until, now):
    blocked_until = _normalize_datetime(blocked_until)
    if not blocked_until or blocked_until <= now:
        return 0
    return max(1, int((blocked_until - now).total_seconds()) + 1)


def _check_scope(cur, scope_key, scope_type, now):
    row = _load_locked_row(cur, scope_key, scope_type, now)
    retry_after = _retry_after_seconds(row.get("blocked_until"), now)
    if retry_after:
        raise AuthenticationRateLimitExceeded(retry_after, scope_type)
    return row


def _increment_scope(cur, scope_key, scope_type, *, limit, window_seconds, block_seconds, now):
    row = _check_scope(cur, scope_key, scope_type, now)
    window_started_at = _normalize_datetime(row.get("window_started_at")) or now
    attempt_count = int(row.get("attempt_count") or 0)
    if window_started_at + timedelta(seconds=window_seconds) <= now:
        attempt_count = 0
        window_started_at = now

    attempt_count += 1
    blocked_until = now + timedelta(seconds=block_seconds) if attempt_count > limit else None
    cur.execute(
        """
        UPDATE authentication_rate_limits
        SET attempt_count = %s,
            window_started_at = %s,
            blocked_until = %s,
            updated_at = %s
        WHERE scope_key = %s;
        """,
        (attempt_count, window_started_at, blocked_until, now, scope_key),
    )
    if blocked_until:
        raise AuthenticationRateLimitExceeded(block_seconds, scope_type)


def _scope_keys(secret_key, client_ip, username):
    normalized_ip = str(client_ip or "unknown")[:120]
    normalized_username = str(username or "").strip().lower()
    return {
        "login_ip": build_rate_limit_key(secret_key, "login_ip", normalized_ip),
        "login_pair": build_rate_limit_key(
            secret_key,
            "login_pair",
            f"{normalized_ip}\x00{normalized_username}",
        ),
    }


def check_password_login_allowed(cur, secret_key, client_ip, username, *, now=None):
    now = now or datetime.now(timezone.utc)
    keys = _scope_keys(secret_key, client_ip, username)
    _check_scope(cur, keys["login_ip"], "login_ip", now)
    _check_scope(cur, keys["login_pair"], "login_pair", now)


def record_password_login_failure(cur, secret_key, client_ip, username, *, now=None):
    now = now or datetime.now(timezone.utc)
    keys = _scope_keys(secret_key, client_ip, username)
    exceeded = None
    for scope_type, limit in (
        ("login_ip", LOGIN_IP_FAILURE_LIMIT),
        ("login_pair", LOGIN_PAIR_FAILURE_LIMIT),
    ):
        try:
            _increment_scope(
                cur,
                keys[scope_type],
                scope_type,
                limit=limit,
                window_seconds=LOGIN_WINDOW_SECONDS,
                block_seconds=LOGIN_BLOCK_SECONDS,
                now=now,
            )
        except AuthenticationRateLimitExceeded as exc:
            exceeded = exc if exceeded is None else max(
                (exceeded, exc), key=lambda item: item.retry_after
            )
    if exceeded:
        raise exceeded


def clear_successful_password_login(cur, secret_key, client_ip, username):
    keys = _scope_keys(secret_key, client_ip, username)
    cur.execute(
        """
        DELETE FROM authentication_rate_limits
        WHERE scope_key = %s AND scope_type = 'login_pair';
        """,
        (keys["login_pair"],),
    )


def consume_public_auth_budget(cur, secret_key, client_ip, endpoint_group, *, now=None):
    now = now or datetime.now(timezone.utc)
    scope_value = f"{str(client_ip or 'unknown')[:120]}\x00{endpoint_group}"
    scope_key = build_rate_limit_key(secret_key, "public_auth", scope_value)
    _increment_scope(
        cur,
        scope_key,
        "public_auth",
        limit=PUBLIC_AUTH_REQUEST_LIMIT,
        window_seconds=PUBLIC_AUTH_WINDOW_SECONDS,
        block_seconds=PUBLIC_AUTH_BLOCK_SECONDS,
        now=now,
    )
    if secrets.randbelow(100) == 0:
        cur.execute(
            """
            DELETE FROM authentication_rate_limits
            WHERE scope_key IN (
                SELECT scope_key
                FROM authentication_rate_limits
                WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '7 days'
                LIMIT 200
            );
            """
        )
