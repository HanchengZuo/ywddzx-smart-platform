export const scheduleStatusLabels = {
  completed: '已检查',
  assigned: '已排班',
  unassigned: '待排班',
  unavailable: '不可安排',
}

export function filterScheduleRows(rows, region, keyword, state = '') {
  const query = String(keyword || '')
    .trim()
    .toLocaleLowerCase()
  return rows.filter(
    (row) =>
      (!region || row.region === region) &&
      (!query || [row.station_name, row.region].join(' ').toLocaleLowerCase().includes(query)) &&
      (!state || Object.values(row.cells).some((cell) => cell.status === state)),
  )
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
  return Boolean(allowed && cell && ['assigned', 'unassigned'].includes(cell.status))
}

export function scheduleCounts(rows) {
  const result = { completed: 0, assigned: 0, unassigned: 0 }
  rows.forEach((row) =>
    Object.values(row.cells).forEach((cell) => {
      if (Object.hasOwn(result, cell.status)) result[cell.status]++
    }),
  )
  return result
}
