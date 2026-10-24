const departmentReports = {
  quality_safety: ['quality_measurement', 'safety_quality'],
  development_plan: ['equipment_facilities'],
  oil_gas: ['on_site_service'],
  non_oil: ['non_oil'],
  finance: ['finance']
}

export function reportPerspective(role, permissions = {}) {
  if (role === 'root' || permissions.view_inspection_reports) return 'center'
  if (permissions.view_department_inspection_reports && departmentReports[role]) return 'department'
  return null
}

export function visibleReportTypes(types, role, permissions = {}) {
  const perspective = reportPerspective(role, permissions)
  if (perspective === 'center') return types
  return types.filter((type) => perspective === 'department' && departmentReports[role].includes(type.key))
}

export function reportMonthLabel(month) {
  if (!/^[0-9]{4}-(0[1-9]|1[0-2])$/.test(String(month || ''))) return '尚无已生成报告'
  const [year, number] = month.split('-')
  return `${year}年${Number(number)}月`
}

export function departmentReportYears(records, currentYear = Number(new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric' }).format(new Date()))) {
  return [...new Set([currentYear, ...records.filter(item => /^[0-9]{4}-(0[1-9]|1[0-2])$/.test(item.month)).map(item => Number(item.month.slice(0, 4)))])].sort((a, b) => b - a)
}

export function departmentMonthOptions(records, year) {
  const available = new Set(records.map(item => item.month))
  return Array.from({ length: 12 }, (_, index) => {
    const month = `${year}-${String(index + 1).padStart(2, '0')}`
    return { month, label: `${index + 1}月`, available: available.has(month) }
  })
}
