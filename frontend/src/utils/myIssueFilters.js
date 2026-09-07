export const reviewFilterDefinitions = [
  ['id', '问题ID'], ['month', '检查月度'], ['dateRange', '检查时间范围'],
  ['region', '站点所属地'], ['station', '站点名称'], ['stationManager', '站点负责人'],
  ['inspector', '检查人员'], ['inspectionTableName', '检查表'], ['standardId', '外部规范ID'],
  ['standardDetail', '规范详情'], ['standardTags', '规范标签'], ['description', '问题描述']
]
export const emptyReviewFilters = () => ({ id: '', month: '', dateFrom: '', dateTo: '', region: [], station: [], stationManager: '', inspector: [], inspectionTableName: [], standardId: '', standardDetail: '', standardTags: [], description: '' })
export const reviewRequestParams = (filters, page = 1, pageSize = 20) => ({
  page, page_size: pageSize, issue_id: filters.id, month: filters.month,
  date_from: filters.dateFrom, date_to: filters.dateTo,
  regions: JSON.stringify(filters.region || []), stations: JSON.stringify(filters.station || []),
  inspectors: JSON.stringify(filters.inspector || []), inspection_tables: JSON.stringify(filters.inspectionTableName || []),
  standard_tags: JSON.stringify(filters.standardTags || []), standard_id: filters.standardId,
  standard_detail: filters.standardDetail, station_manager: filters.stationManager, issue_description: filters.description,
})
export const issueTagLabel = tag => tag.group_name ? `${tag.group_name}：${tag.tag_name}` : tag.tag_name
const text = value => String(value ?? '').trim().toLowerCase()
const contains = (value, query) => !text(query) || text(value).includes(text(query))
const selected = (value, query) => Array.isArray(query) ? !query.length || query.includes(value) : contains(value, query)
export function matchesMyIssue(item, filters) {
  const date = String(item.time || '').slice(0, 10)
  return (!filters.id || String(item.id) === String(filters.id).trim())
    && (!filters.month || item.month === filters.month)
    && (!filters.dateFrom || date >= filters.dateFrom) && (!filters.dateTo || date <= filters.dateTo)
    && selected(item.region, filters.region) && selected(item.station, filters.station)
    && selected(item.inspection_table_name, filters.inspectionTableName) && selected(item.inspector, filters.inspector)
    && contains(item.station_manager, filters.stationManager)
    && (!filters.standardId || String(item.standard_id) === String(filters.standardId).trim())
    && contains(`${item.standard_detail_text || ''} ${item.internal_standard_detail_text || ''}`, filters.standardDetail)
    && (!filters.standardTags?.length || (item.standard_tags || []).some(tag => filters.standardTags.includes(issueTagLabel(tag))))
    && contains(item.description, filters.description)
}
