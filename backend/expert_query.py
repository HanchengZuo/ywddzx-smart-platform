"""Deterministic query understanding. Scope comes from the question, never model SQL."""
import calendar
from datetime import date, datetime, timedelta
import re
from zoneinfo import ZoneInfo


def empty_options():
    return {'date_from': '', 'date_to': '', 'region': ''}


def date_scope(question, today=None):
    today = today or datetime.now(ZoneInfo('Asia/Shanghai')).date()
    if re.search(r'全部历史|所有历史|所有时间|不限时间|历年|历史累计', question):
        return '', '', '全部历史', True
    full = re.findall(r'(20\d{2})[年/\-](\d{1,2})[月/\-](\d{1,2})(?:日|号)?', question)
    if not full:
        full = [(str(today.year), month, day) for month, day in re.findall(r'(?<!\d)(\d{1,2})月(\d{1,2})(?:日|号)', question)]
    months = re.findall(r'(?:(20\d{2})年)?(\d{1,2})月份?', question)
    iso_months = re.findall(r'(?<!\d)(20\d{2})-(\d{2})(?![\d-])', question)
    if not full and iso_months:
        months = iso_months
    try:
        if full:
            days = [date(*map(int, item)) for item in full]
            if len(days) > 2 or len(days) == 2 and days[0] > days[1]:
                raise ValueError()
            start, end = days[0], days[-1]
        elif months:
            spans = [date(int(year or today.year), int(month), 1) for year, month in months]
            if len(set(spans)) > 1:
                raise ValueError('请在一次统计中明确一个月份或完整的起止日期；跨月比较请提供起止日期。')
            start = spans[0]
            end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
        elif '本月' in question or '这个月' in question:
            start, end = today.replace(day=1), today
        elif '上月' in question or '上个月' in question:
            end = today.replace(day=1) - timedelta(days=1)
            start = end.replace(day=1)
        elif '今天' in question or '今日' in question:
            start = end = today
        elif '昨天' in question or '昨日' in question:
            start = end = today - timedelta(days=1)
        elif '本周' in question or '这周' in question:
            start, end = today - timedelta(days=today.weekday()), today
        elif '今年' in question or '本年' in question:
            start, end = today.replace(month=1, day=1), today
        elif '去年' in question:
            start, end = date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
        elif match := re.search(r'(?:最近|近)(\d{1,3})天', question):
            days = int(match[1])
            if not 1 <= days <= 365:
                raise ValueError()
            start, end = today - timedelta(days=days - 1), today
        elif match := re.search(r'(20\d{2})年', question):
            start, end = date(int(match[1]), 1, 1), date(int(match[1]), 12, 31)
        else:
            return '', '', '', False
    except (TypeError, ValueError) as exc:
        message = str(exc) if str(exc).startswith('请在一次统计') else '提问中的日期无法确定，请写明有效的年月或起止日期。'
        raise ValueError(message) from None
    return start.isoformat(), end.isoformat(), f'{start.isoformat()} 至 {end.isoformat()}', True


def infer_options(question, previous=None, today=None):
    options = {**empty_options(), **{key: value for key, value in (previous or {}).items() if key in empty_options()}}
    for key in ('station_names', 'table_patterns'):
        if (previous or {}).get(key):
            options[key] = previous[key]
    start, end, _, explicit = date_scope(question, today)
    if explicit:
        options.update(date_from=start, date_to=end)
    if re.search(r'全部片区|所有片区|全公司|全平台|全系统', question):
        options['region'] = ''
    return options


def resolve_region(question, regions, previous=''):
    """Only unambiguous complete names/area aliases may constrain database aggregates."""
    if re.search(r'全部片区|所有片区|全公司|全平台|全系统', question):
        return ''
    matches = set()
    for region in regions:
        if region in question:
            matches.add(region)
        short = region.replace('管理片区', '片区')
        if short in question:
            matches.add(region)
    if len(matches) > 1:
        raise ValueError('提问涉及多个片区，请每次明确一个片区，或询问全部片区的分布。')
    return next(iter(matches), previous)


def explicit_issue_ids(question):
    matches = re.findall(r'(?:问题\s*(?:ID|id|编号)?\s*[:：#]?\s*|#)([1-9]\d{0,17})(?!\d)', question)
    return list(dict.fromkeys(int(value) for value in matches))[:8]


def resolve_entities(question, options, stations):
    options = dict(options)
    regions = sorted({row['region'] for row in stations if row['region']})
    previous_region = options.get('region', '')
    explicit_region = resolve_region(question, regions)
    all_regions = bool(re.search(r'全部片区|所有片区|全公司|全平台|全系统|其他片区|别的片区', question))
    options['region'] = '' if all_regions else explicit_region or previous_region
    if all_regions or explicit_region and explicit_region != previous_region:
        options.pop('station_names', None)
    names = list(dict.fromkeys(row['station_name'] for row in stations
                              if len(row['station_name']) >= 2 and row['station_name'] in question))
    # Prefer a full long station name to an accidentally matched name prefix.
    names = [name for name in names if not any(name != other and name in other for other in names)]
    if len(names) > 12:
        raise ValueError('提问中涉及的站点超过12座，请询问片区汇总，或分批列出站点。')
    if names:
        named_regions = {row['region'] for row in stations if row['station_name'] in names}
        if explicit_region and explicit_region not in named_regions:
            raise ValueError('提问中的片区与站点归属不一致，请核对名称后再提问。')
        options['station_names'] = names
        if not explicit_region:
            options['region'] = next(iter(named_regions)) if len(named_regions) == 1 else ''
    elif re.search(r'全部站点|所有站点|其他站点|别的站点', question):
        options.pop('station_names', None)
    return options
