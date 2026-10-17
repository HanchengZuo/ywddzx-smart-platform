import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compileScript, compileTemplate, parse } from '@vue/compiler-sfc'
import { directoryPageNumbers, filterDirectoryUsers, permissionConfiguration, permissionScopeDetail, permissionSummary, roleLabelFor, userPermissionGroups, userRegions } from '../src/utils/userDirectory.js'

const roles = [{ value: 'supervisor_manager', label: '督导组管理人员' }, { value: 'station_manager', label: '站点账号' }, { value: 'area_account', label: '片区账号' }]
const catalog = [
  { key: 'view_expert_qa', category: '专家问答', name: '查看页面', description: '全局业务资料' },
  { key: 'view_operations_overview', category: '运营驾驶舱', name: '查看页面', description: '授权数据范围' },
  { key: 'limit_issue_inspection_table_scope', category: '巡检问题列表', name: '限定检查表范围' },
  { key: 'limit_issue_station_region_scope', category: '巡检问题列表', name: '限定片区' },
  { key: 'view_own_inspection_issues', category: '巡检问题列表', name: '查看本站' },
]
const accounts = [
  { id: 1, username: 'root', role: 'root', has_permission_overrides: true, permissions: {}, updated_at: '2026-10-16 09:00' },
  { id: 35335, username: 'yqy', real_name: '杨经理', phone: '13800000001', role: 'supervisor_manager', has_permission_overrides: true, permissions: { view_expert_qa: true }, updated_at: '2026-10-17 08:00' },
  { id: 3, username: 'pudong', real_name: '浦东片区', role: 'area_account', permissions: { limit_issue_station_region_scope: true }, station_region_scope_values: { limit_issue_station_region_scope: ['浦东管理片区'], disabled_scope: ['不应匹配的片区'] } },
  { id: 4, username: 'station', role: 'station_manager', station_id: 10, station_name: '示例加油站', station_region: '浦东管理片区', permissions: { view_own_inspection_issues: true } },
]

test('directory supports ID, identity, phone, role, station and effective region search', () => {
  for (const [keyword, expected] of [['35335', [35335]], ['YQY', [35335]], ['杨经理', [35335]], ['13800000001', [35335]], ['管理人员', [35335]], ['示例加油站', [4]], ['浦东管理片区', [3, 4]]]) {
    assert.deepEqual(filterDirectoryUsers(accounts, { keyword }, roles).map(user => user.id), expected)
  }
  assert.deepEqual(filterDirectoryUsers(accounts, { keyword: '不应匹配的片区' }, roles), [])
  assert.deepEqual(userRegions(accounts[2]), ['浦东管理片区'])
})

test('role, region and configuration filters intersect without inferring unrestricted scope', () => {
  assert.deepEqual(filterDirectoryUsers(accounts, { region: '浦东管理片区', role: 'station_manager', configuration: 'template' }, roles).map(user => user.id), [4])
  assert.deepEqual(filterDirectoryUsers(accounts, { region: '浦东管理片区', role: 'supervisor_manager' }, roles), [])
  assert.deepEqual(filterDirectoryUsers(accounts, { configuration: 'builtin' }, roles).map(user => user.id), [1])
  assert.deepEqual(filterDirectoryUsers(accounts, { configuration: 'custom' }, roles).map(user => user.id), [35335])
  assert.equal(permissionConfiguration(accounts[0]), 'builtin')
  assert.equal(roleLabelFor(roles, 'area_account'), '片区账号')
})

test('sorts are deterministic and never mutate the source or default server role order', () => {
  const before = structuredClone(accounts)
  assert.deepEqual(filterDirectoryUsers(accounts, {}, roles).map(user => user.id), [1, 35335, 3, 4])
  assert.deepEqual(filterDirectoryUsers(accounts, { sort: 'updated' }, roles).map(user => user.id), [35335, 1, 3, 4])
  assert.equal(filterDirectoryUsers(accounts, { sort: 'name' }, roles).length, accounts.length)
  assert.deepEqual(accounts, before)
})

test('permission counters use the effective server result, and root remains all-enabled', () => {
  assert.deepEqual(permissionSummary(accounts[1], catalog), { enabled: 1, total: 5, disabled: 4, kind: 'custom', label: '个性化配置' })
  assert.equal(permissionSummary(accounts[0], catalog).enabled, 5)
  assert.equal(permissionSummary(accounts[0], catalog).disabled, 0)
  assert.equal(permissionSummary({}, []).total, 0)
})

test('permission detail retains effective denials even if the raw individual setting was enabled', () => {
  const user = { ...accounts[1], permissions: { view_expert_qa: false, view_operations_overview: true }, permission_overrides: { view_expert_qa: true } }
  const before = structuredClone(user)
  const groups = userPermissionGroups(user, catalog, [], { view_operations_overview: true })
  assert.deepEqual(groups.map(group => group.category), ['运营驾驶舱', '专家问答', '巡检问题列表'])
  assert.equal(groups[0].items[0].source, '角色模板')
  assert.equal(groups[1].items[0].source, '个人设置')
  assert.equal(groups[1].items[0].enabled, false)
  assert.equal(groups[2].items[0].source, '系统默认')
  assert.deepEqual(user, before)
  assert.ok(userPermissionGroups(accounts[0], catalog, []).every(group => group.items.every(item => item.enabled && item.source === '内置权限')))
  assert.deepEqual(userPermissionGroups(null, catalog, []), [])
})

test('scope detail shows effective table and region names, including missing/retired references', () => {
  const user = { permissions: { limit_issue_inspection_table_scope: true, limit_issue_station_region_scope: true }, inspection_table_scope_ids: { limit_issue_inspection_table_scope: [9, 99] }, station_region_scope_values: { limit_issue_station_region_scope: ['浦东管理片区'] } }
  const tables = [{ id: 9, table_name: '非油检查表', checklist_mode_label: '现场检查' }]
  assert.deepEqual(permissionScopeDetail(user, 'limit_issue_inspection_table_scope', tables).values, ['非油检查表 · 现场检查', '检查表 ID：99（已停用或不在当前目录）'])
  assert.deepEqual(permissionScopeDetail(user, 'limit_issue_station_region_scope', tables).values, ['浦东管理片区'])
  assert.equal(permissionScopeDetail(user, 'view_expert_qa', tables), null)
  assert.equal(permissionScopeDetail({ permissions: {} }, 'limit_issue_inspection_table_scope', tables), null)
  assert.deepEqual(permissionScopeDetail({ permissions: { limit_issue_inspection_table_scope: true } }, 'limit_issue_inspection_table_scope', tables).values, ['未配置有效范围'])
})

test('own-station scope and root are represented honestly, not as made-up all-station grants', () => {
  assert.deepEqual(permissionScopeDetail(accounts[3], 'view_own_inspection_issues', []).values, ['示例加油站'])
  assert.deepEqual(permissionScopeDetail({ permissions: { view_own_inspection_issues: true } }, 'view_own_inspection_issues', []).values, ['未绑定站点，无法访问本站数据'])
  assert.deepEqual(permissionScopeDetail(accounts[0], 'limit_issue_inspection_table_scope', []).values, ['root 不受此范围限制'])
})

test('pagination has a bounded five-page window at start, middle, end and empty results', () => {
  assert.deepEqual(directoryPageNumbers(1, 24), [1, 2, 3, 4, 5])
  assert.deepEqual(directoryPageNumbers(12, 24), [10, 11, 12, 13, 14])
  assert.deepEqual(directoryPageNumbers(24, 24), [20, 21, 22, 23, 24])
  assert.deepEqual(directoryPageNumbers(1, 2), [1, 2])
  assert.deepEqual(directoryPageNumbers(1, 0), [])
})

for (const name of ['UserDirectory', 'UserAccountActions', 'UserPermissionDetailsDialog']) {
  test(`${name} template and script compile with actual binding metadata`, () => {
    const path = new URL(`../src/components/${name}.vue`, import.meta.url)
    const { descriptor, errors } = parse(readFileSync(path, 'utf8'))
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: name })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: path.pathname, id: name, compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  })
}

test('permission inspector is read-only and has modal focus and teardown handling, never writes or fetches', () => {
  const source = readFileSync(new URL('../src/components/UserPermissionDetailsDialog.vue', import.meta.url), 'utf8')
  assert.match(source, /showModal\(\)/)
  assert.match(source, /onBeforeUnmount/)
  assert.match(source, /@cancel.prevent/)
  assert.doesNotMatch(source, /axios|fetch\(|localStorage|sessionStorage|type="checkbox"/)
  assert.match(source, /props\.user\?\.id/)
  const parent = readFileSync(new URL('../src/views/management/UserDataManagementView.vue', import.meta.url), 'utf8')
  assert.match(parent, /users\.value\.find\(user => user\.id === permissionDetailsId\.value\)/)
  assert.match(parent, /const editorOpen = ref\(false\)/)
  assert.match(parent, /!editorOpen && editorHasDraft/)
  assert.match(parent, /const editorHasDraft = computed/)
  assert.match(parent, /@edit="startEdit" @reset="openPasswordReset" @delete="deleteUser"/)
})
