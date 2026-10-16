import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { filterPermissionGroups, countEnabledPermissions, resolvePermissionCategory } from '../src/utils/permissionPanel.js'
import { PAGE_VISIBILITY_GROUPS } from '../src/config/pageVisibilityCatalog.js'

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

for (const path of ['views/management/UserDataManagementView.vue', 'components/AccountPasswordResetDialog.vue']) {
  test(`${path} template and script compile`, () => {
    const filename = new URL('../src/' + path, import.meta.url)
    const { descriptor, errors } = parse(readFileSync(filename, 'utf8'))
    assert.deepEqual(errors, [])
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'user-management' }).errors, [])
    assert.doesNotThrow(() => compileScript(descriptor, { id: 'user-management' }))
  })
}

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
