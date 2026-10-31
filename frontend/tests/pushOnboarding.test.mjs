import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'

function setup(options = {}) {
  const { descriptor } = parse(
    readFileSync(new URL('../src/components/PushNotificationBridge.vue', import.meta.url), 'utf8'),
  )
  const script = compileScript(descriptor, { id: 'onboarding', genDefaultAs: 'component' })
  const template = compileTemplate({
    source: descriptor.template.content,
    id: 'onboarding',
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(template.errors, [])
  const local =
    options.local ||
    new Map([
      ['user_id', '1'],
      ['auth_token', 'test-login-one'],
    ])
  const session = options.session || new Map(),
    calls = [],
    timers = [],
    listeners = new Map()
  let mount, dispose
  const native = {
    open: false,
    showModal() {
      this.open = true
      calls.push(['show'])
    },
    close() {
      this.open = false
    },
  }
  const environment = {
    ...vue,
    AbortController,
    useId: () => 'test',
    useRouter: () => ({ push: (route) => calls.push(['navigate', route]) }),
    onMounted: (callback) => {
      mount = callback
    },
    onBeforeUnmount: (callback) => {
      dispose = callback
    },
    window: { Notification: { permission: options.permission || 'default' } },
    document: {
      hidden: false,
      querySelector: () => null,
      addEventListener: (name, callback) => listeners.set(name, callback),
      removeEventListener: (name) => listeners.delete(name),
    },
    localStorage: { getItem: (key) => local.get(key) },
    sessionStorage: {
      getItem: (key) => session.get(key),
      setItem: (key, value) => session.set(key, value),
    },
    setTimeout: (callback) => {
      timers.push(callback)
      return timers.length
    },
    clearTimeout() {},
    pushCapability: () => ({ code: options.capability || 'supported' }),
    isPushPrepared: () => options.ready !== false,
    syncDevice: options.syncDevice || (async () => ({ active: !!options.active })),
    enableDevice:
      options.enableDevice ||
      (async () => {
        calls.push(['enable'])
        return { active: true }
      }),
    axios: {
      get: async (url, config) => {
        calls.push(['get', url, config])
        return {
          data: {
            enabled: options.enabled !== false,
            configured: options.configured !== false,
            public_key: 'public-test-key',
          },
        }
      },
      put: async (...args) => {
        calls.push(['put', ...args])
      },
      ...options.axios,
    },
  }
  const names = [
    ...new Set([
      ...Object.keys(script.imports),
      'AbortController',
      'window',
      'document',
      'localStorage',
      'sessionStorage',
      'setTimeout',
      'clearTimeout',
    ]),
  ]
  const source = script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*\n/gm, '')
  const component = new Function(...names, source + '\nreturn component')(
    ...names.map((key) => environment[key]),
  )
  const state = component.setup({ userId: '1' }, { expose() {} })
  state.dialog.value = native
  return {
    state,
    native,
    environment,
    calls,
    timers,
    local,
    session,
    listeners,
    mount: () => mount(),
    dispose: () => dispose(),
  }
}
const flush = async () => {
  for (let i = 0; i < 20; i++) await Promise.resolve()
}

test('login automatically presents direct enrollment, without requesting native permission before a click', async () => {
  const s = setup()
  s.mount()
  await flush()
  assert.equal(s.native.open, true)
  assert.equal(s.state.mode.value, 'enable')
  assert.equal(
    s.calls.some((call) => ['enable', 'navigate', 'put'].includes(call[0])),
    false,
  )
  s.dispose()
  assert.equal(s.native.open, false)
  assert.equal(s.listeners.size, 0)
})

test('immediate enable runs in the same gesture, persists only after subscription, and does not navigate', async () => {
  let gesture = false,
    resolve
  const seen = []
  const s = setup({
    enableDevice: (key, context) => {
      seen.push([key, gesture, context.isCurrent()])
      return new Promise((done) => {
        resolve = done
      })
    },
  })
  await s.state.inspect()
  gesture = true
  const pending = s.state.enable()
  gesture = false
  assert.deepEqual(seen, [['public-test-key', true, true]])
  assert.equal(
    s.calls.some((call) => call[0] === 'put'),
    false,
  )
  await s.state.enable()
  assert.equal(seen.length, 1)
  resolve({ active: true })
  await pending
  assert.equal(s.state.mode.value, 'success')
  assert.equal(s.calls.filter((call) => call[0] === 'put').length, 1)
  assert.equal(
    s.calls.some((call) => call[0] === 'navigate'),
    false,
  )
  s.timers.at(-1)()
  assert.equal(s.state.show.value, false)
})

test('subscribed, paused, denied, unsupported and unconfigured environments never request or show an enable dialog', async () => {
  for (const options of [
    { active: true, permission: 'granted' },
    { enabled: false },
    { permission: 'denied' },
    { capability: 'unsupported' },
    { capability: 'insecure' },
    { configured: false },
    { ready: false },
  ]) {
    const s = setup(options)
    await s.state.inspect()
    assert.equal(s.state.show.value, false, JSON.stringify(options))
    assert.equal(
      s.calls.some((call) => call[0] === 'enable'),
      false,
    )
  }
})

test('an allowed browser with a missing subscription can repair in place; iOS outside home screen receives steps only', async () => {
  const repair = setup({ permission: 'granted' })
  await repair.state.inspect()
  assert.equal(repair.state.show.value, true)
  const ios = setup({ capability: 'ios_install_required', ready: false })
  await ios.state.inspect()
  assert.equal(ios.state.mode.value, 'install')
  await ios.state.enable()
  assert.equal(
    ios.calls.some((call) => call[0] === 'enable'),
    false,
  )
})

test('deferring suppresses only the same login, stores no token and never disables account notifications', async () => {
  const s = setup()
  await s.state.inspect()
  s.state.dismiss()
  assert.equal(s.session.size, 1)
  assert.ok(![...s.session.values()].includes('test-login-one'))
  const same = setup({ local: s.local, session: s.session })
  await same.state.inspect()
  assert.equal(same.state.show.value, false)
  s.local.set('auth_token', 'test-login-two')
  const next = setup({ local: s.local, session: s.session })
  await next.state.inspect()
  assert.equal(next.state.show.value, true)
  assert.equal(
    s.calls.some((call) => call[0] === 'put'),
    false,
  )
})

test('failed native authorization retains a usable retry and notification-center fallback', async () => {
  let attempts = 0
  const s = setup({
    enableDevice: async () => {
      attempts++
      throw Error('浏览器未出现授权窗口')
    },
  })
  await s.state.inspect()
  await s.state.enable()
  await s.state.enable()
  assert.equal(attempts, 2)
  assert.equal(s.state.busy.value, false)
  assert.match(s.state.error.value, /授权窗口/)
  assert.equal(s.state.show.value, true)
  s.state.openCenter()
  assert.deepEqual(s.calls.at(-1), ['navigate', '/notifications'])
})

test('dismissed/unmounted/switched-account authorization cannot change the next account preference', async () => {
  for (const change of ['dismiss', 'dispose', 'switch']) {
    let resolve
    const s = setup({
      enableDevice: () =>
        new Promise((done) => {
          resolve = done
        }),
    })
    await s.state.inspect()
    const pending = s.state.enable()
    if (change === 'dismiss') s.state.dismiss()
    else if (change === 'dispose') s.dispose()
    else s.local.set('user_id', '2')
    resolve({ active: true })
    await pending
    assert.equal(
      s.calls.some((call) => call[0] === 'put'),
      false,
    )
  }
})

test('failed metadata checks cannot falsely prompt an already-authorized device and business dialogs take precedence', async () => {
  const unknown = setup({
    permission: 'granted',
    syncDevice: async () => {
      throw Error('test-only timeout')
    },
  })
  await unknown.state.inspect()
  assert.equal(unknown.state.show.value, false)
  const s = setup()
  s.environment.document.querySelector = () => ({ open: true })
  await s.state.inspect()
  assert.equal(s.native.open, false)
  s.environment.document.querySelector = () => null
  await s.state.present()
  assert.equal(s.native.open, true)
})
