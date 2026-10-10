import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { toggleStandardId, isStandardSelected, buildRegistrationSelections, registrationIssueCount, restoreStandardIds } from '../src/utils/registerStandardSelection.js'

const a = { standard_id: '100', inspection_table_id: 1 }, b = { standard_id: '200', inspection_table_id: 2 }
test('cross-table selection toggles independently and submits one reference per standard', () => {
  const ids = toggleStandardId(toggleStandardId([], a), b)
  assert.deepEqual(ids, ['100', '200'])
  assert.ok(isStandardSelected(ids, a))
  assert.deepEqual(toggleStandardId(ids, a), ['200'])
  assert.deepEqual(buildRegistrationSelections([a, b]), [{ standard_id: '100', inspection_table_id: '1' }, { standard_id: '200', inspection_table_id: '2' }])
  assert.equal(registrationIssueCount([a, b]), 2)
})
test('internal references expand the preview count without duplicate external targets', () => {
  const internal = { internal_standard_id: 'N1', linked_externals: [{ external_standard_id: 100 }, { external_standard_id: 200 }] }
  assert.equal(registrationIssueCount([internal, a]), 2)
  assert.deepEqual(buildRegistrationSelections([internal]), [{ internal_standard_id: 'N1' }])
})
test('multi-choice drafts survive reload and old single-choice drafts remain usable', () => {
  assert.deepEqual(restoreStandardIds({ standardIds: ['100', '200', '100', 'missing'] }, [a, b]), ['100', '200'])
  assert.deepEqual(restoreStandardIds({ standardId: 100 }, [a, b]), ['100'])
  assert.deepEqual(restoreStandardIds({ standardIds: [] }, [a, b]), [])
  assert.throws(() => toggleStandardId(Array.from({ length: 100 }, (_, i) => String(i + 1)), b), /最多选择100/)
})
test('registration multi-select template and script compile', () => {
  const { descriptor } = parse(readFileSync(new URL('../src/views/inspection/RegisterView.vue', import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: 'register-multi-check' })
  const template = compileTemplate({ source: descriptor.template.content, filename: 'RegisterView.vue', id: 'register-multi-check', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
})
