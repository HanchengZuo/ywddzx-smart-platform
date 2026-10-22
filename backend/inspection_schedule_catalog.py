"""Explicit business roster and stable column keys for the v9.7 schedule."""
import re

COLUMNS = {
    'annual': (
        ('metering_site', '现场', '计量稽查检查表（现场）'),
        ('metering_video', '视频', '计量稽查检查表（视频）'),
    ),
    'offline': (
        ('odor', '无异味', '环境无异味管理检查表（现场）'),
        ('finance', '财务', '财务检查表（现场）'),
        ('equipment', '设备', '设备设施检查表（现场）'),
        ('safety', '质量健康安全', '质量安全环保检查表（现场）'),
        ('retail', '非油', '非油检查表（现场）'),
        ('service', '加油现场', '现场检查明细表（现场）'),
    ),
    'online': (
        ('safety', '安全', '质量安全环保检查表（视频）'),
        ('measurement', '计量', '计量稽查检查表（视频）'),
        ('service', '现场', '现场检查明细表（视频）'),
    ),
}

OFFLINE_GROUPS = (
    ('松金', '沈浦泾南 金朝 金发 金三角 金山第二 金山第六 金山第三 金山第四 金山第五 金山第一 廊华 乐都 泖新 茸惠 茸平 三新 泗砖 松江第二 松江第三 松江第一 望榭 欣宝 叶新'),
    ('浦东', '爱使浦南 龚路 国郃 环南 金科 苗圃 妙境 浦东北路 浦星 昕鑫 徐浦 杨思 英伦 赵高路 振兴'),
    ('南汇', '滨湾 东新 国彝 鹤鸣 力胜 南汇第二 泥城 人民西路 瓦屑 新场 新桥'),
    ('闵普徐', '虹梅南路 虹莘 华辉 华浦 金迈 泾阳 凯燕 龙吴路 梅莘 闵行第一 普陀第一 上中 莘庄工业区 中春路'),
    ('嘉青', '创智 杜村 方皇 嘉定第二 嘉定第三 嘉定第四 嘉定第一 嘉松 青浜 青华 青浦第二 青浦第一 青物 四岔口 徐行 勇盛 重盈'),
    ('中油同盛', '同盛第一 万祥 新港 洋山保税港区'),
    ('中油申能', '川朴路 平霄路'),
    ('中油上海', '漕宝路'),
    ('中油浦江', '航浦'),
    ('中油浦东', '绿畅 绿地 绿中'),
    ('中油农工商', '共富 潘泾路 前哨 长江 长圳 中鹏'),
    ('中油康桥', '大新场 康桥'),
    ('中油港汇', '古棕路 花柏路'),
    ('中油奉贤', '奉杰 奉贤第二 奉贤第六 奉贤第七 奉贤第三 奉贤第四 奉贤第五 奉贤第一 广达 金山农工商'),
    ('奉贤', '安达 洪庙 金汇 锦桥 平安 钱桥 青村 四团 泰日 塘外 头桥 邬桥 五四 肖塘 新寺 A30'),
    ('崇明', '崇明第八 崇明第二 崇明第二十 崇明第九 崇明第七 崇明第三 崇明第十八 崇明第十三 崇明第十四 崇明第十五 崇明第四 崇明第五 前卫 南门 圆沙'),
    ('宝静', '爱使东方唐山路 宝杨第二 宝杨第一 常德路 晟隆 锦秋 灵广 凌桥第二 凌桥第一 泰和 维辉 物流园区 闸北第一'),
)
VIDEO_EXCLUSIONS = {
    '松金': {'泗砖'}, '闵普徐': {'泾阳'}, '嘉青': {'青浦第二'},
    '中油同盛': {'万祥', '新港'}, '中油申能': {'川朴路', '平霄路'},
    '中油上海': {'漕宝路'}, '中油浦江': {'航浦'}, '中油浦东': {'绿畅', '绿地', '绿中'},
    '中油农工商': {'共富', '潘泾路', '前哨', '长江', '长圳', '中鹏'},
    '中油港汇': {'古棕路', '花柏路'}, '中油奉贤': {'奉杰'}, '宝静': {'晟隆', '灵广'},
}


def normalized_region(value):
    return re.sub(r'(管理片区|片区|公司)$', '', str(value or '').strip())


def roster(mode):
    if mode not in COLUMNS:
        raise ValueError('请选择现场或视频检查。')
    entries = [(region, name) for region, names in OFFLINE_GROUPS for name in names.split()
               if mode != 'online' or name not in VIDEO_EXCLUSIONS.get(region, set())]
    return {entry: index for index, entry in enumerate(entries, 1)}


def roster_position(station, mode):
    name = str(station.get('station_name') or '').strip()
    return roster(mode).get((normalized_region(station.get('region')), name))
