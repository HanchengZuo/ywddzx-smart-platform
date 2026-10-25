"""AMap transport used only by the dedicated full-matrix collector."""
import json
import math
from urllib.parse import urlencode
from urllib.request import urlopen
from driving_errors import DrivingUnavailable

AMAP_DISTANCE_URL = 'https://restapi.amap.com/v3/distance'


def fetch_distance(key, origins, destination, timeout):
    parameters = dict(key=key, origins='|'.join(origins), destination=destination, type='1', output='JSON')
    try:
        with urlopen(AMAP_DISTANCE_URL + '?' + urlencode(parameters), timeout=timeout) as response:
            if response.status != 200:
                raise ValueError()
            return json.loads(response.read(2_000_001))
    except Exception:
        # urllib exceptions include the key-bearing URL. Never propagate them.
        raise DrivingUnavailable('高德驾车服务暂时无法连接，旧路网数据保持不变。') from None


def parse_results(data, count):
    if not isinstance(data, dict) or data.get('status') != '1':
        code = str(data.get('infocode', '')) if isinstance(data, dict) else ''
        if code in ('10001', '10009', '10010', '10012', '10013'):
            raise DrivingUnavailable('高德Web服务Key未授权或平台类型不匹配，请管理员核对AMAP_KEY配置。')
        if code in ('10003', '10004', '10019', '10020', '10021', '10044'):
            raise DrivingUnavailable('高德服务额度或频率受限，当前采集暂停，旧批次仍可使用。')
        raise DrivingUnavailable('高德驾车服务返回异常，旧路网数据保持不变。')
    values = data.get('results')
    if not isinstance(values, list) or len(values) != count:
        raise DrivingUnavailable('高德驾车数据不完整，暂不发布新批次。')
    result = {}
    for value in values:
        try:
            if not isinstance(value, dict) or isinstance(value.get('origin_id'), bool):
                raise ValueError()
            index = int(value['origin_id']) - 1
            if index in result or not 0 <= index < count or str(value.get('dest_id')) != '1':
                raise ValueError()
            if str(value.get('code', '0')) in ('1', '2', '3'):
                result[index] = None
                continue
            if value.get('info') or str(value.get('code', '0')) != '0':
                raise ValueError()
            seconds, meters = float(value['duration']), float(value['distance'])
            if not all(math.isfinite(n) and n >= 0 for n in (seconds, meters)):
                raise ValueError()
            result[index] = dict(seconds=round(seconds), meters=round(meters))
        except (ValueError, KeyError, TypeError, OverflowError):
            raise DrivingUnavailable('高德驾车数据格式异常，暂不发布新批次。') from None
    return result
