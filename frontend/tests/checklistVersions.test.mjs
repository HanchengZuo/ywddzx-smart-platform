import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { matchesMyIssue } from '../src/utils/myIssueFilters.js'
import { groupOriginalVersions, selectedOriginalVersions } from '../src/utils/checklistOriginalVersions.js'

test('original directory can select inactive historical editions without changing the active version', () => {
  const rows = [
    { logical_table_id: 11, version_id: 2, version_number: 1, is_active: false },
    { logical_table_id: 11, version_id: 14, version_number: 2, is_active: true },
    { logical_table_id: 12, version_id: 3, version_number: 1, is_active: true }
  ]
  const groups = groupOriginalVersions(rows)
  assert.deepEqual(selectedOriginalVersions(groups, {}).map(item => item.version_id), [14, 3])
  assert.deepEqual(selectedOriginalVersions(groups, { 11: '2' }).map(item => item.version_id), [2, 3])
  assert.equal(rows[0].is_active, false)
  assert.equal(groups.get(11).length, 2)
  assert.equal(rows[0].version_id, 2)
})

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
