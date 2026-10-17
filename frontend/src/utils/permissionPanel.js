import { PAGE_VISIBILITY_GROUPS } from '../config/pageVisibilityCatalog.js'

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
const categoryAliases = { '报告生成': 'AI报告生成', '证照管理': '站点证照有效期管理', '培训系统': '督导组内部培训系统' }
const categoryOrder = PAGE_VISIBILITY_GROUPS.flatMap((group) => group.pages.map((page) => categoryAliases[page.title] || page.title))

export function sortPermissionGroups(groups) {
  const rank = (category) => {
    if (category === '巡检信息显示') return categoryOrder.indexOf('巡检问题列表') + 0.5
    const index = categoryOrder.indexOf(category)
    return index < 0 ? categoryOrder.length : index
  }
  return [...groups].sort((a, b) => rank(a.category) - rank(b.category))
}
