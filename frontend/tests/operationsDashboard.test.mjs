import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate, compileScript } from '@vue/compiler-sfc'
import { operationsPages } from '../src/config/operationsCatalog.js'
import { auditProgress, intakeMetrics } from '../src/utils/operationsIntake.js'

test('collecting month shows registration metrics even before the first audit', () => {
  const data = {
    summary: {
      total: 180,
      live: 180,
      pending_audit: 180,
      reviewed: 0,
      valid: 0,
      closed: 0,
      destroyed: 0,
      discovery_stations: 32,
      active_days: 8,
    },
    records: { stations: 42, records: 68 },
    highlight_summary: { count: 6, pending: 6, approved: 0, rejected: 0 },
  }
  const metrics = intakeMetrics(data)
  assert.deepEqual(
    metrics.map((r) => r.value),
    [42, 180, 180, 32, 8, 6],
  )
  assert.equal(auditProgress(data.summary), 0)
  assert.ok(metrics.every((r) => !r.label.includes('闭环') && !r.label.includes('有效问题')))
})
test('empty scope and missing record rights never fabricate coverage or percentages', () => {
  const data = {
    summary: {
      total: 0,
      live: 0,
      pending_audit: 0,
      reviewed: 0,
      destroyed: 0,
      discovery_stations: 0,
      active_days: 0,
    },
    records: null,
    highlight_summary: { count: 0, pending: 0, approved: 0, rejected: 0 },
  }
  assert.equal(intakeMetrics(data)[0].value, '—')
  assert.equal(auditProgress(data.summary), 0)
  assert.equal(auditProgress({ total: 10, reviewed: 7 }), 70)
  assert.deepEqual(intakeMetrics(null), [])
})
test('primary panels drill down into pending-inclusive data, workflow remains secondary', () => {
  const source = readFileSync(
    new URL('../src/views/operations/OperationsDashboardView.vue', import.meta.url),
    'utf8',
  )
  assert.match(source, /trendY\(point.registered\)/)
  assert.match(source, /live: '1'/)
  assert.match(source, /<details class="downstream">/)
  assert.match(source, /当前在库问题/)
  assert.ok(!source.includes("showDetails(region + ' · 有效问题'"))
  assert.ok(!source.includes('closurePercent'))
})

for (const component of ['OperationsDashboardView', 'RegionTable']) {
  test(`${component} compiles`, () => {
    const filename = new URL(`../src/views/operations/${component}.vue`, import.meta.url)
    const { descriptor, errors } = parse(readFileSync(filename, 'utf8'))
    assert.deepEqual(errors, [])
    assert.deepEqual(
      compileTemplate({
        source: descriptor.template.content,
        filename: filename.pathname,
        id: component,
      }).errors,
      [],
    )
    assert.doesNotThrow(() => compileScript(descriptor, { id: component }))
  })
}
test('one cockpit permission with guarded redirects from retired menus', () => {
  assert.equal(operationsPages.length, 1)
  assert.equal(operationsPages[0].permission, 'view_operations_overview')
  assert.equal(operationsPages[0].title, '运营驾驶舱')
  assert.ok(
    operationsPages.every(
      (page) => page.path.startsWith('/operations/') && page.permission !== 'view_station_map',
    ),
  )
  const router = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  assert.ok(router.includes('hasPermission(role, permissions, operationsPage.permission)'))
  assert.ok(
    router.includes("{ path: '/operations/rectification', redirect: '/operations/overview' }"),
  )
  assert.ok(router.includes("{ path: '/operations/insights', redirect: '/operations/overview' }"))
  const catalog = readFileSync(
    new URL('../src/config/pageVisibilityCatalog.js', import.meta.url),
    'utf8',
  )
  assert.ok(catalog.includes('...operationsPages.map'))
})
