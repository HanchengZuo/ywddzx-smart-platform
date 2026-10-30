import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'

test('appeal tabs query each stage on the server, reset pagination and retain search and ended records', async () => {
  const source = readFileSync(new URL('../src/views/inspection/AppealsView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'appeals', genDefaultAs: 'component' })
  const template = compileTemplate({source: descriptor.template.content, id: 'appeals', compilerOptions: {bindingMetadata: script.bindings}})
  assert.deepEqual(template.errors, [])
  const calls = []
  const environment = {...vue, onMounted() {}, onBeforeUnmount() {}, useRoute: () => ({query: {}}), useRouter: () => ({}),
    axios: {async get(url, {params}) {calls.push({url, params});return {data: {items: [], total: 0, counts: {active: 3, area_pending: 2, quality_pending: 1, unread_ended: 4}}}}}}
  const bindings = Object.keys(script.imports)
  const component = new Function(...bindings, script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*\n/gm, '')+'\nreturn component')(...bindings.map(key => environment[key]))
  const s = component.setup({}, {expose() {}})
  assert.deepEqual(s.tabs.map(tab => tab.label), ['待片区处理申诉','待质安部处理申诉','已结束记录'])
  await s.load()
  assert.equal(calls.at(-1).params.stage, 'area_pending')
  s.page.value = 4;s.keyword.value = '接地'
  await s.setStage('quality_pending')
  assert.deepEqual(calls.at(-1).params, {page: 1, archive: 0, stage: 'quality_pending', keyword: '接地'})
  assert.equal(s.archive.value, false)
  await s.setStage('ended')
  assert.equal(s.archive.value, true)
  assert.equal(calls.at(-1).params.archive, 1)
  assert.equal(calls.at(-1).params.stage, undefined)
  await s.setStage('area_pending')
  assert.equal(s.archive.value, false)
  assert.equal(s.counts.value.active, 3)
})
