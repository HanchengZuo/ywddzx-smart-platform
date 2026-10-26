import test from 'node:test'
import assert from 'node:assert/strict'
import { emptyReviewFilters, matchesMyIssue, mobileReviewFilterDefinitions, mobileReviewFilters, reviewFilterDefinitions, reviewRequestParams } from '../src/utils/myIssueFilters.js'

const issue = { id: 18, time: '2026-09-05 12:00', month: '2026-09', region: '浦东', station: '杨思', inspector: '测试检查人', station_manager: '测试站长', inspection_table_name: '现场表', standard_id: 1000, standard_detail_text: '安全规定', description: '地面积水', standard_tags: [{ group_name: '区域', tag_name: '加油区' }] }
test('review filters match every supported field together', () => {
  assert.ok(matchesMyIssue(issue, { ...emptyReviewFilters(), id: '18', month: '2026-09', dateFrom: '2026-09-01', dateTo: '2026-09-05', region: ['浦东'], station: ['杨思'], inspector: ['测试检查人'], stationManager: '站长', inspectionTableName: ['现场表'], standardId: '1000', standardDetail: '安全', standardTags: ['区域：加油区'], description: '积水' }))
})
test('external standard ID is exact, dates and selections exclude mismatches', () => {
  for (const extra of [{ standardId: '100' }, { dateTo: '2026-09-04' }, { station: ['别站'] }, { inspector: ['别人'] }, { standardTags: ['区域：卸油区'] }]) assert.equal(matchesMyIssue(issue, { ...emptyReviewFilters(), ...extra }), false)
})
test('station filters remain compatible and excluded review filters are absent', () => {
  assert.ok(matchesMyIssue(issue, { region: '浦', station: '杨', inspectionTableName: '' }))
  assert.equal(reviewFilterDefinitions.length, 12)
  for (const key of ['status', 'excellent', 'rectificationResult', 'reviewResult', 'auditState', 'auditStatus']) assert.ok(!reviewFilterDefinitions.some(([field]) => field === key))
})
test('server review defaults include all dates and serialize full filter values', () => {
  const filters = emptyReviewFilters()
  const request = reviewRequestParams(filters)
  assert.equal(request.month, '')
  assert.equal(request.date_from, '')
  assert.equal(request.date_to, '')
  assert.equal(request.page_size, 20)
  filters.station = ['第一页外站点']
  filters.description = '积水'
  assert.deepEqual(JSON.parse(reviewRequestParams(filters, 2, 5).stations), ['第一页外站点'])
  assert.equal(reviewRequestParams(filters, 2, 5).page, 2)
  assert.equal(reviewRequestParams(filters).issue_description, '积水')
})

test('mobile review exposes only station and table without restricting desktop definitions', () => {
  assert.deepEqual(mobileReviewFilterDefinitions, [['station', '站点名称'], ['inspectionTableName', '检查表']])
  assert.equal(reviewFilterDefinitions.length, 12)
})

test('mobile requests ignore hidden desktop conditions and preserve independent selections', () => {
  const desktop = { ...emptyReviewFilters(), id: '18', month: '2026-09', dateFrom: '2026-09-01', dateTo: '2026-09-30', region: ['浦东'], inspector: ['张三'], description: '积水', station: ['杨思'], inspectionTableName: ['现场表'] }
  const snapshot = structuredClone(desktop)
  const mobile = mobileReviewFilters(desktop)
  const request = reviewRequestParams(mobile, 2, 5)
  assert.deepEqual(mobile, { ...emptyReviewFilters(), station: ['杨思'], inspectionTableName: ['现场表'] })
  assert.equal(request.page_size, 5)
  assert.equal(request.page, 2)
  assert.equal(request.issue_id, '')
  assert.equal(request.date_from, '')
  assert.equal(request.month, '')
  assert.equal(request.issue_description, '')
  assert.deepEqual(JSON.parse(request.stations), ['杨思'])
  assert.deepEqual(JSON.parse(request.inspection_tables), ['现场表'])
  mobile.station.push('新站')
  mobile.inspectionTableName.push('新表')
  assert.deepEqual(desktop, snapshot)
  assert.deepEqual(mobileReviewFilters({ station: '杨思', inspectionTableName: '' }).station, ['杨思'])
})
