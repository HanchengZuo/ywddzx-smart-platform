import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { pushCapability, pushDeviceStatus } from '../src/utils/webPush.js'

const capable = {
  isSecureContext: true,
  navigator: { userAgent: 'Windows Chrome', serviceWorker: {} },
  PushManager: class {},
  Notification: { permission: 'default' },
  matchMedia: () => ({ matches: false }),
}
test('capability detection distinguishes HTTPS, installed iOS, unsupported browsers and real API capability', () => {
  assert.equal(pushCapability(capable).code, 'supported')
  assert.equal(pushCapability({ ...capable, isSecureContext: false }).code, 'insecure')
  assert.equal(pushCapability({ ...capable, PushManager: undefined }).code, 'unsupported')
  assert.equal(
    pushCapability({ ...capable, navigator: { ...capable.navigator, userAgent: 'iPhone Safari' } })
      .code,
    'ios_install_required',
  )
  assert.equal(
    pushCapability({
      ...capable,
      navigator: { ...capable.navigator, userAgent: 'iPhone Safari', standalone: true },
    }).code,
    'supported',
  )
  assert.equal(
    pushCapability({
      ...capable,
      navigator: { ...capable.navigator, userAgent: 'Macintosh', maxTouchPoints: 5 },
    }).code,
    'ios_install_required',
  )
  assert.equal(
    pushCapability({
      ...capable,
      navigator: { ...capable.navigator, userAgent: 'HUAWEI Android Chrome' },
    }).code,
    'supported',
  )
  assert.equal(pushDeviceStatus({ active: false, permission: 'denied' }), '浏览器已拒绝')
})

function workerFixture() {
  const handlers = {},
    shown = [],
    opened = []
  const self = {
    addEventListener: (type, fn) => {
      handlers[type] = fn
    },
    skipWaiting() {},
    location: { origin: 'https://example.com' },
    registration: {
      showNotification: async (title, options) => {
        shown.push({ title, options })
      },
    },
    clients: {
      claim: async () => {},
      matchAll: async () => [],
      openWindow: async (url) => {
        opened.push(url)
      },
    },
  }
  vm.runInNewContext(readFileSync(new URL('../public/push-sw.js', import.meta.url), 'utf8'), {
    self,
    URL,
  })
  return { handlers, shown, opened, self }
}
test('service worker displays a visible privacy-safe notification without a page or authenticated fetch', async () => {
  const { handlers, shown } = workerFixture()
  let pending
  handlers.push({
    data: {
      json: () => ({ body: 'secret problem details', url: 'https://evil.test/', tag: 'test' }),
    },
    waitUntil: (promise) => {
      pending = promise
    },
  })
  await pending
  assert.equal(shown.length, 1)
  assert.equal(shown[0].options.data.url, '/notifications')
  assert.equal(shown[0].options.tag, 'test')
  assert.ok(!JSON.stringify(shown).includes('secret'))
  handlers.push({
    data: {
      json: () => {
        throw Error('bad json')
      },
    },
    waitUntil: (promise) => {
      pending = promise
    },
  })
  await pending
  assert.equal(shown.length, 2)
})
test('notification clicks only open a same-origin authenticated page', async () => {
  const { handlers, opened } = workerFixture()
  let pending,
    closed = false
  handlers.notificationclick({
    notification: {
      close: () => {
        closed = true
      },
      data: { url: 'https://evil.test' },
    },
    waitUntil: (promise) => {
      pending = promise
    },
  })
  await pending
  assert.equal(closed, true)
  assert.deepEqual(opened, ['/notifications'])
})
test('permission request happens before any asynchronous registration and denied permission never subscribes', async () => {
  const source = readFileSync(new URL('../src/utils/webPush.js', import.meta.url), 'utf8')
    .replace("import axios from 'axios'", '')
    .replaceAll('export ', '')
  const calls = []
  const context = {
    axios: {},
    Uint8Array,
    Promise,
    Error,
    window: { ...capable },
    navigator: { ...capable.navigator },
    Notification: {
      requestPermission: () => {
        calls.push('permission')
        return Promise.resolve('denied')
      },
    },
    setTimeout,
  }
  vm.createContext(context)
  vm.runInContext(source + ';globalThis.enable=enableDevice', context)
  const result = context.enable('public-key')
  assert.deepEqual(calls, ['permission'])
  await assert.rejects(result, /尚未允许/)
})
