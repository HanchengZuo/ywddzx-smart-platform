import json


INSPECTION_STANDARD_RECOMMENDATION_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的巡检规范引用助手。"
    "请根据督导员填写的现场实际问题描述，从给定的巡检规范库资料中筛选最相关的规范。"
    "你只能引用资料中真实存在的规范ID，不允许编造规范ID。"
    "如果没有足够相关的规范，请明确返回 no_related=true。"
    "必须只输出 JSON，不要解释，不要使用 Markdown。"
)

QUALITY_MEASUREMENT_REPORT_INSIGHT_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的月度监督检查报告分析助手。"
    "请基于系统提供的真实巡检问题数据，挑选突出问题并生成管理追溯和工作计划。"
    "只能引用输入数据中真实存在的问题ID，不允许编造站点、问题或问题ID。"
    "必须只输出 JSON，不要解释，不要使用 Markdown。"
)

SAFETY_QUALITY_REPORT_INSIGHT_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的安全质量月度检查报告分析助手。"
    "请严格基于系统提供的审核通过问题，分别分析视频扫站与四不两直现场检查。"
    "只能引用输入数据中真实存在的问题ID，不允许编造站点、问题、分类或问题ID。"
    "必须只输出 JSON，不要解释，不要使用 Markdown。"
)

FINANCE_REPORT_INSIGHT_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的财务月度检查报告分析助手。"
    "请严格基于系统提供的审核通过问题，围绕财务检查表中的项目和关键环节分析问题，"
    "并提出具体、可执行的检查内容建议。"
    "只能引用输入数据中真实存在的问题ID、项目和关键环节，不允许编造站点、问题或分类。"
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


def build_quality_measurement_report_insight_prompt(report_context):
    context_payload = json.dumps(
        report_context,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "下面是质量计量监督检查报告的结构化巡检问题数据 JSON。\n"
        "数据字段说明：flow_name=业务流程，issues=该业务流程下的问题，"
        "issue_id=问题ID，station_name=站点名称，unit_name=所属片区或控参股单位，"
        "description=问题描述，is_prohibited=是否禁止项，is_marked_typical=是否被人工标记为典型/优秀。\n"
        f"{context_payload}\n\n"
        "请返回如下 JSON 对象：\n"
        "{"
        "\"flow_highlights\":["
        "{"
        "\"flow_name\":\"必须来自输入中的业务流程名称\","
        "\"highlight_issue_ids\":[1,2,3],"
        "\"summary\":\"该环节突出问题的一句话概括，控制在50字内\""
        "}"
        "],"
        "\"management_trace\":{"
        "\"typical_issue_id\":1,"
        "\"execution_analysis\":\"执行层面分析，控制在80字内\","
        "\"supervision_analysis\":\"监督层面分析，控制在90字内\","
        "\"management_analysis\":\"管理层面分析，控制在90字内\","
        "\"conclusion\":\"必须以综上所述开头，控制在110字内\","
        "\"improvement_measures\":["
        "{\"level\":\"管理层面\",\"content\":\"改进措施，控制在70字内\"},"
        "{\"level\":\"监督层面\",\"content\":\"改进措施，控制在70字内\"},"
        "{\"level\":\"执行层面\",\"content\":\"改进措施，控制在70字内\"}"
        "]"
        "},"
        "\"work_plan\":["
        "{\"title\":\"工作计划标题，控制在24字内\",\"content\":\"计划内容，控制在120字内\"}"
        "]"
        "}\n"
        "要求：\n"
        "1. 每个业务流程最多挑选 3 个突出问题，必须只返回该流程内真实 issue_id。\n"
        "2. 管理追溯优先选择 is_marked_typical=true 的问题；没有时选择禁止项或最具代表性的问题。\n"
        "3. 工作计划输出 3 条，面向下月质量计量管理改进。\n"
        "4. 所有文字要像正式企业检查报告，不要像聊天回复。\n"
        "5. 只能输出 JSON 本身。"
    )


def build_safety_quality_report_insight_prompt(report_context):
    context_payload = json.dumps(
        report_context,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "下面是安全质量检查报告的结构化巡检问题数据 JSON。\n"
        "sections 中 mode=video 表示视频扫站，按“检查内容”分类；"
        "mode=onsite 表示四不两直现场检查，按“检查主题”分类。"
        "issues 中 issue_id=问题ID，station_name=站点名称，unit_name=所属片区或控参股单位，"
        "category_name=真实分类，description=问题描述，has_photo=是否有问题照片。\n"
        f"{context_payload}\n\n"
        "请返回如下 JSON 对象：\n"
        "{"
        "\"typical_issues\":["
        "{"
        "\"mode\":\"video或onsite\","
        "\"title\":\"高频典型问题名称，控制在24字内\","
        "\"issue_ids\":[1,2,3],"
        "\"summary\":\"说明该问题的共性表现，控制在70字内\""
        "}"
        "],"
        "\"category_highlights\":["
        "{"
        "\"mode\":\"video或onsite\","
        "\"category_name\":\"必须来自对应模式的真实分类名称\","
        "\"issue_ids\":[1,2],"
        "\"summary\":\"该分类重点问题概括，控制在60字内\""
        "}"
        "],"
        "\"problem_analysis\":["
        "{\"title\":\"分析标题，控制在24字内\",\"content\":\"结合两类检查数据的问题分析，控制在120字内\"}"
        "],"
        "\"work_suggestions\":["
        "{\"title\":\"建议标题，控制在24字内\",\"content\":\"可执行的安全质量工作建议，控制在120字内\"}"
        "]"
        "}\n"
        "要求：\n"
        "1. typical_issues 必须分别为 video 和 onsite 各返回 1 项；应识别描述相近、重复出现的高频问题，"
        "issue_ids 返回该典型问题涉及的全部真实问题ID，以便系统准确计算站点数和占比。\n"
        "2. category_highlights 应覆盖输入中每个有数据的分类；每个分类挑选 1-3 个最有代表性的问题ID。\n"
        "3. problem_analysis 输出 3-5 条，分析共性原因、执行短板、监督管理和风险趋势。\n"
        "4. work_suggestions 输出 3-5 条，建议必须具体、可执行，并与输入问题相匹配。\n"
        "5. 视频和现场数据必须分别判断，不得把一个模式的问题ID放到另一个模式。\n"
        "6. 所有文字使用正式企业检查报告语气，不要像聊天回复。\n"
        "7. 只能输出 JSON 本身。"
    )


def build_finance_report_insight_prompt(report_context):
    context_payload = json.dumps(
        report_context,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "下面是财务检查报告的结构化巡检问题数据 JSON，所有问题均已审核通过。\n"
        "project_distribution=按“项目”统计的分布，key_link_distribution=按“关键环节”统计的分布。"
        "issues 中 issue_id=问题ID，station_name=站点名称，unit_name=所属片区或控参股单位，"
        "report_date=检查日期，project=项目，key_link=关键环节，"
        "management_standard=管理规范，description=问题描述。\n"
        f"{context_payload}\n\n"
        "请返回如下 JSON 对象：\n"
        "{"
        "\"result_analysis\":["
        "{"
        "\"title\":\"分析标题，控制在24字内\","
        "\"content\":\"结合项目、关键环节和真实问题形成的分析，控制在130字内\","
        "\"related_issue_ids\":[1,2,3]"
        "}"
        "],"
        "\"content_suggestions\":["
        "{"
        "\"title\":\"建议标题，控制在24字内\","
        "\"content\":\"具体可执行的财务检查内容建议，控制在130字内\","
        "\"focus_projects\":[\"必须来自输入的真实项目\"],"
        "\"focus_key_links\":[\"必须来自输入的真实关键环节\"]"
        "}"
        "]"
        "}\n"
        "要求：\n"
        "1. result_analysis 输出 3-5 条，分析高频项目、薄弱关键环节、重复问题和单位差异。\n"
        "2. 每条分析最多引用 3 个真实问题ID；没有合适问题时 related_issue_ids 可为空。\n"
        "3. content_suggestions 输出 3-5 条，建议要明确检查对象、检查动作和管理要求。\n"
        "4. focus_projects 和 focus_key_links 只能使用输入分布中真实存在的名称。\n"
        "5. 所有文字使用正式企业财务检查报告语气，不要像聊天回复。\n"
        "6. 只能输出 JSON 本身。"
    )
