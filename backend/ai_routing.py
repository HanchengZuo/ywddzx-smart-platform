"""Model catalog, explicit scenario routing and provider protocol adaptation."""
import os
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps


DEFAULT_MODEL = 'deepseek-v4-pro'
PROVIDERS = {
    'deepseek': {'name': 'DeepSeek', 'key_env': 'DEEPSEEK_API_KEY', 'base_url': 'https://api.deepseek.com'},
    'zhipu': {'name': '智谱 GLM', 'key_env': 'ZHIPU_API_KEY', 'base_url': 'https://open.bigmodel.cn/api/paas/v4'},
    'qwen': {'name': '阿里云百炼', 'key_env': 'DASHSCOPE_API_KEY', 'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1'},
    'mimo': {'name': '小米 MiMo', 'key_env': 'MIMO_API_KEY', 'base_url': 'https://api.xiaomimimo.com/v1'},
}
MODELS = {
    'deepseek-v4-pro': ('deepseek', 'DeepSeek-V4-Pro'),
    'deepseek-flash': ('deepseek', 'DeepSeek-Flash'),
    'glm-5.3': ('zhipu', 'GLM-5.3'),
    'glm-5.3-flash': ('zhipu', 'GLM-5.3-Flash'),
    'glm-5.3-flashx': ('zhipu', 'GLM-5.3-FlashX'),
    'qwen3.8-max': ('qwen', 'Qwen3.8-Max'),
    'qwen3.8-flash': ('qwen', 'Qwen3.8-Flash'),
    'mimo-v2.6-pro': ('mimo', 'MiMo-V2.6-Pro'),
    'mimo-v2.6-flash': ('mimo', 'MiMo-V2.6-Flash'),
    'mimo-v2.6-pro-ultraspeed': ('mimo', 'MiMo-V2.6-Pro-UltraSpeed'),
}
MODEL_ALIASES = {
    'deepseek-v4-flash': 'deepseek-flash',
    'deepseek-v4-flash-vision-exp': 'deepseek-flash',
}
SCENARIOS = {
    'standard_recommendation': ('巡检登记', 'AI引用规范', '本地检索后由模型排序候选规范；可靠历史命中不调用模型。'),
    'expert_qa': ('运营系统', '专家问答', '根据检索到的业务证据生成带来源的回答。'),
    'feedback_title': ('系统反馈', '反馈标题', '根据反馈内容生成简短标题。'),
    'quality_flow': ('质量计量监督检查报告', 'AI环节分类', '对未分类问题判定业务流程；已有分类与人工调整继续复用。'),
    'quality_insights': ('质量计量监督检查报告', '选题、管理追溯与工作计划', '禁止项同优先级决策、典型问题、追溯分析与计划。'),
    'non_oil_category': ('非油检查报告', 'AI其他问题分类', '将其他问题归入检查项目；已有分类与人工调整继续复用。'),
    'non_oil_key': ('非油检查报告', 'AI重点问题分类', '识别重点商品、月度盘点、商品过期和团购问题。'),
    'non_oil_insights': ('非油检查报告', '典型问题与分析建议', '片区亮点、典型问题、归因分析与改善建议。'),
    'equipment_high': ('设备设施检查报告', '高频问题选题', '挑选高频问题；原因仍取规范数据，不由AI编写。'),
    'equipment_special': ('设备设施检查报告', '特性问题选题', '分片区挑选非高频的特性问题。'),
    'equipment_severe': ('设备设施检查报告', '重点问题选题', '挑选需重点关注的问题，保留人工调整。'),
    'equipment_insights': ('设备设施检查报告', '典型问题与分析建议', '典型问题、问题分析和工作建议。'),
    'safety_insights': ('安全质量检查报告', '典型问题与分析建议', '典型问题、分类分析与工作建议。'),
    'finance_insights': ('财务检查报告', '检查结果与内容建议', '检查结果分析与内容建议。'),
    'service_insights': ('现场服务检查报告', '重点问题与总结建议', '片区重点问题、总结与下一步计划。'),
}
_loader = None
_target = ContextVar('ai_model_target', default=None)


def configure_routing(loader):
    """Register a read-only settings loader; never query DB or start tasks at import."""
    global _loader
    _loader = loader


def canonical_model(model):
    """Accept retired IDs in saved settings without exposing duplicate catalog entries."""
    return MODEL_ALIASES.get(model, model) if isinstance(model, str) else model


def model_aliases(model):
    canonical = canonical_model(model)
    return [canonical, *(alias for alias, target in MODEL_ALIASES.items() if target == canonical)]


def normalize_model_settings(settings):
    result = dict(settings)
    if 'default_model' in result:
        result['default_model'] = canonical_model(result['default_model'])
    if isinstance(result.get('overrides'), dict):
        result['overrides'] = {scene: canonical_model(model) for scene, model in result['overrides'].items()}
    return result


def model_info(model):
    model = canonical_model(model)
    provider, label = MODELS[model]
    info = dict(PROVIDERS[provider], provider=provider, model=model, label=label)
    if provider == 'qwen':
        info['base_url'] = os.environ.get('DASHSCOPE_BASE_URL', '').strip() or info['base_url']
    return info


def resolve_model(scenario):
    if scenario not in SCENARIOS:
        raise ValueError('未知AI调用场景。')
    try:
        config = _loader() if _loader else {}
    except Exception:
        raise RuntimeError('大模型配置暂时不可用，请检查数据库迁移或联系管理员。') from None
    model = canonical_model((config.get('overrides') or {}).get(scenario) or config.get('default_model') or DEFAULT_MODEL)
    if not isinstance(model, str) or model not in MODELS:
        raise RuntimeError('AI模型配置无效，请联系管理员。')
    return model


def current_model():
    return (_target.get() or {}).get('model', DEFAULT_MODEL)


@contextmanager
def model_scope(scenario):
    previous = _target.get()
    # Nested helpers in one scenario must share the same immutable routing snapshot.
    if previous and previous['scenario'] == scenario:
        yield previous['model']
        return
    model = resolve_model(scenario)
    token = _target.set({'scenario': scenario, 'model': model})
    try:
        yield model
    finally:
        _target.reset(token)


def ai_scene(scenario):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            key = scenario(*args, **kwargs) if callable(scenario) else scenario
            with model_scope(key):
                return function(*args, **kwargs)
        return wrapped
    return decorate


def get_ai_client():
    info = model_info(current_model())
    key = os.environ.get(info['key_env'], '').strip()
    if not key:
        return None
    from openai import OpenAI
    try:
        timeout = max(30, min(600, float(os.environ.get('AI_TIMEOUT_SECONDS') or os.environ.get('DEEPSEEK_TIMEOUT_SECONDS', '240'))))
    except (TypeError, ValueError):
        timeout = 240
    return OpenAI(api_key=key, base_url=info['base_url'], timeout=timeout, max_retries=1)


def completion_options(model, options):
    """Translate provider-only parameters without changing messages or output schema."""
    model = canonical_model(model)
    result = dict(options, model=model)
    body = dict(result.get('extra_body') or {})
    thinking = body.pop('thinking', {}).get('type', 'disabled') == 'enabled'
    provider = MODELS[model][0]
    if provider == 'zhipu':
        body['thinking'] = {'type': 'enabled'}
        result['reasoning_effort'] = 'low'
        if 'max_tokens' in result:
            # GLM's budget includes its mandatory thinking, not only the JSON answer.
            result['max_tokens'] = max(16384, result['max_tokens'])
    elif provider == 'qwen':
        body['enable_thinking'] = thinking
    else:
        body['thinking'] = {'type': 'enabled' if thinking else 'disabled'}
    if provider == 'mimo' and 'max_tokens' in result:
        result['max_completion_tokens'] = result.pop('max_tokens')
    result['extra_body'] = body
    return result


def create_ai_completion(client, **options):
    return client.chat.completions.create(**completion_options(current_model(), options))
