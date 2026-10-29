import { stationCoordinates } from './schedulingCoverage.js'

export const STATION_REMINDER_METERS = 1000

export function distanceMeters(a, b) {
  const rad = value => value * Math.PI / 180
  const dlat = rad(b[1] - a[1]), dlng = rad(b[0] - a[0])
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dlng / 2) ** 2
  return 6371008.8 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, h))))
}

export function proximityResult(station, position, converted) {
  const target = stationCoordinates(station || {})
  if (!target) return { kind: 'unavailable', message: '该站点尚无有效坐标，无法核对距离。请确认站点名称后继续。' }
  const point = stationCoordinates({ longitude: converted?.[0], latitude: converted?.[1] })
  if (!point) throw new Error('坐标转换失败，暂时无法核对距离。')
  const distance = distanceMeters(target, point)
  const accuracy = Number(position.coords.accuracy)
  const precise = Number.isFinite(accuracy) && accuracy > 0 && accuracy <= 300
  const kind = distance > STATION_REMINDER_METERS ? 'outside'
    : precise && distance + accuracy <= STATION_REMINDER_METERS ? 'near' : 'uncertain'
  return { kind, distance, accuracy: Number.isFinite(accuracy) ? accuracy : null,
    message: kind === 'outside' ? '当前位置可能不在所选站点 1 公里范围内，请核对是否选错站点。'
      : kind === 'uncertain' ? '定位精度较低，暂时不能准确判断是否在站点附近，请核对站点。'
        : '当前位置在所选站点 1 公里范围内。' }
}

export function locationErrorMessage(error) {
  if (error?.code === 1) return '未获得定位授权，请核对站点名称；不授权也可以继续提交。'
  if (error?.code === 2) return '暂时无法获取位置，请检查设备定位服务；仍可继续提交。'
  if (error?.code === 3) return '定位核对超时，请核对站点后继续，或重新定位。'
  return error?.message || '暂时无法核对位置，请确认站点名称后继续。'
}

// Browser coordinates are WGS84; station map coordinates are GCJ-02. Never
// compare them directly. Use the existing AMap SDK's official conversion.
export async function checkStationProximity(station, { geolocation, secure, loadMap, signal }) {
  if (!stationCoordinates(station || {})) return proximityResult(station)
  if (!secure) throw new Error('当前连接不支持安全定位，请使用 HTTPS；仍可继续提交。')
  if (!geolocation) throw new Error('当前浏览器不支持定位，请核对站点后继续。')
  let timer, cancel, ended = false
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => reject({ code: 3 }), 10000)
    cancel = () => reject(new Error('定位核对已取消。'))
    signal?.addEventListener('abort', cancel, { once: true })
  })
  const check = async () => {
    if (ended || signal?.aborted) throw new Error('定位核对已取消。')
    const position = await new Promise((resolve, reject) => geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true, timeout: 8000, maximumAge: 60000,
    }))
    if (ended || signal?.aborted) throw new Error('定位核对已取消。')
    if (!stationCoordinates(position.coords)) throw new Error('设备返回的位置无效，请核对站点后继续。')
    const map = await loadMap()
    if (ended || signal?.aborted) throw new Error('定位核对已取消。')
    const converted = await new Promise((resolve, reject) => map.convertFrom(
      [position.coords.longitude, position.coords.latitude], 'gps', (status, result) => {
        if (status === 'complete' && result?.locations?.length) {
          const point = result.locations[0]
          resolve([point.getLng(), point.getLat()])
        } else reject(new Error('地图坐标转换暂不可用，请核对站点后继续。'))
      },
    ))
    return proximityResult(station, position, converted)
  }
  try { return await Promise.race([check(), deadline]) }
  finally { ended = true; clearTimeout(timer); signal?.removeEventListener('abort', cancel) }
}
