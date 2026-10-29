import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import {
  manualClassificationChanges,
  safetyFocusSelection,
  safetyFocusCategory,
} from '../src/utils/safetyReportConfig.js'
import { reportConfigurationDiffers } from '../src/utils/reportConfiguration.js'

test('opening and saving AI evidence does not manufacture manual overrides', () => {
  const baseline = {
    'onsite:设备设施': { assignments: { 1: '接地' }, summaries: { 接地: '接地缺失' } },
  }
  assert.deepEqual(manualClassificationChanges(baseline, baseline, {}), {})
  const draft = structuredClone(baseline)
  draft['onsite:设备设施'].assignments[1] = '维护'
  draft['onsite:设备设施'].summaries.维护 = '连接待维护'
  assert.deepEqual(manualClassificationChanges(draft, baseline, {}), {
    'onsite:设备设施': { assignments: { 1: '维护' }, summaries: { 维护: '连接待维护' } },
  })
  assert.equal(baseline['onsite:设备设施'].assignments[1], '接地')
})
test('explicit saved choices persist; removing a manual category returns it to AI', () => {
  const saved = { 'video:卸油作业': { assignments: { 2: '手动' }, summaries: {} } }
  assert.deepEqual(manualClassificationChanges(saved, saved, saved), saved)
  const draft = structuredClone(saved)
  delete draft['video:卸油作业'].assignments[2]
  assert.deepEqual(manualClassificationChanges(draft, saved, saved), {})
})
test('safety configuration warning tracks saved inputs and clears after regeneration', () => {
  const dates = { date_from: '2026-09-01', date_to: '2026-09-30' }
  const settings = {
    station_ids: null,
    typical_issue_ids: {},
    focus_category: '',
    classifications: {},
  }
  const report = { month: '2026-09', snapshot: dates, safety_settings: settings }
  const current = { ...dates, type: 'safety_quality', safety_settings: structuredClone(settings) }
  assert.equal(reportConfigurationDiffers(report, current), false)
  current.safety_settings.focus_category = '设备设施'
  assert.equal(reportConfigurationDiffers(report, current), true)
  report.safety_settings = structuredClone(current.safety_settings)
  assert.equal(reportConfigurationDiffers(report, current), false)
})
test('focus selection and issue membership use topics, not inspection-content phrases', () => {
  const topics = [
    { name: '设备设施', count: 4 },
    { name: '污染防治', count: 3 },
  ]
  assert.equal(safetyFocusSelection('油罐操作井', topics), '')
  assert.equal(safetyFocusSelection('设备设施', topics), '设备设施')
  const result = safetyFocusCategory('设备设施', [
    { issue_id: 1, mode: 'onsite', topic: '设备设施', category_name: '油罐操作井' },
    { issue_id: 2, mode: 'onsite', topic: '设备设施', category_name: '配发电' },
    { issue_id: 3, mode: 'onsite', topic: '污染防治', category_name: '设备设施' },
    { issue_id: 4, mode: 'video', topic: '设备设施', category_name: '设备设施' },
  ])
  assert.equal(result.key, 'onsite:topic:设备设施')
  assert.deepEqual(
    result.issues.map((issue) => issue.issue_id),
    [1, 2],
  )
})
test('safety configuration compiles with actual Vue bindings and no automatic AI call', () => {
  const source = readFileSync(
    new URL('../src/components/SafetyReportConfig.vue', import.meta.url),
    'utf8',
  )
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'safety-config' })
  const output = compileTemplate({
    source: descriptor.template.content,
    id: 'safety-config',
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(output.errors, [])
  assert.match(source, /:disabled="!canGenerate \|\| analyzing/)
  assert.match(source, /\/safety-analysis/)
  assert.match(source, /signal: controller.signal/)
})
