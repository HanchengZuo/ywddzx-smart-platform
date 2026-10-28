import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { captureIssueListPosition, restoreIssueListPosition } from '../src/utils/myIssueViewport.js'

function fixture({ nested = false } = {}) {
  const scroller = (top, left = 0, parentElement = null) => ({
    isConnected: true, scrollTop: top, scrollLeft: left, overflowY: 'auto', parentElement, calls: [],
    scrollTo(value) { this.scrollTop = value.top; this.scrollLeft = value.left; this.calls.push(value) },
  })
  const documentScroller = scroller(0)
  const content = scroller(1800, 0, documentScroller)
  const inner = nested ? scroller(700, 900, content) : content
  const makeRow = (id, offset, visible = true) => ({
    dataset: { issueId: String(id) }, parentElement: inner,
    getClientRects: () => visible ? [{}] : [],
    getBoundingClientRect: () => ({ top: offset - content.scrollTop - (nested ? inner.scrollTop : 0) }),
  })
  const root = {
    isConnected: true,
    ownerDocument: { scrollingElement: documentScroller, defaultView: { getComputedStyle: node => node } },
    rows: [makeRow(1, 100), makeRow(2, 1500), makeRow(3, 2900), makeRow(3, 500, false)],
    querySelectorAll: () => root.rows,
  }
  return { root, content, inner, documentScroller, makeRow }
}

test('next pending card takes the removed card position without scrolling the document', () => {
  const { root, content, documentScroller, makeRow } = fixture()
  const position = captureIssueListPosition(root, 2)
  assert.equal(position.candidates.length, 3, 'hidden desktop copy excluded')
  root.rows = [makeRow(1, 100), makeRow(3, 1500)]
  content.scrollTop = 100
  restoreIssueListPosition(root, position)
  assert.equal(content.scrollTop, 1800)
  assert.equal(root.rows[1].getBoundingClientRect().top, position.top)
  assert.equal(documentScroller.scrollTop, 0)
})

test('refresh failure retains same card and accounts for error banner height', () => {
  const { root, content, makeRow } = fixture()
  const position = captureIssueListPosition(root, 2)
  root.rows = [makeRow(1, 160), makeRow(2, 1560), makeRow(3, 2960)]
  restoreIssueListPosition(root, position)
  assert.equal(content.scrollTop, 1860)
  assert.equal(root.rows[1].getBoundingClientRect().top, position.top)
})

test('last card falls back to preceding card; server-clamped page uses new first row', () => {
  const { root, content, makeRow } = fixture()
  const position = captureIssueListPosition(root, 3)
  root.rows = [makeRow(1, 100), makeRow(2, 1500)]
  restoreIssueListPosition(root, position)
  assert.equal(content.scrollTop, 1800)
  root.rows = [makeRow(9, 100)]
  restoreIssueListPosition(root, position)
  assert.equal(root.rows[0].getBoundingClientRect().top, position.top)
})

test('desktop preserves both horizontal table position and outer content viewport', () => {
  const { root, content, inner, makeRow } = fixture({ nested: true })
  const position = captureIssueListPosition(root, 2)
  root.rows = [makeRow(1, 100), makeRow(3, 1500)]
  content.scrollTop = 200; inner.scrollTop = 10; inner.scrollLeft = 0
  restoreIssueListPosition(root, position)
  assert.equal(content.scrollTop, 1800)
  assert.equal(inner.scrollTop, 700)
  assert.equal(inner.scrollLeft, 900)
  assert.equal(root.rows[1].getBoundingClientRect().top, position.top)
})

test('empty queues, hidden/unmounted views and absent snapshots safely do nothing', () => {
  const { root } = fixture()
  assert.equal(captureIssueListPosition(root, 99), null)
  assert.doesNotThrow(() => restoreIssueListPosition(root, null))
  const position = captureIssueListPosition(root, 2)
  root.rows = []
  assert.doesNotThrow(() => restoreIssueListPosition(root, position))
  root.isConnected = false
  assert.doesNotThrow(() => restoreIssueListPosition(root, position))
  assert.doesNotThrow(() => restoreIssueListPosition(null, position))
})

const source = readFileSync(new URL('../src/views/inspection/MyIssuesView.vue', import.meta.url), 'utf8')
test('post-review refresh retains list height throughout network wait and on errors; ordinary fetch still clears stale page', async () => {
  for (const preserveList of [true, false]) {
    for (const fail of [true, false]) {
      let finish
      const request = new Promise((resolve, reject) => { finish = () => fail ? reject(new Error('网络异常')) : resolve({ data: { success: true, items: [{ id: 3 }], total: 1, page: 2 } }) })
      const issues = { value: [{ id: 2 }] }, loading = { value: false }, listError = { value: '' }
      const page = { value: 2 }
      const context = {
        localStorage: { getItem: () => '17' }, listSequence: 0, listController: null, AbortController,
        isReviewQueue: { value: true }, isMobileReview: { value: true }, issues, loading, listError,
        page, pageSize: { value: 5 }, appliedFilters: { value: { keyword: '' } }, serverTotal: { value: 2 }, acceptingPage: false,
        reviewRequestParams: () => ({}), mobileReviewFilters: value => value, showActionToast: () => {},
        axios: { get: () => request, isCancel: () => false }, preserveList,
      }
      const promise = runInNewContext(`(() => { ${source.slice(source.indexOf('const fetchMyIssues ='), source.indexOf('const applyFilters ='))}; return fetchMyIssues({ preserveList }) })()`, context)
      assert.equal(issues.value.length, preserveList ? 1 : 0)
      assert.equal(loading.value, !preserveList)
      finish(); await promise
      assert.equal(loading.value, false)
      assert.equal(issues.value[0]?.id, fail ? preserveList ? 2 : undefined : 3)
      assert.equal(listError.value, fail ? '网络异常' : '')
      assert.equal(page.value, 2)
    }
  }
})

test('mobile review distinguishes issue ID, single-line standard excerpt and emphasis without changing desktop fields', () => {
  const mobile = source.slice(source.indexOf('<div class="mobile-issue-list">'), source.indexOf('<div class="table-scroll-wrap">'))
  assert.match(mobile, /问题ID：\$\{item.id\}/)
  assert.match(mobile, /v-if="!isReviewQueue" class="mobile-card-row"><span>检查表/)
  assert.match(mobile, /getStandardDetailPreview\(item.standard_detail_text, isReviewQueue \? 1 : 3\)/)
  assert.match(mobile, /查看详情/)
  assert.match(source, /\.is-review-card \.mobile-card-standard-preview\s*\{[^}]*white-space: nowrap;[^}]*font-family: inherit;/)
  assert.match(source, /\.is-review-card \.mobile-card-text\s*\{\s*font-weight: 700;/)
  assert.match(source, /await fetchMyIssues\(\{ preserveList: true \}\)\s+closeActionDrawer\(\)\s+await nextTick\(\)/)
})
