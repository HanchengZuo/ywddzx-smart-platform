import { stationCoordinates } from './schedulingCoverage.js'

function hull(points) {
  const sorted = [...new Map(points.map(point => [point.join(','), point])).values()]
    .sort((a, b) => a[0] - b[0] || a[1] - b[1])
  if (sorted.length < 3) return sorted
  const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
  const half = rows => {
    const result = []
    for (const point of rows) {
      while (result.length > 1 && cross(result[result.length - 2], result[result.length - 1], point) <= 0) result.pop()
      result.push(point)
    }
    return result.slice(0, -1)
  }
  return [...half(sorted), ...half([...sorted].reverse())]
}

export function buildRegionAreas(groups) {
  return (groups || []).flatMap(group => {
    const region = String(group.region || '').trim()
    if (!region || region === '未填写片区') return []
    const points = (group.coordinates || []).map(point => Array.isArray(point)
      ? stationCoordinates({ longitude: point[0], latitude: point[1] }) : null).filter(Boolean)
    if (!points.length) return []
    const origin = [0, 1].map(axis => points.reduce((sum, point) => sum + point[axis], 0) / points.length)
    const scale = [111320 * Math.max(.01, Math.cos(origin[1] * Math.PI / 180)), 111320]
    const projected = points.map(point => point.map((value, axis) => (value - origin[axis]) * scale[axis]))
    // A rounded 500m buffer also gives one-point and collinear regions visible area.
    const radius = 500 / Math.cos(Math.PI / 16)
    const outline = hull(hull(projected).flatMap(point => Array.from({ length: 16 }, (_, index) => {
      const angle = index * Math.PI / 8
      return [point[0] + Math.cos(angle) * radius, point[1] + Math.sin(angle) * radius]
    })))
    let area = 0
    const centroid = [0, 0]
    outline.forEach((point, index) => {
      const next = outline[(index + 1) % outline.length]
      const cross = point[0] * next[1] - next[0] * point[1]
      area += cross
      for (const axis of [0, 1]) centroid[axis] += (point[axis] + next[axis]) * cross
    })
    const unproject = point => point.map((value, axis) => Math.max(axis ? -90 : -180,
      Math.min(axis ? 90 : 180, value / scale[axis] + origin[axis])))
    const colorIndex = [...region].reduce((sum, char) => sum + char.codePointAt(0), 0) % 3
    return [{ region, path: outline.map(unproject),
      center: unproject(centroid.map(value => value / (3 * area))),
      color: ['#2563eb', '#0284c7', '#1d4ed8'][colorIndex] }]
  }).sort((a, b) => a.region.localeCompare(b.region, 'zh-CN'))
}
