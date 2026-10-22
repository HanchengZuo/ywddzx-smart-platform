import { taskGroups } from './staffScheduling.js'

export function taskProgressGroups(tasks) {
  return taskGroups(tasks || []).map((group) => {
    const completed = group.tasks.filter((task) => task.status === 'completed').length
    const total = group.tasks.length
    return {
      ...group,
      completed,
      total,
      pending: total - completed,
      percent: total ? Math.round((100 * completed) / total) : 0,
    }
  })
}

export function inboxMetrics(summary) {
  const buckets = summary?.buckets || {}
  const n = (key, field) => buckets[key]?.[field] || 0
  return {
    todayCompleted: n('today_offline', 'completed') + n('today_online', 'completed'),
    todayTotal: n('today_offline', 'total') + n('today_online', 'total'),
    todayPending: n('today_offline', 'pending') + n('today_online', 'pending'),
    historyOffline: n('history_offline', 'pending'),
    historyOnline: n('history_online', 'pending'),
  }
}
