import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { routingKey, groupAiScenes } from '../src/utils/aiModelSettings.js'

test('routing comparison ignores order but distinguishes explicit model selection from inheritance', () => {
  const a = { default_model: 'a', overrides: { one: 'b', two: 'c' }, revision: 1 }
  assert.equal(routingKey(a), routingKey({ default_model: 'a', overrides: { two: 'c', one: 'b' }, revision: 4 }))
  assert.notEqual(routingKey(a), routingKey({ ...a, overrides: { ...a.overrides, three: 'a' } }))
  assert.notEqual(routingKey(a), routingKey({ ...a, overrides: {} }))
  assert.notEqual(routingKey(a), routingKey({ ...a, default_model: 'c' }))
})

test('scene grouping and searching retain business order without changing caller evidence', () => {
  const scenes = [{ id: 'a', group: '非油报告', name: '分类', description: '其他问题分类' },
    { id: 'b', group: '计量报告', name: '选题', description: '重点问题' },
    { id: 'c', group: '非油报告', name: '分析', description: '工作建议' }]
  assert.deepEqual(groupAiScenes(scenes).map((group) => group.items.map((scene) => scene.id)), [['a', 'c'], ['b']])
  assert.deepEqual(groupAiScenes(scenes, '其他').map((group) => group.items.map((scene) => scene.id)), [['a']])
  assert.deepEqual(groupAiScenes(scenes, '不存在'), [])
  assert.deepEqual(scenes.map((scene) => scene.id), ['a', 'b', 'c'])
})

test('management template and script compile with real bindings, and menu order matches catalog', () => {
  const path = new URL('../src/views/management/AiModelManagementView.vue', import.meta.url)
  const { descriptor, errors } = parse(readFileSync(path, 'utf8'))
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'model-settings-test' })
  const template = compileTemplate({ source: descriptor.template.content, filename: path.pathname,
    id: 'model-settings-test', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  for (const file of ['App.vue', 'config/pageVisibilityCatalog.js']) {
    const text = readFileSync(new URL('../src/' + file, import.meta.url), 'utf8')
    assert.ok(text.indexOf('/management/ai-models') < text.indexOf('/management/ai-usage'))
  }
  assert.ok(script.content.includes('revision: settings.value.revision'))
  assert.ok(script.content.includes('onBeforeRouteLeave'))
  assert.ok(!descriptor.template.content.includes('type="password"'))
})
