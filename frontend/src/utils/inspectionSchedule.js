export const scheduleStatusLabels = {
  completed: '已检查',
  assigned: '已排班',
  unassigned: '待排班',
  unavailable: '不可安排',
}

export function shelfHasCapacity(item) {
  return Number.isSafeInteger(item?.remaining) && item.remaining > 0
}

export function stationScheduleProgress(row) {
  // An inapplicable annual video column is exempt; a missing checklist is not.
  const cells = Object.values(row?.cells || {}).filter((cell) => cell.applicable !== false)
  const total = cells.length
  const completed = cells.filter((cell) => cell.status === 'completed').length
  const assigned = cells.filter((cell) => cell.status === 'assigned').length
  const blocked =
    !total || cells.some((cell) => !['completed', 'assigned', 'unassigned'].includes(cell.status))
  const remaining = total - completed
  const status =
    total > 0 && remaining === 0
      ? 'completed'
      : !blocked && remaining > 0 && assigned === remaining
        ? 'assigned'
        : 'unassigned'
  return {
    status,
    total,
    completed,
    assigned,
    remaining,
    blocked,
    partialCompleted: completed > 0 && remaining > 0,
    partialAssigned: assigned > 0 && assigned < remaining,
  }
}

export function filterScheduleRows(rows, region, keyword, state = '') {
  const query = String(keyword || '')
    .trim()
    .toLocaleLowerCase()
  return rows.filter((row) => {
    if (
      (region && row.region !== region) ||
      (query && ![row.station_name, row.region].join(' ').toLocaleLowerCase().includes(query))
    )
      return false
    if (!state) return true
    const progress = stationScheduleProgress(row)
    if (state === 'partial_completed') return progress.partialCompleted
    if (state === 'partial_assigned') return progress.partialAssigned
    if (state === 'blocked') return progress.blocked
    return progress.status === state
  })
}

export function displayedInspectors(cell) {
  return cell.status === 'completed' ? cell.completed_inspectors : cell.assignees
}

export function inspectorPreview(cell) {
  const people = displayedInspectors(cell) || []
  const names = people
    .slice(0, 2)
    .map((person) => person.display_name)
    .join('、')
  return names + (people.length > 2 ? ` 等${people.length}人` : '')
}

export function scheduleCellEditable(cell, allowed) {
  return Boolean(
    allowed && cell && !cell.row_locked && ['assigned', 'unassigned'].includes(cell.status),
  )
}

export function scheduleRowLocked(row) {
  return Boolean(
    row?.locked ||
    Object.values(row?.cells || {}).some((c) => c.row_locked || c.status === 'completed'),
  )
}

export function scheduleCounts(rows) {
  const result = {
    completed: 0,
    assigned: 0,
    unassigned: 0,
    total: rows.length,
    partialCompleted: 0,
    partialAssigned: 0,
    blocked: 0,
  }
  rows.forEach((row) => {
    const progress = stationScheduleProgress(row)
    result[progress.status]++
    for (const flag of ['partialCompleted', 'partialAssigned', 'blocked'])
      result[flag] += Number(progress[flag])
  })
  return result
}
