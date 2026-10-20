import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import {
  filterScheduleRows,
  inspectorPreview,
  scheduleCellEditable,
  scheduleCounts,
} from '../src/utils/inspectionSchedule.js'

const people = [1, 2, 3].map((id) => ({ id, display_name: '人员' + id }))
const completed = { status: 'completed', assignees: [people[0]], completed_inspectors: people }
const assigned = { status: 'assigned', assignees: [people[1]], completed_inspectors: [] }
const rows = [
  { region: '松金', station_name: '甲站', cells: { a: completed, b: assigned } },
  {
    region: '浦东',
    station_name: '乙站',
    cells: { a: { status: 'unassigned' }, b: { status: 'unavailable' } },
  },
]

test('completed cells display actual people, not the planned person; long lists have a count', () => {
  assert.equal(inspectorPreview(completed), '人员1、人员2 等3人')
  assert.equal(inspectorPreview(assigned), '人员2')
  assert.equal(inspectorPreview({ status: 'unassigned' }), '')
  assert.equal(scheduleCellEditable(completed, true), false)
  assert.equal(scheduleCellEditable(assigned, true), true)
  assert.equal(scheduleCellEditable(assigned, false), false)
  assert.equal(scheduleCellEditable({ status: 'unavailable' }, true), false)
})
test('local filters intersect and preserve business roster order; summary excludes unavailable', () => {
  assert.deepEqual(filterScheduleRows(rows, '', ''), rows)
  assert.deepEqual(filterScheduleRows(rows, '松金', '甲', 'assigned'), [rows[0]])
  assert.deepEqual(filterScheduleRows(rows, '浦东', '', 'completed'), [])
  assert.deepEqual(scheduleCounts(rows), { completed: 1, assigned: 1, unassigned: 1 })
})
test('new independent rights replace retired plan routes and no longer render plan todos', () => {
  const router = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  const app = readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8')
  assert.match(router, /InspectionScheduleView/)
  assert.match(router, /view_inspection_schedule/)
  assert.doesNotMatch(app, /planAssignmentPending|plan-todo|view_inspection_plans/)
  const panel = readFileSync(
    new URL('../src/components/InspectionSchedulePanel.vue', import.meta.url),
    'utf8',
  )
  assert.match(panel, /revision: selection.value.revision/)
  assert.match(panel, /controller\?\.abort\(\)/)
  assert.match(panel, /polling.dispose\(\)/)
})

const panelSource = readFileSync(
  new URL('../src/components/InspectionSchedulePanel.vue', import.meta.url),
  'utf8',
)
test('cached panels pause and abort when inactive; returning reuses fresh data and refreshes stale data', () => {
  const hooks = {}
  const calls = { load: 0, start: 0, pause: 0, abort: 0, close: 0 }
  const context = vm.createContext({
    active: false, online: { value: true }, navigator: { onLine: true },
    board: { value: null }, error: { value: '' }, loading: { value: true },
    lastSyncedAt: 1000, serial: 0, switchTimer: 7, peopleSerial: 0, peopleController: null,
    Date: { now: () => 2000 }, clearTimeout: () => {},
    controller: { abort: () => calls.abort++ },
    polling: { start: () => calls.start++, pause: () => calls.pause++ },
    loadBoard: async () => { calls.load++ },
    closeCell: (force) => { assert.equal(force, true); calls.close++ },
    onActivated: (fn) => { hooks.activate = fn },
    onDeactivated: (fn) => { hooks.deactivate = fn },
  })
  vm.runInContext(
    panelSource.slice(panelSource.indexOf('onActivated(() =>'), panelSource.indexOf('onBeforeUnmount(() =>')),
    context,
  )
  hooks.activate()
  assert.equal(context.active, true)
  assert.equal(calls.load, 1)
  hooks.deactivate()
  assert.equal(context.active, false)
  assert.equal(context.loading.value, false)
  assert.equal(context.serial, 1)
  assert.deepEqual(calls, { load: 1, start: 1, pause: 1, abort: 1, close: 1 })
  context.board.value = { rows: [] }
  hooks.activate()
  assert.equal(calls.load, 1, 'a fresh cached board must not refetch on every tab switch')
  context.Date.now = () => 61000
  hooks.activate()
  assert.equal(calls.load, 2, 'a board at least one minute old must be checked again')
  context.Date.now = () => 2000
  context.error.value = 'previous request failed'
  hooks.activate()
  assert.equal(calls.load, 3, 'reactivating an errored board must retry')
})

test('inactive panels cannot poll, including after network and visibility events', () => {
  let options
  const context = vm.createContext({
    active: false, disposed: false, document: { hidden: false },
    online: { value: true }, blocked: { value: false }, saving: { value: false }, shelfSaving: { value: false }, dialog: { value: null },
    loadBoard: () => {}, createAdaptivePolling: (value) => { options = value },
  })
  vm.runInContext(
    panelSource.slice(panelSource.indexOf('const polling ='), panelSource.indexOf('function visibilityChanged')),
    context,
  )
  assert.equal(options.canRun(), false)
  context.active = true
  assert.equal(options.canRun(), true)
  for (const ref of [context.online, context.blocked, context.saving, context.shelfSaving]) {
    ref.value = !ref.value
    assert.equal(options.canRun(), false)
    ref.value = !ref.value
  }
  context.document.hidden = true
  assert.equal(options.canRun(), false)
})

test('schedule has one active cached panel, all rows in page flow, and responsive cards without table scrollers', () => {
  const page = readFileSync(new URL('../src/views/inspection/InspectionScheduleView.vue', import.meta.url), 'utf8')
  assert.match(page, /<KeepAlive :max="2">/)
  assert.equal((page.match(/<InspectionSchedulePanel\b/g) || []).length, 1)
  assert.match(page, /:key="activeMode \+ ':' \+ refreshKey" :mode="activeMode"/)
  assert.match(page, /role="tablist"/)
  assert.match(panelSource, /role="tabpanel"/)
  assert.match(panelSource, /v-for="row in rows"/)
  assert.doesNotMatch(panelSource, /matrix-scroll|min-width: (?:1160|1030|780|630)px/)
  const layoutStyles = panelSource.slice(panelSource.indexOf('.schedule-panel {'), panelSource.indexOf('.schedule-cell-dialog {'))
  assert.doesNotMatch(layoutStyles, /overflow: (?:auto|scroll|hidden)|max-height:/)
  assert.match(layoutStyles, /top: calc\(var\(--schedule-sticky-top/)
  assert.match(panelSource, /@container \(max-width: 760px\)/)
})
