import json


INSPECTION_STANDARD_RECOMMENDATION_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的巡检规范引用助手。"
    "请根据督导员填写的现场实际问题描述，从给定的巡检规范库资料中筛选最相关的规范。"
    "你只能引用资料中真实存在的规范ID，不允许编造规范ID。"
    "如果没有足够相关的规范，请明确返回 no_related=true。"
    "必须只输出 JSON，不要解释，不要使用 Markdown。"
)


def build_inspection_standard_recommendation_prompt(issue_description, standards):
    standards_payload = json.dumps(
        standards,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "现场实际问题描述：\n"
        f"{issue_description}\n\n"
        "巡检规范库资料 JSON 数组如下。每一项包含："
        "standard_id=规范ID，inspection_table_name=检查表名称，detail_text=规范详情。\n"
        f"{standards_payload}\n\n"
        "请返回如下 JSON 对象：\n"
        "{"
        "\"no_related\": false,"
        "\"summary\": \"一句话说明匹配依据\","
        "\"recommendations\": ["
        "{"
        "\"standard_id\": \"必须来自资料中的真实规范ID\","
        "\"confidence\": \"高/中/低\","
        "\"reason\": \"为什么这条规范与问题描述相关，控制在40字以内\""
        "}"
        "]"
        "}\n"
        "要求：\n"
        "1. recommendations 最多返回 8 条，按相关性从高到低排序。\n"
        "2. 如果没有相关规范，返回 {\"no_related\": true, \"summary\": \"未找到相关规范\", \"recommendations\": []}。\n"
        "3. 只能输出 JSON 本身，不要附加任何说明文字。"
    )
