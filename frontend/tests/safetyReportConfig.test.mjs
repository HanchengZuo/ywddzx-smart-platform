import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import {
  manualClassificationChanges,
  safetyFocusSelection,
  safetyFocusCategory,
  safetyFocusName,
  safetyAnalysisReady,
  safetySubgroups,
  safetyIssueSearch,
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

test('monthly theme defaults to highest frequency and excludes empty catalog entries', () => {
  const options = [
    { name: '空主题', count: 0 },
    { name: '污染防治', count: 3 },
    { name: '设备设施', count: 4 },
  ]
  assert.equal(safetyFocusName('', options), '设备设施')
  assert.equal(safetyFocusName('污染防治', options), '污染防治')
  assert.equal(safetyFocusName('空主题', options), '设备设施')
  assert.equal(safetyFocusName('', []), '')
})

test('analysis is ready only with complete unique coverage, never from manual overrides alone', () => {
  const category = {
    issues: [{ issue_id: 1 }, { issue_id: 2 }],
    analysis: { groups: [{ issue_ids: [1, 2] }] },
  }
  assert.equal(safetyAnalysisReady(category), true)
  category.analysis.groups[0].issue_ids = [1, 1]
  assert.equal(safetyAnalysisReady(category), false)
  category.analysis.groups[0].issue_ids = [1, 99]
  assert.equal(safetyAnalysisReady(category), false)
  category.analysis.groups[0].issue_ids = [1, 2]
  category.analysis.complete = false
  assert.equal(safetyAnalysisReady(category), false)
  assert.equal(safetyAnalysisReady({ issues: [], analysis: { groups: [] } }), false)
})

test('subgroup navigation is isolated to selected theme and supports manual empty categories', () => {
  const category = { issues: [{ issue_id: 1 }, { issue_id: 2 }] }
  const manual = {
    assignments: { 1: '接地', 2: '接地', 3: '其他主题' },
    summaries: { 接地: '接地缺失', 新类别: '' },
  }
  assert.deepEqual(safetySubgroups(category, manual), [
    { name: '接地', count: 2 },
    { name: '新类别', count: 0 },
  ])
})

test('candidate search keeps mode filtering and searches ID, station and description locally', () => {
  const rows = [
    { issue_id: 8534, station_name: '龚路', description: '接地缺失', mode: 'onsite' },
    { issue_id: 9001, station_name: '乐都', description: '警示标志', mode: 'video' },
  ]
  for (const query of ['8534', '龚路', '接地'])
    assert.deepEqual(safetyIssueSearch(rows, query), [rows[0]])
  assert.deepEqual(
    safetyIssueSearch(
      rows.filter((i) => i.mode === 'video'),
      '接地',
    ),
    [],
  )
  assert.deepEqual(safetyIssueSearch(rows, ' '), rows)
})
