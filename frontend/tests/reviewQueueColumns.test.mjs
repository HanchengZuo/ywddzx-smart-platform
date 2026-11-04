import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/inspection/MyIssuesView.vue', import.meta.url), 'utf8')
const code = source.slice(source.indexOf('const myIssueColumnDefinitions ='), source.indexOf('const myIssueColumnVisibility ='))
function columns(saved, review = true) {
  return new Function('localStorage', 'MY_ISSUES_COLUMNS_STORAGE_KEY', 'isReviewQueue', code + '\nreturn { definitions: myIssueColumnDefinitions, load: loadMyIssueColumnVisibility, defaults: buildDefaultMyIssueColumnVisibility }')(
    { getItem: () => JSON.stringify(saved || {}) }, 'fixture', { value: review },
  )
}
test('review defaults show month and region, but hide review photos', () => {
  const value = columns().load()
  assert.equal(value.month, true)
  assert.equal(value.region, true)
  assert.equal(value.review_photo, false)
})
test('station rectification keeps its existing default fields', () => {
  const value = columns(undefined, false).load()
  assert.equal(value.month, false)
  assert.equal(value.region, false)
  assert.equal(value.review_photo, true)
})
test('old default field selection migrates while real personal selections are preserved', () => {
  const api = columns()
  const old = { ...api.defaults(), month: false, region: false, review_photo: true }
  assert.deepEqual(columns(old).load(), api.defaults())
  const custom = { ...old, standard_detail: false }
  assert.deepEqual(columns(custom).load(), custom)
})
