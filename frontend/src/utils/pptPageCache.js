// Per-view authenticated image cache. Never persisted or shared between accounts/reports.
export function createPptPageCache(
  fetchBlob,
  { maxPages = 8, maxBytes = 24 * 1024 * 1024, urls = URL } = {},
) {
  const entries = new Map(),
    pending = new Map(),
    queue = []
  let active = 0,
    currentPage = 1,
    bytes = 0,
    closed = false
  function trim() {
    for (const [page, entry] of entries) {
      if (entries.size <= maxPages && bytes <= maxBytes) break
      if (page === currentPage) continue
      urls.revokeObjectURL(entry.url)
      entries.delete(page)
      bytes -= entry.size
    }
  }
  function peek(page) {
    const entry = entries.get(page)
    if (!entry) return null
    entries.delete(page)
    entries.set(page, entry)
    return entry.url
  }
  function pump() {
    while (!closed && active < 2 && queue.length) {
      const job = queue.shift()
      active++
      Promise.resolve()
        .then(() => fetchBlob(job.page, job.controller.signal))
        .then((blob) => {
          if (closed) throw new Error('Preview cache closed')
          const url = urls.createObjectURL(blob)
          entries.set(job.page, { url, size: blob.size || 0 })
          bytes += blob.size || 0
          trim()
          job.resolve(url)
        })
        .catch(job.reject)
        .finally(() => {
          active--
          pending.delete(job.page)
          pump()
        })
    }
  }
  function get(page, { prefetch = false } = {}) {
    if (closed) return Promise.reject(new Error('Preview cache closed'))
    const cached = peek(page)
    if (cached) return Promise.resolve(cached)
    if (pending.has(page)) {
      const job = pending.get(page)
      if (!prefetch && queue.includes(job)) {
        queue.splice(queue.indexOf(job), 1)
        queue.unshift(job)
      }
      return job.promise
    }
    const job = { page, controller: new AbortController() }
    job.promise = new Promise((resolve, reject) => {
      job.resolve = resolve
      job.reject = reject
    })
    pending.set(page, job)
    if (prefetch) queue.push(job)
    else queue.unshift(job)
    pump()
    return job.promise
  }
  function dispose() {
    closed = true
    for (const job of pending.values()) {
      job.controller.abort()
      job.reject(new Error('Preview cache closed'))
    }
    pending.clear()
    queue.length = 0
    for (const entry of entries.values()) urls.revokeObjectURL(entry.url)
    entries.clear()
    bytes = 0
  }
  return {
    peek,
    get,
    dispose,
    focus(page) {
      currentPage = page
      peek(page)
      trim()
    },
  }
}
