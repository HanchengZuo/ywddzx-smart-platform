export function filterPermissionGroups(groups, keyword) {
  const query = String(keyword || '').trim().toLocaleLowerCase()
  if (!query) return groups
  return groups.filter((group) => [group.category, ...group.items.flatMap((item) => [item.name, item.description])]
    .some((text) => String(text || '').toLocaleLowerCase().includes(query)))
}

export function countEnabledPermissions(group, permissions, role) {
  if (role === 'root') return group.items.length
  return group.items.filter((item) => Boolean(permissions[item.key])).length
}

export function resolvePermissionCategory(groups, current) {
  return groups.some((group) => group.category === current) ? current : (groups[0]?.category || '')
}
