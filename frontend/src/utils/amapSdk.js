const AMAP_KEY = import.meta.env?.VITE_AMAP_KEY || '9f35886b6810874b8578ab8dd3d2525e'
export const SHANGHAI_CENTER = [121.4737, 31.2304]
let pending = null
const icons = new Map()

export function loadAmapSdk() {
  if (window.AMap) return Promise.resolve(window.AMap)
  if (pending) return pending
  pending = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    const finish = (error) => {
      window.clearTimeout(timer)
      script.onload = script.onerror = null
      if (error) {
        pending = null
        script.remove()
        reject(error)
      } else resolve(window.AMap)
    }
    const timer = window.setTimeout(() => finish(new Error('高德地图加载超时，请重试。')), 30000)
    script.async = true
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(AMAP_KEY)}`
    script.onload = () => finish(window.AMap ? null : new Error('高德地图加载失败，请重试。'))
    script.onerror = () => finish(new Error('无法加载高德地图，请检查网络后重试。'))
    document.head.appendChild(script)
  })
  return pending
}

export function amapPinIcon(color) {
  if (!icons.has(color)) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="36" viewBox="0 0 30 36"><path d="M15 1C7.82 1 2 6.82 2 14c0 9.25 13 21 13 21s13-11.75 13-21C28 6.82 22.18 1 15 1z" fill="${color}" stroke="white" stroke-width="2"/><circle cx="15" cy="14" r="5" fill="white" fill-opacity=".92"/></svg>`
    icons.set(color, `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`)
  }
  return icons.get(color)
}

export function amapStationLabel(name) {
  return {
    content: String(name || ''), direction: 'top', offset: [0, -4],
    style: { fontSize: 12, fontWeight: '600', fillColor: '#0f172a',
      strokeColor: '#ffffff', strokeWidth: 3, padding: [2, 4] },
  }
}
