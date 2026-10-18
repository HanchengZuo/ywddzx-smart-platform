export const filterManualDocuments = (documents, query) => {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
  return documents.filter((item) => {
    const text = [item.title, item.category, item.description, ...(item.tags || [])]
      .join(' ')
      .toLocaleLowerCase()
    return terms.every((term) => text.includes(term))
  })
}

export const formatManualSize = (bytes) =>
  bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`

export function createManualPreviewCache(fetchBlob, urls = URL) {
  const entries = new Map()
  let disposed = false
  return {
    load(id, url) {
      if (disposed) return Promise.reject(new DOMException('Reader closed', 'AbortError'))
      if (entries.has(id)) return entries.get(id).promise
      const entry = { controller: new AbortController(), url: '' }
      entries.set(id, entry)
      entry.promise = Promise.resolve()
        .then(() => fetchBlob(url, { signal: entry.controller.signal }))
        .then((blob) => {
          if (disposed || entry.controller.signal.aborted)
            throw new DOMException('Reader closed', 'AbortError')
          if (blob.type !== 'image/png') throw new Error('Preview is not a PNG')
          entry.url = urls.createObjectURL(blob)
          return entry.url
        })
        .catch((error) => {
          entries.delete(id)
          throw error
        })
      return entry.promise
    },
    dispose() {
      disposed = true
      for (const entry of entries.values()) {
        entry.controller.abort()
        if (entry.url) urls.revokeObjectURL(entry.url)
      }
      entries.clear()
    },
  }
}
