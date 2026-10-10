import re


MAX_DESCRIPTION_SEARCH_LENGTH = 1000
MAX_DESCRIPTION_KEYWORDS = 20


class IssueDescriptionFilterError(ValueError):
    pass


def parse_description_keywords(value):
    text = str(value or "").strip()
    if len(text) > MAX_DESCRIPTION_SEARCH_LENGTH:
        raise IssueDescriptionFilterError("问题描述搜索最多输入1000个字符。")
    keywords = []
    seen = set()
    for keyword in re.split(r"[\s,，;；、]+", text):
        if not keyword or keyword.lower() in seen:
            continue
        seen.add(keyword.lower())
        keywords.append(keyword)
    if len(keywords) > MAX_DESCRIPTION_KEYWORDS:
        raise IssueDescriptionFilterError("问题描述搜索最多使用20个不同关键词。")
    return keywords


def normalize_description_match(value):
    mode = str(value or "all").strip()
    if mode not in ("all", "any"):
        raise IssueDescriptionFilterError("请选择全部包含或任一包含的匹配方式。")
    return mode


def description_filter_clause(value, mode="all"):
    keywords = parse_description_keywords(value)
    mode = normalize_description_match(mode)
    if not keywords:
        return "", []
    operator = " AND " if mode == "all" else " OR "
    clause = "(" + operator.join(["COALESCE(i.description, '') ILIKE %s ESCAPE '!'" for _ in keywords]) + ")"
    # Match literal text, not user-controlled LIKE wildcards. Values stay bound parameters.
    params = ["%" + word.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%" for word in keywords]
    return clause, params
