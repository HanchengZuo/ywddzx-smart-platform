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

export function safetyFocusSelection(saved, topics = []) {
  return topics.some((topic) => topic.name === saved) ? saved : ''
}

export function safetyFocusCategory(topic, issues = []) {
  return {
    key: `onsite:topic:${topic}`,
    mode: 'onsite',
    category: `topic:${topic}`,
    name: `1. 月度重点：${topic}`,
    issues: issues.filter((issue) => issue.mode === 'onsite' && issue.topic === topic),
    analysis: {},
  }
}
