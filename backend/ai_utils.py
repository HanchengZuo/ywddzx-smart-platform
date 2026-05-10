import logging
import os
import re


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"

AI_ERROR_MESSAGES = {
    400: "AI 标题生成请求格式异常，已使用默认标题。",
    401: "AI 服务认证失败，已使用默认标题。",
    402: "AI 服务余额不足，已使用默认标题。",
    422: "AI 服务参数异常，已使用默认标题。",
    429: "AI 服务请求过于频繁，已使用默认标题。",
    500: "AI 服务暂时不可用，已使用默认标题。",
    503: "AI 服务繁忙，已使用默认标题。",
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
    "巡检表数据管理": "巡检表数据问题",
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


def generate_feedback_title(feedback_type, module_name, detail_text):
    fallback_title = build_feedback_fallback_title(
        feedback_type,
        module_name,
        detail_text,
    )
    client = None

    try:
        client = get_deepseek_client()
    except Exception as exc:
        logging.exception("DeepSeek client initialization failed: %s", exc)
        return {
            "title": fallback_title,
            "generated": False,
            "message": "AI 服务初始化失败，已使用默认标题。",
        }

    if not client:
        return {
            "title": fallback_title,
            "generated": False,
            "message": "未配置 AI 服务，已使用默认标题。",
        }

    prompt = (
        f"反馈类型：{feedback_type}\n"
        f"问题模块：{module_name}\n"
        f"详细说明：{detail_text}\n\n"
        "请生成一个 8-20 个中文字符的问题标题。"
    )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是“业务督导中心数智化管理平台”的系统反馈标题生成助手。"
                        "请根据反馈类型、问题模块和详细说明，生成一个简短、专业、准确的问题标题。"
                        "标题用于反馈列表展示，必须直接输出标题本身，不要解释，不要加前缀，不要加标点。"
                    ),
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
            return {
                "title": fallback_title,
                "generated": False,
                "message": "AI 标题内容不符合规范，已使用默认标题。",
            }
        return {
            "title": title,
            "generated": True,
            "message": "AI 标题生成成功。",
        }
    except Exception as exc:
        status_code = get_ai_error_status_code(exc)
        logging.exception(
            "DeepSeek feedback title generation failed. status=%s error=%s",
            status_code,
            exc,
        )
        return {
            "title": fallback_title,
            "generated": False,
            "message": get_ai_error_message(exc),
        }
