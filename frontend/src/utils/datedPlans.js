import { shanghaiToday } from './staffScheduling.js'

export const dateSelection = (values, options) => [...new Set(values)].filter(day => options.some(option => option.day === day)).sort()
export const preferredPlanningDay = options => options.find(option => option.day === shanghaiToday())?.day || options[0]?.day || ''
export const planningDateLabel = day => day + ' · ' + new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', weekday: 'long' }).format(new Date(day + 'T12:00:00+08:00'))
export function datePeriod(day) {
  if (!day) return {}
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) throw new Error('排班日期格式不正确。')
  const [year, month] = day.split('-').map(Number)
  return { year, month, quarter: Math.ceil(month / 3) }
}
export const planSession = (day, activeDay, active, sessions) => day === activeDay ? active : sessions[day]
export function personnelApplyPlan(session) {
  const draft = session?.preview
  if (!draft) return null
  return { day: session.context.day, source: draft.source, revision: session.context.revision,
    manager_modes: draft.manager_modes || session.managerModes, seed: draft.seed, token: draft.token, moves: draft.moves || [] }
}
