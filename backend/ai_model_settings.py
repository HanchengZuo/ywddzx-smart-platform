"""Shared routing settings and transactional change history. Never stores API keys."""
from psycopg2.extras import Json
from ai_routing import MODELS, PROVIDERS, SCENARIOS, model_info


class SettingsConflict(ValueError):
    pass


def read_settings(cur, lock=False):
    cur.execute('SELECT default_model, overrides, revision, updated_by_name, updated_at '
                'FROM ai_model_settings WHERE singleton=TRUE' + (' FOR UPDATE' if lock else ''))
    row = cur.fetchone()
    if not row:
        raise RuntimeError('大模型配置尚未初始化，请执行数据库迁移。')
    return dict(row)


def save_settings(cur, data, user):
    if not isinstance(data, dict) or type(data.get('revision')) is not int:
        raise ValueError('请先读取最新模型配置。')
    mode = data.get('mode', 'settings')
    model = data.get('default_model')
    overrides = {} if mode == 'all' else data.get('overrides')
    if mode not in ('all', 'settings') or not isinstance(model, str) or model not in MODELS or not isinstance(overrides, dict):
        raise ValueError('请选择有效的大模型。')
    if any(key not in SCENARIOS or not isinstance(value, str) or value not in MODELS for key, value in overrides.items()):
        raise ValueError('调用场景或模型配置无效。')
    before = read_settings(cur, lock=True)
    if before['revision'] != data['revision']:
        raise SettingsConflict('配置已被其他管理员更新，请刷新后重新调整。')
    # Validate changed targets only; unrelated unconfigured providers do not block editing.
    import os
    old = before.get('overrides') or {}
    changed = {model} if model != before['default_model'] or mode == 'all' else set()
    for key in SCENARIOS:
        new_model = overrides.get(key, model)
        if new_model != old.get(key, before['default_model']):
            changed.add(new_model)
    for target in changed:
        info = model_info(target)
        if not os.environ.get(info['key_env'], '').strip():
            raise ValueError(f"{info['name']} 的 {info['key_env']} 尚未配置，请在后端运行环境中设置。")
    after = {'default_model': model, 'overrides': overrides}
    if model == before['default_model'] and overrides == old:
        return read_settings(cur)
    cur.execute('''UPDATE ai_model_settings SET default_model=%s, overrides=%s,
        revision=revision+1, updated_by_name=%s, updated_at=CURRENT_TIMESTAMP WHERE singleton=TRUE''',
        (model, Json(overrides), user.get('real_name') or user.get('username') or str(user['id'])))
    cur.execute('''INSERT INTO ai_model_setting_events(actor_id, actor_name, before_config, after_config)
        VALUES(%s,%s,%s,%s)''', (user['id'], user.get('real_name') or user.get('username') or '',
        Json({key: before[key] for key in after}), Json(after)))
    return read_settings(cur)


def serialize_settings(settings):
    result = dict(settings)
    result['updated_at'] = str(result.get('updated_at') or '')
    return result


def catalog():
    import os
    return {
        'providers': [dict(id=key, name=item['name'], key_env=item['key_env'],
                           configured=bool(os.environ.get(item['key_env'], '').strip()))
                      for key, item in PROVIDERS.items()],
        'models': [dict(id=key, provider=value[0], name=value[1]) for key, value in MODELS.items()],
        'scenarios': [dict(id=key, group=value[0], name=value[1], description=value[2])
                      for key, value in SCENARIOS.items()],
    }
