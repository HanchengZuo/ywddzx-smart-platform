import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { renderToString } from '@vue/server-renderer'
import { schedulingMenuPages } from '../src/config/schedulingCatalog.js'
import { operationsMenuPages, operationsPages } from '../src/config/operationsCatalog.js'
import { PAGE_VISIBILITY_GROUPS, PAGE_VISIBILITY_PAGES } from '../src/config/pageVisibilityCatalog.js'
import { sortPermissionGroups } from '../src/utils/permissionPanel.js'
import { isSupervisorRole } from '../src/utils/roles.js'

const app = readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8')
const expression = app.match(/^const visibleSchedulingPages = (.+)$/m)[1]
const resolvePages = new Function('computed', 'schedulingMenuPages', 'hasPermissionKey', 'isPageVisible', `return ${expression}`)
const fragment = app.slice(app.indexOf('<div v-if="visibleSchedulingPages.length"'), app.indexOf('<div v-if="canViewInspectionReports"'))
const render = new Function('Vue', compile(fragment, { mode: 'function', prefixIdentifiers: true }).code)(Vue)

async function menu({ role = 'area_account', permissions = {}, hidden = [], collapsed = false } = {}) {
  const visibleSchedulingPages = resolvePages(Vue.computed, schedulingMenuPages,
    key => role === 'root' || Boolean(permissions[key]), path => !hidden.includes(path))
  return renderToString(Vue.createSSRApp({ render, setup: () => ({ visibleSchedulingPages,
    sidebarCollapsed: collapsed, isActive: path => path === '/inspection/plan', go: () => {} }) }))
}

test('scheduling appears after inspection, with each existing URL listed exactly once', () => {
  const index = PAGE_VISIBILITY_GROUPS.findIndex(group => group.key === 'inspection')
  const group = PAGE_VISIBILITY_GROUPS[index + 1]
  assert.equal(group.title, '排班系统')
  assert.equal(PAGE_VISIBILITY_GROUPS[index + 2].key, 'ai')
  assert.deepEqual(group.pages.map(page => page.path), schedulingMenuPages.map(page => page.path))
  assert.deepEqual(schedulingMenuPages.map(page => [page.title, page.permission]), [
    ['排班地图', 'view_scheduling_map'], ['路网数据', 'view_driving_matrix'], ['人员档期', 'view_staff_availability'], ['巡检排班', 'view_inspection_schedule'],
  ])
  assert.equal(new Set(PAGE_VISIBILITY_PAGES.map(page => page.path)).size, PAGE_VISIBILITY_PAGES.length)
  assert.ok(!operationsMenuPages.some(page => page.key === 'scheduling-map'))
  assert.ok(!PAGE_VISIBILITY_GROUPS[index].pages.some(page => page.path === '/inspection/plan'))
  const inspection = app.indexOf('class="menu-section-title">巡检系统')
  const scheduling = app.indexOf('class="menu-section-title">排班系统')
  assert.ok(scheduling > inspection && scheduling < app.indexOf('class="menu-section-title">AI系统'))
})

test('real sidebar template renders only authorized pages and hides empty scheduling group', async () => {
  assert.doesNotMatch(await menu(), /排班系统|排班地图|路网数据|巡检排班|人员档期|<button/)
  const map = await menu({ permissions: { view_scheduling_map: true } })
  assert.match(map, /排班系统/)
  assert.match(map, /排班地图/)
  assert.doesNotMatch(map, /路网数据|巡检排班|人员档期/)
  const road = await menu({ permissions: { view_driving_matrix: true } })
  assert.match(road, /排班系统/)
  assert.match(road, /路网数据/)
  assert.doesNotMatch(road, /排班地图|巡检排班|人员档期/)
  const plan = await menu({ permissions: { view_inspection_schedule: true } })
  assert.match(plan, /巡检排班/)
  assert.match(plan, /class="nav-item active"/)
  assert.doesNotMatch(plan, /排班地图/)
  const root = await menu({ role: 'root' })
  assert.match(root, /排班地图/)
  assert.match(root, /巡检排班/)
  assert.match(root, /人员档期/)
  assert.equal((root.match(/<button /g) || []).length, 4)
})

test('page visibility still wins and collapsed navigation retains accessible titles', async () => {
  const hidden = await menu({ role: 'root', hidden: schedulingMenuPages.map(p => p.path) })
  assert.doesNotMatch(hidden, /排班系统|<button/)
  const collapsed = await menu({ role: 'root', collapsed: true, hidden: ['/inspection/scheduling-map'] })
  assert.doesNotMatch(collapsed, /排班系统|排班地图/)
  assert.match(collapsed, /title="巡检排班"/)
  assert.match(collapsed, /nav-item-icon/)
})

test('user and role permission editors inherit the same new menu order', () => {
  const groups = ['AI报告生成', '巡检排班', '路网数据', '人员档期', '排班地图', '站点证照有效期管理'].map(category => ({ category, items: [] }))
  assert.deepEqual(sortPermissionGroups(groups).map(group => group.category), [
    '站点证照有效期管理', '排班地图', '路网数据', '人员档期', '巡检排班', 'AI报告生成',
  ])
})

test('unchanged route guards keep both pages independently protected at their existing URLs', () => {
  const source = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  const guard = source.slice(source.indexOf('const canAccessPath = '), source.indexOf('const resolveFallbackPath = '))
  const canAccess = new Function('operationsPages', 'isSupervisorRole', `const hasPermission = (role, permissions, key) => role === 'root' || Boolean(permissions[key]); ${guard}; return canAccessPath`)(operationsPages, isSupervisorRole)
  for (const page of schedulingMenuPages) {
    assert.equal(canAccess(page.path, 'area_account', {}), false)
    assert.equal(canAccess(page.path, 'root', {}), true)
    assert.equal(canAccess(page.path, 'area_account', { [page.permission]: true }), true)
    const other = schedulingMenuPages.find(item => item !== page)
    assert.equal(canAccess(page.path, 'area_account', { [other.permission]: true }), false)
  }
})

test('application shell compiles with actual scheduling menu bindings', () => {
  const { descriptor, errors } = parse(app)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'scheduling-shell' })
  const result = compileTemplate({ source: descriptor.template.content, filename: 'App.vue', id: 'scheduling-shell', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(result.errors, [])
})
