import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildFilterSummary } from '../src/utils/filterSummary.js'

for (const view of ['IssuesView', 'RecordsView']) {
  const source = readFileSync(new URL(`../src/views/inspection/${view}.vue`, import.meta.url), 'utf8')
  const definitionSource = source.split('const filterSummaryFields = computed(() => buildFilterSummary(')[1].split('].filter')[0]
  const definitions = [...definitionSource.matchAll(/\['([^']+)', '([^']+)'\]/g)].map((match) => [match[1], match[2]])

  test(`${view}: today's shortcut shows both date and current inspector`, () => {
    const filters = { dateFrom: '2026-09-05', dateTo: '2026-09-05', inspector: ['测试检查人'] }
    const selected = buildFilterSummary(definitions, filters).filter((field) => field.value)
    assert.equal(new Set(definitions.map(([key]) => key)).size, definitions.length)
    assert.deepEqual(selected.map((field) => field.key), ['dateRange', 'inspector'])
    assert.equal(selected[1].value, '测试检查人')
    assert.equal(selected.some((field) => field.changed), false)
  })

  test(`${view}: each multi-select is represented independently and clearing stays pending`, () => {
    for (const key of ['station', 'inspectionTableName', 'inspector', ...(view === 'IssuesView' ? ['region', 'standardTags'] : [])]) {
      const selected = buildFilterSummary(definitions, { [key]: ['测试值'] }).filter((field) => field.value)
      assert.deepEqual(selected.map((field) => field.key), [key])
      const cleared = buildFilterSummary(definitions, { [key]: [] }, { [key]: ['测试值'] }).filter((field) => field.changed)
      assert.deepEqual(cleared.map((field) => field.key), [key])
      assert.equal(cleared[0].state, 'pending')
      assert.equal(cleared[0].applied, '测试值')
    }
  })
}
