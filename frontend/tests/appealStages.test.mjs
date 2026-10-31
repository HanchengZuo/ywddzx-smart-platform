import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'

function setup(get, post) {
  const source = readFileSync(
    new URL('../src/views/inspection/AppealsView.vue', import.meta.url),
    'utf8',
  )
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'appeals', genDefaultAs: 'component' })
  const template = compileTemplate({
    source: descriptor.template.content,
    id: 'appeals',
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(template.errors, [])
  const environment = {
    ...vue,
    onMounted() {},
    onBeforeUnmount() {},
    useRoute: () => ({ query: {} }),
    useRouter: () => ({}),
    axios: { get, post },
  }
  const bindings = Object.keys(script.imports)
  const component = new Function(
    ...bindings,
    script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*\n/gm, '') + '\nreturn component',
  )(...bindings.map((key) => environment[key]))
  return component.setup({}, { expose() {} })
}
const response = (extra = {}) => ({
  data: {
    items: [],
    total: 0,
    counts: { active: 3, area_pending: 2, quality_pending: 1, unread_ended: 4 },
    filter_options: { regions: ['浦东'], tables: [{ id: 1, name: '视频检查表' }] },
    ...extra,
  },
})

test('appeal tabs query each stage on the server, reset pagination and retain applied filters', async () => {
  const calls = []
  const s = setup(async (url, { params }) => {
    calls.push({ url, params })
    return response()
  })
  assert.deepEqual(
    s.tabs.map((tab) => tab.label),
    ['待片区处理申诉', '待质安部处理申诉', '已结束记录'],
  )
  await s.load()
  assert.equal(calls.at(-1).params.stage, 'area_pending')
  s.keyword.value = '接地'
  await s.applyFilters()
  s.page.value = 4
  s.keyword.value = '还未提交的草稿'
  await s.setStage('quality_pending')
  assert.deepEqual(calls.at(-1).params, {
    page: 1,
    archive: 0,
    stage: 'quality_pending',
    keyword: '接地',
  })
  assert.equal(s.archive.value, false)
  await s.setStage('ended')
  assert.equal(s.archive.value, true)
  assert.equal(calls.at(-1).params.archive, 1)
  assert.equal(calls.at(-1).params.stage, undefined)
  await s.setStage('area_pending')
  assert.equal(s.archive.value, false)
  assert.equal(s.counts.value.active, 3)
})

test('filters apply only on submit; pagination and stage changes do not apply drafts', async () => {
  const calls = []
  const s = setup(async (url, { params }) => {
    calls.push(params)
    return response({ items: [{ id: 1 }], total: 50 })
  })
  await s.load()
  assert.equal(calls[0].include_filters, '1')
  s.keyword.value = '  接地  '
  Object.assign(s.filters.value, {
    region: '浦东',
    table_id: '1',
    date_from: '2026-10-01',
    date_to: '2026-10-31',
  })
  assert.equal(calls.length, 1)
  assert.ok(s.filterFields.value.some((field) => field.changed))
  await s.applyFilters()
  assert.deepEqual(calls.at(-1), {
    page: 1,
    archive: 0,
    stage: 'area_pending',
    keyword: '接地',
    region: '浦东',
    table_id: '1',
    date_from: '2026-10-01',
    date_to: '2026-10-31',
  })
  assert.equal(s.filterFields.value.find((field) => field.key === 'table_id').value, '视频检查表')
  s.filters.value.region = '松金'
  s.page.value = 2
  await s.load()
  assert.equal(calls.at(-1).region, '浦东')
  assert.equal(calls.at(-1).page, 2)
  await s.setStage('quality_pending')
  assert.equal(calls.at(-1).region, '浦东')
  assert.equal(calls.at(-1).page, 1)
  await s.resetFilters()
  assert.deepEqual(calls.at(-1), { page: 1, archive: 0, stage: 'quality_pending', keyword: '' })
})

test('invalid date ranges do not request and ended filters are ignored by active stages', async () => {
  const calls = []
  const s = setup(async (url, { params }) => {
    calls.push(params)
    return response()
  })
  Object.assign(s.filters.value, { date_from: '2026-10-31', date_to: '2026-10-01' })
  await s.applyFilters()
  assert.equal(calls.length, 0)
  assert.match(s.filterError.value, /不能晚于/)
  await s.resetFilters()
  await s.setStage('ended')
  Object.assign(s.filters.value, { outcome: 'rejected', unread: true })
  await s.applyFilters()
  assert.equal(calls.at(-1).outcome, 'rejected')
  assert.equal(calls.at(-1).unread, '1')
  await s.setStage('area_pending')
  assert.equal(calls.at(-1).outcome, undefined)
  assert.equal(calls.at(-1).unread, undefined)
})

test('latest query wins; superseded requests are aborted and cannot replace results', async () => {
  const requests = []
  const s = setup((url, options) => new Promise((resolve) => requests.push({ options, resolve })))
  const first = s.load()
  const second = s.setStage('quality_pending')
  assert.equal(requests[0].options.signal.aborted, true)
  requests[1].resolve(response({ items: [{ id: 2 }], total: 1 }))
  await second
  requests[0].resolve(response({ items: [{ id: 1 }], total: 1 }))
  await first
  assert.equal(s.items.value[0].id, 2)
  assert.equal(s.loading.value, false)
})

test('read result remains expanded, preserves notification version and updates shared counts', async () => {
  const oldWindow = globalThis.window
  globalThis.window = { dispatchEvent() {} }
  try {
    const calls = []
    const s = setup(
      async () => response(),
      async (url, body) => {
        calls.push({ url, body })
        return { data: { counts: { unread_ended: 0 } } }
      },
    )
    const item = { id: 7, unread: true, notification_version: '2026-10-31T08:00:00+00:00' }
    await s.viewResult(item)
    assert.equal(item.unread, false)
    assert.ok(s.expanded.value.has(7))
    assert.deepEqual(calls, [
      { url: '/api/issue-appeals/7/read', body: { version: item.notification_version } },
    ])
    assert.equal(s.counts.value.unread_ended, 0)
    await s.viewResult(item)
    assert.equal(calls.length, 1)
    assert.equal(s.expanded.value.has(7), false)
  } finally {
    globalThis.window = oldWindow
  }
})

test('audit submits the original stage and mandatory reason once, then refreshes the same list', async () => {
  const oldWindow = globalThis.window
  globalThis.window = { dispatchEvent() {} }
  try {
    const calls = []
    let finish
    const s = setup(
      async () => response(),
      (url, body) => {
        calls.push({ url, body })
        return new Promise((resolve) => {
          finish = resolve
        })
      },
    )
    s.openDecision({ id: 8, status: 'quality_pending', station_name: '测试站' })
    await s.decide()
    assert.equal(calls.length, 0)
    s.decision.value = 'reject'
    s.reason.value = '   '
    await s.decide()
    assert.equal(calls.length, 0)
    s.reason.value = ' 核查后问题属实 '
    const pending = s.decide()
    await s.decide()
    assert.equal(calls.length, 1)
    assert.deepEqual(calls[0], {
      url: '/api/issue-appeals/8/decision',
      body: { decision: 'reject', reason: '核查后问题属实', stage: 'quality_pending' },
    })
    finish({ data: { message: '审核已提交' } })
    await pending
    assert.equal(s.selected.value, null)
    assert.equal(s.saving.value, false)
    assert.equal(s.notice.value, '审核已提交')
  } finally {
    globalThis.window = oldWindow
  }
})

test('a removed last-page record returns to a valid page instead of leaving an empty list', async () => {
  const calls = []
  const s = setup(async (url, { params }) => {
    calls.push(params.page)
    return response({ items: params.page === 1 ? [{ id: 1 }] : [], total: 1 })
  })
  s.page.value = 2
  await s.load()
  assert.deepEqual(calls, [2, 1])
  assert.equal(s.page.value, 1)
  assert.equal(s.items.value[0].id, 1)
})
