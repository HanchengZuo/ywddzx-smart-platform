import { stationCoordinates } from './schedulingCoverage.js'

const icons = new Map()

export function schedulingBeaconIcon(selected = false) {
  const key = Boolean(selected)
  if (!icons.has(key)) {
    const light = key ? '#ffd76a' : '#5bfff2'
    const edge = key ? '#b67b16' : '#147f95'
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40"><defs><radialGradient id="halo"><stop stop-color="${light}" stop-opacity=".5"/><stop offset="1" stop-color="${light}" stop-opacity="0"/></radialGradient></defs><circle cx="20" cy="20" r="20" fill="url(#halo)"/><circle cx="20" cy="20" r="14" fill="#082c3b" fill-opacity=".12" stroke="${edge}" stroke-opacity=".6"/><path d="M20 5v4m15 11h-4M20 35v-4M5 20h4" stroke="${edge}" stroke-width="2" stroke-linecap="round"/><path d="m20 10 10 10-10 10-10-10Z" fill="#073345" stroke="${light}" stroke-width="1.5"/><circle cx="20" cy="20" r="5" fill="${light}"/><circle cx="19" cy="19" r="2" fill="white"/></svg>`
    icons.set(key, `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`)
  }
  return icons.get(key)
}

// Keep DOM animations bounded; all stations remain visible in the canvas label layer.
export function choosePulseStations(stations, selectedId, bounds, limit) {
  const budget = Math.max(0, Math.min(14, Math.floor(Number(limit) || 0)))
  if (!budget) return []
  const seen = new Set()
  const candidates = stations.filter(station => {
    const point = stationCoordinates(station)
    return point && (!bounds || (point[0] >= bounds[0][0] && point[0] <= bounds[1][0]
      && point[1] >= bounds[0][1] && point[1] <= bounds[1][1]))
  })
  const selected = candidates.find(station => String(station.station_id) === String(selectedId))
  const unique = (selected ? [selected, ...candidates] : candidates).filter(station => {
    const key = stationCoordinates(station).join(',')
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
  if (unique.length <= budget) return unique
  if (budget === 1) return unique.slice(0, 1)
  return Array.from({ length: budget }, (_, index) => unique[Math.floor(index * (unique.length - 1) / (budget - 1))])
}

export function beaconPhase(id) {
  let hash = 0
  for (const character of String(id)) hash = (hash * 31 + character.charCodeAt(0)) >>> 0
  return `-${hash % 3000}ms`
}
