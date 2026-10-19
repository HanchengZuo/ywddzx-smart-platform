import { coverageQuery } from './schedulingCoverage.js'

export function coverageKey(source) {
  return JSON.stringify(coverageQuery(source))
}

// Per-view cache: never persisted or shared between accounts. Only the latest selection may publish.
export function createCoverageLoader({ fetchCoverage, onChange, delay = 180, ttl = 30000,
  maxEntries = 8, now = Date.now, setTimer = setTimeout, clearTimer = clearTimeout }) {
  const cache = new Map()
  let state = { result:null, loading:false, error:'', blocked:false }
  let active = null
  let controller = null
  let timer = null
  let serial = 0
  let closed = false

  function publish(patch) {
    if (closed) return
    state = { ...state, ...patch }
    onChange(state)
  }
  function cancel() {
    serial++
    if (timer !== null) clearTimer(timer)
    timer = null
    controller?.abort()
    controller = null
  }
  function peek(key) {
    const item = cache.get(key)
    if (item) { cache.delete(key); cache.set(key, item) }
    return item
  }
  async function load(query, token) {
    const request = new AbortController()
    controller = request
    try {
      let data = await fetchCoverage(query, request.signal)
      if (closed || token !== serial || request.signal.aborted) return false
      const key = coverageKey(query)
      if (!data || !Array.isArray(data.stations) || !Array.isArray(data.regions) || !data.summary ||
          !data.period || coverageKey(data.period) !== key) throw new Error('Invalid coverage response')
      const previous = cache.get(key)?.data
      // A background timestamp change alone must not rebuild the map or reset its viewport.
      if (previous && JSON.stringify(previous.stations) === JSON.stringify(data.stations)) {
        data = { ...data, stations:previous.stations }
      }
      cache.delete(key)
      cache.set(key, { data, at:now() })
      while (cache.size > maxEntries) cache.delete(cache.keys().next().value)
      publish({ result:data, loading:false, error:'' })
      return true
    } catch (error) {
      if (closed || token !== serial || request.signal.aborted) return false
      const blocked = [401, 403].includes(error.response?.status)
      if (blocked) cache.clear()
      publish({ ...(blocked ? { result:null } : {}), loading:false, blocked,
        error:error.response?.data?.error || '覆盖数据暂时无法读取，将自动重试。' })
      return false
    } finally {
      if (controller === request) controller = null
    }
  }
  return {
    select(source, { immediate = false } = {}) {
      if (closed || state.blocked) return
      let query
      try { query = coverageQuery(source) } catch (error) {
        cancel()
        active = null
        publish({ loading:false, error:error.message })
        return
      }
      const key = coverageKey(query)
      if (active && coverageKey(active) === key && (controller || timer !== null)) return
      cancel()
      active = query
      const cached = peek(key)
      const fresh = cached && now() - cached.at < ttl
      publish({ result:cached?.data || state.result, loading:!fresh, error:'' })
      if (fresh) return
      const token = serial
      if (immediate) void load(query, token)
      else timer = setTimer(() => { timer = null; void load(query, token) }, delay)
    },
    async refresh() {
      if (closed || state.blocked || !active || controller || timer !== null) return true
      const cached = cache.get(coverageKey(active))
      if (cached && now() - cached.at < ttl) return true
      publish({ loading:true, error:'' })
      return load(active, serial)
    },
    dispose() {
      closed = true
      cancel()
      cache.clear()
      state = { result:null, loading:false, error:'', blocked:false }
    },
  }
}
