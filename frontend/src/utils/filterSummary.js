export const filterValues = (value) => (Array.isArray(value) ? value : [value])
  .filter((item) => item !== null && item !== undefined && String(item).trim() !== '')
  .map((item) => String(item).trim())

const equivalent = (left, right) => JSON.stringify([...filterValues(left)].sort()) === JSON.stringify([...filterValues(right)].sort())

const valueLabels = {
  excellent: { starred: '已点亮优秀问题', unstarred: '未点亮优秀问题' },
  auditState: { pending: '待审核', done: '已审核' },
  auditStatus: { approved: '审核通过', rejected: '审核否决' },
  signStatus: { signed: '已签名', pending: '待签名' },
  completionStatus: { completed: '已确认完成', pending: '待检查人确认' }
}

export const buildFilterSummary = (definitions, draft, applied = draft) => definitions.map(([key, label]) => {
  const dateRange = (source) => [source.dateFrom || '', source.dateTo || '']
  const raw = key === 'dateRange' ? dateRange(draft) : draft[key]
  const previous = key === 'dateRange' ? dateRange(applied) : applied[key]
  const display = (value) => {
    if (key === 'dateRange') {
      return value.some(Boolean) ? `${value[0] || '不限开始'} 至 ${value[1] || '不限结束'}` : ''
    }
    return filterValues(value).map((item) => valueLabels[key]?.[item] || item).join('、')
  }
  // Date endpoints are ordered; moving a boundary must not compare as a set.
  const changed = key === 'dateRange' ? JSON.stringify(raw) !== JSON.stringify(previous) : !equivalent(raw, previous)
  return {
    key, label, value: display(raw), applied: display(previous), changed,
    state: changed ? 'pending' : filterValues(raw).length ? 'set' : 'empty'
  }
})
