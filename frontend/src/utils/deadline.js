export const deadlineRemaining = (deadline, now = Date.now()) => Math.max(0, Number(deadline || 0) - now)
export const deadlineExpired = (deadline, now = Date.now()) => Boolean(deadline) && Number(deadline) <= now
export function deadlineLabel(deadline, now = Date.now()) {
  if (!deadline) return '期限同步中'
  const minutes = Math.ceil(deadlineRemaining(deadline, now) / 60000)
  if (!minutes) return '期限已结束'
  return `剩余 ${Math.floor(minutes / 1440)}天 ${Math.floor(minutes / 60) % 24}小时 ${minutes % 60}分`
}
