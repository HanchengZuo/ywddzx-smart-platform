import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { stationPlanEnrollmentBlocked, stationPlanEnrollmentMessage } from '../src/utils/stationPlanEligibility.js'

test('on-site and video eligibility are independent; old responses default to included', () => {
  assert.equal(stationPlanEnrollmentBlocked({}, 'offline'), false)
  assert.equal(stationPlanEnrollmentBlocked({}, 'online'), false)
  const station = { include_offline_plan: false, include_online_plan: true }
  assert.equal(stationPlanEnrollmentBlocked(station, 'offline'), true)
  assert.equal(stationPlanEnrollmentBlocked(station, 'online'), false)
  assert.match(stationPlanEnrollmentMessage(station, 'offline'), /现场/)
  assert.equal(stationPlanEnrollmentMessage(station, 'online'), '')
  assert.equal(stationPlanEnrollmentBlocked({ include_online_plan: false }, 'online'), true)
})

test('historical plan inclusions are preserved with an explicit explanation', () => {
  const station = { include_offline_plan: false, originallyIncluded: true }
  assert.equal(stationPlanEnrollmentBlocked(station, 'offline'), false)
  assert.match(stationPlanEnrollmentMessage(station, 'offline'), /保留本计划原有任务/)
  assert.equal(stationPlanEnrollmentBlocked({ ...station, originallyIncluded: false }, 'offline'), true)
})

test('actual station form defaults to true and editing false values never resets them', () => {
  const source = readFileSync(new URL('../src/views/management/StationDataManagementView.vue', import.meta.url), 'utf8')
  const empty = source.split('const createEmptyForm = ')[1].split('\n\nconst stationExportFieldGroups')[0]
  const createEmptyForm = new Function(`return (${empty})`)()
  assert.equal(createEmptyForm().include_offline_plan, true)
  assert.equal(createEmptyForm().include_online_plan, true)
  const expression = source.split('const normalizeStationForForm = ')[1].split('\n\nconst startEdit')[0]
  const normalize = new Function('normalizeAssetType', `return (${expression})`)(value => value)
  assert.equal(normalize({ include_offline_plan: false }).include_offline_plan, false)
  assert.equal(normalize({ include_online_plan: false }).include_online_plan, false)
  assert.equal(normalize({}).include_offline_plan, true)
  assert.match(source, /v-model="form.include_offline_plan"/)
  assert.match(source, /v-model="form.include_online_plan"/)
})

for (const name of ['views/inspection/PlanView.vue', 'views/management/StationDataManagementView.vue', 'views/inspection/SchedulingMapView.vue']) {
  test(`real scheduling and station template compiles: ${name}`, () => {
    const source = readFileSync(new URL('../src/' + name, import.meta.url), 'utf8')
    const { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: 'station-plan' })
    const result = compileTemplate({ source: descriptor.template.content, filename: name, id: 'station-plan', compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(result.errors, [])
  })
}
