import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { emptyReviewFilters, mobileReviewFilters, reviewRequestParams } from '../src/utils/myIssueFilters.js'

const source = readFileSync(new URL('../src/views/inspection/MyIssuesView.vue', import.meta.url), 'utf8')
const action = (name, next, context) => runInNewContext(
  `(() => {\n${source.slice(source.indexOf(`const ${name} =`), source.indexOf(`const ${next} =`))}\n${name}()\n})()`,
  context,
)
const plain = value => JSON.parse(JSON.stringify(value))

test('mobile apply uses visible draft fields, fetches page one and leaves desktop conditions unchanged', () => {
  const old = { ...emptyReviewFilters(), id: '18', dateFrom: '2026-09-01', dateTo: '2026-09-30', description: '积水' }
  const draft = { ...old, id: '99', dateFrom: '2026-10-31', dateTo: '2026-10-01', station: ['杨思'], inspectionTableName: ['现场表'], keyword: '接地 锈蚀' }
  const appliedFilters = { value: structuredClone(old) }
  const page = { value: 4 }
  let calls = 0
  action('applyFilters', 'fetchReviewOptions', {
    isMobileReview: { value: true }, filters: { value: draft }, appliedFilters, page,
    acceptingPage: false, fetchMyIssues: () => calls++,
    showActionToast: () => assert.fail('hidden desktop dates must not block mobile filters'),
  })
  assert.equal(calls, 1)
  assert.equal(page.value, 1)
  assert.deepEqual(plain(appliedFilters.value), { ...old, station: ['杨思'], inspectionTableName: ['现场表'], keyword: '接地 锈蚀' })
  assert.equal(draft.id, '99')
  assert.equal(reviewRequestParams(mobileReviewFilters(appliedFilters.value)).issue_id, '')
  assert.notEqual(appliedFilters.value.station, draft.station)
})

test('desktop apply still validates dates and applies all fields', () => {
  const filters = { value: { ...emptyReviewFilters(), id: '99', dateFrom: '2026-10-31', dateTo: '2026-10-01' } }
  const appliedFilters = { value: emptyReviewFilters() }
  let calls = 0
  let errors = 0
  const context = {
    isMobileReview: { value: false }, filters, appliedFilters, page: { value: 4 },
    acceptingPage: false, fetchMyIssues: () => calls++, showActionToast: () => errors++,
  }
  action('applyFilters', 'fetchReviewOptions', context)
  assert.equal(errors, 1)
  assert.equal(calls, 0)
  assert.equal(appliedFilters.value.id, '')
  filters.value.dateTo = '2026-10-31'
  action('applyFilters', 'fetchReviewOptions', context)
  assert.equal(calls, 1)
  assert.deepEqual(plain(appliedFilters.value), filters.value)
})

test('mobile reset clears visible fields only; desktop and station-manager resets retain previous scope', () => {
  for (const [mobile, role] of [[true, 'supervisor'], [false, 'supervisor'], [false, 'station_manager']]) {
    const initial = { ...emptyReviewFilters(), id: '18', station: ['杨思'], inspectionTableName: ['现场表'], keyword: '接地' }
    const filters = { value: initial }
    let closed = 0
    let removed = 0
    action('resetFilters', 'prevPage', {
      filters, isMobileReview: { value: mobile }, currentRole: { value: role },
      isMobileView: { value: mobile }, emptyReviewFilters,
      closeAllDropdowns: () => closed++, getMobileStationStorageKey: () => 'station-filter',
      localStorage: { removeItem: key => { assert.equal(key, 'station-filter'); removed++ } },
    })
    const expected = mobile ? { ...initial, station: [], inspectionTableName: [], keyword: '' }
      : role === 'station_manager' ? { region: '', station: '', inspectionTableName: '' } : emptyReviewFilters()
    assert.deepEqual(plain(filters.value), expected)
    assert.equal(closed, 1)
    assert.equal(removed, mobile ? 1 : 0)
  }
})
