import logging
import json
import os
import re

from ai_prompts import (
    FINANCE_REPORT_INSIGHT_SYSTEM_PROMPT,
    INSPECTION_STANDARD_RECOMMENDATION_SYSTEM_PROMPT,
    QUALITY_MEASUREMENT_REPORT_INSIGHT_SYSTEM_PROMPT,
    SAFETY_QUALITY_REPORT_INSIGHT_SYSTEM_PROMPT,
    build_finance_report_insight_prompt,
    build_inspection_standard_recommendation_prompt,
    build_quality_measurement_report_insight_prompt,
    build_safety_quality_report_insight_prompt,
)
from ai_usage import build_ai_usage_meta


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"
FEEDBACK_TITLE_SYSTEM_PROMPT = (
    "你是“业务督导中心数智化管理平台”的系统反馈标题生成助手。"
    "请根据反馈类型、问题模块和详细说明，生成一个简短、专业、准确的问题标题。"
    "标题用于反馈列表展示，必须直接输出标题本身，不要解释，不要加前缀，不要加标点。"
)

AI_ERROR_MESSAGES = {
    400: "AI 标题生成请求格式异常，已使用默认标题。",
    401: "AI 服务认证失败，已使用默认标题。",
    402: "AI 服务余额不足，已使用默认标题。",
    422: "AI 服务参数异常，已使用默认标题。",
    429: "AI 服务请求过于频繁，已使用默认标题。",
    500: "AI 服务暂时不可用，已使用默认标题。",
    503: "AI 服务繁忙，已使用默认标题。",
}

STANDARD_RECOMMENDATION_AI_ERROR_MESSAGES = {
    400: "AI 规范匹配请求格式异常，已使用本地规则匹配。",
    401: "AI 服务认证失败，已使用本地规则匹配。",
    402: "AI 服务余额不足，已使用本地规则匹配。",
    422: "AI 服务参数异常，已使用本地规则匹配。",
    429: "AI 服务请求过于频繁，已使用本地规则匹配。",
    500: "AI 服务暂时不可用，已使用本地规则匹配。",
    503: "AI 服务繁忙，已使用本地规则匹配。",
}

FEEDBACK_MODULE_FALLBACK_TITLES = {
    "巡检系统": "巡检系统问题",
    "巡检规范库": "巡检规范问题",
    "检查表原件库": "检查表原件问题",
    "巡检计划": "巡检计划问题",
    "证照管理": "证照管理问题",
    "考核系统": "考核系统问题",
    "培训系统": "培训系统问题",
    "培训材料库": "培训材料问题",
    "车辆管理系统": "车辆管理问题",
    "数据备份管理": "数据备份问题",
    "用户数据管理": "用户管理问题",
    "站点数据管理": "站点数据问题",
    "检查表数据管理": "检查表数据问题",
    "巡检规范库数据管理": "巡检规范问题",
}

FEEDBACK_TYPE_FALLBACK_TITLES = {
    "Bug反馈": "系统功能异常",
    "功能建议": "系统功能建议",
    "体验问题": "系统体验问题",
    "界面优化": "系统体验问题",
    "其他": "系统反馈事项",
}


def get_deepseek_client():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI
    except Exception as exc:
        logging.exception("OpenAI SDK is not available for DeepSeek calls.")
        raise RuntimeError("OpenAI SDK 未安装。") from exc

    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


def normalize_ai_title(value):
    title = str(value or "").strip()
    title = re.sub(r"^[\"'“”‘’《》【】\s]+|[\"'“”‘’《》【】\s]+$", "", title)
    title = re.sub(r"^(标题|问题标题)\s*[:：]\s*", "", title).strip()
    title = re.sub(r"[。！？!?；;：:，,、]+$", "", title).strip()
    title = re.sub(r"\s+", "", title)
    if not title or "问题反馈" in title:
        return ""
    return title[:24]


def build_feedback_fallback_title(feedback_type, module_name, detail_text=""):
    module_title = FEEDBACK_MODULE_FALLBACK_TITLES.get(str(module_name or "").strip())
    if module_title:
        return module_title
    type_title = FEEDBACK_TYPE_FALLBACK_TITLES.get(str(feedback_type or "").strip())
    if type_title:
        return type_title

    detail = str(detail_text or "").strip()
    if "上传" in detail:
        return "文件上传异常"
    if "登录" in detail:
        return "登录使用异常"
    if "导入" in detail:
        return "数据导入异常"
    if "备份" in detail:
        return "数据备份异常"
    return "系统反馈事项"


def get_ai_error_status_code(error):
    status_code = getattr(error, "status_code", None)
    if status_code:
        return status_code
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None)


def get_ai_error_message(error):
    status_code = get_ai_error_status_code(error)
    return AI_ERROR_MESSAGES.get(
        status_code,
        "AI 标题生成失败，已使用默认标题。",
    )


def get_standard_recommendation_ai_error_message(error):
    status_code = get_ai_error_status_code(error)
    return STANDARD_RECOMMENDATION_AI_ERROR_MESSAGES.get(
        status_code,
        "AI 规范匹配失败，已使用本地规则匹配。",
    )


def with_ai_usage_meta(
    result,
    prompt_text="",
    completion_text="",
    ai_called=False,
    success=False,
    fallback_used=False,
    status_code=None,
):
    payload = dict(result or {})
    payload["usage"] = build_ai_usage_meta(
        DEEPSEEK_MODEL,
        prompt_text=prompt_text,
        completion_text=completion_text,
        ai_called=ai_called,
        success=success,
        fallback_used=fallback_used,
        status_code=status_code,
    )
    return payload


def normalize_standard_id(value):
    return str(value or "").strip()


def extract_json_from_ai_text(value):
    text = str(value or "").strip()
    if not text:
        return None

    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        return json.loads(text)
    except Exception:
        pass

    object_match = re.search(r"\{[\s\S]*\}", text)
    if object_match:
        try:
            return json.loads(object_match.group(0))
        except Exception:
            return None
    return None


def normalize_standard_recommendation_payload(payload, standard_map, limit=8):
    if not isinstance(payload, dict):
        return {
            "no_related": True,
            "summary": "AI 返回内容无法识别。",
            "recommendations": [],
        }

    recommendations = []
    seen_standard_ids = set()
    raw_recommendations = payload.get("recommendations")
    if not isinstance(raw_recommendations, list):
        raw_recommendations = []

    for raw_item in raw_recommendations:
        if not isinstance(raw_item, dict):
            continue
        standard_id = normalize_standard_id(raw_item.get("standard_id"))
        if not standard_id or standard_id in seen_standard_ids:
            continue
        standard = standard_map.get(standard_id)
        if not standard:
            continue
        seen_standard_ids.add(standard_id)
        recommendations.append(
            {
                "standard_id": standard_id,
                "confidence": str(raw_item.get("confidence") or "中").strip()[:8] or "中",
                "reason": str(raw_item.get("reason") or "").strip()[:80],
            }
        )
        if len(recommendations) >= limit:
            break

    no_related = bool(payload.get("no_related")) or not recommendations
    return {
        "no_related": no_related,
        "summary": str(payload.get("summary") or "").strip()[:120]
        or ("未找到相关规范。" if no_related else "已找到相关规范。"),
        "recommendations": recommendations,
    }


def build_local_standard_recommendations(issue_description, standards, limit=6):
    description = str(issue_description or "").lower()
    if not description.strip():
        return []

    raw_tokens = [
        token.strip()
        for token in re.split(r"[^\w\u4e00-\u9fff]+", description)
        if len(token.strip()) >= 2
    ]
    token_set = set(raw_tokens)
    for token in raw_tokens:
        chinese_text = "".join(re.findall(r"[\u4e00-\u9fff]", token))
        if len(chinese_text) < 4:
            continue
        for size in (2, 3, 4):
            for index in range(0, len(chinese_text) - size + 1):
                token_set.add(chinese_text[index : index + size])

    tokens = sorted(token_set, key=lambda item: (-len(item), item))
    if not tokens:
        return []

    scored = []
    for standard in standards:
        haystack = " ".join(
            [
                str(standard.get("standard_id") or ""),
                str(standard.get("inspection_table_name") or ""),
                str(standard.get("detail_text") or ""),
            ]
        ).lower()
        score = 0
        for token in tokens:
            if token in haystack:
                score += max(2, len(token))
        if score:
            scored.append((score, standard))

    scored.sort(key=lambda item: (-item[0], str(item[1].get("standard_id") or "")))
    return [
        {
            "standard_id": normalize_standard_id(standard.get("standard_id")),
            "confidence": "低",
            "reason": "根据问题描述关键词本地匹配。",
        }
        for _score, standard in scored[:limit]
        if normalize_standard_id(standard.get("standard_id"))
    ]


def build_standard_recommendation_result(
    issue_description,
    standards,
    generated,
    message,
    payload=None,
):
    standard_map = {
        normalize_standard_id(item.get("standard_id")): item
        for item in standards
        if normalize_standard_id(item.get("standard_id"))
    }

    if payload is None:
        recommendations = build_local_standard_recommendations(issue_description, standards)
        return {
            "generated": generated,
            "message": message,
            "summary": "已使用本地规则匹配。" if recommendations else "未找到相关规范。",
            "no_related": not recommendations,
            "recommendations": recommendations,
        }

    normalized = normalize_standard_recommendation_payload(payload, standard_map)
    return {
        "generated": generated,
        "message": message,
        **normalized,
    }


def generate_standard_recommendations(issue_description, standards):
    normalized_description = str(issue_description or "").strip()
    normalized_standards = [
        item
        for item in standards
        if normalize_standard_id(item.get("standard_id"))
    ]

    if not normalized_standards:
        return with_ai_usage_meta(
            {
                "generated": False,
                "message": "巡检规范库暂无可匹配数据。",
                "summary": "巡检规范库暂无可匹配数据。",
                "no_related": True,
                "recommendations": [],
            },
            prompt_text=normalized_description,
            fallback_used=True,
        )

    try:
        client = get_deepseek_client()
    except Exception as exc:
        logging.exception("DeepSeek client initialization failed for standard recommendation: %s", exc)
        return with_ai_usage_meta(
            build_standard_recommendation_result(
                normalized_description,
                normalized_standards,
                False,
                "AI 服务初始化失败，已使用本地规则匹配。",
            ),
            prompt_text=normalized_description,
            fallback_used=True,
        )

    if not client:
        return with_ai_usage_meta(
            build_standard_recommendation_result(
                normalized_description,
                normalized_standards,
                False,
                "未配置 AI 服务，已使用本地规则匹配。",
            ),
            prompt_text=normalized_description,
            fallback_used=True,
        )

    prompt = build_inspection_standard_recommendation_prompt(
        normalized_description,
        normalized_standards,
    )
    prompt_text = f"{INSPECTION_STANDARD_RECOMMENDATION_SYSTEM_PROMPT}\n{prompt}"

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": INSPECTION_STANDARD_RECOMMENDATION_SYSTEM_PROMPT,
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        raw_content = response.choices[0].message.content
        payload = extract_json_from_ai_text(raw_content)
        if payload is None:
            logging.warning(
                "DeepSeek returned an unusable standard recommendation payload: %r",
                raw_content,
            )
            return with_ai_usage_meta(
                build_standard_recommendation_result(
                    normalized_description,
                    normalized_standards,
                    False,
                    "AI 返回内容无法识别，已使用本地规则匹配。",
                ),
                prompt_text=prompt_text,
                completion_text=raw_content,
                ai_called=True,
                fallback_used=True,
            )

        return with_ai_usage_meta(
            build_standard_recommendation_result(
                normalized_description,
                normalized_standards,
                True,
                "AI 规范匹配完成。",
                payload,
            ),
            prompt_text=prompt_text,
            completion_text=raw_content,
            ai_called=True,
            success=True,
        )
    except Exception as exc:
        status_code = get_ai_error_status_code(exc)
        logging.exception(
            "DeepSeek standard recommendation failed. status=%s error=%s",
            status_code,
            exc,
        )
        return with_ai_usage_meta(
            build_standard_recommendation_result(
                normalized_description,
                normalized_standards,
                False,
                get_standard_recommendation_ai_error_message(exc),
            ),
            prompt_text=prompt_text,
            ai_called=True,
            fallback_used=True,
            status_code=status_code,
        )


def generate_quality_measurement_report_insights(report_context):
    prompt = build_quality_measurement_report_insight_prompt(report_context or {})
    prompt_text = f"{QUALITY_MEASUREMENT_REPORT_INSIGHT_SYSTEM_PROMPT}\n{prompt}"
    try:
        client = get_deepseek_client()
    except Exception as exc:
        logging.exception("DeepSeek client initialization failed for report insights: %s", exc)
        return with_ai_usage_meta(
            {
                "generated": False,
                "message": "AI 服务初始化失败，已使用本地规则生成报告分析。",
                "payload": None,
            },
            prompt_text=prompt_text,
            fallback_used=True,
        )

    if not client:
        return with_ai_usage_meta(
            {
                "generated": False,
                "message": "未配置 AI 服务，已使用本地规则生成报告分析。",
                "payload": None,
            },
            prompt_text=prompt_text,
            fallback_used=True,
        )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": QUALITY_MEASUREMENT_REPORT_INSIGHT_SYSTEM_PROMPT,
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        raw_content = response.choices[0].message.content
        payload = extract_json_from_ai_text(raw_content)
        if payload is None:
            logging.warning(
                "DeepSeek returned an unusable report insight payload: %r",
                raw_content,
            )
            return with_ai_usage_meta(
                {
                    "generated": False,
                    "message": "AI 返回内容无法识别，已使用本地规则生成报告分析。",
                    "payload": None,
                },
                prompt_text=prompt_text,
                completion_text=raw_content,
                ai_called=True,
                fallback_used=True,
            )

        return with_ai_usage_meta(
            {
                "generated": True,
                "message": "AI 报告分析生成成功。",
                "payload": payload,
            },
            prompt_text=prompt_text,
            completion_text=raw_content,
            ai_called=True,
            success=True,
        )
    except Exception as exc:
        status_code = get_ai_error_status_code(exc)
        logging.exception(
            "DeepSeek report insight generation failed. status=%s error=%s",
            status_code,
            exc,
        )
        return with_ai_usage_meta(
            {
                "generated": False,
                "message": "AI 报告分析生成失败，已使用本地规则生成报告分析。",
                "payload": None,
            },
            prompt_text=prompt_text,
            ai_called=True,
            fallback_used=True,
            status_code=status_code,
        )


def generate_safety_quality_report_insights(report_context):
    prompt = build_safety_quality_report_insight_prompt(report_context or {})
    prompt_text = f"{SAFETY_QUALITY_REPORT_INSIGHT_SYSTEM_PROMPT}\n{prompt}"
    try:
        client = get_deepseek_client()
    except Exception as exc:
        logging.exception("DeepSeek client initialization failed for safety report insights: %s", exc)
        return with_ai_usage_meta(
            {
                "generated": False,
                "message": "AI 服务初始化失败，已使用本地规则生成安全质量报告分析。",
                "payload": None,
            },
            prompt_text=prompt_text,
            fallback_used=True,
        )

    if not client:
        return with_ai_usage_meta(
            {
                "generated": False,
                "message": "未配置 AI 服务，已使用本地规则生成安全质量报告分析。",
                "payload": None,
            },
            prompt_text=prompt_text,
            fallback_used=True,
        )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SAFETY_QUALITY_REPORT_INSIGHT_SYSTEM_PROMPT,
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        raw_content = response.choices[0].message.content
        payload = extract_json_from_ai_text(raw_content)
        if payload is None:
            logging.warning(
                "DeepSeek returned an unusable safety report payload: %r",
                raw_content,
            )
            return with_ai_usage_meta(
                {
                    "generated": False,
                    "message": "AI 返回内容无法识别，已使用本地规则生成安全质量报告分析。",
                    "payload": None,
                },
                prompt_text=prompt_text,
                completion_text=raw_content,
                ai_called=True,
                fallback_used=True,
            )

        return with_ai_usage_meta(
            {
                "generated": True,
                "message": "AI 安全质量报告分析生成成功。",
                "payload": payload,
            },
            prompt_text=prompt_text,
            completion_text=raw_content,
            ai_called=True,
            success=True,
        )
    except Exception as exc:
        status_code = get_ai_error_status_code(exc)
        logging.exception(
            "DeepSeek safety report insight generation failed. status=%s error=%s",
            status_code,
            exc,
        )
        return with_ai_usage_meta(
            {
                "generated": False,
                "message": "AI 安全质量报告分析失败，已使用本地规则生成报告。",
                "payload": None,
            },
            prompt_text=prompt_text,
            ai_called=True,
            fallback_used=True,
            status_code=status_code,
        )


def generate_finance_report_insights(report_context):
    prompt = build_finance_report_insight_prompt(report_context or {})
    prompt_text = f"{FINANCE_REPORT_INSIGHT_SYSTEM_PROMPT}\n{prompt}"
    try:
        client = get_deepseek_client()
    except Exception as exc:
        logging.exception("DeepSeek client initialization failed for finance report insights: %s", exc)
        return with_ai_usage_meta(
            {
                "generated": False,
                "message": "AI 服务初始化失败，已使用本地规则生成财务报告分析。",
                "payload": None,
            },
            prompt_text=prompt_text,
            fallback_used=True,
        )

    if not client:
        return with_ai_usage_meta(
            {
                "generated": False,
                "message": "未配置 AI 服务，已使用本地规则生成财务报告分析。",
                "payload": None,
            },
            prompt_text=prompt_text,
            fallback_used=True,
        )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": FINANCE_REPORT_INSIGHT_SYSTEM_PROMPT,
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        raw_content = response.choices[0].message.content
        payload = extract_json_from_ai_text(raw_content)
        if payload is None:
            logging.warning(
                "DeepSeek returned an unusable finance report payload: %r",
                raw_content,
            )
            return with_ai_usage_meta(
                {
                    "generated": False,
                    "message": "AI 返回内容无法识别，已使用本地规则生成财务报告分析。",
                    "payload": None,
                },
                prompt_text=prompt_text,
                completion_text=raw_content,
                ai_called=True,
                fallback_used=True,
            )

        return with_ai_usage_meta(
            {
                "generated": True,
                "message": "AI 财务报告分析生成成功。",
                "payload": payload,
            },
            prompt_text=prompt_text,
            completion_text=raw_content,
            ai_called=True,
            success=True,
        )
    except Exception as exc:
        status_code = get_ai_error_status_code(exc)
        logging.exception(
            "DeepSeek finance report insight generation failed. status=%s error=%s",
            status_code,
            exc,
        )
        return with_ai_usage_meta(
            {
                "generated": False,
                "message": "AI 财务报告分析失败，已使用本地规则生成报告。",
                "payload": None,
            },
            prompt_text=prompt_text,
            ai_called=True,
            fallback_used=True,
            status_code=status_code,
        )


def generate_feedback_title(feedback_type, module_name, detail_text):
    fallback_title = build_feedback_fallback_title(
        feedback_type,
        module_name,
        detail_text,
    )
    prompt = (
        f"反馈类型：{feedback_type}\n"
        f"问题模块：{module_name}\n"
        f"详细说明：{detail_text}\n\n"
        "请生成一个 8-20 个中文字符的问题标题。"
    )
    prompt_text = f"{FEEDBACK_TITLE_SYSTEM_PROMPT}\n{prompt}"
    client = None

    try:
        client = get_deepseek_client()
    except Exception as exc:
        logging.exception("DeepSeek client initialization failed: %s", exc)
        return with_ai_usage_meta(
            {
                "title": fallback_title,
                "generated": False,
                "message": "AI 服务初始化失败，已使用默认标题。",
            },
            prompt_text=prompt_text,
            fallback_used=True,
        )

    if not client:
        return with_ai_usage_meta(
            {
                "title": fallback_title,
                "generated": False,
                "message": "未配置 AI 服务，已使用默认标题。",
            },
            prompt_text=prompt_text,
            fallback_used=True,
        )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": FEEDBACK_TITLE_SYSTEM_PROMPT,
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        raw_title = response.choices[0].message.content
        title = normalize_ai_title(raw_title)
        if not title:
            logging.warning("DeepSeek returned an unusable feedback title: %r", raw_title)
            return with_ai_usage_meta(
                {
                    "title": fallback_title,
                    "generated": False,
                    "message": "AI 标题内容不符合规范，已使用默认标题。",
                },
                prompt_text=prompt_text,
                completion_text=raw_title,
                ai_called=True,
                fallback_used=True,
            )
        return with_ai_usage_meta(
            {
                "title": title,
                "generated": True,
                "message": "AI 标题生成成功。",
            },
            prompt_text=prompt_text,
            completion_text=raw_title,
            ai_called=True,
            success=True,
        )
    except Exception as exc:
        status_code = get_ai_error_status_code(exc)
        logging.exception(
            "DeepSeek feedback title generation failed. status=%s error=%s",
            status_code,
            exc,
        )
        return with_ai_usage_meta(
            {
                "title": fallback_title,
                "generated": False,
                "message": get_ai_error_message(exc),
            },
            prompt_text=prompt_text,
            ai_called=True,
            fallback_used=True,
            status_code=status_code,
        )
