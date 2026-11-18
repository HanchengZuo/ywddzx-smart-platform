import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { businessNotificationPath } from '../src/utils/notificationTarget.js'
import { roleReviewColumns } from '../src/utils/roleReviewColumns.js'
import { rectificationReturnKind } from '../src/utils/issueWorkflow.js'

const source = name => readFileSync(new URL('../src/views/inspection/' + name, import.meta.url), 'utf8')
test('preliminary negative opinions do not pretend the issue has already returned to station', () => {
  for (const stage of ['field','department','area_return']) {
    assert.equal(rectificationReturnKind({ status:'待复核',non_oil_review_stage:stage,review_result:'整改不通过' }), '')
  }
  assert.equal(rectificationReturnKind({ status:'待整改',review_result:'整改不通过' }), 'review')
})
test('station initial filters have no month/date restrictions; other roles retain existing defaults', () => {
  const issues = source('IssuesView.vue').split('const currentMonthValue = () => {')[1].split('\n}')[0]
  const records = source('RecordsView.vue').split('const getDefaultDateRange = () => {')[1].split('\n}')[0]
  for (const role of ['station_manager', 'non_oil', 'supervisor']) {
    const storage = { getItem: () => role }
    const month = new Function('localStorage', issues)(storage)
    const range = new Function('localStorage', 'formatLocalDate', records)(storage, () => 'date')
    assert.equal(month === '', role === 'station_manager')
    assert.equal(range.dateFrom === '' && range.dateTo === '', role === 'station_manager')
  }
})
test('three independent review groups offer all five fields including export photos', () => {
  assert.equal(new Set(roleReviewColumns.map(column => column.key)).size, 15)
  for (const group of ['area','department','field']) {
    assert.equal(roleReviewColumns.filter(column => column.key.startsWith(group + '_')).length, 5)
    assert.ok(roleReviewColumns.find(column => column.key === group + '_review_photo').photo)
  }
  assert.match(source('IssuesView.vue'), /currentRole === 'non_oil' \? roleReviewColumns : \[\]/)
})
test('non-oil messages link to the authorized review or rectification issue, never an arbitrary URL', () => {
  for (const path of ['/inspection/my-reviews','/inspection/my-rectifications']) {
    assert.deepEqual(businessNotificationPath({ kind:'business',source:'non_oil_review',action_path:path,entity_id:48 }),
      { path,query:{issue_id:'48'} })
  }
  assert.equal(businessNotificationPath({kind:'business',source:'non_oil_review',action_path:'https://bad.test',entity_id:48}), '')
})
