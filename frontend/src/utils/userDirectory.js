import { sortPermissionGroups } from './permissionPanel.js'

export const personalScopeDraft = (effective, overrides) => ({
  ...(effective || {}),
  ...Object.fromEntries(Object.entries(overrides || {}).filter(([, values]) => Array.isArray(values) && values.length)),
})

export function changePermissionOverride(overrides, key, mode, exclusiveGroups) {
  const next = { ...overrides }
  if (mode === 'inherit') delete next[key]
  else {
    next[key] = mode === 'allow'
    if (next[key]) exclusiveGroups.filter(group => group.includes(key)).forEach(group => {
      group.filter(other => other !== key && next[other] === true).forEach(other => { delete next[other] })
    })
  }
  return next
}

export function previewPersonalPermissions(base, overrides, exclusiveGroups, normalize, role) {
  const merged = { ...base, ...overrides }
  exclusiveGroups.forEach(group => {
    const chosen = group.find(key => overrides[key] === true)
    if (chosen) group.forEach(key => { merged[key] = key === chosen })
  })
  return normalize(merged, role)
}

export const permissionConfiguration = (user) => user.role === 'root' ? 'builtin' : user.has_permission_overrides ? 'custom' : 'template'
export const permissionConfigurationLabel = (user) => ({ builtin: '内置管理员', custom: '个性化配置', template: '角色模板' })[permissionConfiguration(user)]
export const roleLabelFor = (roles, role) => roles.find(item => item.value === role)?.label || role || '未设置角色'
export const userInitial = (user) => String(user.real_name || user.username || '?').trim().slice(0, 1).toUpperCase()

export function userRegions(user) {
  const configured = Object.entries(user.station_region_scope_values || {})
    .filter(([key]) => user.permissions?.[key])
    .flatMap(([, values]) => Array.isArray(values) ? values : [])
  return [...new Set([user.station_region, ...configured].filter(Boolean))]
}

export function permissionSummary(user, catalog) {
  const enabled = user.role === 'root' ? catalog.length : catalog.filter(item => Boolean(user.permissions?.[item.key])).length
  return { enabled, total: catalog.length, disabled: catalog.length - enabled, kind: permissionConfiguration(user), label: permissionConfigurationLabel(user) }
}

const normalize = (value) => String(value ?? '').toLocaleLowerCase().replace(/\s+/g, '')

export function filterDirectoryUsers(users, filters, roles) {
  const query = normalize(filters.keyword)
  const filtered = users.filter(user => (
    (!filters.role || user.role === filters.role) &&
    (!filters.region || userRegions(user).includes(filters.region)) &&
    (!filters.configuration || permissionConfiguration(user) === filters.configuration) &&
    (!query || [user.id, user.username, user.real_name, user.phone, user.station_name, roleLabelFor(roles, user.role), ...userRegions(user)]
      .some(value => normalize(value).includes(query)))
  ))
  if (filters.sort === 'name') filtered.sort((a, b) => String(a.real_name || a.username).localeCompare(String(b.real_name || b.username), 'zh-CN') || Number(a.id) - Number(b.id))
  if (filters.sort === 'updated') filtered.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')) || Number(a.id) - Number(b.id))
  return filtered
}

export function directoryPageNumbers(page, total) {
  const start = Math.max(1, Math.min(page - 2, total - 4))
  return Array.from({ length: Math.min(5, total) }, (_, index) => start + index)
}

const scopeKinds = {
  limit_issue_inspection_table_scope: 'tables', limit_record_inspection_table_scope: 'tables',
  limit_issue_station_region_scope: 'regions', limit_record_station_region_scope: 'regions', limit_certificate_station_region_scope: 'regions',
  view_own_inspection_issues: 'station', view_own_inspection_records: 'station', view_own_certificates: 'station',
}

export function permissionScopeDetail(user, permissionKey, tables) {
  const kind = scopeKinds[permissionKey]
  if (!kind || (user.role !== 'root' && !user.permissions?.[permissionKey])) return null
  if (user.role === 'root') return { title: '数据范围', values: ['root 不受此范围限制'] }
  if (kind === 'station') return { title: '绑定站点', values: [user.station_name || (user.station_id ? `站点 ID：${user.station_id}` : '未绑定站点，无法访问本站数据')] }
  const values = (kind === 'tables' ? user.inspection_table_scope_ids : user.station_region_scope_values)?.[permissionKey] || []
  return {
    title: kind === 'tables' ? '生效检查表' : '生效片区',
    values: values.length ? values.map(value => {
      if (kind !== 'tables') return String(value)
      const table = tables.find(item => String(item.id) === String(value))
      return table ? `${table.table_name}${table.checklist_mode_label && !/[（(](现场|视频)[）)]/.test(table.table_name) ? ` · ${table.checklist_mode_label}` : ''}` : `检查表 ID：${value}（已停用或不在当前目录）`
    }) : ['未配置有效范围'],
  }
}

export function userPermissionGroups(user, catalog, tables, roleOverrides = {}) {
  if (!user) return []
  const groups = new Map()
  catalog.forEach(permission => {
    const source = user.role === 'root' ? '内置权限'
      : Object.hasOwn(user.permission_overrides || {}, permission.key) ? '个人设置'
      : Object.hasOwn(roleOverrides, permission.key) ? '角色模板' : '系统默认'
    const item = { ...permission, enabled: user.role === 'root' || Boolean(user.permissions?.[permission.key]), source, scope: permissionScopeDetail(user, permission.key, tables) }
    if (!groups.has(permission.category)) groups.set(permission.category, { category: permission.category, items: [] })
    groups.get(permission.category).items.push(item)
  })
  return sortPermissionGroups([...groups.values()])
}
