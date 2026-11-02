import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'
import { reportConfigurationDiffers } from '../src/utils/reportConfiguration.js'

const source = readFileSync(new URL('../src/components/SafetyPhrasesPanel.vue', import.meta.url), 'utf8')
const fixture = () => ({ rows: [
  { key: 'onsite:key', mode: 'onsite', source: '原检查内容', standard_ids: ['13001'], phrase: '既有短语', status: 'default' },
  { key: 'video:key', mode: 'video', source: '原评分项', standard_ids: ['14001'], phrase: '', status: 'missing' },
], meta: { revision: 4, updated_by_name: '甲', updated_at: '2026-11-02' }, catalog_signature: 'catalog', can_generate: true })

function harness(axios, props = {}) {
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'phrases', genDefaultAs: 'component' })
  const code = compiled.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*\n/gm, '')
  const cleanup = [], events = [], scope = vue.effectScope()
  const document = { body: { style: { overflow: '' } }, activeElement: { focus() {} } }
  const env = { ...vue, axios: { isCancel: () => false, ...axios }, onBeforeUnmount: fn => cleanup.push(fn), document }
  const bindings = Object.keys(compiled.imports).concat('document')
  const component = new Function(...bindings, `${code}\nreturn component`)(...bindings.map(key => env[key]))
  const state = scope.run(() => component.setup({ canGenerate: true, busy: false, ...props }, { expose() {}, emit: (...args) => events.push(args) }))
  return { state, events, document, dispose() { cleanup.forEach(fn => fn()); scope.stop() } }
}

test('phrase panel compiles and presents mode-first source/phrase editing', () => {
  const { descriptor } = parse(source)
  const compiled = compileTemplate({ source: descriptor.template.content, filename: 'SafetyPhrasesPanel.vue', id: 'phrases' })
  assert.deepEqual(compiled.errors, [])
  assert.match(source, /role="dialog"/)
  assert.match(source, /检查内容/)
  assert.match(source, /评分项/)
})

test('manual edit saves only explicit changes with optimistic revision, never POSTs AI', async () => {
  const calls = []
  const h = harness({ get: async () => ({ data: fixture() }),
    put: async (url, body) => { calls.push(body); return { data: fixture() } },
    post: async () => { throw new Error('manual edits must not call AI') } })
  await h.state.open()
  h.state.draft.value['onsite:key'] = '新短语'
  await h.state.save()
  assert.deepEqual(calls, [{ catalog_signature: 'catalog', revision: 4, changes: { 'onsite:key': '新短语' } }])
  assert.deepEqual(h.events, [['saved']])
  h.state.close()
  assert.equal(h.document.body.style.overflow, '')
  h.dispose()
})

test('AI actions respect generation permission and do not discard unsaved edits', async () => {
  let calls = 0
  const h = harness({ get: async () => ({ data: fixture() }), post: async () => { calls++; return { data: fixture() } } }, { canGenerate: false })
  await h.state.open()
  await h.state.generate()
  assert.equal(calls, 0)
  h.dispose()
  const editable = harness({ get: async () => ({ data: fixture() }), post: async () => { calls++; return { data: fixture() } } })
  await editable.state.open()
  editable.state.draft.value['video:key'] = '人工短语'
  await editable.state.generate()
  assert.equal(calls, 0)
  editable.dispose()
})

test('late read after closing does not resurrect modal data; failed save keeps edits', async () => {
  let resolve
  const h = harness({ get: () => new Promise(done => { resolve = done }) })
  const opening = h.state.open()
  await vue.nextTick()
  h.state.close()
  resolve({ data: fixture() })
  await opening
  assert.equal(h.state.data.value, null)
  h.dispose()
  const editable = harness({ get: async () => ({ data: fixture() }), put: async () => { throw { response: { data: { error: '配置冲突' } } } } })
  await editable.state.open()
  editable.state.draft.value['video:key'] = '人工短语'
  await editable.state.save()
  assert.equal(editable.state.error.value, '配置冲突')
  assert.equal(editable.state.draft.value['video:key'], '人工短语')
  await editable.state.reload()
  assert.equal(editable.state.changeCount.value, 0)
  editable.dispose()
})

test('saved phrase signature participates in report drift detection without breaking legacy defaults', () => {
  const report = { month: '2026-10', summary: { date_from: '2026-10-01', date_to: '2026-10-31' }, safety_settings: {} }
  const current = { type: 'safety_quality', date_from: '2026-10-01', date_to: '2026-10-31', safety_settings: { analysis_phrases: {}, phrases_signature: '' } }
  assert.equal(reportConfigurationDiffers(report, current), false)
  current.safety_settings.phrases_signature = 'new'
  assert.equal(reportConfigurationDiffers(report, current), true)
})
