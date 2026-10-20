import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import {
  shanghaiToday,
  offsetDay,
  cellKey,
  personCanSchedule,
  availabilityLabel,
  staffCellPresentation,
  staffTodaySummary,
  taskGroups,
  isCurrentPerson,
  scheduleSelfRole,
} from '../src/utils/staffScheduling.js'
import { scheduleCellEditable } from '../src/utils/inspectionSchedule.js'

test('current-user highlighting matches account IDs, never names, and distinguishes plan and actual', () => {
  assert.equal(isCurrentPerson({id:2,display_name:'重名'},'2'),true)
  assert.equal(isCurrentPerson({id:3,display_name:'重名'},2),false)
  assert.equal(isCurrentPerson({id:null},null),false)
  assert.equal(scheduleSelfRole({assignees:[{id:2}],completed_inspectors:[{id:3}]},2),'我的计划')
  assert.equal(scheduleSelfRole({assignees:[{id:3}],completed_inspectors:[{id:2}]},2),'我的实绩')
  assert.equal(scheduleSelfRole({assignees:[{id:2}],completed_inspectors:[{id:2}]},2),'我的计划及实绩')
  assert.equal(scheduleSelfRole({assignees:[{id:3}],completed_inspectors:[]},2),'')
  assert.equal(scheduleSelfRole(null,2),'')
})

test('inbox opening automatically reconciles tasks; only video can navigate to registration', async () => {
  const source = readFileSync(new URL('../src/components/ScheduleTaskInbox.vue',import.meta.url),'utf8')
  let loads=0,starts=0,opens=0
  const context=vm.createContext({dialog:{value:{showModal(){opens++}}},load(){loads++},polling:{start(){starts++}}})
  vm.runInContext(source.slice(source.indexOf('function open()'),source.indexOf('function close()')),context)
  context.open()
  assert.deepEqual([loads,starts,opens],[1,1,1])
  const template=source.slice(0,source.indexOf('<script setup>'))
  assert.match(template,/v-if="canRegister && task.mode === 'online'/)
  assert.doesNotMatch(template,/<footer>|核对完成情况/)
  assert.match(template,/currentAgenda.field_team.members/)
})

test('Shanghai dates and week navigation remain correct across UTC and year boundaries', () => {
  assert.equal(shanghaiToday(new Date('2026-12-31T17:00:00Z')), '2027-01-01')
  assert.equal(shanghaiToday(new Date('2026-10-19T00:01:00+08:00')), '2026-10-19')
  assert.equal(offsetDay('2026-12-28', 7), '2027-01-04')
  assert.equal(offsetDay('2026-01-01', -7), '2025-12-25')
})
test('only explicitly free, bound people without cross-mode work are selectable', () => {
  const person = { id: 2, available: true, planned_modes: [], actual_modes: [] }
  assert.equal(personCanSchedule(person, 'offline'), true)
  for (const patch of [
    { available: null },
    { available: false },
    { id: null },
    { planned_modes: ['online'] },
    { actual_modes: [{ mode: 'online' }] },
  ]) {
    assert.ok(!personCanSchedule({ ...person, ...patch }, 'offline'))
  }
  assert.equal(personCanSchedule({ ...person, planned_modes: ['offline'] }, 'offline'), true)
  assert.equal(
    availabilityLabel({ ...person, available: false, reason: '出差' }, 'offline'),
    '出差',
  )
  assert.equal(availabilityLabel({ ...person, available: null }, 'offline'), '档期未确认')
  assert.equal(
    availabilityLabel({ ...person, planned_modes: ['online'] }, 'offline'),
    '已安排另一种检查',
  )
})
test('personal tasks group only the same date, mode and station, keeping every table task', () => {
  const tasks = [
    { id: 1, scheduled_date: '2026-10-19', mode: 'offline', station_id: 2 },
    { id: 2, scheduled_date: '2026-10-19', mode: 'offline', station_id: 2 },
    { id: 3, scheduled_date: '2026-10-19', mode: 'online', station_id: 2 },
    { id: 4, scheduled_date: '2026-10-20', mode: 'offline', station_id: 2 },
  ]
  const groups = taskGroups(tasks)
  assert.deepEqual(
    groups.map((group) => group.tasks.map((task) => task.id)),
    [[1, 2], [3], [4]],
  )
  assert.equal(tasks.length, 4)
})
test('availability and inspection modes have distinct semantic tones, with actual records preceding plans', () => {
  const today = '2026-10-19'
  const cell = { available: true, reason: '', planned_modes: [], actual_modes: [] }
  assert.equal(staffCellPresentation(cell, today, today).tone, 'free')
  assert.equal(
    staffCellPresentation({ ...cell, available: false, reason: '出差' }, today, today).detail,
    '出差',
  )
  assert.equal(staffCellPresentation({ ...cell, available: false }, today, today).tone, 'busy')
  assert.equal(staffCellPresentation({ ...cell, available: null }, today, today).tone, 'unknown')
  assert.equal(
    staffCellPresentation({ ...cell, planned_modes: ['offline'] }, today, today).tone,
    'offline',
  )
  assert.equal(
    staffCellPresentation({ ...cell, planned_modes: ['online'] }, today, today).tone,
    'online',
  )
  const actual = staffCellPresentation(
    { ...cell, planned_modes: ['offline'], actual_modes: [{ mode: 'online', count: 3 }] },
    today,
    today,
  )
  assert.equal(actual.tone, 'online')
  assert.equal(actual.stage, '实绩')
  assert.match(actual.detail, /3 张检查表/)
  assert.equal(
    staffCellPresentation(
      {
        ...cell,
        actual_modes: [
          { mode: 'offline', count: 1 },
          { mode: 'online', count: 1 },
        ],
      },
      today,
      today,
    ).tone,
    'mixed',
  )
  assert.equal(
    staffCellPresentation({ ...cell, planned_modes: ['offline'] }, '2026-10-16', today).tone,
    'past',
    'past plans must not masquerade as actual inspections',
  )
})
test('today counters exclude every other day and never double-count actual and planned work', () => {
  const cell = { available: true, actual_modes: [], planned_modes: [] }
  const days = ['2026-10-16', '2026-10-19', '2026-10-20', '2026-10-21', '2026-10-22', '2026-10-23']
  const cells = [
    cell,
    cell,
    { ...cell, available: false },
    { ...cell, available: null },
    { ...cell, planned_modes: ['offline'], actual_modes: [{ mode: 'offline', count: 8 }] },
    {
      ...cell,
      actual_modes: [
        { mode: 'offline', count: 1 },
        { mode: 'online', count: 1 },
      ],
    },
  ]
  const board = {
    today: '2026-10-19',
    days: days.map((day) => ({ day })),
    people: [{ cells: Object.fromEntries(days.map((day, i) => [day, cells[i]])) }],
  }
  assert.deepEqual(staffTodaySummary(board), { free: 1, busy: 0, unknown: 0, offline: 0, online: 0 })
  board.people = cells.map(value => ({cells: {[board.today]: value}}))
  assert.deepEqual(staffTodaySummary(board), { free: 2, busy: 1, unknown: 1, offline: 2, online: 1 })
  assert.deepEqual(staffTodaySummary(null), { free: 0, busy: 0, unknown: 0, offline: 0, online: 0 })
})
test('browsing a historical week still displays the server-owned today counts', () => {
  const today_summary = { free: 7, busy: 3, unknown: 1, offline: 8, online: 6 }
  assert.deepEqual(staffTodaySummary({today_summary, today: '2026-10-19', people: [{cells: {'2026-10-12': {available: true}}}]}), today_summary)
})
test('staff editing always resets to the clicked individual cell and saves exactly one person-day', async () => {
  const source = readFileSync(
    new URL('../src/views/inspection/StaffAvailabilityView.vue', import.meta.url),
    'utf8',
  )
  const values = {
    available: true,
    reason: '',
    revision: 2,
    updated_at: '',
    actual_modes: [],
    planned_modes: [],
  }
  const person = {
    display_name: '步雪琼',
    cells: {
      '2026-10-19': values,
      '2026-10-20': { ...values, available: false, reason: '出差', revision: 3 },
    },
  }
  let payload,
    reloads = 0,
    opens = 0
  const context = vm.createContext({
    selection: { value: null },
    selectionState: { value: null },
    available: { value: true },
    reason: { value: '' },
    savedMeta: { value: '' },
    editable: { value: false },
    saveError: { value: '' },
    conflict: { value: false },
    saving: { value: false },
    notice: { value: '' },
    historyStatus: { value: 'auto' }, originalRecords: { value: '' }, historical: { value: false },
    board: { value: { can_edit: true, today: '2026-10-19' } },
    disposed: false,
    nextTick: async () => {},
    polling: { pause() {}, start() {} },
    dialog: {
      value: {
        showModal() {
          opens++
        },
        close() {},
      },
    },
    state: (p, day) => staffCellPresentation(p.cells[day.day], day.day, '2026-10-19'),
    axios: {
      put: async (url, body) => {
        assert.equal(url, '/api/staff-availability')
        payload = JSON.parse(JSON.stringify(body))
      },
    },
    load: async () => {
      reloads++
    },
  })
  vm.runInContext(
    source.slice(source.indexOf('async function openCell('), source.indexOf('function close()')),
    context,
  )
  vm.runInContext(
    source.slice(source.indexOf('async function save()'), source.indexOf('const polling =')),
    context,
  )
  await context.openCell(person, { day: '2026-10-20' })
  assert.equal(context.reason.value, '出差')
  await context.openCell(person, { day: '2026-10-19' })
  assert.equal(context.reason.value, '')
  assert.equal(context.available.value, true)
  await context.save()
  assert.deepEqual(payload.cells, [{ person_name: '步雪琼', day: '2026-10-19', revision: 2 }])
  assert.equal(payload.available, true)
  assert.equal(reloads, 1)
  assert.equal(opens, 2)
  context.historical.value = true
  context.historyStatus.value = 'online'
  context.selection.value = { person_name: '步雪琼', day: '2026-10-16', revision: 0 }
  await context.save()
  assert.equal(payload.history_status, 'online')
  assert.equal(Object.hasOwn(payload, 'available'), false)
  assert.equal(reloads, 2)
  context.historical.value = false
  await context.openCell(person, { day: '2026-10-20' })
  context.board.value.can_edit = false
  await context.openCell(person, { day: '2026-10-19' })
  assert.equal(context.editable.value, false)
  await context.save()
  assert.equal(reloads, 2, 'read-only dialogs cannot save')
  assert.doesNotMatch(
    source,
    /selectedPeople|selectedDays|openBatch|canBatch|type="checkbox"|批量设置档期/,
  )
})
test('manual history takes precedence only in staff display, with explicit provenance and no fabricated issue counts', () => {
  const cell = { history_status: 'online', reason: '', actual_modes: [{ mode: 'offline', count: 4 }], planned_modes: [] }
  const state = staffCellPresentation(cell, '2026-10-16', '2026-10-20')
  assert.equal(state.tone, 'online')
  assert.equal(state.stage, '人工补录')
  assert.match(state.detail, /保留原始巡检数据/)
  assert.equal(cell.actual_modes[0].mode, 'offline')
  assert.equal(staffCellPresentation({ ...cell, history_status: 'busy', reason: '培训' }, '2026-10-16', '2026-10-20').detail, '培训')
  assert.equal(staffCellPresentation({ ...cell, history_status: null }, '2026-10-16', '2026-10-20').stage, '实绩')
  assert.equal(staffCellPresentation({ ...cell, actual_modes: [] }, '2026-10-20', '2026-10-20').tone, 'unknown', 'manual history cannot override current-day availability')
})
test('multi-selection is row-only and excludes completed cells; no column selection remains', () => {
  const source = readFileSync(
    new URL('../src/components/InspectionSchedulePanel.vue', import.meta.url),
    'utf8',
  )
  const row = { station_id: 1, cells: { a: { status: 'unassigned' }, b: { status: 'completed' } } }
  const second = {
    station_id: 2,
    cells: { a: { status: 'assigned' }, b: { status: 'unassigned' } },
  }
  const columns = [{ key: 'a' }, { key: 'b' }]
  const context = vm.createContext({
    multiSelect: { value: false },
    selectedCells: { value: [] },
    canEdit: { value: true },
    board: { value: { columns } },
    rows: { value: [row] },
    cellKey,
    scheduleCellEditable,
  })
  vm.runInContext(
    source.slice(
      source.indexOf('function toggleMulti()'),
      source.indexOf('const sameIds'),
    ),
    context,
  )
  context.toggleMulti()
  context.selectRow(row)
  assert.deepEqual(Array.from(context.selectedCells.value), ['1:a'])
  assert.equal(context.rowSelected(row), true)
  context.selectRow(second)
  assert.deepEqual(Array.from(context.selectedCells.value), ['1:a', '2:a', '2:b'])
  context.selectRow(second)
  assert.deepEqual(Array.from(context.selectedCells.value), ['1:a'])
  assert.doesNotMatch(source, /selectColumn|选列|function toggleCell/)
  context.canEdit.value = false
  context.selectRow(second)
  assert.deepEqual(Array.from(context.selectedCells.value), ['1:a'])
})
for (const filename of [
  'components/AutomaticSchedule.vue',
  'components/DailyInspectionTeams.vue',
  'components/ScheduleTaskInbox.vue',
  'components/InspectionSchedulePanel.vue',
  'views/inspection/StaffAvailabilityView.vue',
]) {
  test(`dated scheduling component compiles with real bindings and responsive styles: ${filename}`, () => {
    const { descriptor, errors } = parse(
      readFileSync(new URL('../src/' + filename, import.meta.url), 'utf8'),
    )
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: filename })
    const compiled = compileTemplate({
      source: descriptor.template.content,
      filename,
      id: filename,
      compilerOptions: { bindingMetadata: script.bindings },
    })
    assert.deepEqual(compiled.errors, [])
    for (const style of descriptor.styles)
      assert.deepEqual(
        compileStyle({ source: style.content, filename, id: filename, scoped: true }).errors,
        [],
      )
  })
}
