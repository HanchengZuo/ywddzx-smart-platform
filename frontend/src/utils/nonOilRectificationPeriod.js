const parseDate = (value) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return null
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? date : null
}
const isoDate = (date) => date.toISOString().slice(0, 10)

export const defaultRectificationPeriod = (mainStart) => {
  const start = parseDate(mainStart)
  if (!start) return { date_from: '', date_to: '' }
  const previousMonthEnd = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), 0))
  const previousStart = new Date(previousMonthEnd)
  previousStart.setUTCDate(Math.min(start.getUTCDate(), previousMonthEnd.getUTCDate()))
  const end = new Date(start)
  end.setUTCDate(end.getUTCDate() - 1)
  return { date_from: isoDate(previousStart), date_to: isoDate(end) }
}

export const rectificationPeriodError = (period) => {
  const start = parseDate(period?.date_from)
  const end = parseDate(period?.date_to)
  if (!start || !end) return '请完整填写有效的开始日期和结束日期。'
  if (end < start) return '结束日期不能早于开始日期。'
  if ((end - start) / 86400000 > 366) return '整改统计日期范围不能超过一年。'
  return ''
}

export const historicalRectificationPeriod = (report) => {
  const period = report?.generation_context?.non_oil_rectification_period
  const previous = report?.previous_month_rectification || {}
  const saved = period?.date_from && period?.date_to ? period : previous
  if (saved.date_from && saved.date_to)
    return { date_from: saved.date_from, date_to: saved.date_to }
  // Old snapshots stored the actual calendar month, not explicit boundaries.
  if (/^\d{4}-\d{2}$/.test(previous.month || '')) {
    const start = parseDate(`${previous.month}-01`)
    if (start)
      return {
        date_from: isoDate(start),
        date_to: isoDate(new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 0))),
      }
  }
  return null
}
