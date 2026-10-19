import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

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

for (const name of ['views/inspection/InspectionScheduleView.vue', 'components/InspectionSchedulePanel.vue', 'views/management/StationDataManagementView.vue', 'views/inspection/SchedulingMapView.vue']) {
  test(`real scheduling and station template compiles: ${name}`, () => {
    const source = readFileSync(new URL('../src/' + name, import.meta.url), 'utf8')
    const { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: 'station-plan' })
    const result = compileTemplate({ source: descriptor.template.content, filename: name, id: 'station-plan', compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(result.errors, [])
  })
}
