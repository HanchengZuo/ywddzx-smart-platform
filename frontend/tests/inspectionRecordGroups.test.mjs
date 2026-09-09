import test from 'node:test'
import assert from 'node:assert/strict'
import { groupInspectionRecords } from '../src/utils/inspectionRecordGroups.js'

test('same station and calendar month merge across dates, batches and tables', () => {
  const rows = [
    { id: 1, station_id: 1, station: '甲', date: '2026-09-30', batch_id: 10, issue_count: 2, result: '异常' },
    { id: 2, station_id: 1, station: '甲', date: '2026-09-01', batch_id: 11, issue_count: 3, sign_status: '已签名确认' }
  ]
  const [group] = groupInspectionRecords(rows)
  assert.equal(group.date, '2026-09')
  assert.equal(group.rowspan, 2)
  assert.equal(group.batchIssueCount, 5)
  assert.equal(group.signedCount, 1)
  assert.equal(group.batchResult, '异常')
  assert.deepEqual(group.records, rows)
})

test('different stations, months and years remain independent, including identical names', () => {
  const rows = [
    { station_id: 1, station: '甲', date: '2026-09-01' },
    { station_id: 2, station: '甲', date: '2026-09-01' },
    { station_id: 1, station: '甲', date: '2026-08-31' },
    { station_id: 1, station: '甲', date: '2025-09-01' }
  ]
  assert.equal(groupInspectionRecords(rows).length, 4)
  assert.deepEqual(groupInspectionRecords([]), [])
})
