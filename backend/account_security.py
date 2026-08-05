import re
import secrets

from werkzeug.security import check_password_hash, generate_password_hash


PASSWORD_HASH_PREFIXES = ("scrypt:", "pbkdf2:")
PRIVILEGED_PASSWORD_ROLES = {"root", "supervisor"}
DEFAULT_WEAK_PASSWORDS = [
    "123456",
    "12345678",
    "123456789",
    "password",
    "password123",
    "admin",
    "admin123",
    "qwerty",
    "abc123",
    "111111",
]

RISK_REASON_LABELS = {
    "initial_password": "仍在使用初始密码",
    "common_password": "属于已知常见弱密码",
    "too_short": "密码长度低于当前策略",
    "identity_related": "密码与用户名、手机号或站点编号高度相关",
    "policy_outdated": "尚未按当前密码策略重新设置",
}


class PasswordPolicyError(ValueError):
    pass


def is_supported_password_hash(value):
    text = str(value or "")
    return text.startswith(PASSWORD_HASH_PREFIXES) or text.startswith("$argon2")


def hash_password(password):
    return generate_password_hash(str(password), method="scrypt")


def verify_password(password_hash, candidate):
    if not password_hash or candidate is None:
        return False
    try:
        return check_password_hash(str(password_hash), str(candidate))
    except (TypeError, ValueError):
        return False


def normalize_weak_passwords(values):
    result = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text[:128])
    return result


def get_role_min_length(policy, role):
    key = "privileged_min_length" if str(role or "") in PRIVILEGED_PASSWORD_ROLES else "normal_min_length"
    return int(policy.get(key) or 12)


def normalize_identity(value):
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").casefold())


def identity_is_related(password, identity_values):
    normalized_password = normalize_identity(password)
    if not normalized_password:
        return False
    for value in identity_values or []:
        normalized_value = normalize_identity(value)
        if len(normalized_value) < 4:
            continue
        candidates = {normalized_value}
        if normalized_value.isdigit() and len(normalized_value) >= 6:
            candidates.add(normalized_value[-6:])
        for candidate in candidates:
            if len(candidate) >= 4 and (
                candidate in normalized_password
                or (len(normalized_password) >= 4 and normalized_password in candidate)
            ):
                return True
    return False


def assess_plaintext_password_risks(password, user, policy, *, policy_outdated=True):
    password_text = str(password or "")
    weak_passwords = {
        value.casefold() for value in normalize_weak_passwords(policy.get("weak_passwords") or DEFAULT_WEAK_PASSWORDS)
    }
    flags = []
    if password_text == "123456":
        flags.append("initial_password")
    if password_text.casefold() in weak_passwords and "initial_password" not in flags:
        flags.append("common_password")
    if len(password_text) < get_role_min_length(policy, user.get("role")):
        flags.append("too_short")
    if policy.get("forbid_identity_similarity", True) and identity_is_related(
        password_text,
        [user.get("username"), user.get("phone"), user.get("hos_station_code"), "ywddzx"],
    ):
        flags.append("identity_related")
    if policy_outdated:
        flags.append("policy_outdated")
    return list(dict.fromkeys(flags))


def password_character_rules(policy):
    return {
        "uppercase": bool(policy.get("require_uppercase", True)),
        "lowercase": bool(policy.get("require_lowercase", True)),
        "number": bool(policy.get("require_number", True)),
        "special": bool(policy.get("require_special", True)),
    }


def validate_password_against_policy(password, user, policy, password_history_hashes=None):
    if not isinstance(password, str) or not password:
        raise PasswordPolicyError("请填写新密码。")

    min_length = get_role_min_length(policy, user.get("role"))
    max_length = int(policy.get("max_length") or 64)
    if len(password) < min_length:
        raise PasswordPolicyError(f"当前账号密码至少需要 {min_length} 个字符。")
    if len(password) > max_length:
        raise PasswordPolicyError(f"密码不能超过 {max_length} 个字符。")

    character_rules = password_character_rules(policy)
    missing_rules = []
    if character_rules["uppercase"] and not re.search(r"[A-Z]", password):
        missing_rules.append("大写字母")
    if character_rules["lowercase"] and not re.search(r"[a-z]", password):
        missing_rules.append("小写字母")
    if character_rules["number"] and not re.search(r"\d", password):
        missing_rules.append("数字")
    if character_rules["special"] and not any(
        not character.isalnum() and not character.isspace() for character in password
    ):
        missing_rules.append("特殊字符")
    if missing_rules:
        raise PasswordPolicyError("密码还需包含：" + "、".join(missing_rules) + "。")

    weak_passwords = {
        value.casefold() for value in normalize_weak_passwords(policy.get("weak_passwords") or DEFAULT_WEAK_PASSWORDS)
    }
    if password.casefold() in weak_passwords:
        raise PasswordPolicyError("该密码属于常见弱密码，请更换更安全的密码或密码短语。")

    if policy.get("forbid_identity_similarity", True) and identity_is_related(
        password,
        [
            user.get("username"),
            user.get("phone"),
            user.get("hos_station_code"),
            "ywddzx",
            "业务督导中心",
            "数智管理平台",
        ],
    ):
        raise PasswordPolicyError("密码不能包含用户名、手机号、站点编号或系统名称等关联信息。")

    history_count = max(0, int(policy.get("history_count") or 0))
    for previous_hash in list(password_history_hashes or [])[:history_count]:
        if verify_password(previous_hash, password):
            raise PasswordPolicyError(f"新密码不能与最近 {history_count} 次使用过的密码重复。")
    return password


def generate_strong_initial_password(user, policy, *, minimum_length=18):
    """Generate a one-time credential that satisfies the active password policy."""
    uppercase = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    lowercase = "abcdefghijkmnopqrstuvwxyz"
    numbers = "23456789"
    special = "!@#$%*-_=+?"
    all_characters = uppercase + lowercase + numbers + special
    min_length = get_role_min_length(policy, user.get("role"))
    max_length = int(policy.get("max_length") or 64)
    target_length = min(max_length, max(int(minimum_length), min_length))
    if target_length < 8:
        raise PasswordPolicyError("当前密码策略无法生成安全的初始密码。")

    random_source = secrets.SystemRandom()
    for _ in range(100):
        # Always include all four categories even if an administrator relaxes a rule later.
        characters = [
            secrets.choice(uppercase),
            secrets.choice(lowercase),
            secrets.choice(numbers),
            secrets.choice(special),
        ]
        characters.extend(
            secrets.choice(all_characters) for _ in range(target_length - len(characters))
        )
        random_source.shuffle(characters)
        password = "".join(characters)
        try:
            validate_password_against_policy(password, user, policy)
            return password
        except PasswordPolicyError:
            continue
    raise PasswordPolicyError("暂时无法生成符合策略的初始密码，请检查密码策略。")


def get_risk_level(account_status, must_change_password, risk_flags):
    flags = set(risk_flags or [])
    if account_status != "active":
        return "disabled"
    if flags & {"initial_password", "common_password"}:
        return "critical"
    if flags & {"too_short", "identity_related"}:
        return "high"
    if must_change_password or "policy_outdated" in flags:
        return "remediation"
    return "normal"


def get_risk_reasons(risk_flags, risk_level):
    if risk_level == "disabled":
        return ["账号已暂停"]
    reasons = [RISK_REASON_LABELS[flag] for flag in risk_flags or [] if flag in RISK_REASON_LABELS]
    return reasons or (["符合当前密码策略"] if risk_level == "normal" else ["需要更新密码安全状态"])
