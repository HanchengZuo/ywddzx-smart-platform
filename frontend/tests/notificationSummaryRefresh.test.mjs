import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { runInNewContext } from 'node:vm'

const app = readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8')
const section = (from, to) => app.slice(app.indexOf(`const ${from} =`), app.indexOf(`const ${to} =`))

test('cross-tab profile and expiry changes never trigger session verification or notification requests', () => {
  let checks = 0, syncs = 0, refreshes = 0
  const context = {
    syncAuthState: () => syncs++, isLoginPage: { value: false }, lastUserActivityAt: 0,
    resetNotificationCounts: () => {}, isUsableAuthToken: () => true, getStoredAuthToken: () => 'session',
    scheduleIdleLogout: () => {}, verifySessionSilently: () => checks++,
    isPasswordChangeModeActive: () => false, refreshNotificationSummary: () => refreshes++,
  }
  const handle = runInNewContext(section('handleAuthStorageChange', 'handlePasswordChangeRequired') + '\nhandleAuthStorageChange', context)
  for (const key of ['auth_expires_at', 'user_id', 'permissions', 'must_change_password', 'password_policy']) {
    handle({ key, oldValue: 'before', newValue: 'after' })
  }
  assert.equal(syncs, 5)
  assert.equal(checks, 0)
  assert.equal(refreshes, 0)
  handle({ key: 'auth_token', oldValue: 'before', newValue: 'session' })
  assert.equal(checks, 1)
  assert.equal(refreshes, 1)
})

test('forced notification refreshes are coalesced and one trailing request still updates badges', async () => {
  let now = 10000, requests = 0, applied = 0
  const timers = new Map()
  const context = {
    Date: { now: () => now }, route: { path: '/' }, isLoginPage: { value: false },
    isPasswordChangeModeActive: () => false, isUsableAuthToken: () => true, getStoredAuthToken: () => 'session',
    notificationSummaryStartedAt: 0, notificationSummaryFetchedAt: 0, notificationSummaryInFlight: null,
    notificationSummaryTrailingTimer: null, notificationSummaryPending: false,
    notificationForceMinIntervalMs: 3000, notificationCacheTtlMs: 15000,
    axios: { get: async () => { requests++; return { data: {} } } },
    applyNotificationSummary: () => applied++,
    window: {
      setTimeout: (callback, delay) => { const id = Symbol(); timers.set(id, { callback, delay }); return id },
      clearTimeout: id => timers.delete(id),
    },
  }
  const refresh = runInNewContext(section('clearNotificationTrailingRefresh', 'applyNotificationSummary') +
    section('refreshNotificationSummary', 'resetServerResourceState') + '\nrefreshNotificationSummary', context)
  await Promise.all(Array.from({ length: 40 }, () => refresh({ force: true })))
  assert.equal(requests, 1)
  assert.equal(timers.size, 1)
  const [id, { callback, delay }] = [...timers][0]
  assert.equal(delay, 3000)
  now += delay
  timers.delete(id)
  callback()
  await context.notificationSummaryInFlight
  assert.equal(requests, 2)
  assert.equal(applied, 2)
  assert.equal(timers.size, 0)
})
