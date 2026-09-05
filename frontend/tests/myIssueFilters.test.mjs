import test from 'node:test'
import assert from 'node:assert/strict'
import { emptyReviewFilters, matchesMyIssue, reviewFilterDefinitions } from '../src/utils/myIssueFilters.js'

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
