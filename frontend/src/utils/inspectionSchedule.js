export const scheduleStatusLabels = {
  completed: '已检查',
  assigned: '已排班',
  unassigned: '待排班',
  unavailable: '不可安排',
  exception: '视频异常免检',
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
  const exempted = cells.filter((cell) => cell.status === 'exception').length
  const blocked =
    !total ||
    cells.some(
      (cell) => !['completed', 'assigned', 'unassigned', 'exception'].includes(cell.status),
    )
  const remaining = total - completed - exempted
  const status =
    exempted > 0
      ? 'exception'
      : total > 0 && remaining === 0
        ? 'completed'
        : !blocked && remaining > 0 && assigned === remaining
          ? 'assigned'
          : 'unassigned'
  return {
    status,
    total,
    completed,
    assigned,
    exempted,
    remaining,
    blocked,
    partialCompleted: !exempted && completed > 0 && remaining > 0,
    partialAssigned: assigned > 0 && assigned < remaining,
  }
}

export const scheduleCellColorOptions = [
  { value: 'green', label: '绿色 · 已检查', color: '#bce6cc' },
  { value: 'red', label: '红色 · 已排班', color: '#f3b9be' },
  { value: 'yellow', label: '黄色 · 逾期未检查', color: '#f3d78d' },
  { value: 'neutral', label: '浅色 · 待排班', color: '#e8eff5' },
  { value: 'gray', label: '灰色 · 不适用 / 异常免检', color: '#cbd5df' },
]

export function scheduleCellColor(cell) {
  if (cell.status === 'completed') return 'green'
  if (cell.status === 'assigned') return cell.overdue ? 'yellow' : 'red'
  if (cell.status === 'unassigned') return 'neutral'
  return 'gray'
}

export function scheduleCellMatches(cell, color = '', person = '') {
  if (color && scheduleCellColor(cell) !== color) return false
  const query = String(person || '').trim().toLocaleLowerCase()
  if (!query) return true
  // Search plan and actual independently; never substitute one for the other.
  return [...(cell.assignees || []), ...(cell.completed_inspectors || [])].some(
    (p) => [p.display_name, p.username].filter(Boolean).join(' ').toLocaleLowerCase().includes(query),
  )
}

export function filterScheduleRows(rows, region, keyword, state = '', color = '', person = '') {
  const query = String(keyword || '')
    .trim()
    .toLocaleLowerCase()
  return rows.filter((row) => {
    if (
      (region && row.region !== region) ||
      (query && ![row.station_name, row.region].join(' ').toLocaleLowerCase().includes(query))
    )
      return false
    if ((color || String(person || '').trim()) &&
        !Object.values(row.cells || {}).some((cell) => scheduleCellMatches(cell, color, person)))
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
    Object.values(row?.cells || {}).some(
      (c) => c.row_locked || ['completed', 'exception'].includes(c.status),
    ),
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
  if (rows.some((row) => Object.values(row?.cells || {}).some((c) => c.status === 'exception')))
    result.exception = 0
  rows.forEach((row) => {
    const progress = stationScheduleProgress(row)
    result[progress.status]++
    for (const flag of ['partialCompleted', 'partialAssigned', 'blocked'])
      result[flag] += Number(progress[flag])
  })
  return result
}
