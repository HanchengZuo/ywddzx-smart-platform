import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
const source = (file) => readFileSync(new URL('../src/' + file, import.meta.url), 'utf8')

test('dispatched source or field destination refuses a student move before sending any request', async () => {
  const script = source('components/DailyInspectionTeams.vue')
  for (const locked of ['source', 'target']) {
    const calls = []
    const context = vm.createContext({
      draggingStudent: { value: 10 },
      selectedStudent: { value: null },
      editable: { value: true },
      loading: { value: false },
      saving: { value: false },
      displayGroups: { value: [{ name: '外勤甲组', members: [{ id: 10 }] }] },
      personLocked: () => locked === 'source',
      groupLocked: () => locked === 'target',
      warn: (message) => calls.push(message),
      axios: {
        post() {
          throw Error('locked membership must not be submitted')
        },
      },
    })
    vm.runInContext(
      script.slice(script.indexOf('async function dropStudent'), script.indexOf('let controller,')),
      context,
    )
    await context.dropStudent({ name: '外勤乙组', leader_id: 2 })
    assert.equal(calls.length, 1)
    assert.match(calls[0], /派工.*任务实绩/)
    assert.equal(context.draggingStudent.value, null)
  }
})

test('annual quota focus clears the input display, not saved configuration, and empty blur restores it', () => {
  const script = source('components/MeteringAnnualPlan.vue')
  const context = vm.createContext({
    month: { value: 10 },
    quotas: { value: { 10: { 松金: 12 } } },
  })
  vm.runInContext(
    script.slice(script.indexOf('function clearQuotaInput'), script.indexOf('function open()')),
    context,
  )
  const event = { target: { value: '12' } }
  context.clearQuotaInput(event)
  assert.equal(event.target.value, '')
  assert.equal(context.quotas.value['10']['松金'], 12)
  context.restoreQuotaInput(event, '松金')
  assert.equal(event.target.value, '12')
  assert.match(script, /appearance: textfield/)
  assert.match(script, /-webkit-appearance: none/)
})

test('smart quota progress only includes regions with a positive current-month target', () => {
  const script = source('components/AutomaticSchedule.vue')
  const context = vm.createContext({
    preview: {
      value: {
        metering_plan: {
          regions: [
            { region: '松金', target: 2 },
            { region: '浦东', target: 0 },
          ],
        },
      },
    },
    computed: (fn) => ({
      get value() {
        return fn()
      },
    }),
  })
  vm.runInContext(
    script.slice(script.indexOf('const targetRegions'), script.indexOf('const replaceConfirmed')),
    context,
  )
  assert.equal(vm.runInContext('targetRegions.value.length', context), 1)
  assert.equal(vm.runInContext('targetRegions.value[0].region', context), '松金')
  assert.doesNotMatch(script, /<h4>今日已确认排班/)
  assert.match(source('views/inspection/InspectionScheduleView.vue'), /<TodayInspectionDispatch/)
})

test('saved daily window uses only its read endpoint and resumes polling after the request', async () => {
  const calls = [],
    script = source('components/TodayInspectionDispatch.vue')
  const context = vm.createContext({
    serial: 0,
    controller: undefined,
    disposed: false,
    AbortController,
    dialog: { value: { open: true } },
    loading: { value: false },
    error: { value: '' },
    data: { value: null },
    polling: { start: () => calls.push('poll') },
    axios: {
      get: async (url) => {
        calls.push(url)
        return { data: { day: '2026-10-22', groups: [{ mode: 'offline' }, { mode: 'online' }] } }
      },
    },
  })
  vm.runInContext(
    script.slice(script.indexOf('async function load()'), script.indexOf('function open()')),
    context,
  )
  await context.load()
  assert.deepEqual(calls, ['/api/inspection-schedule/today', 'poll'])
  assert.equal(context.data.value.groups.length, 2)
  assert.equal(context.loading.value, false)
})

test('staff save conflicts produce a transient warning and reload the cell instead of appending red retry instructions', async () => {
  const calls = [],
    script = source('views/inspection/StaffAvailabilityView.vue')
  const context = vm.createContext({
    saving: { value: false },
    editable: { value: true },
    conflict: { value: false },
    selection: { value: { person_name: '甲', day: '2026-10-22', revision: 1 } },
    historical: { value: false },
    available: { value: false },
    reason: { value: '' },
    disposed: false,
    polling: { start() {} },
    axios: {
      put: async () => {
        throw { response: { status: 409, data: { error: '当天已有排班，请先撤下。' } } }
      },
    },
    warn: (message) => calls.push(message),
    loadDetail: async () => calls.push('detail'),
    load: async () => calls.push('board'),
  })
  vm.runInContext(
    script.slice(
      script.indexOf('async function save()'),
      script.indexOf('async function onTeamsSaved'),
    ),
    context,
  )
  await context.save()
  assert.deepEqual(calls, ['当天已有排班，请先撤下。', 'detail', 'board'])
  assert.equal(context.conflict.value, false)
  assert.equal(context.saving.value, false)
  assert.doesNotMatch(script, /请关闭并重新选择/)
})
