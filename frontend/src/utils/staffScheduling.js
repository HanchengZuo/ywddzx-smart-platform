export function shanghaiToday(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now)
  return ['year', 'month', 'day']
    .map((key) => parts.find((part) => part.type === key).value)
    .join('-')
}
export function offsetDay(day, offset) {
  const value = new Date(day + 'T12:00:00Z')
  value.setUTCDate(value.getUTCDate() + offset)
  return value.toISOString().slice(0, 10)
}
export function cellKey(row, column) {
  return `${row.station_id}:${column.key}`
}
export function personCanSchedule(person, mode) {
  return (
    person.id &&
    person.available === true &&
    !(person.planned_modes || []).some((value) => value !== mode) &&
    !(person.actual_modes || []).some((value) => value.mode !== mode)
  )
}
export function availabilityLabel(person, mode) {
  if (!person.id) return '账号未匹配'
  if (person.available === false) return person.reason || '没空'
  if (person.available !== true) return '档期未确认'
  if (!personCanSchedule(person, mode)) return '已安排另一种检查'
  return '有空'
}
export function taskGroups(tasks) {
  const groups = new Map()
  for (const task of tasks) {
    const key = `${task.scheduled_date}:${task.mode}:${task.station_id}`
    if (!groups.has(key)) groups.set(key, { key, ...task, tasks: [] })
    groups.get(key).tasks.push(task)
  }
  return [...groups.values()]
}
