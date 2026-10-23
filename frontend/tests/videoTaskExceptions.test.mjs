import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { taskProgressGroups, inboxMetrics } from '../src/utils/inspectionTaskProgress.js'
import {
  scheduleCounts,
  stationScheduleProgress,
  filterScheduleRows,
  scheduleCellEditable,
  scheduleRowLocked,
} from '../src/utils/inspectionSchedule.js'

const read = (name) =>
  readFileSync(new URL(`../src/components/${name}.vue`, import.meta.url), 'utf8')
const source = read('ScheduleTaskInbox')
const ref = (value) => ({ value })

test('whole station video waiver removes pending tasks without counting inspections', () => {
  const tasks = [1, 2, 3].map((id) => ({
    id,
    station_id: 1,
    mode: 'online',
    scheduled_date: '2026-10-23',
    status: 'exception',
    exception_reason: '监控故障',
  }))
  const group = taskProgressGroups(tasks)[0]
  assert.equal(group.completed, 0)
  assert.equal(group.pending, 0)
  assert.equal(group.exempted, 3)
  assert.equal(group.percent, 100)
  assert.equal(group.exception.exception_reason, '监控故障')
  const metrics = inboxMetrics({
    buckets: { today_online: { total: 3, pending: 0, completed: 0 } },
    exception_counts: { today_online: 3 },
  })
  assert.equal(metrics.todayCompleted, 0)
  assert.equal(metrics.todayExempted, 3)
  assert.equal(metrics.todayPending, 0)
})

test('gray station is distinct from completed, assigned, unassigned and invalid definitions', () => {
  const row = {
    station_name: '沈浦泾南',
    region: '松金',
    cells: Object.fromEntries(
      ['safety', 'measurement', 'service'].map((k) => [
        k,
        { status: 'exception', applicable: true },
      ]),
    ),
  }
  const progress = stationScheduleProgress(row)
  assert.equal(progress.status, 'exception')
  assert.equal(progress.completed, 0)
  assert.equal(progress.remaining, 0)
  assert.equal(progress.blocked, false)
  const counts = scheduleCounts([row])
  assert.equal(counts.exception, 1)
  assert.equal(counts.completed + counts.assigned + counts.unassigned, 0)
  assert.deepEqual(filterScheduleRows([row], '', '', 'exception'), [row])
  assert.equal(scheduleRowLocked(row), true)
  assert.equal(scheduleCellEditable(row.cells.safety, true), false)
})

test('station action selects a pending video task only; submitting sends reason but never a forged owner', async () => {
  const calls = []
  const context = vm.createContext({
    exceptionDialog: ref({ showModal: () => calls.push('open'), close: () => calls.push('close') }),
    exceptionTarget: ref(null),
    exceptionReason: ref(''),
    exceptionError: ref(''),
    exceptionSaving: ref(false),
    axios: { post: async (...args) => calls.push(args) },
    disposed: false,
    serial: 0,
    controller: { abort: () => calls.push('abort') },
    loading: ref(true),
    load: async () => calls.push('reload'),
    window: { dispatchEvent: (event) => calls.push(event.type) },
    Event,
  })
  vm.runInContext(
    source.slice(source.indexOf('function openException('), source.indexOf('let permissions =')),
    context,
  )
  context.openException({ mode: 'offline', tasks: [{ id: 1, status: 'pending' }] })
  assert.equal(calls.length, 0)
  context.openException({
    mode: 'online',
    tasks: [
      { id: 1, status: 'completed' },
      { id: 2, status: 'pending' },
    ],
  })
  assert.equal(context.exceptionTarget.value.id, 2)
  context.exceptionReason.value = '  监控故障  '
  await context.saveException()
  const request = calls.find((item) => Array.isArray(item))
  assert.equal(request[0], '/api/my-schedule-tasks/2/video-exception')
  assert.deepEqual(JSON.parse(JSON.stringify(request[1])), { reason: '监控故障' })
  assert.ok(calls.includes('reload'))
  assert.ok(calls.includes('inspection-schedule-changed'))
  assert.equal(context.exceptionSaving.value, false)
})

test('failed save keeps form and reason, exposes server error and allows retry', async () => {
  let closed = false
  const context = vm.createContext({
    exceptionTarget: ref({ id: 2 }),
    exceptionReason: ref('监控故障'),
    exceptionSaving: ref(false),
    exceptionError: ref(''),
    disposed: false,
    axios: {
      post: async () => {
        throw { response: { data: { error: '派工已变化' } } }
      },
    },
    exceptionDialog: ref({ close: () => (closed = true) }),
  })
  vm.runInContext(
    source.slice(
      source.indexOf('async function saveException()'),
      source.indexOf('let permissions ='),
    ),
    context,
  )
  await context.saveException()
  assert.equal(context.exceptionError.value, '派工已变化')
  assert.equal(context.exceptionReason.value, '监控故障')
  assert.equal(context.exceptionSaving.value, false)
  assert.equal(closed, false)
})

test('all affected views compile and preserve distinct actuals, waiver reasons and station-level controls', () => {
  for (const name of [
    'ScheduleTaskInbox',
    'InspectionSchedulePanel',
    'TodayInspectionDispatch',
    'StaffDispatchDetails',
  ]) {
    const { descriptor } = parse(read(name))
    compileScript(descriptor, { id: name })
    assert.deepEqual(
      compileTemplate({ source: descriptor.template.content, filename: name + '.vue', id: name })
        .errors,
      [],
    )
  }
  assert.match(source, /group.mode === 'online' && group.pending/)
  assert.match(source, /task.status === 'pending'/)
  assert.match(source, /maxlength="500"/)
  assert.match(read('InspectionSchedulePanel'), /video_exception\?\.reason/)
})
