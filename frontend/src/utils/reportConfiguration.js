import { historicalRectificationPeriod } from './nonOilRectificationPeriod.js'

const ids = (values = []) => [...new Set(values.map(Number))].sort((a, b) => a - b)
const stable = value => {
  if (Array.isArray(value)) return value.map(stable)
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, stable(value[key])]))
  return value
}
const equal = (a, b) => JSON.stringify(stable(a)) === JSON.stringify(stable(b))
const source = (value = {}) => ({
  mode: value.mode === 'custom' ? 'custom' : 'all',
  station_ids: value.mode === 'custom' ? ids(value.station_ids) : []
})
const rules = (value = {}) => ({
  sample_counts: Object.fromEntries(Object.entries({
    more_than_20: 8, more_than_10: 6, more_than_4: 4, at_most_4: 2,
    ...value.sample_counts
  }).map(([key, count]) => [key, Number(count)])),
  prohibited_standard_priorities: (value.prohibited_standard_priorities || []).map(Number),
  flow_standard_priorities: Object.fromEntries(Object.entries(value.flow_standard_priorities || {})
    .filter(([, values]) => values.length).map(([key, values]) => [key, values.map(Number)]))
})
const categoriesChanged = (current = [], saved = []) => {
  const previous = new Map(saved.map(item => [Number(item.issue_id), String(item.effective_category || '')]))
  return current.some(item => previous.get(Number(item.issue_id)) !== String(item.effective_category || ''))
}

// Compare effective inputs, not save timestamps, actor names, AI provenance or revision counters.
export function reportConfigurationDiffers(report, current) {
  if (!report?.month) return false
  const context = report.generation_context || {}
  const period = report.snapshot || report.summary || {}
  if (current.date_from !== period.date_from || current.date_to !== period.date_to) return true
  if (current.type === 'quality_measurement') {
    const selection = source(current.source)
    if (!equal(selection, source(context.source_selection || report.source_selection))) return true
    const savedRules = context.selection_settings || report.selection_settings || {}
    if (!equal(rules(current.selection_rules), rules(savedRules.settings || savedRules))) return true
    const stationIds = new Set(selection.station_ids)
    const relevant = (current.flow_classifications || []).filter(item => selection.mode !== 'custom' || stationIds.has(Number(item.station_id)))
    return categoriesChanged(relevant, context.flow_classifications || report.flow_classifications)
  }
  if (current.type === 'non_oil') {
    const previousPeriod = historicalRectificationPeriod(report)
    if (previousPeriod && !equal(current.rectification_period, previousPeriod)) return true
    const library = context.issue_library || report.issue_library_snapshot
    if (Array.isArray(library)) {
      const included = rows => ids(rows.filter(item => item.included !== false).map(item => item.issue_id))
      if (!equal(included(current.issue_library || []), included(library))) return true
    }
    return categoriesChanged(current.category_classifications, context.category_classifications || report.category_classifications)
      || categoriesChanged(current.key_classifications, context.key_issue_classifications || report.key_issue_classifications)
  }
  return false
}
