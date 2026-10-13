export function operationsScopeLabel(scope, options = []) {
  if (!scope.station_id) return scope.region || '全部可见片区'
  const group = options.find((row) => row.region === scope.region)
  const station = group?.stations.find((row) => String(row.id) === String(scope.station_id))
  return `${scope.region || '站点'} / ${station?.name || `站点 #${scope.station_id}`}`
}
