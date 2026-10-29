import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { reportPerspective, visibleReportTypes, reportMonthLabel, departmentReportYears, departmentMonthOptions } from '../src/utils/reportAccess.js'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const types = ['quality_measurement', 'safety_quality', 'finance', 'non_oil', 'equipment_facilities', 'on_site_service'].map(key => ({ key }))
test('department readers have only their own report types; center grants retain the complete workbench', () => {
  const pairs = {
    quality_safety: ['quality_measurement', 'safety_quality'], development_plan: ['equipment_facilities'],
    oil_gas: ['on_site_service'], non_oil: ['non_oil'], finance: ['finance']
  }
  for (const [role, keys] of Object.entries(pairs)) {
    const permissions = { view_department_inspection_reports: true, generate_inspection_reports: true }
    assert.equal(reportPerspective(role, permissions), 'department')
    assert.deepEqual(visibleReportTypes(types, role, permissions).map(x => x.key), keys)
    assert.deepEqual(visibleReportTypes(types, role, { ...permissions, view_inspection_reports: true }), types)
    assert.deepEqual(visibleReportTypes(types, role, {}), [])
  }
  for (const role of ['supervisor', 'supervisor_manager', 'station_manager', 'area_account', 'unknown']) {
    assert.equal(reportPerspective(role, { view_department_inspection_reports: true }), null)
  }
  assert.deepEqual(visibleReportTypes(types, 'root'), types)
})

test('month labels contain no day boundaries; only actual historical months are selectable', () => {
  const records = [{ month: '2025-12' }, { month: '2026-09' }, { month: '2026-09' }]
  assert.equal(reportMonthLabel('2026-09'), '2026年9月')
  assert.equal(reportMonthLabel('2026-09-01'), '尚无已生成报告')
  assert.equal(reportMonthLabel(''), '尚无已生成报告')
  assert.deepEqual(departmentReportYears(records, 2026), [2026, 2025])
  assert.deepEqual(departmentReportYears([], 2026), [2026])
  const options = departmentMonthOptions(records, 2026)
  assert.equal(options.length, 12)
  assert.deepEqual(options.filter(item => item.available).map(item => item.month), ['2026-09'])
  assert.deepEqual(departmentMonthOptions(records, 2025).filter(item => item.available).map(item => item.month), ['2025-12'])
  assert.equal(departmentMonthOptions([], 2026).some(item => item.available), false)
})

test('department view hides mutation/history UI and returns before loading mutable panels', () => {
  const source = readFileSync(new URL('../src/views/inspection/ReportGeneratorView.vue', import.meta.url), 'utf8')
  assert.match(source, /<nav v-if="!isDepartmentView" class="studio-workflow"/)
  assert.match(source, /v-if="!isDepartmentView && \(isQualityMeasurementReport \|\| isSafetyQualityReport \|\| hasIssueLibrary\)/)
  const earlyReturn = source.slice(source.indexOf('if (isDepartmentView.value) {'), source.indexOf('applyWorkspaceSettings(response.data'))
  assert.match(earlyReturn, /report.value.snapshot\?\.date_from/)
  assert.match(earlyReturn, /return/)
  assert.doesNotMatch(earlyReturn, /loadSourceOptions|loadSelectionSettings|loadNonOil|axios/)
  const exportAction = source.slice(source.indexOf('const exportCurrentReport ='), source.indexOf('const closeExportDialog'))
  assert.match(exportAction, /reportDisplayMode.value === 'ppt'\) return openExportDialog\(\)/)
  assert.match(exportAction, /downloadReportHtml\(document.querySelector\('\.report-document-html'\)/)
  assert.doesNotMatch(exportAction, /axios.post|startGeneration|startPptExport/)
})

test('month picker compiles and disables missing months; choosing a month only reads a saved report', () => {
  const filename = new URL('../src/components/DepartmentReportMonth.vue', import.meta.url)
  const source = readFileSync(filename, 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'department-month' })
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: String(filename), id: 'department-month', compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  assert.match(source, /:disabled="loading \|\| !item.available"/)
  assert.doesNotMatch(source, /axios|fetch\(|type="date"|date_from|date_to/)
  const view = readFileSync(new URL('../src/views/inspection/ReportGeneratorView.vue', import.meta.url), 'utf8')
  const handler = view.slice(view.indexOf('const selectDepartmentMonth ='), view.indexOf('const loadReportTypes ='))
  assert.match(handler, /departmentMonths.value.some/)
  assert.match(handler, /selectedSnapshotId.value = 0/)
  assert.match(handler, /await loadReportState\(\)/)
  assert.doesNotMatch(handler, /startGeneration|saveReport|axios.post|axios.put/)
  assert.match(view, /ref\(isDepartmentView.value \? 'html' : readReportViewMode\(\)\)/)
})
