import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { buildReportHtmlSections, equipmentPhraseDistribution, reportReadingMetrics } from '../src/utils/reportHtmlContent.js'
import { distributionRows } from '../src/utils/reportDistributions.js'

test('distribution colors always exist and preserve counts, actual percentages and zeros', () => {
  const rows = distributionRows([{ name: '现场资金管理', count: 51, percentage: 82.3 }, { name: '卡类资金管理', count: 7, percentage: 11.3 }, { name: '设备设施管理', count: 4, percentage: 6.5 }, { name: '零值', count: 0, percentage: 0 }])
  assert.equal(rows[0].percentage, 82.3)
  assert.equal(rows[3].percentage, 0)
  assert.equal(new Set(rows.map(row => row.color)).size, 4)
  assert.ok(rows.every(row => /^#[0-9a-f]{6}$/.test(row.color)))
  assert.deepEqual(distributionRows([{ name: '甲', count: 1 }, { name: '乙', count: 3 }]).map(row => row.percentage), [25, 75])
  assert.deepEqual(distributionRows([]), [])
})

test('equipment HTML projects current saved topic evidence, causes and every inspected station, without empty legacy chapters', () => {
  const first = { issue_id: 1, station_id: 10, station_name: '乐都', management_unit: '松金管理片区', description: '接地锈蚀', phrase: '接地螺栓', external_standard_id: 9000, issue_photo: 'one.jpg' }
  const second = { ...first, issue_id: 2, station_id: 11, station_name: '金朝', external_standard_id: '9001', issue_photo: '' }
  const special = { ...first, issue_id: 3, phrase: '灯具损坏', external_standard_id: 9999, description: '灯罩破损' }
  const report = { summary: { total_issue_count: 3, station_count: 3 }, region_rows: [{ unit_name: '松金片区', station_count: 3, issue_count: 3, average_issue_count: 1 }], station_ranking: [{ station_id: 10, station_name: '乐都', management_unit: '松金管理片区', issue_count: 2 }, { station_id: 11, station_name: '金朝', management_unit: '松金管理片区', issue_count: 1 }, { station_id: 12, station_name: '三新', management_unit: '松金管理片区', issue_count: 0 }], equipment_analysis: { issues: [first, second, special], high_groups: [{ phrase: '接地螺栓', causes: ['规范参考表的原因原文'], issues: [first, second] }], special_issue_ids: [3], severe_issue_ids: [3] } }
  const before = JSON.stringify(report)
  const sections = buildReportHtmlSections(report, 'equipment_facilities')
  assert.deepEqual(equipmentPhraseDistribution(report.equipment_analysis), [{ name: '设备接地不规范', count: 2, percentage: 66.7 }, { name: '灯具损坏', count: 1, percentage: 33.3 }])
  assert.match(sections[1].paragraphs[0], /设备接地不规范.*2个问题.*66.7%/)
  assert.equal(sections.find(s => s.title.includes('高频问题')).items[0].content, '规范参考表的原因原文')
  const unit = sections.find(s => s.title.includes('片区检查发现'))
  assert.equal(unit.tables[0].rows.length, 3)
  assert.equal(unit.tables[0].rows[2][1], 0)
  assert.match(unit.tables[0].rows[0][2], /接地锈蚀.*\n灯罩破损/)
  assert.equal(unit.issues[0].issue_id, 3)
  assert.equal(sections.find(s => s.title === '重点问题').issues[0].issue_id, 3)
  assert.equal(sections.some(s => s.title === '工作建议'), false)
  assert.ok(sections.every(s => s.paragraphs.length || s.tables.some(t => t.rows.length) || s.issues.length || s.items.length))
  assert.equal(JSON.stringify(report), before)
  assert.equal(reportReadingMetrics(report, 'equipment_facilities')[0].value, 3)
})

test('non-oil folds long prose and area details without losing saved content or business order', () => {
  const report = { issue_overview_text: '完整原文', units: [{ unit_name: '浦东', station_count: 2, issue_count: 3 }, { unit_name: '闵普徐', station_count: 0, issue_count: 0 }], category_distribution_text: '原分类说明', category_distribution: [{ name: '卫生', count: 3, percentage: 100 }], summary: { total_issue_count: 3, station_count: 2 }, key_issue_count: 0 }
  const sections = buildReportHtmlSections(report, 'non_oil')
  assert.equal(sections[1].notes[0].content, '完整原文')
  assert.equal(sections[2].tables[0].description, '原分类说明')
  assert.deepEqual(sections.filter(s => s.collapsible).map(s => s.title), ['片区问题汇总 · 浦东', '片区问题汇总 · 闵普徐'])
  assert.equal(reportReadingMetrics(report, 'non_oil').at(-1).value, 0)
})

test('distribution and shared report reader compile as safe Vue text, including collapsible sections', () => {
  for (const name of ['ReportDistribution', 'ReportHtmlContent']) {
    const path = new URL(`../src/components/${name}.vue`, import.meta.url)
    const source = readFileSync(path, 'utf8'), { descriptor } = parse(source)
    const script = compileScript(descriptor, { id: name })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: String(path), id: name, compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
    assert.doesNotMatch(source, /v-html|axios|fetch\(/)
  }
})
