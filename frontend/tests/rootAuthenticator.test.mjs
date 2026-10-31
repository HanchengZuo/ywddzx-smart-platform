import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'

const source = readFileSync(new URL('../src/components/RootAuthenticatorPanel.vue', import.meta.url), 'utf8')
function harness(axios) {
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'root-authenticator', genDefaultAs: 'component' })
  assert.deepEqual(compileTemplate({source: descriptor.template.content, id: 'root-authenticator', compilerOptions: {bindingMetadata: script.bindings}}).errors, [])
  const cleanup = [], events = []
  const environment = {...vue, axios, onMounted() {}, onBeforeUnmount(fn) {cleanup.push(fn)},
    passkeyClientAvailable: () => true, runPasskeyAuthentication: async () => ({id: 'device-proof'}),
    friendlyPasskeyError: (error, fallback) => fallback}
  const bindings = Object.keys(script.imports)
  const component = new Function(...bindings, script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*\n/gm, '')+'\nreturn component')(...bindings.map(key => environment[key]))
  const props = vue.reactive({externalBusy: false})
  const state = component.setup(props, {expose() {}, emit: (...args) => events.push(args)})
  return {state, events, props, close() {cleanup.forEach(fn => fn())}}
}

test('Authenticator setup requires device proof, holds secrets only while open and emits session revocation', async () => {
  const calls = []
  const h = harness({
    async get(url) {calls.push(url);return {data: {enabled: false}}},
    async post(url, body) {
      calls.push([url, body])
      return {data: url.endsWith('/options') ? {flow_id: 'flow', public_key: {}} : url.endsWith('/verify') ? {management_token: 'proof'} : {setup_id: 'nonce',secret: 'TEST-ONLY',qr_code: 'data:image/png;base64,TEST'}}
    },
    async put(url, body) {calls.push([url,body]);return {data: {session_invalidated: true,message: '请重新登录'}}},
  })
  const s = h.state
  await s.load()
  assert.equal(s.enabled.value, false)
  h.props.externalBusy = true
  await s.beginSetup()
  assert.equal(calls.length, 1)
  h.props.externalBusy = false
  await s.beginSetup()
  assert.equal(calls[1][0], '/api/auth/passkey/reauth/options')
  assert.equal(calls[2][0], '/api/auth/passkey/reauth/verify')
  assert.deepEqual(calls[3], ['/api/auth/root-authenticator', {management_token: 'proof'}])
  assert.equal(s.setup.value.secret, 'TEST-ONLY')
  s.code.value = '012345'
  await s.confirmSetup()
  assert.deepEqual(calls[4], ['/api/auth/root-authenticator', {management_token: 'proof',setup_id: 'nonce',code: '012345'}])
  assert.equal(s.setup.value, null)
  assert.equal(s.code.value, '')
  assert.ok(h.events.some(([event]) => event === 'session-invalidated'))
  await s.beginSetup()
  h.close()
  assert.equal(s.setup.value, null)
  assert.equal(s.code.value, '')
  assert.doesNotMatch(source, /localStorage|sessionStorage/)
})

test('root-only binding controls stay outside the unchanged login page and cannot claim password-only access', () => {
  const manager = readFileSync(new URL('../src/components/PasskeyManagerModal.vue', import.meta.url), 'utf8')
  assert.match(manager, /v-if="rootAuthenticatorAvailable"/)
  assert.match(manager, /response\.data\.root_authenticator_available/)
  assert.match(manager, /普通密码直登关闭/)
})
