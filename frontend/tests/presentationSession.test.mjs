import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse, compileTemplate, compileScript } from '@vue/compiler-sfc'
import {
  activePresentation,
  setPresentationMode,
  presentationKindForRoute,
  needsPresentationRenewal,
} from '../src/utils/presentationSession.js'

test('only the matching cockpit or map route can suspend idle logout', () => {
  assert.equal(presentationKindForRoute('/operations/overview', 'cockpit'), 'cockpit')
  assert.equal(presentationKindForRoute('/inspection/station-map', 'map'), 'map')
  for (const path of ['/inspection/issues', '/login', '/operations/overview']) {
    assert.equal(presentationKindForRoute(path, 'map'), '')
  }
  assert.equal(presentationKindForRoute('/operations/overview', ''), '')
})
test('closing an old view cannot cancel a different active presentation', () => {
  setPresentationMode('cockpit', true)
  setPresentationMode('map', true)
  setPresentationMode('cockpit', false)
  assert.equal(activePresentation.value, 'map')
  setPresentationMode('unsupported', true)
  assert.equal(activePresentation.value, 'map')
  setPresentationMode('map', false)
  assert.equal(activePresentation.value, '')
})
test('renewal starts thirty minutes before expiry, never resurrects an expired token', () => {
  assert.equal(needsPresentationRenewal('cockpit', 1801), false)
  assert.equal(needsPresentationRenewal('cockpit', 1800), true)
  assert.equal(needsPresentationRenewal('map', 1), true)
  for (const seconds of [0, -1, NaN]) assert.equal(needsPresentationRenewal('map', seconds), false)
  assert.equal(needsPresentationRenewal('', 600), false)
})

const app = readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8')
test('two hours without input cannot log out a presentation; ordinary pages retain their limit', () => {
  const declarations = ['isIdleLogoutDue', 'scheduleIdleLogout', 'markUserActivity']
    .map((name) => app.match(new RegExp(`const ${name} = [\\s\\S]*?(?=\\nconst )`))[0])
    .join('\n')
  const context = {
    isLoginPage: { value: false },
    presentationKind: { value: 'cockpit' },
    isUsableAuthToken: () => true,
    getStoredAuthToken: () => 'token',
    lastUserActivityAt: 0,
    lastIdleActivityMarkedAt: 0,
    idleLogoutMs: 7200000,
    idleActivityThrottleMs: 1000,
    Date: { now: () => 10800000 },
    stops: 0,
    logouts: 0,
    timers: [],
  }
  context.stopIdleLogoutTimer = () => context.stops++
  context.handleIdleLogout = () => context.logouts++
  context.window = { setTimeout: (_, delay) => context.timers.push(delay) }
  vm.createContext(context)
  vm.runInContext(
    declarations +
      '\nglobalThis.actions = { isIdleLogoutDue, scheduleIdleLogout, markUserActivity }',
    context,
  )
  assert.equal(context.actions.isIdleLogoutDue(), false)
  context.actions.scheduleIdleLogout()
  context.actions.markUserActivity()
  assert.equal(context.logouts, 0)
  assert.equal(context.timers.length, 0)
  context.presentationKind.value = ''
  assert.equal(context.actions.isIdleLogoutDue(), true)
  context.actions.markUserActivity()
  assert.equal(context.logouts, 1)
  context.lastUserActivityAt = context.Date.now()
  context.actions.scheduleIdleLogout()
  assert.equal(context.timers[0], 7200000)
})
test('exit restarts the idle clock while true server expiry remains visible', () => {
  assert.match(
    app,
    /watch\(presentationKind,[\s\S]*?lastUserActivityAt = Date.now\(\)[\s\S]*?scheduleIdleLogout\(\)/,
  )
  assert.match(app, /mode === 'warning'.*!presentationKind/)
  assert.match(app, /mode === 'expired' && !isLoginPage/)
  assert.match(
    app,
    /needsPresentationRenewal\(presentationKind.value, getStoredAuthSecondsRemaining\(\)\)/,
  )
  assert.match(
    app,
    /verifyAuthSession\(\{ preserveOnTransientError: Boolean\(presentationKind.value\) \}\)/,
  )
  const authSource = readFileSync(new URL('../src/utils/authSession.js', import.meta.url), 'utf8')
  assert.match(
    authSource,
    /if \(preserveOnTransientError && error\?\.response\?\.status !== 401\) throw error/,
  )
})
test('late renewal cannot restore a logged-out or switched account; network failure is not swallowed', async () => {
  const source = readFileSync(new URL('../src/utils/authSession.js', import.meta.url), 'utf8')
  const declaration = source
    .match(/export const renewPresentationSession = [\s\S]*?(?=\nexport const)/)[0]
    .replace('export ', '')
  let token = 'original'
  let resolve
  const context = {
    getStoredAuthToken: () => token,
    axios: {
      post: () =>
        new Promise((done) => {
          resolve = done
        }),
    },
  }
  vm.createContext(context)
  vm.runInContext(declaration + '\nglobalThis.renew = renewPresentationSession', context)
  const pending = context.renew('map')
  token = ''
  resolve({ data: { token: 'renewed', expires_in: 14400 } })
  assert.equal((await pending).superseded, true)
  context.axios.post = () => Promise.reject(new Error('offline'))
  await assert.rejects(context.renew('map'), /offline/)
})
for (const component of [
  'App.vue',
  'views/operations/OperationsDashboardView.vue',
  'views/inspection/StationMapView.vue',
]) {
  test(`${component} compiles with presentation lifecycle hooks`, () => {
    const source = readFileSync(new URL('../src/' + component, import.meta.url), 'utf8')
    const { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: component })
    assert.deepEqual(
      compileTemplate({
        source: descriptor.template.content,
        filename: component,
        id: component,
        compilerOptions: { bindingMetadata: script.bindings },
      }).errors,
      [],
    )
    if (component !== 'App.vue')
      assert.match(
        source,
        /onBeforeUnmount\(\(\) => \{[\s\S]*?setPresentationMode\('[^']+', false\)/,
      )
  })
}
