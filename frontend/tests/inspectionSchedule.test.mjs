import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
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
