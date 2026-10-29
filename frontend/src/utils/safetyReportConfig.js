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

export function safetyFocusName(saved, topics = []) {
  const usable = topics.filter((topic) => Number(topic.count) > 0)
  if (usable.some((topic) => topic.name === saved)) return saved
  return (
    [...usable].sort(
      (a, b) => b.count - a.count || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0),
    )[0]?.name || ''
  )
}

export function safetyAnalysisReady(category) {
  if (!category?.issues?.length || category.analysis?.complete === false) return false
  const ids = new Set(category.issues.map((issue) => Number(issue.issue_id)))
  const classified = (category.analysis?.groups || []).flatMap((group) =>
    group.issue_ids.map(Number),
  )
  return (
    classified.length === ids.size &&
    new Set(classified).size === ids.size &&
    classified.every((id) => ids.has(id))
  )
}

export function safetySubgroups(category, override = {}) {
  const ids = new Set((category?.issues || []).map((issue) => String(issue.issue_id)))
  const counts = new Map()
  for (const name of Object.keys(override.summaries || {})) counts.set(name, 0)
  for (const [id, name] of Object.entries(override.assignments || {})) {
    if (ids.has(id) && name) counts.set(name, (counts.get(name) || 0) + 1)
  }
  return [...counts]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'zh-CN'))
}

export function safetyIssueSearch(issues, keyword) {
  const query = String(keyword || '')
    .trim()
    .toLowerCase()
  return !query
    ? issues
    : issues.filter((issue) =>
        [
          issue.issue_id,
          issue.station_name,
          issue.description,
          issue.topic,
          issue.category_name,
        ].some((value) =>
          String(value || '')
            .toLowerCase()
            .includes(query),
        ),
      )
}
