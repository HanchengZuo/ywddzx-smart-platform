import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { filterPermissionGroups, countEnabledPermissions, resolvePermissionCategory, sortPermissionGroups } from '../src/utils/permissionPanel.js'
import { PAGE_VISIBILITY_GROUPS } from '../src/config/pageVisibilityCatalog.js'
import { isSupervisorRole, SUPERVISOR_ROLE_LABELS } from '../src/utils/roles.js'

const groups = [
  { category: '巡检问题列表', items: [{ key: 'view', name: '查看问题', description: '片区数据' }, { key: 'edit', name: '编辑', description: '' }] },
  { category: 'AI 报告生成', items: [{ key: 'generate', name: '生成报告', description: '重新生成' }] },
]

test('permission search matches categories, names and descriptions without discarding group settings', () => {
  assert.equal(filterPermissionGroups(groups, ''), groups)
  assert.deepEqual(filterPermissionGroups(groups, ' AI '), [groups[1]])
  assert.deepEqual(filterPermissionGroups(groups, '片区'), [groups[0]])
  assert.deepEqual(filterPermissionGroups(groups, '编辑'), [groups[0]])
  assert.deepEqual(filterPermissionGroups(groups, '不存在'), [])
  assert.equal(groups[0].items.length, 2)
})

test('category selection stays stable and falls back safely after a search', () => {
  assert.equal(resolvePermissionCategory(groups, 'AI 报告生成'), 'AI 报告生成')
  assert.equal(resolvePermissionCategory(groups, 'missing'), '巡检问题列表')
  assert.equal(resolvePermissionCategory([], '巡检问题列表'), '')
})

test('permission counts show stored switches and root full access without mutating them', () => {
  const switches = Object.freeze({ view: true, edit: false })
  assert.equal(countEnabledPermissions(groups[0], switches, 'supervisor'), 1)
  assert.equal(countEnabledPermissions(groups[0], switches, 'root'), 2)
  assert.equal(switches.edit, false)
})

for (const path of ['views/management/UserDataManagementView.vue', 'components/AccountPasswordResetDialog.vue', 'components/PermissionCategoryNav.vue']) {
  test(`${path} template and script compile`, () => {
    const filename = new URL('../src/' + path, import.meta.url)
    const { descriptor, errors } = parse(readFileSync(filename, 'utf8'))
    assert.deepEqual(errors, [])
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'user-management' }).errors, [])
    assert.doesNotThrow(() => compileScript(descriptor, { id: 'user-management' }))
  })
}

test('permission groups follow the main menu and keep unknown groups without mutating input', () => {
  const input = ['站点数据管理', '站点评分', '巡检信息显示', '专家问答', '站点地图', '运营驾驶舱', '申诉空间', 'AI报告生成', '巡检问题列表', '系统安全管理']
    .map(category => ({ category, items: [] }))
  assert.deepEqual(sortPermissionGroups(input).map(group => group.category), [
    '运营驾驶舱', '站点地图', '专家问答', '巡检问题列表', '巡检信息显示', '申诉空间', 'AI报告生成', '站点评分', '系统安全管理', '站点数据管理',
  ])
  assert.equal(input[0].category, '站点数据管理')
  assert.equal(sortPermissionGroups([{ category: 'future', items: [] }])[0].category, 'future')
})

test('both supervisor roles retain inspection affordances and distinct labels', () => {
  for (const role of ['supervisor', 'supervisor_manager']) assert.equal(isSupervisorRole(role), true)
  assert.equal(isSupervisorRole('quality_safety'), false)
  assert.equal(SUPERVISOR_ROLE_LABELS.supervisor_manager, '督导组管理人员')
  assert.equal(SUPERVISOR_ROLE_LABELS.supervisor, '督导组组员')
})

test('user and role-template editors share navigation with a bounded scrolling detail panel', () => {
  const source = readFileSync(new URL('../src/views/management/UserDataManagementView.vue', import.meta.url), 'utf8')
  assert.equal((source.match(/<PermissionCategoryNav /g) || []).length, 2)
  assert.match(source, /visibleRolePermissionGroups/)
  assert.match(source, /scrollbar-gutter: stable/)
  assert.match(source, /overflow-anchor: none/)
  assert.doesNotMatch(source, /resetAllUserPermissions|resettingPermissions|reset-permissions-to-role-defaults|一键重置权限/)
})

test('management menu and page catalog put security before users', () => {
  const source = readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8')
  assert.ok(source.indexOf('v-if="canManageSecurity"') < source.indexOf('v-if="canManageUsers"'))
  const pages = PAGE_VISIBILITY_GROUPS.find((group) => group.key === 'management').pages.map((page) => page.path)
  assert.ok(pages.indexOf('/management/security') < pages.indexOf('/management/users'))
})

test('reset dialog uses modal focus handling and clears credentials on close', () => {
  const view = readFileSync(new URL('../src/views/management/UserDataManagementView.vue', import.meta.url), 'utf8')
  const dialog = readFileSync(new URL('../src/components/AccountPasswordResetDialog.vue', import.meta.url), 'utf8')
  assert.match(view, /visible: false, target: null, credential: null, error: ''/)
  assert.match(view, /user\.role === 'root' \|\| resetPasswordDialog.loading/)
  assert.match(dialog, /showModal\(\)/)
  assert.match(dialog, /@cancel.prevent="close"/)
  assert.doesNotMatch(dialog, /localStorage|sessionStorage/)
})
