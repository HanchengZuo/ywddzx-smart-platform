export function stationPlanEnrollmentMessage(station, mode) {
  const field = mode === 'offline' ? 'include_offline_plan' : 'include_online_plan'
  if (station?.[field] !== false) return ''
  const label = mode === 'offline' ? '现场' : '视频'
  return station.originallyIncluded
    ? `站点档案已关闭${label}计划纳入；保留本计划原有任务，取消并保存后不可再次纳入。`
    : `站点档案已关闭纳入${label}巡检计划。`
}

export function stationPlanEnrollmentBlocked(station, mode) {
  return Boolean(stationPlanEnrollmentMessage(station, mode) && !station.originallyIncluded)
}
