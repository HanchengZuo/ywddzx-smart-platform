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
export function isCurrentPerson(person, userId) {
  return Number(userId) > 0 && Number(person?.id) === Number(userId)
}
export function scheduleSelfRole(cell, userId) {
  const planned = cell?.assignees?.some((p) => isCurrentPerson(p, userId))
  const actual = cell?.completed_inspectors?.some((p) => isCurrentPerson(p, userId))
  return planned && actual ? '我的计划及实绩' : actual ? '我的实绩' : planned ? '我的计划' : ''
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
export function staffCellPresentation(cell, day, today) {
  if (cell.available === false || (day < today && cell.history_status === 'busy'))
    return {
      tone: 'busy',
      stage: day < today ? '原始档期' : '不派工',
      label: '没空',
      detail: cell.reason || '未填写原因',
    }
  const work = cell.dispatch || {}
  if (work.total) {
    const tone = work.modes.length > 1 ? 'mixed' : work.modes[0]
    return {
      tone,
      stage: work.completed ? '实绩' : '已派工',
      label: tone === 'mixed' ? '现场 / 视频' : tone === 'offline' ? '现场巡检' : '视频巡检',
      detail: `已完成 ${work.completed}/${work.total} 项 · ${work.station_completed}/${work.station_total} 站`,
    }
  }
  const actual = cell.actual_modes || []
  if (day < today && cell.history_status && !actual.length) {
    const tone = cell.history_status === 'busy' ? 'busy' : cell.history_status
    return {
      tone,
      stage: '人工补录',
      label: tone === 'busy' ? '没空' : tone === 'offline' ? '现场巡检' : '视频巡检',
      detail: tone === 'busy' ? cell.reason || '未填写原因' : '人工记录 · 保留原始巡检数据',
    }
  }
  const modes = [
    ...new Set(actual.length ? actual.map((item) => item.mode) : cell.planned_modes || []),
  ]
  if (modes.length) {
    const tone = modes.length > 1 ? 'mixed' : modes[0]
    const name = tone === 'mixed' ? '现场 / 视频' : tone === 'offline' ? '现场巡检' : '视频巡检'
    return {
      tone,
      stage: actual.length ? '实绩' : '已排班',
      label: name,
      detail: actual.length
        ? `已记录 ${actual.reduce((sum, item) => sum + Number(item.count || 0), 0)} 张检查表`
        : cell.daily_assignment?.group_name || '已安排 · 等待巡检记录',
    }
  }
  if (cell.available === true)
    return {
      tone: 'free',
      stage: day < today ? '原始档期' : '可排班',
      label: '有空',
      detail:
        day < today
          ? work.cancelled
            ? '原派工已撤销，可查看历史'
            : '当日有空 · 无站点派工'
          : '可选择此人派工',
    }
  if (day < today) return { tone: 'past', stage: '历史', label: '无巡检记录', detail: '' }
  return { tone: 'unknown', stage: '待确认', label: '未确认', detail: '请逐格确认档期' }
}
export function staffTodaySummary(board) {
  const result = { free: 0, busy: 0, unknown: 0, offline: 0, online: 0 }
  if (!board) return result
  if (board.today_summary) return { ...result, ...board.today_summary }
  for (const person of board.people) {
    const cell = person.cells[board.today]
    if (!cell) continue
    const state = staffCellPresentation(cell, board.today, board.today)
    if (['free', 'busy', 'unknown'].includes(state.tone)) result[state.tone]++
    if (state.tone === 'mixed' || state.tone === 'offline') result.offline++
    if (state.tone === 'mixed' || state.tone === 'online') result.online++
  }
  return result
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
