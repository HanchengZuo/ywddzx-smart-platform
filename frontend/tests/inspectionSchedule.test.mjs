import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import {
  filterScheduleRows,
  inspectorPreview,
  scheduleCellEditable,
  scheduleCounts,
  stationScheduleProgress,
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
  assert.deepEqual(scheduleCounts(rows), { completed: 0, assigned: 1, unassigned: 1, total: 2,
    partialCompleted: 1, partialAssigned: 0, blocked: 1 })
})

test('station counts are mutually exclusive; partial inspection does not mean station completion', () => {
  const row = statuses => ({ cells: Object.fromEntries(statuses.map((status, i) => [i, { status }])) })
  const cases = [
    [Array(6).fill('completed'), 'completed', false, false],
    [Array(3).fill('assigned'), 'assigned', false, false],
    [['completed', ...Array(5).fill('assigned')], 'assigned', true, false],
    [['completed', ...Array(5).fill('unassigned')], 'unassigned', true, false],
    [['assigned', 'unassigned', 'unassigned'], 'unassigned', false, true],
    [['completed', 'assigned', 'unassigned'], 'unassigned', true, true],
  ]
  const stations = cases.map(([statuses]) => row(statuses))
  cases.forEach(([, status, partialCompleted, partialAssigned], i) => {
    const progress = stationScheduleProgress(stations[i])
    assert.equal(progress.status, status)
    assert.equal(progress.partialCompleted, partialCompleted)
    assert.equal(progress.partialAssigned, partialAssigned)
  })
  const counts = scheduleCounts(stations)
  assert.deepEqual(counts, { completed: 1, assigned: 2, unassigned: 3, total: 6,
    partialCompleted: 3, partialAssigned: 2, blocked: 0 })
  assert.equal(counts.completed + counts.assigned + counts.unassigned, counts.total)
})

test('annual video exemptions are distinct from missing/disabled required checklists', () => {
  const site = { status: 'completed', applicable: true }
  const exempt = { cells: { site, video: { status: 'unavailable', applicable: false } } }
  assert.equal(stationScheduleProgress(exempt).status, 'completed')
  assert.equal(stationScheduleProgress(exempt).total, 1)
  const monitoredDown = { cells: { site, video: { status: 'unassigned', applicable: true } } }
  assert.equal(stationScheduleProgress(monitoredDown).status, 'unassigned')
  assert.equal(stationScheduleProgress(monitoredDown).partialCompleted, true)
  const missing = { cells: { site, other: { status: 'unavailable', applicable: true } } }
  assert.equal(stationScheduleProgress(missing).status, 'unassigned')
  assert.equal(stationScheduleProgress(missing).blocked, true)
  assert.equal(stationScheduleProgress({ cells: {} }).status, 'unassigned')
  assert.equal(stationScheduleProgress({ cells: {} }).blocked, true)
})

test('station state filters agree with counters and auxiliary partial-state filters preserve row order', () => {
  const stations = [
    { station_name: '甲', region: '松金', cells: { a: { status: 'completed' }, b: { status: 'assigned' } } },
    { station_name: '乙', region: '浦东', cells: { a: { status: 'completed' }, b: { status: 'completed' } } },
    { station_name: '丙', region: '松金', cells: { a: { status: 'completed' }, b: { status: 'unassigned' } } },
    { station_name: '丁', region: '松金', cells: { a: { status: 'assigned' }, b: { status: 'unassigned' } } },
    { station_name: '戊', region: '松金', cells: { a: { status: 'unavailable', applicable: true } } },
  ]
  const counts = scheduleCounts(stations)
  for (const state of ['completed', 'assigned', 'unassigned']) {
    const filtered = filterScheduleRows(stations, '', '', state)
    assert.equal(filtered.length, counts[state])
    assert.equal(scheduleCounts(filtered)[state], filtered.length)
  }
  assert.deepEqual(filterScheduleRows(stations, '', '', 'partial_completed').map(r => r.station_name), ['甲', '丙'])
  assert.deepEqual(filterScheduleRows(stations, '', '', 'partial_assigned').map(r => r.station_name), ['丁'])
  assert.deepEqual(filterScheduleRows(stations, '松金', '戊', 'blocked').map(r => r.station_name), ['戊'])
})

test('every combination of six checklist states counts each station once, never each cell', () => {
  const states = ['completed', 'assigned', 'unassigned', 'unavailable']
  for (let code = 0; code < 4 ** 6; code++) {
    let n = code
    const cells = {}
    for (let i = 0; i < 6; i++) { cells[i] = { status: states[n % 4], applicable: true }; n = Math.floor(n / 4) }
    const station = { cells }
    const progress = stationScheduleProgress(station)
    const counts = scheduleCounts([station])
    assert.equal(counts.completed + counts.assigned + counts.unassigned, 1)
    assert.equal(counts[progress.status], 1)
    if (progress.status === 'completed') assert.ok(Object.values(cells).every(c => c.status === 'completed'))
    if (progress.status === 'assigned') assert.ok(Object.values(cells).every(c => ['completed', 'assigned'].includes(c.status)))
  }
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
test('all schedule panels show station totals and explain partial completion without cell counters', () => {
  const template = panelSource.slice(0, panelSource.indexOf('<script setup>'))
  assert.doesNotMatch(template, /按单元格计数|有已检查项|有已排班项|有待排班项/)
  assert.match(template, /counts\.total/)
  assert.match(template, /每站只计一次/)
  assert.match(template, /全部应检表已检查/)
  assert.match(template, /剩余应检表全已安排/)
  assert.match(template, /counts\.partialCompleted/)
  assert.match(template, /counts\.partialAssigned/)
  assert.match(template, /value="partial_completed"/)
})
test('schedule hides roster diagnostics and separates adjacent colored cells on desktop and mobile', () => {
  const template = panelSource.slice(0, panelSource.indexOf('<script setup>'))
  assert.doesNotMatch(template, /board\.roster_total|board\.excluded_stations|纳入设置由站点基础档案维护/)
  assert.match(template, /mode === 'annual'/, 'annual metering instructions remain visible')
  assert.match(panelSource, /border-bottom: 2px solid var\(--matrix-grid\)/)
  assert.match(panelSource, /border-right: 2px solid var\(--matrix-grid\)/)
  const mobile = panelSource.slice(panelSource.indexOf('@container (max-width: 760px)'))
  assert.match(mobile, /\.schedule-matrix \.station-row\s*\{[^}]*gap: 2px;[^}]*background: var\(--matrix-grid\)/)
  assert.match(mobile, /\.schedule-matrix\.online \.matrix-cell:last-child\s*\{\s*grid-column: 1 \/ -1;/)
  assert.match(panelSource, /\.schedule-matrix \.completed\s*\{\s*background: #d3f1df;/)
  assert.match(panelSource, /\.schedule-matrix \.assigned\s*\{\s*background: #ffe0df;/)
})
test('cached panels pause and abort when inactive; returning reuses fresh data and refreshes stale data', () => {
  const hooks = {}
  const calls = { load: 0, start: 0, pause: 0, abort: 0, close: 0 }
  const context = vm.createContext({
    active: false, online: { value: true }, navigator: { onLine: true },
    board: { value: null }, error: { value: '' }, loading: { value: true }, shelfSaving: {value:false},
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
  context.shelfSaving.value = true
  hooks.activate()
  assert.equal(calls.load, 2, 'reactivating during dispatch must not race an old board response against the save')
  context.shelfSaving.value = false
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
  assert.match(page, /<KeepAlive :max="3">/)
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
