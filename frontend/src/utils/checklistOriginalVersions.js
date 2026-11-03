export function groupOriginalVersions(items) {
  const groups = new Map()
  for (const item of items) {
    const editions = groups.get(item.logical_table_id) || []
    editions.push(item)
    groups.set(item.logical_table_id, editions)
  }
  for (const editions of groups.values()) editions.sort((a, b) => b.version_number - a.version_number)
  return groups
}

export function selectedOriginalVersions(groups, selection) {
  return [...groups.entries()].map(([id, editions]) =>
    editions.find(item => String(item.version_id) === String(selection[id])) ||
    editions.find(item => item.is_active) || editions[0])
}
