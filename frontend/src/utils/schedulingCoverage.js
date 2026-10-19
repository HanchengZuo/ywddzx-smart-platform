export function currentCoveragePeriod(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'numeric' }).formatToParts(now)
  const year = Number(parts.find(p => p.type === 'year').value)
  const month = Number(parts.find(p => p.type === 'month').value)
  return { mode: 'offline', year, quarter: Math.floor((month - 1) / 3) + 1, month }
}

export function coverageQuery(draft) {
  const year = Number(draft.year)
  const unit = Number(draft.mode === 'offline' ? draft.quarter : draft.month)
  if (!['offline', 'online'].includes(draft.mode) || !Number.isInteger(year) || year < 2000 || year > 2100 || !Number.isInteger(unit) || unit < 1 || unit > (draft.mode === 'offline' ? 4 : 12)) {
    throw new Error('请选择有效年份和季度或月份。')
  }
  return { mode: draft.mode, year, [draft.mode === 'offline' ? 'quarter' : 'month']: unit }
}

export function stationCoordinates(station) {
  if ([station.longitude, station.latitude].some(value => value === null || value === undefined || String(value).trim() === '')) return null
  const [lng, lat] = [Number(station.longitude), Number(station.latitude)]
  return Number.isFinite(lng) && Number.isFinite(lat) && lng >= -180 && lng <= 180 && lat >= -90 && lat <= 90 && (lng !== 0 || lat !== 0) ? [lng, lat] : null
}

export function filterUncoveredStations(stations, region, keyword) {
  const text = String(keyword || '').trim().toLocaleLowerCase()
  return stations.filter(station => (!region || station.region === region) && (!text ||
    [station.station_name, station.region, station.address].some(value => String(value || '').toLocaleLowerCase().includes(text))))
}
