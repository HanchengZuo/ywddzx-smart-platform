export const reviewFilterDefinitions = [
  ['id', '问题ID'], ['month', '检查月度'], ['dateRange', '检查时间范围'],
  ['region', '站点所属地'], ['station', '站点名称'], ['stationManager', '站点负责人'],
  ['inspector', '检查人员'], ['inspectionTableName', '检查表'], ['standardId', '外部规范ID'],
  ['standardDetail', '规范详情'], ['description', '问题描述'], ['rectificationResult', '站经理整改结果']
]
export const emptyReviewFilters = () => ({ id: '', month: '', dateFrom: '', dateTo: '', region: [], station: [], stationManager: '', inspector: [], inspectionTableName: [], standardId: '', standardDetail: '', rectificationResult: '', description: '', keyword: '' })
export const mobileReviewFilterDefinitions = [...reviewFilterDefinitions.filter(([key]) => ['station', 'inspectionTableName'].includes(key)), ['rectificationResult', '站经理整改结果'], ['keyword', '关键词搜索']]
const copySelection = value => Array.isArray(value) ? [...value] : value ? [value] : []
export const mobileReviewFilters = filters => ({
  ...emptyReviewFilters(), station: copySelection(filters.station), inspectionTableName: copySelection(filters.inspectionTableName), rectificationResult: filters.rectificationResult || '', keyword: String(filters.keyword || '').trim(),
})
export const reviewRequestParams = (filters, page = 1, pageSize = 20) => ({
  page, page_size: pageSize, issue_id: filters.id, month: filters.month,
  date_from: filters.dateFrom, date_to: filters.dateTo,
  regions: JSON.stringify(filters.region || []), stations: JSON.stringify(filters.station || []),
  inspectors: JSON.stringify(filters.inspector || []), inspection_tables: JSON.stringify(filters.inspectionTableName || []),
  rectification_result: filters.rectificationResult, standard_id: filters.standardId,
  standard_detail: filters.standardDetail, station_manager: filters.stationManager, issue_description: filters.description,
})
const text = value => String(value ?? '').trim().toLowerCase()
const contains = (value, query) => !text(query) || text(value).includes(text(query))
const selected = (value, query) => Array.isArray(query) ? !query.length || query.includes(value) : contains(value, query)
const tableSelected = (item, query) => {
  const choices = copySelection(query)
  return !choices.length || choices.some(value => / · v[1-9]\d*$/.test(value)
    ? value === `${item.inspection_table_name} · v${item.version_number}`
    : contains(item.inspection_table_name, value))
}
export function matchesMyIssue(item, filters) {
  const date = String(item.time || '').slice(0, 10)
  return (!filters.id || String(item.id) === String(filters.id).trim())
    && (!filters.month || item.month === filters.month)
    && (!filters.dateFrom || date >= filters.dateFrom) && (!filters.dateTo || date <= filters.dateTo)
    && selected(item.region, filters.region) && selected(item.station, filters.station)
    && tableSelected(item, filters.inspectionTableName) && selected(item.inspector, filters.inspector)
    && contains(item.station_manager, filters.stationManager)
    && (!filters.standardId || String(item.standard_id) === String(filters.standardId).trim())
    && contains(`${item.standard_detail_text || ''} ${item.internal_standard_detail_text || ''}`, filters.standardDetail)
    && (!filters.rectificationResult || (['站级无法整改', '站经无法整改', '站级无法完成整改', '站经理无法整改'].includes(item.rectification_result) ? '站级无法整改' : item.rectification_result) === filters.rectificationResult)
    && contains(item.description, filters.description)
}
