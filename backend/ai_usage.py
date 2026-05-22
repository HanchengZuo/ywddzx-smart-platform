import re


AI_USAGE_BASE_URL = "https://api.deepseek.com"

AI_USAGE_PRICING = {
    "deepseek-v4-flash": {
        "label": "DeepSeek-V4-Flash",
        "input_cache_hit": 0.02,
        "input_cache_miss": 1.0,
        "output": 2.0,
        "concurrency": 2500,
    },
    "deepseek-v4-pro": {
        "label": "DeepSeek-V4-Pro",
        "input_cache_hit": 0.025,
        "input_cache_miss": 3.0,
        "output": 6.0,
        "concurrency": 500,
    },
}

CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def count_cjk_chars(text):
    return len(CJK_PATTERN.findall(str(text or "")))


def estimate_text_tokens(text):
    value = str(text or "")
    chinese_chars = count_cjk_chars(value)
    other_chars = max(0, len(value) - chinese_chars)
    return {
        "chars": len(value),
        "chinese_chars": chinese_chars,
        "other_chars": other_chars,
        "tokens": round(chinese_chars * 0.6 + other_chars * 0.3, 2),
    }


def estimate_ai_usage(model, prompt_text="", completion_text="", cache_hit=False):
    normalized_model = str(model or "deepseek-v4-pro").strip() or "deepseek-v4-pro"
    pricing = AI_USAGE_PRICING.get(normalized_model, AI_USAGE_PRICING["deepseek-v4-pro"])
    input_metrics = estimate_text_tokens(prompt_text)
    output_metrics = estimate_text_tokens(completion_text)
    input_price = pricing["input_cache_hit"] if cache_hit else pricing["input_cache_miss"]
    output_price = pricing["output"]
    input_cost = input_metrics["tokens"] / 1_000_000 * input_price
    output_cost = output_metrics["tokens"] / 1_000_000 * output_price

    return {
        "model": normalized_model,
        "base_url": AI_USAGE_BASE_URL,
        "cache_hit_estimated": bool(cache_hit),
        "prompt_chars": input_metrics["chars"],
        "prompt_chinese_chars": input_metrics["chinese_chars"],
        "prompt_other_chars": input_metrics["other_chars"],
        "completion_chars": output_metrics["chars"],
        "completion_chinese_chars": output_metrics["chinese_chars"],
        "completion_other_chars": output_metrics["other_chars"],
        "total_chars": input_metrics["chars"] + output_metrics["chars"],
        "input_tokens_est": input_metrics["tokens"],
        "output_tokens_est": output_metrics["tokens"],
        "total_tokens_est": round(input_metrics["tokens"] + output_metrics["tokens"], 2),
        "input_cost_est": round(input_cost, 6),
        "output_cost_est": round(output_cost, 6),
        "total_cost_est": round(input_cost + output_cost, 6),
        "input_price_per_million": input_price,
        "output_price_per_million": output_price,
    }


def build_ai_usage_meta(
    model,
    prompt_text="",
    completion_text="",
    ai_called=False,
    success=False,
    fallback_used=False,
    status_code=None,
):
    usage = estimate_ai_usage(model, prompt_text, completion_text) if ai_called else estimate_ai_usage(model, "", "")
    usage.update(
        {
            "ai_called": bool(ai_called),
            "success": bool(success),
            "fallback_used": bool(fallback_used),
            "status_code": status_code,
        }
    )
    return usage


def get_ai_pricing_table():
    return [
        {
            "model": model,
            **pricing,
        }
        for model, pricing in AI_USAGE_PRICING.items()
    ]
