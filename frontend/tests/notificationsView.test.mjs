import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'

function setup(overrides = {}) {
  const { descriptor } = parse(
    readFileSync(new URL('../src/views/NotificationsView.vue', import.meta.url), 'utf8'),
  )
  const script = compileScript(descriptor, { id: 'notifications', genDefaultAs: 'component' })
  const compiled = compileTemplate({
    source: descriptor.template.content,
    id: 'notifications',
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(compiled.errors, [])
  let mount, dispose, poll
  const timers = [],
    events = [],
    calls = []
  const environment = {
    ...vue,
    AbortController,
    window: {
      Notification: { permission: 'granted' },
      dispatchEvent: (event) => events.push(event.type),
    },
    document: { hidden: false },
    Event,
    onMounted: (callback) => {
      mount = callback
    },
    onBeforeUnmount: (callback) => {
      dispose = callback
    },
    setInterval: (callback) => {
      poll = callback
      return 1
    },
    clearInterval() {},
    setTimeout: (callback) => {
      timers.push(callback)
      return timers.length
    },
    clearTimeout() {},
    pushCapability: () => ({ code: 'supported' }),
    isPushPrepared: () => true,
    pushDeviceStatus: () => '已订阅',
    currentDeviceKey: () => 'fixture-key',
    newRequestId: () => 'fixture-request',
    enableDevice: async () => ({ id: 'current', active: true }),
    disableDevice: async () => {},
    syncDevice: async () => ({ id: 'current', active: true }),
    axios: {
      get: async (url, options) => {
        calls.push({ url, options })
        return {
          data: url.endsWith('/devices')
            ? {
                items: [
                  { id: 'current', active: true },
                  { id: 'current', active: true },
                  { id: 'archived', active: false },
                  { id: 'other-computer', active: true },
                ],
              }
            : {
                items: [],
                total: 0,
                unread: 0,
                enabled: true,
                configured: true,
                public_key: 'fixture',
              },
        }
      },
    },
    ...overrides,
  }
  const names = [
    ...new Set([
      ...Object.keys(script.imports),
      'AbortController',
      'window',
      'document',
      'Event',
      'setTimeout',
      'clearTimeout',
      'setInterval',
      'clearInterval',
    ]),
  ]
  const source = script.content
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*\n/gm, '')
    .replace(/^import ['"][^'"]+['"]\s*\n/gm, '')
  const component = new Function(...names, source + '\nreturn component')(
    ...names.map((key) => environment[key]),
  )
  const state = component.setup({}, { expose() {} })
  return {
    state,
    calls,
    timers,
    events,
    mount: () => mount(),
    dispose: () => dispose(),
    poll: () => poll(),
  }
}
const flush = async () => {
  for (let i = 0; i < 15; i++) await Promise.resolve()
}

test('refresh has independent bounded progress and completion feedback, then returns to idle', async () => {
  let release
  const s = setup({
    syncDevice: () =>
      new Promise((resolve) => {
        release = resolve
      }),
  })
  const pending = s.state.refresh()
  await flush()
  assert.equal(s.state.refreshing.value, true)
  assert.equal(s.state.busy.value, false)
  await s.state.refresh()
  assert.equal(s.calls.length, 2)
  assert.equal(s.calls[0].options.timeout, 10000)
  release({ id: 'current', active: true })
  await pending
  assert.equal(s.state.refreshing.value, false)
  assert.equal(s.state.refreshDone.value, true)
  assert.ok(s.state.lastUpdated.value)
  s.timers.at(-1)()
  assert.equal(s.state.refreshDone.value, false)
})

test('background reads do not disable actions and active subscriptions deduplicate by identity, not browser label', async () => {
  const s = setup()
  s.mount()
  await flush()
  assert.equal(s.state.refreshing.value, false)
  s.poll()
  await flush()
  assert.equal(s.state.busy.value, false)
  assert.deepEqual(
    s.state.devices.value.map((device) => device.id),
    ['current', 'other-computer'],
  )
  s.state.openTodayArrangement()
  assert.deepEqual(s.events, ['inspection-tasks-open'])
  s.dispose()
})

test('refresh failure releases controls, preserves loaded data and permits retry', async () => {
  let fail = true
  const s = setup({
    syncDevice: async () => {
      if (fail) throw Error('设备同步超时')
      return { id: 'current' }
    },
  })
  await s.state.refresh()
  assert.equal(s.state.refreshing.value, false)
  assert.match(s.state.error.value, /超时/)
  assert.equal(s.state.devices.value.length, 2)
  fail = false
  await s.state.refresh()
  assert.equal(s.state.error.value, '')
  assert.equal(s.state.refreshDone.value, true)
})

test('a late read cannot overwrite a newer page or change a disposed view', async () => {
  const pending = []
  const s = setup({ axios: { get: () => new Promise((resolve) => pending.push(resolve)) } })
  const old = s.state.read()
  const latest = s.state.read()
  pending[2]({ data: { items: [{ id: 'new' }], enabled: true } })
  pending[3]({ data: { items: [] } })
  await latest
  pending[0]({ data: { items: [{ id: 'old' }] } })
  pending[1]({ data: { items: [] } })
  await old
  assert.equal(s.state.items.value[0].id, 'new')
  const disposedRead = s.state.read()
  s.dispose()
  pending[4]({ data: { items: [{ id: 'disposed' }] } })
  pending[5]({ data: { items: [] } })
  await disposedRead
  assert.equal(s.state.items.value[0].id, 'new')
})
