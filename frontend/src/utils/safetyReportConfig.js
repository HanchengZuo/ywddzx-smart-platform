// Store only explicit edits, not every AI value materialized for editing.
export function manualClassificationChanges(draft, baseline, saved) {
  const result = JSON.parse(JSON.stringify(saved || {}))
  for (const [key, value] of Object.entries(draft || {})) {
    const entry = (result[key] ||= { assignments: {}, summaries: {} })
    for (const field of ['assignments', 'summaries', 'representatives']) {
      const before = baseline?.[key]?.[field] || {},
        after = value[field] || {}
      for (const id of new Set([...Object.keys(before), ...Object.keys(after)])) {
        if (JSON.stringify(before[id]) === JSON.stringify(after[id])) continue
        if (after[id] !== undefined && (field === 'representatives' || after[id])) {
          entry[field] ||= {}
          entry[field][id] = Array.isArray(after[id]) ? [...after[id]] : after[id]
        } else if (entry[field]) delete entry[field][id]
      }
    }
    if (
      !['assignments', 'summaries', 'representatives'].some(
        (field) => Object.keys(entry[field] || {}).length,
      )
    )
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
    slot_limit: 3,
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
    (group.issue_ids || []).map(Number),
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
    .sort((a, b) => b.count - a.count || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))
}

export function safetyClassificationDraft(category, saved = {}) {
  const result = { assignments: {}, summaries: {}, representatives: {} }
  for (const group of category?.analysis?.groups || []) {
    for (const id of group.issue_ids || []) result.assignments[id] = group.name
    result.summaries[group.name] = group.summary || ''
    result.representatives[group.name] = [...(group.representative_issue_ids || [])]
  }
  for (const field of Object.keys(result))
    Object.assign(result[field], JSON.parse(JSON.stringify(saved[field] || {})))
  for (const name of Object.keys(result.representatives))
    result.representatives[name] = safetyRepresentativeIds(category, result, name)
  return result
}

export function safetyGroupingEdited(draft = {}, baseline = {}) {
  return ['assignments', 'summaries'].some((field) => {
    const before = baseline[field] || {},
      after = draft[field] || {}
    return [...new Set([...Object.keys(before), ...Object.keys(after)])].some(
      (key) => before[key] !== after[key],
    )
  })
}

export function safetyMoveIssue(override, id, name) {
  override.assignments[id] = name
  for (const [group, ids] of Object.entries(override.representatives || {}))
    if (group !== name && ids.some((value) => Number(value) === Number(id)))
      override.representatives[group] = ids.filter((value) => Number(value) !== Number(id))
}

export function safetyFixedCategories(categories = [], mode) {
  return categories.filter(
    (item) =>
      item.mode === mode && item.category !== '__typical__' && !item.category.startsWith('topic:'),
  )
}

export function safetySlotLimit(category) {
  if (category?.category?.startsWith('topic:')) return 3
  if ([3, 6].includes(category?.slot_limit)) return category.slot_limit
  return category?.mode === 'onsite' &&
    ['devices', 'other', '设备设施', '其他隐患类'].includes(category.category)
    ? 6
    : 3
}

export function safetySelectedGroup(groups, selected = '') {
  return (
    groups.find((group) => group.name === selected && group.count)?.name ||
    groups.find((group) => group.count)?.name ||
    groups[0]?.name ||
    ''
  )
}

export function safetyRepresentativeIds(category, override, name, limit = 6) {
  const eligible = new Set(
    (category?.issues || [])
      .filter((issue) => override?.assignments?.[issue.issue_id] === name)
      .map((issue) => Number(issue.issue_id)),
  )
  return [...new Set((override?.representatives?.[name] || []).map(Number))]
    .filter((id) => eligible.has(id))
    .slice(0, limit)
}

export function safetyRepresentativeOrder(category, override, name, limit = 6, manual = {}) {
  const group = category?.analysis?.groups?.find((item) => item.name === name)
  const ready = category?.analysis?.representatives_ready
  const explicit =
    manual.representatives?.[name] ||
    (group?.representative_source === 'manual' ? override?.representatives?.[name] : [])
  const priority = safetyRepresentativeIds(
    category,
    ready
      ? override
      : { assignments: override?.assignments, representatives: { [name]: explicit } },
    name,
  )
  const eligible = (category?.issues || [])
    .filter((issue) => override?.assignments?.[issue.issue_id] === name && issue.issue_photo)
    .map((issue) => Number(issue.issue_id))
  const fallback = ready
    ? [
        ...(group?.ai_representative_issue_ids || group?.representative_issue_ids || []).map(
          Number,
        ),
        ...eligible.sort((a, b) => a - b),
      ]
    : []
  return [...new Set([...priority, ...fallback])]
    .filter((id) => eligible.includes(id))
    .slice(0, limit)
}

// Match report slots: one image per top monthly group; fixed sections fill in rounds.
export function safetyPptPicks(category, override, monthly = false, manual = {}) {
  const groups = safetySubgroups(category, override).filter((group) => group.count)
  const choices = (monthly ? groups.slice(0, 3) : groups).map((group) => ({
    name: group.name,
    ids: safetyRepresentativeOrder(category, override, group.name, 6, manual),
  }))
  const result = [],
    limit = safetySlotLimit(category)
  for (let round = 0; round < (monthly ? 1 : limit); round++) {
    for (const group of choices) {
      if (group.ids[round] !== undefined)
        result.push({ name: group.name, issue_id: group.ids[round] })
      if (result.length === limit) return result
    }
  }
  return result
}

export function safetyRequirementChanges(standards = [], draft = {}) {
  return standards
    .filter((row) => Object.hasOwn(draft, row.key) && draft[row.key] !== (row.requirement || ''))
    .map((row) => ({
      key: row.key,
      source_signature: row.source_signature,
      revision: row.revision,
      requirement: draft[row.key],
    }))
}

export function safetyUpdatedAt(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
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

export function videoTypicalGroups(category) {
  const eligible = new Set((category?.issues || []).map((i) => Number(i.issue_id)))
  return (category?.analysis?.groups || [])
    .map((group) => {
      const issue_ids = [...new Set(group.issue_ids.map(Number))].filter((id) => eligible.has(id))
      return {
        ...group,
        issue_ids,
        count: issue_ids.length,
        percentage: eligible.size ? ((100 * issue_ids.length) / eligible.size).toFixed(1) : '0.0',
      }
    })
    .filter((group) => group.count)
    .sort((a, b) => b.count - a.count || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))
}

export function videoTypicalSelection(saved, groups) {
  return groups.find((group) => group.name === saved) || groups[0] || null
}

export function videoTypicalIssue(issues, group, saved) {
  const ids = new Set(group?.issue_ids || [])
  const photos = issues
    .filter((issue) => issue.mode === 'video' && ids.has(issue.issue_id) && issue.issue_photo)
    .sort((a, b) => a.issue_id - b.issue_id)
  return photos.find((issue) => issue.issue_id === saved) || photos[0] || null
}
