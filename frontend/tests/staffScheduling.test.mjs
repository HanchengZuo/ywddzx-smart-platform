import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { shanghaiToday, offsetDay, cellKey, personCanSchedule, availabilityLabel, taskGroups } from '../src/utils/staffScheduling.js'
import { scheduleCellEditable } from '../src/utils/inspectionSchedule.js'

test('Shanghai dates and week navigation remain correct across UTC and year boundaries', () => {
  assert.equal(shanghaiToday(new Date('2026-12-31T17:00:00Z')), '2027-01-01')
  assert.equal(shanghaiToday(new Date('2026-10-19T00:01:00+08:00')), '2026-10-19')
  assert.equal(offsetDay('2026-12-28', 7), '2027-01-04')
  assert.equal(offsetDay('2026-01-01', -7), '2025-12-25')
})
test('only explicitly free, bound people without cross-mode work are selectable', () => {
  const person = { id: 2, available: true, planned_modes: [], actual_modes: [] }
  assert.equal(personCanSchedule(person, 'offline'), true)
  for (const patch of [{ available: null }, { available: false }, { id: null }, { planned_modes: ['online'] }, { actual_modes: [{ mode: 'online' }] }]) {
    assert.ok(!personCanSchedule({ ...person, ...patch }, 'offline'))
  }
  assert.equal(personCanSchedule({ ...person, planned_modes: ['offline'] }, 'offline'), true)
  assert.equal(availabilityLabel({ ...person, available: false, reason: '出差' }, 'offline'), '出差')
  assert.equal(availabilityLabel({ ...person, available: null }, 'offline'), '档期未确认')
  assert.equal(availabilityLabel({ ...person, planned_modes: ['online'] }, 'offline'), '已安排另一种检查')
})
test('personal tasks group only the same date, mode and station, keeping every table task', () => {
  const tasks = [
    { id: 1, scheduled_date: '2026-10-19', mode: 'offline', station_id: 2 },
    { id: 2, scheduled_date: '2026-10-19', mode: 'offline', station_id: 2 },
    { id: 3, scheduled_date: '2026-10-19', mode: 'online', station_id: 2 },
    { id: 4, scheduled_date: '2026-10-20', mode: 'offline', station_id: 2 },
  ]
  const groups = taskGroups(tasks)
  assert.deepEqual(groups.map(group => group.tasks.map(task => task.id)), [[1, 2], [3], [4]])
  assert.equal(tasks.length, 4)
})
test('real selection handlers support individual, row and visible-column selection, never completed cells', () => {
  const source = readFileSync(new URL('../src/components/InspectionSchedulePanel.vue', import.meta.url), 'utf8')
  const row = { station_id: 1, cells: { a: { status: 'unassigned' }, b: { status: 'completed' } } }
  const second = { station_id: 2, cells: { a: { status: 'assigned' }, b: { status: 'unassigned' } } }
  const columns = [{ key: 'a' }, { key: 'b' }]
  const context = vm.createContext({ multiSelect: { value: false }, selectedCells: { value: [] }, canEdit: { value: true },
    board: { value: { columns } }, rows: { value: [row] }, cellKey, scheduleCellEditable })
  vm.runInContext(source.slice(source.indexOf('function toggleMulti()'), source.indexOf('async function openBulk(')), context)
  context.toggleMulti(); context.selectRow(row)
  assert.deepEqual(Array.from(context.selectedCells.value), ['1:a'])
  assert.equal(context.rowSelected(row), true)
  context.toggleCell(row, columns[1])
  assert.deepEqual(Array.from(context.selectedCells.value), ['1:a'])
  context.selectColumn(columns[0]); assert.equal(context.selectedCells.value.length, 0)
  context.rows.value = [row, second]; context.selectColumn(columns[0])
  assert.deepEqual(Array.from(context.selectedCells.value), ['1:a', '2:a'])
  context.canEdit.value = false; context.selectRow(second)
  assert.deepEqual(Array.from(context.selectedCells.value), ['1:a', '2:a'])
})
for (const filename of ['components/AutomaticSchedule.vue', 'components/ScheduleTaskInbox.vue', 'components/InspectionSchedulePanel.vue', 'views/inspection/StaffAvailabilityView.vue']) {
  test(`dated scheduling component compiles with real bindings and responsive styles: ${filename}`, () => {
    const { descriptor, errors } = parse(readFileSync(new URL('../src/' + filename, import.meta.url), 'utf8'))
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: filename })
    const compiled = compileTemplate({ source: descriptor.template.content, filename, id: filename, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(compiled.errors, [])
    for (const style of descriptor.styles) assert.deepEqual(compileStyle({ source: style.content, filename, id: filename, scoped: true }).errors, [])
  })
}
