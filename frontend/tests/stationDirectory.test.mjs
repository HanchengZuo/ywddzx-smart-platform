import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createStationFilters, filterStationDirectory, stationAssetType,
  stationFilterDefinitions, stationFilterSummary, stationUsernames,
} from '../src/utils/stationDirectory.js'

const rows = [
  { id: 1, station_name: '测试1站', region: '浦东', station_type: '油站', status: '营业中',
    hos_station_code: 'PD01', address: '示例路11号', station_manager_name: '张三', station_manager_phone: '13800000001',
    landline_phone: '021-12345678', station_usernames: 'pd01 pd02', asset_type: '控股', is_consolidated: '是',
    online_3_status: '上线', monitoring_status: '运行中', operating_hours: '06:00-22:00',
    include_offline_plan: false, include_online_plan: true, longitude: 121.1, latitude: 31.2, updated_at: '2026-10-19 12:00:00' },
  { id: 2, station_name: '测试10站', region: '浦东', station_type: '充电站', status: '停业',
    asset_type: '全资', monitoring_status: '未运行', include_offline_plan: true, include_online_plan: false,
    longitude: 0, latitude: 0, updated_at: '2026-10-18 12:00:00' },
  { id: 3, station_name: '测试2站', region: '松金', station_type: '油站', status: '营业中',
    asset_type: '参股', station_usernames: '  sj01\n sj02 ', operating_hours: '24小时', updated_at: '2026-10-20 12:00:00' },
]
const matchingIds = (overrides, source = rows, sort) => filterStationDirectory(source, { ...createStationFilters(), ...overrides }, sort).map(row => row.id)

test('station filters are fresh, complete and default to no restrictions', () => {
  const first = createStationFilters()
  first.keyword = '修改'
  const second = createStationFilters()
  assert.ok(Object.values(second).every(value => value === ''))
  assert.deepEqual(Object.keys(second), stationFilterDefinitions.map(field => field.key))
  assert.deepEqual(matchingIds({}), [1, 2, 3])
})

test('independent plan filters distinguish false from unrestricted and support legacy defaults', () => {
  assert.deepEqual(matchingIds({ include_offline_plan: 'no' }), [1])
  assert.deepEqual(matchingIds({ include_online_plan: 'no' }), [2])
  assert.deepEqual(matchingIds({ include_offline_plan: 'yes' }), [2, 3])
  assert.deepEqual(matchingIds({ include_online_plan: 'yes' }), [1, 3])
  assert.deepEqual(matchingIds({ include_offline_plan: 'no', include_online_plan: 'no' }), [])
  assert.deepEqual(matchingIds({ include_offline_plan: 'yes', include_online_plan: 'yes' }), [3])
})

test('keyword search supports station, contact, code, account and address fields, ignoring case', () => {
  for (const keyword of ['测试1站', ' PD01 ', '示例路', '张三', '13800000001', '021-12345678', 'pd02']) {
    assert.deepEqual(matchingIds({ keyword }), [1], keyword)
  }
  assert.deepEqual(matchingIds({ keyword: '松金' }), [3])
  assert.deepEqual(matchingIds({ keyword: '不存在' }), [])
})

test('all archive filters work individually and combine as intersections', () => {
  const expectations = {
    region: ['浦东', [1, 2]], station_type: ['充电站', [2]], status: ['停业', [2]],
    monitoring_status: ['未运行', [2]], asset_type: ['股权', [1, 3]],
    is_consolidated: ['是', [1]], online_3_status: ['上线', [1]],
    operating_hours: ['fixed', [1]], coordinates: ['complete', [1]], account_binding: ['unbound', [2]],
  }
  for (const [key, [value, expected]] of Object.entries(expectations)) {
    assert.deepEqual(matchingIds({ [key]: value }), expected, key)
  }
  assert.deepEqual(matchingIds({ region: '浦东', include_offline_plan: 'yes', monitoring_status: '未运行', status: '停业' }), [2])
  assert.deepEqual(matchingIds({ region: '松金', status: '停业' }), [])
})

test('legacy display defaults, asset aliases and account normalization match the archive', () => {
  assert.deepEqual(matchingIds({ monitoring_status: '运行中' }), [1, 3])
  assert.deepEqual(matchingIds({ is_consolidated: '否', online_3_status: '未上线', operating_hours: 'all-day' }), [2, 3])
  assert.deepEqual(stationUsernames(rows[2]), ['sj01', 'sj02'])
  assert.deepEqual(stationUsernames({}), [])
  for (const name of ['股权', '控股', '参股', '控股公司']) assert.equal(stationAssetType(name), '股权')
  assert.equal(stationAssetType('全资'), '全资')
  assert.equal(stationAssetType(''), '-')
})

test('coordinate completeness uses validated coordinates, not truthiness', () => {
  const source = [
    { id: 1, longitude: 121, latitude: 31 }, { id: 2, longitude: '', latitude: 31 },
    { id: 3, longitude: 200, latitude: 31 }, { id: 4, longitude: 121, latitude: null },
    { id: 5, longitude: 'bad', latitude: 31 }, { id: 6, longitude: 0, latitude: 0 },
    { id: 7, longitude: 0, latitude: 31 },
  ]
  assert.deepEqual(matchingIds({ coordinates: 'complete' }, source), [1, 7])
  assert.deepEqual(matchingIds({ coordinates: 'missing' }, source), [2, 3, 4, 5, 6])
})

test('sorting is deterministic without mutating stations or filter state', () => {
  const copy = structuredClone(rows)
  assert.deepEqual(matchingIds({}, rows, 'name'), [1, 3, 2])
  assert.deepEqual(matchingIds({}, rows, 'updated'), [3, 1, 2])
  assert.deepEqual(rows, copy)
  const equalRows = [{ id: 4, station_name: '同名' }, { id: 2, station_name: '同名' }]
  assert.deepEqual(matchingIds({}, equalRows, 'name'), [2, 4])
  assert.deepEqual(matchingIds({}, equalRows, 'updated'), [2, 4])
  assert.deepEqual(matchingIds({}, equalRows), [4, 2])
})

test('active filter summary displays readable Chinese values even when advanced filters collapse', () => {
  const summary = stationFilterSummary({ ...createStationFilters(), region: '浦东', include_offline_plan: 'no',
    include_online_plan: 'yes', coordinates: 'missing', operating_hours: 'fixed', account_binding: 'bound' })
  const active = Object.fromEntries(summary.filter(field => field.value).map(field => [field.label, field.value]))
  assert.deepEqual(active, { 所属片区: '浦东', 纳入现场计划: '否', 纳入视频计划: '是',
    营业时段: '固定时段营业', 地图坐标: '缺少有效坐标', 站点账号: '已绑定账号' })
  assert.equal(summary.length, stationFilterDefinitions.length)
})
