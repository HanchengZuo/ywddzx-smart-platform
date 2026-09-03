import test from 'node:test'
import assert from 'node:assert/strict'
import { reportConfigurationDiffers } from '../src/utils/reportConfiguration.js'

const period = { date_from: '2026-07-01', date_to: '2026-07-31' }
const flow = { issue_id: 51, station_id: 1, effective_category: '人员管理' }
const quality = () => ({
  month: '2026-07', snapshot: { ...period }, workspace_revision: 1,
  generation_context: {
    source_selection: { mode: 'custom', station_ids: [1, 2], updated_at: 'earlier' },
    selection_settings: { settings: { prohibited_standard_priorities: [51, 52] } },
    flow_classifications: [{ ...flow, classification_source: 'ai' }]
  }
})
const inputs = () => ({
  ...period, type: 'quality_measurement', source: { mode: 'custom', station_ids: ['2', '1'] },
  selection_rules: { prohibited_standard_priorities: [51, 52] },
  flow_classifications: [{ ...flow, classification_source: 'manual' }, { issue_id: 99, station_id: 50, effective_category: '' }]
})

test('fresh quality report matches despite unselected station categories, actor metadata and ordering', () => {
  assert.equal(reportConfigurationDiffers(quality(), inputs()), false)
})
test('saving identical rules or reverting to report configuration removes warning', () => {
  const saved = quality(), live = inputs()
  live.selection_rules.flow_standard_priorities = { 人员管理: [] }
  assert.equal(reportConfigurationDiffers(saved, live), false)
  live.selection_rules.prohibited_standard_priorities.reverse()
  assert.equal(reportConfigurationDiffers(saved, live), true)
  live.selection_rules.prohibited_standard_priorities.reverse()
  assert.equal(reportConfigurationDiffers(saved, live), false)
})
test('quality source, dates and relevant classification changes trigger warning', () => {
  for (const change of [
    live => { live.date_from = '2026-07-02' },
    live => { live.source.station_ids = [1] },
    live => { live.flow_classifications[0].effective_category = '器具管理' },
    live => { live.selection_rules.sample_counts = { more_than_20: 6 } }
  ]) {
    const live = inputs()
    change(live)
    assert.equal(reportConfigurationDiffers(quality(), live), true)
  }
})
test('generation using saved inputs clears warning without clearing actual user choices', () => {
  const saved = quality(), live = inputs()
  live.flow_classifications[0].effective_category = '器具管理'
  assert.equal(reportConfigurationDiffers(saved, live), true)
  saved.generation_context.flow_classifications[0].effective_category = '器具管理'
  assert.equal(reportConfigurationDiffers(saved, live), false)
})
test('all-station mode ignores informational list of resolved stations', () => {
  const saved = quality(), live = inputs()
  saved.generation_context.source_selection.mode = 'all'
  live.source.mode = 'all'
  live.flow_classifications.pop()
  assert.equal(reportConfigurationDiffers(saved, live), false)
})
const nonOil = () => ({
  month: '2026-07', snapshot: { ...period }, generation_context: {
    non_oil_rectification_period: { date_from: '2026-06-01', date_to: '2026-06-30' },
    issue_library: [{ issue_id: 51, included: true }, { issue_id: 52, included: false }],
    category_classifications: [{ issue_id: 51, effective_category: '便利店卫生情况' }],
    key_issue_classifications: [{ issue_id: 51, effective_category: '不纳入重点问题' }]
  }
})
const nonOilInputs = () => ({
  ...period, type: 'non_oil',
  rectification_period: { date_from: '2026-06-01', date_to: '2026-06-30' },
  issue_library: [{ issue_id: 52, included: false }, { issue_id: 51, included: true }],
  category_classifications: [{ issue_id: 51, effective_category: '便利店卫生情况' }],
  key_classifications: [{ issue_id: 51, effective_category: '不纳入重点问题' }]
})
test('non-oil settings exactly match generation regardless of issue order', () => {
  assert.equal(reportConfigurationDiffers(nonOil(), nonOilInputs()), false)
})
test('all non-oil panels participate in effective comparison', () => {
  for (const change of [
    live => { live.rectification_period.date_from = '2026-05-01' },
    live => { live.issue_library[0].included = true },
    live => { live.category_classifications[0].effective_category = '仓库管理情况' },
    live => { live.key_classifications[0].effective_category = '重点商品' }
  ]) {
    const live = nonOilInputs()
    change(live)
    assert.equal(reportConfigurationDiffers(nonOil(), live), true)
  }
})
test('no generated report does not show mismatch warning', () => {
  assert.equal(reportConfigurationDiffers({}, inputs()), false)
})
