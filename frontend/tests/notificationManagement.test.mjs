import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'

function setup(path, axios, events = []) {
  const { descriptor } = parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: 'push', genDefaultAs: 'component' })
  const template = compileTemplate({
    source: descriptor.template.content,
    id: 'push',
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(template.errors, [])
  let sequence = 0
  const environment = {
    ...vue,
    onMounted() {},
    onBeforeUnmount() {},
    axios,
    newRequestId: () => `request-${++sequence}`,
    pushDeviceStatus: () => '',
    NotificationCompose: {},
  }
  const imports = Object.keys(script.imports)
  const source = script.content
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*\n/gm, '')
    .replace(/^import ['"][^'"]+['"]\s*\n/gm, '')
  const component = new Function(...imports, source + '\nreturn component')(
    ...imports.map((key) => environment[key]),
  )
  return component.setup({}, { expose() {}, emit: (...args) => events.push(args) })
}
const composePath = '../src/components/NotificationCompose.vue'
const managementPath = '../src/views/management/NotificationManagementView.vue'

test('compose searches and pages recipients independently, retaining cross-page selections', async () => {
  const calls = []
  const s = setup(composePath, {
    get: async (url, { params }) => {
      calls.push({ url, params })
      return { data: { items: [{ id: 2, username: 'station' }], total: 60 } }
    },
  })
  s.keyword.value = ' 浦东 '
  await s.search()
  s.toggle({ id: 2 }, true)
  await s.changePage(1)
  assert.deepEqual(calls.at(-1).params, { keyword: '浦东', page: 2, recipients_only: '1' })
  assert.deepEqual(
    s.selected.value.map((user) => user.id),
    [2],
  )
  s.toggle({ id: 2 }, false)
  assert.equal(s.selected.value.length, 0)
})

test('compose preserves idempotency on uncertain send, disables changes while sending and emits success once', async () => {
  const calls = [],
    events = []
  let rejectFirst = true,
    release
  const s = setup(
    composePath,
    {
      post: async (url, data) => {
        calls.push({ url, data })
        if (rejectFirst) {
          rejectFirst = false
          throw Error('test-only network failure')
        }
        await new Promise((resolve) => {
          release = resolve
        })
        return { data: { message: '已入队' } }
      },
    },
    events,
  )
  s.title.value = '提醒'
  s.body.value = '请及时办理'
  s.toggle({ id: 2 }, true)
  await vue.nextTick()
  await s.send()
  assert.match(s.error.value, /相同请求不会重复/)
  const pending = s.send()
  s.toggle({ id: 3 }, true)
  s.close()
  await s.send()
  assert.equal(calls.length, 2)
  assert.equal(s.selected.value.length, 1)
  assert.equal(events.length, 0)
  assert.equal(calls[0].data.request_id, calls[1].data.request_id)
  release()
  await pending
  assert.deepEqual(events, [['sent', '已入队']])
})

test('management filters complete server-side send history by business source without changing user filters', async () => {
  const calls = []
  const s = setup(managementPath, {
    get: async (url, { params }) => {
      calls.push(params)
      return {
        data: {
          items: [],
          records: [],
          summary: {},
          sources: [{ key: 'appeal_area', name: '待片区处理申诉' }],
          total: 0,
          configured: true,
        },
      }
    },
  })
  s.keyword.value = '浦东'
  await s.filter()
  await s.filterLogs('appeal_area')
  assert.deepEqual(calls.at(-1), {
    keyword: '浦东',
    status: '',
    page: 1,
    log_page: 1,
    log_source: 'appeal_area',
  })
  assert.equal(s.sourceLabel({ source: 'appeal_area', kind: 'business' }), '待片区处理申诉')
  assert.equal(s.sourceLabel({ kind: 'manual' }), '手动通知')
  const source = readFileSync(new URL(managementPath, import.meta.url), 'utf8')
  assert.ok(!source.includes('type="checkbox"'))
})
