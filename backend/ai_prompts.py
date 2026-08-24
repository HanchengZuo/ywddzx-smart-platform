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

QUALITY_MEASUREMENT_FLOW_CLASSIFICATION_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的质量计量问题环节分类助手。"
    "请依据两张计量检查表的真实规范内容，把原始业务流程为其他或未设置的问题，"
    "归入系统给定的一个有效业务流程。只能使用允许分类列表中的名称，"
    "只能引用输入中真实存在的问题ID，不允许创造新分类或问题。"
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

EQUIPMENT_FACILITIES_REPORT_INSIGHT_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的设备设施月度检查报告分析助手。"
    "请严格基于系统提供的审核通过问题，识别跨站重复出现的高频典型问题，"
    "并围绕所属区域、检查事项和检查内容分析原因、提出工作建议。"
    "只能引用输入数据中真实存在的问题ID、分类和站点，不允许编造任何信息。"
    "必须只输出 JSON，不要解释，不要使用 Markdown。"
)

ON_SITE_SERVICE_REPORT_INSIGHT_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的现场服务月度检查报告分析助手。"
    "请严格基于系统提供的审核通过问题，按管理片区或控参股单位、服务板块分析现场服务问题，"
    "筛选真实突出问题，并形成正式的问题总结和下一步建议。"
    "只能引用输入数据中真实存在的问题ID、站点和分类，不允许编造任何信息。"
    "必须只输出 JSON，不要解释，不要使用 Markdown。"
)

NON_OIL_REPORT_INSIGHT_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的非油月度检查报告分析助手。"
    "请严格基于系统提供的已审核通过问题，按管理片区或控参股单位、非油业务分类分析问题，"
    "筛选真实典型问题，并形成归因分析和改善建议。"
    "只能引用输入数据中真实存在的问题ID、站点和分类，不允许编造任何信息。"
    "必须只输出 JSON，不要解释，不要使用 Markdown。"
)

NON_OIL_CATEGORY_CLASSIFICATION_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的非油检查问题分类助手。"
    "请把原检查项目为‘其他’的问题归入系统给定的一个有效非油检查类别。"
    "只能使用允许分类列表中的完整名称，只能引用输入中真实存在的问题ID，"
    "不允许保留‘其他’，不允许创造新分类或问题。必须只输出JSON，不要解释。"
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
        "designated_typical_issue_id 是系统随机抽取并指定用于管理追溯的真实问题ID。\n"
        "prohibited_candidate_groups 是经过星标和外部规范优先级筛选后仍无法唯一确定的禁止项候选组，"
        "每个 unit_key 必须且只能从本组 candidates 中选一个最具代表性的问题。\n"
        f"{context_payload}\n\n"
        "请返回如下 JSON 对象：\n"
        "{"
        "\"prohibited_decisions\":["
        "{\"unit_key\":\"region:浦东片区\",\"issue_id\":1}"
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
        "1. prohibited_decisions 必须覆盖 prohibited_candidate_groups 中的每个 unit_key，"
        "issue_id 只能取对应 candidates 中的真实值，并优先选择描述具体、风险清楚、代表性强的问题。\n"
        "2. 管理追溯必须围绕 designated_typical_issue_id 对应的问题分析，不得更换问题。\n"
        "3. 工作计划输出 3 条，面向下月质量计量管理改进。\n"
        "4. 所有文字要像正式企业检查报告，不要像聊天回复。\n"
        "5. 只能输出 JSON 本身。"
    )


def build_quality_measurement_flow_classification_prompt(classification_context):
    context_payload = json.dumps(
        classification_context,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "下面是质量计量监督检查报告中待分类的问题，以及“计量稽查检查表（现场）”和"
        "“计量稽查检查表（视频）”的真实规范资料。\n"
        "allowed_categories 是唯一允许返回的业务流程；standards 包含外部规范ID、检查表名称、"
        "原业务流程和完整规范详情；issues 包含问题ID、引用的外部规范ID、检查表、站点、"
        "实际问题描述和原规范详情。请综合问题描述、引用规范及全部规范体系判断最合适的环节。\n"
        f"{context_payload}\n\n"
        "请返回如下 JSON 对象：\n"
        "{\"classifications\":["
        "{\"issue_id\":1,\"category\":\"必须来自allowed_categories\","
        "\"reason\":\"分类依据，控制在60字内\"}"
        "]}\n"
        "要求：\n"
        "1. classifications 必须覆盖 issues 中每个问题ID，且每个问题只返回一次。\n"
        "2. category 必须与 allowed_categories 中某一项完全一致，不能返回其他、其他问题、"
        "未设置、无法判断或自定义名称。\n"
        "3. 优先依据该问题引用的外部规范和问题描述，再参考两张检查表的整体规范结构。\n"
        "4. 只能输出 JSON 本身。"
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


def build_equipment_facilities_report_insight_prompt(report_context):
    context_payload = json.dumps(
        report_context,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "下面是设备设施检查报告的结构化巡检问题数据 JSON，所有问题均已审核通过。\n"
        "area_distribution=按检查表“所属区域”统计的分布，"
        "item_distribution=按检查表“检查事项”统计的分布。"
        "issues 中 issue_id=问题ID，station_name=站点名称，management_unit=管理片区或控参股单位，"
        "area_name=所属区域，inspection_item=检查事项，inspection_content=检查内容，"
        "description=实际问题描述，has_photo=是否有问题照片。\n"
        f"{context_payload}\n\n"
        "请返回如下 JSON 对象：\n"
        "{"
        "\"typical_issue\":{"
        "\"title\":\"高频典型问题名称，控制在24字内\","
        "\"issue_ids\":[1,2,3],"
        "\"summary\":\"说明共性表现和风险，控制在90字内\""
        "},"
        "\"problem_analysis\":["
        "{\"title\":\"分析标题，控制在24字内\",\"content\":\"问题分析，控制在130字内\"}"
        "],"
        "\"work_suggestions\":["
        "{\"title\":\"建议标题，控制在24字内\",\"content\":\"具体可执行的工作建议，控制在130字内\"}"
        "]"
        "}\n"
        "要求：\n"
        "1. typical_issue 必须选择跨多个站点重复出现、具有代表性的同类问题，"
        "issue_ids 返回该类问题涉及的全部真实问题ID，最多 100 个。\n"
        "2. 典型问题不能只因为文字长而入选，应优先考虑发生站点多、描述相近、风险明确的问题。\n"
        "3. problem_analysis 输出 3-5 条，结合所属区域、检查事项、高频问题和单位差异分析。\n"
        "4. work_suggestions 输出 3-5 条，明确排查对象、整改动作、复核要求和责任落实。\n"
        "5. 所有文字使用正式企业设备设施检查报告语气，不要像聊天回复。\n"
        "6. 只能输出 JSON 本身。"
    )


def build_on_site_service_report_insight_prompt(report_context):
    context_payload = json.dumps(
        report_context,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "下面是现场服务检查报告的结构化巡检问题数据 JSON，所有问题均已审核通过。\n"
        "unit_blocks 按所属管理片区或控参股单位组织，service_area 仅包含"
        "暖心服务、快捷服务、整洁舒心、其他管理。"
        "issues 中 issue_id=问题ID，station_name=站点名称，mode=video或onsite，"
        "primary_category和secondary_category=检查表中的真实分类，description=原始问题描述，"
        "has_photo=是否有问题照片。\n"
        f"{context_payload}\n\n"
        "请返回如下 JSON 对象：\n"
        "{"
        "\"region_highlights\":["
        "{"
        "\"unit_name\":\"必须来自输入的真实单位名称\","
        "\"service_area\":\"必须来自对应单位的真实服务板块\","
        "\"summary\":\"该单位该板块的总体概括，控制在90字内\","
        "\"highlights\":["
        "{\"title\":\"突出问题小标题，控制在18字内\","
        "\"issue_ids\":[1,2,3],"
        "\"analysis\":\"突出问题表现，控制在80字内\"}"
        "]"
        "}"
        "],"
        "\"problem_summary\":["
        "{\"title\":\"总结标题，控制在26字内\",\"content\":\"共性问题总结，控制在150字内\"}"
        "],"
        "\"next_steps\":["
        "{\"title\":\"建议标题，控制在24字内\",\"content\":\"具体可执行的下一步建议，控制在180字内\"}"
        "]"
        "}\n"
        "要求：\n"
        "1. region_highlights 覆盖每个有问题的单位及其有数据的服务板块；每个板块输出1-3个突出问题。\n"
        "2. 每个突出问题引用1-5个同一单位、同一服务板块内的真实问题ID，不得跨组引用。\n"
        "3. 优先归纳重复出现、影响服务体验或存在现场风险的问题，不要只选择描述最长的问题。\n"
        "4. problem_summary 输出3-6条，覆盖服务规范、安全劝导、响应效率、现场秩序等真实薄弱点。\n"
        "5. next_steps 输出3-5条，明确责任、培训、整改闭环、复核或迎检准备等可执行动作。\n"
        "6. 所有文字使用正式企业检查报告语气，不要像聊天回复。\n"
        "7. 只能输出 JSON 本身。"
    )


def build_non_oil_report_insight_prompt(report_context):
    context_payload = json.dumps(
        report_context,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "下面是非油检查报告的结构化数据 JSON，所有问题均已审核通过。\n"
        "category_distribution 是六类非油业务问题分布；unit_blocks 按管理片区或控参股单位组织。"
        "issues 中 issue_id=问题ID，station_name=站点名称，unit_name=所属单位，"
        "source_project=检查表原始项目，category_name=归一后的非油分类，description=原始问题描述，"
        "has_photo=是否有问题照片。\n"
        f"{context_payload}\n\n"
        "请返回如下 JSON 对象：\n"
        "{"
        "\"unit_highlights\":["
        "{\"unit_name\":\"必须来自输入的真实单位\","
        "\"summary\":\"该单位问题特征概括，控制在90字内\","
        "\"highlight_issue_ids\":[1,2,3]}"
        "],"
        "\"typical_issues\":["
        "{\"title\":\"典型问题标题，控制在24字内\","
        "\"category_name\":\"必须来自输入的真实分类\","
        "\"issue_ids\":[1,2,3],"
        "\"summary\":\"共性表现和风险概括，控制在90字内\"}"
        "],"
        "\"attribution_analysis\":["
        "{\"title\":\"归因标题，控制在24字内\",\"content\":\"结合真实数据的归因分析，控制在140字内\"}"
        "],"
        "\"improvement_suggestions\":["
        "{\"title\":\"改善建议标题，控制在24字内\",\"content\":\"具体可执行的改善建议，控制在140字内\"}"
        "]"
        "}\n"
        "要求：\n"
        "1. unit_highlights 覆盖每个有问题的单位，每个单位挑选1-4个最有代表性的真实问题ID。\n"
        "2. typical_issues 输出3-6类，优先选择跨站重复、普遍性高或风险明确的问题，"
        "每类最多引用8个真实问题ID。\n"
        "3. attribution_analysis 输出3条，分析流程惯性、执行动力、风险认知或监督机制中真实存在的问题。\n"
        "4. improvement_suggestions 输出3-5条，明确执行动作、责任层级和闭环验证方式。\n"
        "5. 所有文字使用正式企业检查报告语气，不要像聊天回复。\n"
        "6. 只能输出 JSON 本身。"
    )


def build_non_oil_category_classification_prompt(classification_context):
    payload = json.dumps(
        classification_context or {},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "下面是非油检查表中原检查项目为‘其他’的问题数据。\n"
        f"{payload}\n\n"
        "请返回JSON对象："
        "{\"classifications\":[{\"issue_id\":1,\"category\":\"允许分类中的完整名称\","
        "\"reason\":\"不超过50字的分类依据\"}]}。\n"
        "要求每个输入问题都返回一次，category必须来自allowed_categories，不能输出‘其他’。"
    )
