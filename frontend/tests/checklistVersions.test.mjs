import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { matchesMyIssue } from '../src/utils/myIssueFilters.js'

test('version filtering narrows within the chosen logical checklist without hiding old snapshots', () => {
  const old = { inspection_table_name: '现场检查明细表（现场）', version_number: 1 }
  const current = { ...old, version_number: 2 }
  assert.equal(matchesMyIssue(old, { inspectionTableName: ['现场检查明细表（现场）'] }), true)
  assert.equal(matchesMyIssue(old, { inspectionTableName: ['现场检查明细表（现场） · v1'] }), true)
  assert.equal(matchesMyIssue(current, { inspectionTableName: ['现场检查明细表（现场） · v1'] }), false)
  assert.equal(matchesMyIssue(old, { inspectionTableName: '现场检查明细表（现场） · v2' }), false)
  assert.equal(matchesMyIssue(old, { inspectionTableName: [] }), true)
})

for (const path of ['components/ChecklistVersionSelect.vue', 'views/management/ChecklistDataManagementView.vue',
  'views/inspection/ChecklistOriginalsView.vue', 'views/inspection/RecordsView.vue', 'views/inspection/MyIssuesView.vue']) {
  test(`${path} compiles against actual component bindings`, () => {
    const { descriptor, errors } = parse(readFileSync(new URL('../src/' + path, import.meta.url), 'utf8'), { filename: path })
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: path })
    const result = compileTemplate({ source: descriptor.template.content, filename: path, id: path, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(result.errors, [])
  })
}
