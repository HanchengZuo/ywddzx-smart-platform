import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { PAGE_VISIBILITY_PAGE_BY_KEY, PAGE_VISIBILITY_PAGE_BY_PATH } from '../src/config/pageVisibilityCatalog.js'
import { previousScoreMonth, scoreMonthLabel, scoreLedgerRows } from '../src/utils/stationScoreMonth.js'
const read = p => readFileSync(new URL('../src/' + p, import.meta.url), 'utf8')
const ref = value => ({ value })

test('previous month follows Shanghai calendar including new year and UTC month boundaries', () => {
  assert.equal(previousScoreMonth(new Date('2026-10-24T00:00:00+08:00')), '2026-09')
  assert.equal(previousScoreMonth(new Date('2026-01-01T00:00:00+08:00')), '2025-12')
  assert.equal(previousScoreMonth(new Date('2026-09-30T17:00:00Z')), '2026-09')
  assert.equal(scoreMonthLabel('2026-09'), '2026年9月')
  assert.equal(scoreMonthLabel('2026-13'), '请选择评分月份')
})

test('ledger filters keep raw scores and support ID, normative text, issue text and adjustment state', () => {
  const rows = [{ standard_id: 9001, all_fields: [{ value: '接地检查' }], issues: [{ description: '螺栓锈蚀' }], is_deducted: true },
    { standard_id: 9002, all_fields: [], issues: [], has_manual_adjustment: true }]
  for (const keyword of ['9001', '接地', '锈蚀']) assert.deepEqual(scoreLedgerRows(rows, keyword), [rows[0]])
  assert.deepEqual(scoreLedgerRows(rows, '', 'adjusted'), [rows[1]])
  assert.equal(rows.length, 2)
})

test('saved global visibility beats an older in-flight read and a transient error does not re-show hidden pages', async () => {
  let resolve, fail = false
  const events = []
  const context = vm.createContext({
    PAGE_VISIBILITY_PAGE_BY_KEY, PAGE_VISIBILITY_PAGE_BY_PATH, PAGE_VISIBILITY_PAGES: [],
    getStoredAuthToken: () => 'mock', isUsableAuthToken: () => true, Date,
    PAGE_VISIBILITY_UPDATED_EVENT: 'page-visibility-updated',
    axios: { get: () => fail ? Promise.reject(new Error('offline')) : new Promise(r => { resolve = r }) },
    window: { dispatchEvent: event => events.push(event.detail) },
    CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init.detail } }, console: { warn() {} },
  })
  const code = read('utils/pageVisibility.js').replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*/gm, '').replaceAll('export ', '')
  vm.runInContext(code + ';globalThis.api={fetchPageVisibility,publishPageVisibility,getPageVisibilitySnapshot}', context)
  const pending = context.api.fetchPageVisibility({ force: true })
  context.api.publishPageVisibility({ '/inspection/issues': false })
  resolve({ data: { success: true, settings: { '/inspection/issues': true } } })
  await pending
  assert.equal(context.api.getPageVisibilitySnapshot()['/inspection/issues'], false)
  fail = true
  await context.api.fetchPageVisibility({ force: true })
  assert.equal(context.api.getPageVisibilitySnapshot()['/inspection/issues'], false)
  assert.equal(events.length, 1)
})

test('switch saves only changed keys, updates menus after success, and restores state on failure', async () => {
  const source = read('views/management/PageVisibilityManagementView.vue')
  const calls = [], settings = { '/inspection/issues': true, '/inspection/records': false }
  let failure = false
  const context = vm.createContext({ canManage: true, loaded: ref(true), saving: ref(false), message: ref(''), settings,
    axios: { put: async (path, body) => { calls.push(body); if (failure) throw { response: { data: { error: '保存失败' } } }; return { data: { success: true, settings: { '/inspection/issues': false, '/inspection/records': false } } } } },
    applySettings: raw => Object.assign(settings, raw), publishPageVisibility: raw => calls.push(raw), showMessage: text => calls.push(text),
  })
  vm.runInContext(source.slice(source.indexOf('const saveSettings ='), source.indexOf('onMounted(loadSettings)')) + ';globalThis.save=saveSettings', context)
  await context.save([{ page_key: '/inspection/issues', is_visible: false }])
  assert.equal(calls[0].pages.length, 1)
  assert.equal(settings['/inspection/records'], false)
  assert.equal(calls.length, 3)
  failure = true
  await context.save([{ page_key: '/inspection/issues', is_visible: true }])
  assert.equal(settings['/inspection/issues'], false)
  assert.equal(context.saving.value, false)
})

test('initial configuration read errors preserve the retry action instead of disappearing', () => {
  const source = read('views/management/PageVisibilityManagementView.vue')
  const timers = []
  const context = vm.createContext({ loaded: ref(false), message: ref(''), messageType: ref(''),
    window: { setTimeout: callback => timers.push(callback) },
  })
  vm.runInContext(source.slice(source.indexOf('const showMessage ='), source.indexOf('const applySettings =')) + ';globalThis.show=showMessage', context)
  context.show('读取失败', 'error')
  assert.equal(context.message.value, '读取失败')
  assert.equal(timers.length, 0)
  context.loaded.value = true
  context.show('已保存')
  assert.equal(timers.length, 1)
})

test('page-management access is independently delegable without user-management access', () => {
  const source = read('router/index.js')
  const code = source.slice(source.indexOf('const hasPermission ='), source.indexOf('const resolveFallbackPath ='))
  const context = vm.createContext({})
  vm.runInContext(code + ';globalThis.check=canAccessPath', context)
  for (const role of ['area_account', 'supervisor', 'quality_safety']) {
    assert.equal(context.check('/management/page-visibility', role, { manage_page_visibility: true }), true)
    assert.equal(context.check('/management/page-visibility', role, { manage_users: true }), false)
  }
})

for (const file of ['views/management/PageVisibilityManagementView.vue', 'views/assessment/StationScoreView.vue']) {
  test(file + ' compiles with real bindings and responsive styles', () => {
    const { descriptor, errors } = parse(read(file))
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: 'v110' })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: 'v110', compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
    for (const style of descriptor.styles) assert.deepEqual(compileStyle({ source: style.content, id: 'v110', scoped: style.scoped }).errors, [])
  })
}

test('monthly score view snapshots export/adjustment month, limits requests to selected table and cancels stale loads', () => {
  const source = read('views/assessment/StationScoreView.vue')
  assert.match(source, /type="month"/)
  assert.doesNotMatch(source, /DateRangePicker|filters\.dateFrom|filters\.dateTo/)
  assert.match(source, /inspection_table_id: filters.inspectionTableId/)
  assert.match(source, /ticket !== scoreSerial/)
  assert.match(source, /month: exportDialog.month/)
  assert.match(source, /month: adjustDialog.month/)
  assert.match(source, /showModal\(\)/)
  const visibility = read('views/management/PageVisibilityManagementView.vue')
  assert.doesNotMatch(visibility, /刷新配置|保存显示设置|已临时切换|仅 root/)
  assert.match(visibility, /role="switch"/)
})
