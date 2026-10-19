"""Station enrollment switches; historical plan items are never removed implicitly."""

PLAN_FIELDS = {'offline': 'include_offline_plan', 'online': 'include_online_plan'}
PLAN_LABELS = {'offline': '现场', 'online': '视频'}
SCHEMA_SQL = '''
ALTER TABLE stations ADD COLUMN IF NOT EXISTS include_offline_plan BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE stations ADD COLUMN IF NOT EXISTS include_online_plan BOOLEAN NOT NULL DEFAULT TRUE;
UPDATE stations SET include_offline_plan=TRUE WHERE include_offline_plan IS NULL;
UPDATE stations SET include_online_plan=TRUE WHERE include_online_plan IS NULL;
ALTER TABLE stations ALTER COLUMN include_offline_plan SET DEFAULT TRUE,
  ALTER COLUMN include_offline_plan SET NOT NULL,
  ALTER COLUMN include_online_plan SET DEFAULT TRUE,
  ALTER COLUMN include_online_plan SET NOT NULL;
'''


def plan_field(mode):
    if mode not in PLAN_FIELDS:
        raise ValueError('检查类型不合法。')
    return PLAN_FIELDS[mode]


def enrollment_value(data, field):
    value = data.get(field, True)
    if type(value) is bool:
        return value
    if value in ('是', '否'):
        return value == '是'
    label = PLAN_LABELS[next(mode for mode, key in PLAN_FIELDS.items() if key == field)]
    raise ValueError(f'是否纳入{label}巡检计划须为是或否。')


def enrollment_error(station, mode):
    if station.get(plan_field(mode), True) is not False:
        return ''
    return f"【{station.get('station_name') or station.get('id')}】已关闭纳入{PLAN_LABELS[mode]}巡检计划，不能新增纳入。"


def require_plan_enrollment(cur, station, mode, plan_config_id):
    message = enrollment_error(station, mode)
    if not message:
        return
    # Existing inclusions remain historical commitments; removing one revokes this exception.
    cur.execute('''SELECT is_included FROM inspection_plan_station_items
                   WHERE plan_config_id=%s AND station_id=%s FOR UPDATE''',
                (plan_config_id, station['id']))
    previous = cur.fetchone()
    if not previous or not previous['is_included']:
        raise ValueError(message)
