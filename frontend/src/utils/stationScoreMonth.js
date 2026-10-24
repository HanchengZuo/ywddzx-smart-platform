export function previousScoreMonth(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'numeric',
  }).formatToParts(now)
  let year = Number(parts.find((p) => p.type === 'year').value)
  let month = Number(parts.find((p) => p.type === 'month').value) - 1
  if (!month) {
    year--
    month = 12
  }
  return `${year}-${String(month).padStart(2, '0')}`
}

export function scoreMonthLabel(month) {
  return /^\d{4}-(0[1-9]|1[0-2])$/.test(month || '')
    ? `${Number(month.slice(0, 4))}年${Number(month.slice(5))}月`
    : '请选择评分月份'
}

export function scoreLedgerRows(standards, keyword = '', state = '') {
  const query = keyword.trim().toLocaleLowerCase()
  return (standards || []).filter(
    (row) =>
      (!query ||
        [
          row.standard_id,
          ...(row.all_fields || []).map((f) => f.value),
          ...(row.issues || []).map((i) => i.description),
        ]
          .join(' ')
          .toLocaleLowerCase()
          .includes(query)) &&
      (state !== 'deducted' || row.is_deducted) &&
      (state !== 'adjusted' || row.has_manual_adjustment),
  )
}
