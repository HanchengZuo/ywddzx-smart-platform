from psycopg2.extras import Json

from account_security import (
    DEFAULT_WEAK_PASSWORDS,
    get_role_min_length,
    hash_password,
    normalize_weak_passwords,
    validate_password_against_policy,
    verify_password,
)


DEFAULT_PASSWORD_POLICY = {
    "id": 1,
    "enforcement_mode": "observe",
    "normal_min_length": 12,
    "privileged_min_length": 15,
    "max_length": 64,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_number": True,
    "require_special": True,
    "weak_passwords": DEFAULT_WEAK_PASSWORDS,
    "forbid_identity_similarity": True,
    "history_count": 5,
    "grace_period_days": 30,
    "logout_other_sessions": True,
    "version": 1,
}


def fetch_password_policy(cur):
    cur.execute(
        """
        SELECT
            p.id,
            p.enforcement_mode,
            p.normal_min_length,
            p.privileged_min_length,
            p.max_length,
            p.require_uppercase,
            p.require_lowercase,
            p.require_number,
            p.require_special,
            p.weak_passwords,
            p.forbid_identity_similarity,
            p.history_count,
            p.grace_period_days,
            p.logout_other_sessions,
            p.version,
            p.updated_by,
            updater.username AS updated_by_username,
            TO_CHAR(p.updated_at, 'YYYY-MM-DD HH24:MI') AS updated_at
        FROM password_security_policies p
        LEFT JOIN users updater ON updater.id = p.updated_by
        WHERE p.id = 1
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        return dict(DEFAULT_PASSWORD_POLICY)
    policy = dict(row)
    policy["weak_passwords"] = normalize_weak_passwords(
        policy.get("weak_passwords") or DEFAULT_WEAK_PASSWORDS
    )
    return policy


def build_password_policy_summary(policy, role):
    return {
        "enforcement_mode": policy.get("enforcement_mode", "observe"),
        "min_length": get_role_min_length(policy, role),
        "max_length": int(policy.get("max_length") or 64),
        "require_uppercase": bool(policy.get("require_uppercase", True)),
        "require_lowercase": bool(policy.get("require_lowercase", True)),
        "require_number": bool(policy.get("require_number", True)),
        "require_special": bool(policy.get("require_special", True)),
        "forbid_identity_similarity": bool(policy.get("forbid_identity_similarity", True)),
        "history_count": int(policy.get("history_count") or 0),
        "version": int(policy.get("version") or 1),
    }


def is_password_change_enforced(user, policy):
    if not bool(user.get("must_change_password")):
        return False
    return bool(
        user.get("force_change_immediately")
        or policy.get("enforcement_mode") == "enforce"
    )


def fetch_password_history(cur, user_id, limit):
    if int(limit or 0) <= 0:
        return []
    cur.execute(
        """
        SELECT password_hash
        FROM user_password_history
        WHERE user_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        (user_id, int(limit)),
    )
    return [row["password_hash"] for row in cur.fetchall()]


def validate_and_hash_password(cur, user, password, policy=None):
    effective_policy = policy or fetch_password_policy(cur)
    history = fetch_password_history(cur, user["id"], effective_policy.get("history_count")) if user.get("id") else []
    validated = validate_password_against_policy(password, user, effective_policy, history)
    return hash_password(validated), effective_policy


def update_user_password(
    cur,
    user,
    password,
    *,
    policy=None,
    must_change_password=False,
    force_change_immediately=False,
):
    password_hash, effective_policy = validate_and_hash_password(cur, user, password, policy)
    cur.execute(
        """
        UPDATE users
        SET password_hash = %s,
            must_change_password = %s,
            force_change_immediately = %s,
            password_changed_at = CURRENT_TIMESTAMP,
            password_policy_version = %s,
            password_risk_flags = '[]'::jsonb,
            auth_version = auth_version + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (
            password_hash,
            bool(must_change_password),
            bool(force_change_immediately),
            int(effective_policy.get("version") or 1),
            user["id"],
        ),
    )
    cur.execute(
        """
        INSERT INTO user_password_history (user_id, password_hash, created_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        """,
        (user["id"], password_hash),
    )
    keep_count = max(1, int(effective_policy.get("history_count") or 0) + 1)
    cur.execute(
        """
        DELETE FROM user_password_history
        WHERE user_id = %s
          AND id NOT IN (
              SELECT id FROM user_password_history
              WHERE user_id = %s
              ORDER BY created_at DESC, id DESC
              LIMIT %s
          )
        """,
        (user["id"], user["id"], keep_count),
    )
    return password_hash


def verify_user_password(user, password):
    return verify_password(user.get("password_hash"), password)


def record_security_event(
    cur,
    actor,
    action_type,
    action_result,
    *,
    target=None,
    request_ip=None,
    user_agent=None,
    affected_count=1,
    failure_reason=None,
    details=None,
):
    safe_details = dict(details or {})
    for forbidden_key in (
        "password",
        "current_password",
        "new_password",
        "confirm_password",
        "password_hash",
    ):
        safe_details.pop(forbidden_key, None)
    cur.execute(
        """
        INSERT INTO security_audit_logs (
            actor_user_id,
            actor_username,
            actor_role,
            target_user_id,
            target_username,
            action_type,
            action_result,
            failure_reason,
            request_ip,
            user_agent,
            affected_count,
            details,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (
            actor.get("id") if actor else None,
            str((actor or {}).get("username") or "SYSTEM")[:120],
            str((actor or {}).get("role") or "system")[:80],
            (target or {}).get("id"),
            str((target or {}).get("username") or "")[:120] or None,
            str(action_type or "unknown")[:120],
            "success" if action_result == "success" else "failure",
            str(failure_reason or "")[:500] or None,
            str(request_ip or "")[:120] or None,
            str(user_agent or "")[:500] or None,
            max(0, int(affected_count or 0)),
            Json(safe_details),
        ),
    )
