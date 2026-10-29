// Store only explicit edits, not every AI value materialized for editing.
export function manualClassificationChanges(draft, baseline, saved) {
  const result = JSON.parse(JSON.stringify(saved || {}))
  for (const [key, value] of Object.entries(draft || {})) {
    const entry = (result[key] ||= { assignments: {}, summaries: {} })
    for (const field of ['assignments', 'summaries']) {
      entry[field] ||= {}
      const before = baseline[key]?.[field] || {},
        after = value[field] || {}
      for (const id of new Set([...Object.keys(before), ...Object.keys(after)])) {
        if (before[id] === after[id]) continue
        if (after[id]) entry[field][id] = after[id]
        else delete entry[field][id]
      }
    }
    if (!Object.keys(entry.assignments).length && !Object.keys(entry.summaries).length)
      delete result[key]
  }
  return result
}
