const labels = {
  issueId: '问题ID', issue_id: '问题ID', month: '检查月度', date: '检查日期',
  dateFrom: '检查开始日期', date_from: '检查开始日期', dateTo: '检查结束日期', date_to: '检查结束日期',
  region: '站点所属地', regions: '站点所属地', station: '站点名称', stations: '站点名称',
  stationManager: '站点负责人', station_manager: '站点负责人', inspector: '检查人员', inspectors: '检查人员',
  inspectionTableName: '检查表', inspection_tables: '检查表', inspection_table_name: '检查表',
  standardId: '外部规范ID', standard_id: '外部规范ID', standardDetail: '规范详情', standard_detail: '规范详情',
  standardTags: '规范标签', standard_tags: '规范标签', issueDescription: '问题描述', issue_description: '问题描述',
  rectificationResult: '站经理整改结果', rectification_result: '站经理整改结果', reviewResult: '督导组复核结果', review_result: '督导组复核结果',
  status: '问题状态', excellent: '优秀问题', auditStatus: '审核结论', audit_status: '审核结论',
  auditState: '审核状态', audit_state: '审核状态', description_match: '关键词匹配方式',
}
const values = {
  excellent: { starred: '已标星', unstarred: '未标星' },
  auditStatus: { pending: '待审核', approved: '通过', rejected: '否决' },
  auditState: { pending: '未审核', done: '已审核' },
  description_match: { all: '全部关键词', any: '任一关键词' },
}
values.audit_status = values.auditStatus
values.audit_state = values.auditState

export function issueExportFilterChips(summary = {}) {
  return Object.entries(summary).flatMap(([key, raw]) => {
    const text = (Array.isArray(raw) ? raw.join('、') : String(raw ?? '')).trim()
    return text ? [{ key, label: labels[key] || '其他筛选条件', value: values[key]?.[text] || text }] : []
  })
}

export function beginIssueExportDownload(taskId, url, filename, document, origin) {
  const target = new URL(url, origin)
  if (target.origin !== origin || target.pathname !== `/api/issues/export-tasks/${encodeURIComponent(taskId)}/download` || target.search || target.hash) {
    throw new Error('下载地址不正确，请重新点击下载。')
  }
  const link = document.createElement('a')
  link.href = target.href
  link.download = filename || `巡检问题列表_${taskId.slice(0, 8)}.xlsx`
  link.referrerPolicy = 'no-referrer'
  document.body.appendChild(link)
  link.click()
  link.remove()
}
