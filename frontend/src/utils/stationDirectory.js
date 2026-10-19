import { stationCoordinates } from './schedulingCoverage.js'

const options = (...values) => values.map(value => ({ value, label: value }))
const yesNo = [{ value: 'yes', label: '是' }, { value: 'no', label: '否' }]
export const stationFilterDefinitions = [
  { key: 'keyword', label: '关键词' },
  { key: 'region', label: '所属片区', options: [] },
  { key: 'station_type', label: '站点类型', options: options('油站', '充电站') },
  { key: 'status', label: '站点状态', options: options('营业中', '停业') },
  { key: 'include_offline_plan', label: '纳入现场计划', options: yesNo },
  { key: 'include_online_plan', label: '纳入视频计划', options: yesNo },
  { key: 'monitoring_status', label: '监控状态', options: options('运行中', '未运行') },
  { key: 'asset_type', label: '资产类型', options: options('全资', '股权') },
  { key: 'is_consolidated', label: '是否并表', options: options('是', '否') },
  { key: 'online_3_status', label: '上线3.0', options: options('未上线', '上线', '上线参股模式') },
  { key: 'operating_hours', label: '营业时段', options: [{ value: 'all-day', label: '24小时营业' }, { value: 'fixed', label: '固定时段营业' }] },
  { key: 'coordinates', label: '地图坐标', options: [{ value: 'complete', label: '已配置有效坐标' }, { value: 'missing', label: '缺少有效坐标' }] },
  { key: 'account_binding', label: '站点账号', options: [{ value: 'bound', label: '已绑定账号' }, { value: 'unbound', label: '未绑定账号' }] },
]

export const createStationFilters = () => Object.fromEntries(stationFilterDefinitions.map(field => [field.key, '']))
export const stationAssetType = value => ['股权', '控股', '参股'].some(word => String(value || '').includes(word)) ? '股权' : value || '-'
export const stationUsernames = station => String(station.station_usernames || '').split(/\s+/).filter(Boolean)

export function stationFilterSummary(filters) {
  return stationFilterDefinitions.map(field => ({ key: field.key, label: field.label,
    value: field.options?.find(option => option.value === filters[field.key])?.label || String(filters[field.key] || '') }))
}

const nameOrder = new Intl.Collator('zh-Hans-CN', { numeric: true, sensitivity: 'base' })
const timestamp = value => Date.parse(String(value || '').replace(' ', 'T')) || 0
export function filterStationDirectory(stations, filters, sort = 'default') {
  const keyword = String(filters.keyword || '').trim().toLocaleLowerCase()
  const rows = stations.filter(station => {
    const values = { ...station, asset_type: stationAssetType(station.asset_type),
      monitoring_status: station.monitoring_status || '运行中', is_consolidated: station.is_consolidated || '否',
      online_3_status: station.online_3_status || '未上线',
      include_offline_plan: station.include_offline_plan === false ? 'no' : 'yes',
      include_online_plan: station.include_online_plan === false ? 'no' : 'yes',
      operating_hours: !station.operating_hours || station.operating_hours === '24小时' ? 'all-day' : 'fixed',
      coordinates: stationCoordinates(station) ? 'complete' : 'missing',
      account_binding: stationUsernames(station).length ? 'bound' : 'unbound',
    }
    if (keyword && ![station.id, station.station_name, station.region, station.address, station.station_manager_name,
      station.station_manager_phone, station.hos_station_code, station.landline_phone, station.station_usernames]
      .join(' ').toLocaleLowerCase().includes(keyword)) return false
    return stationFilterDefinitions.every(field => field.key === 'keyword' || !filters[field.key] || values[field.key] === filters[field.key])
  })
  if (sort === 'name') rows.sort((a, b) => nameOrder.compare(a.station_name || '', b.station_name || '') || Number(a.id) - Number(b.id))
  if (sort === 'updated') rows.sort((a, b) => timestamp(b.updated_at) - timestamp(a.updated_at) || Number(a.id) - Number(b.id))
  return rows
}
