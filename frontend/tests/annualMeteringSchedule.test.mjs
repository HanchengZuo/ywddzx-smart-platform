import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
const source = file => readFileSync(new URL('../src/' + file, import.meta.url), 'utf8')

test('annual query omits month/quarter without changing the coverage map query contract', () => {
  const panel = source('components/InspectionSchedulePanel.vue')
  const context = vm.createContext({ coveragePeriodQuery: value => ({ checkedByMap: value.mode }) })
  vm.runInContext(panel.slice(panel.indexOf('function coverageQuery'), panel.indexOf('const draft =')), context)
  assert.deepEqual(JSON.parse(JSON.stringify(context.coverageQuery({ mode: 'annual', year: 2026, month: 10, quarter: 4 }))), { mode: 'annual', year: 2026 })
  assert.equal(context.coverageQuery({ mode: 'online' }).checkedByMap, 'online')
  assert.equal(context.coverageQuery({ mode: 'offline' }).checkedByMap, 'offline')
})

test('switching months preserves unsaved quotas and their original optimistic-lock revision', async () => {
  const script = source('components/MeteringAnnualPlan.vue')
  const context = vm.createContext({
    serial: 0, controller: undefined, AbortController, structuredClone,
    loading: { value: false }, error: { value: '' }, state: { value: {} },
    quotas: { value: { '10': { 松金: 2 } } }, original: { value: '{}' },
    baselineRevision: { value: 1 }, dirty: { value: true },
    year: { value: 2026 }, month: { value: 11 },
    axios: { get: async () => ({ data: { revision: 3, quotas: { '11': { 浦东: 2 } }, regions: [] } }) },
  })
  vm.runInContext(script.slice(script.indexOf('async function load(reset)'), script.indexOf('async function save()')), context)
  await context.load(false)
  assert.equal(context.state.value.revision, 3)
  assert.equal(context.baselineRevision.value, 1)
  assert.equal(context.quotas.value['10'].松金, 2)
  assert.equal(context.quotas.value['11'], undefined)
  await context.load(true)
  assert.equal(context.baselineRevision.value, 3)
  assert.equal(context.quotas.value['11'].浦东, 2)
})
