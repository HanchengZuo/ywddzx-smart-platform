const DAY = 86400000
const SHANGHAI = 8 * 3600000

export function workingRemaining(deadline, now, days) {
  if (!deadline || !days) return null
  let cursor = now, remaining = 0
  while (cursor < Number(deadline)) {
    const localDay = Math.floor((cursor + SHANGHAI) / DAY)
    const key = new Date(localDay * DAY).toISOString().slice(0, 10)
    if (!(key in days)) return null
    const end = Math.min(Number(deadline), (localDay + 1) * DAY - SHANGHAI)
    if (days[key]) remaining += end - cursor
    cursor = end
  }
  return remaining
}

export function workingLabel(deadline, now, days) {
  const remaining = workingRemaining(deadline, now, days)
  if (remaining === null) return '工作日历待同步，请查看截止时间'
  if (Number(deadline) <= now) return '期限已结束'
  const minutes = Math.ceil(remaining / 60000)
  const key = new Date(now + SHANGHAI).toISOString().slice(0, 10)
  return `${days[key] ? '' : '非工作日暂停 · '}剩余 ${Math.floor(minutes / 60)}工作小时 ${minutes % 60}分`
}
