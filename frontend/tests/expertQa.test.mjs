import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { operationsPages } from '../src/config/operationsCatalog.js'
import { PAGE_VISIBILITY_PAGES } from '../src/config/pageVisibilityCatalog.js'

const source = readFileSync(
  new URL('../src/views/operations/ExpertQaView.vue', import.meta.url),
  'utf8',
)
test('expert has an independent permission without changing global evidence access', () => {
  const expert = operationsPages.find((page) => page.key === 'expert')
  assert.notEqual(
    expert.permission,
    operationsPages.find((page) => page.key === 'overview').permission,
  )
  assert.equal(expert.permission, 'view_expert_qa')
  assert.equal(expert.title, '专家问答')
  assert.ok(PAGE_VISIBILITY_PAGES.some((page) => page.path === expert.path))
  const router = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  assert.match(router, /page.key === 'expert'/)
  assert.match(router, /ExpertQaView.vue/)
})
test('expert template and script compile and do not render model HTML', () => {
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'expert-qa' })
  assert.deepEqual(
    compileTemplate({
      source: descriptor.template.content,
      id: 'expert-qa',
      filename: 'ExpertQaView.vue',
      compilerOptions: { bindingMetadata: script.bindings },
    }).errors,
    [],
  )
  assert.ok(!source.includes('v-html'))
  assert.match(source, /paragraph.text/)
  assert.match(source, /source.text/)
})
test('questions are explicitly sent, background poll cleans up and mobile layout exists', () => {
  assert.match(source, /@submit.prevent="submit"/)
  assert.match(source, /@keydown.ctrl.enter.prevent="submit"/)
  assert.match(source, /parent_id: parentId.value/)
  assert.match(source, /disposed = true/)
  assert.match(source, /clearTimeout\(timer\)/)
  assert.match(source, /controller\?\.abort\(\)/)
  assert.match(source, /max-width: 760px/)
  assert.ok(!source.includes('watch(question'))
})
test('citations open their exact source, and global-data scope is explicit', () => {
  assert.match(source, /focusSource\(item.id, ref\)/)
  assert.match(source, /source.open = true/)
  assert.match(source, /panel.open = true/)
  assert.match(source, /全局业务资料/)
  assert.match(source, /未调用AI/)
})
