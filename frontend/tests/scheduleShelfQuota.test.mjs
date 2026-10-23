import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { shelfHasCapacity } from '../src/utils/inspectionSchedule.js'
const source = (file) => readFileSync(new URL('../src/' + file, import.meta.url), 'utf8')
const ref = (value = null) => ({ value })

test('only positive whole remaining station counts are dispatchable', () => {
  for (const remaining of [1,2,10]) assert.equal(shelfHasCapacity({remaining}),true)
  for (const remaining of [0,-1,undefined,null,'1',NaN,Infinity,0.5])
    assert.equal(shelfHasCapacity({remaining}),false)
  assert.equal(shelfHasCapacity(null),false)
  const script=source('components/InspectionSchedulePanel.vue')
  assert.match(script,/shelf.value = \(response.data.shelf \|\| \[\]\).filter\(shelfHasCapacity\)/)
  assert.doesNotMatch(script,/角标仅作提醒，仍可额外手动派站/)
})

test('smart opening reads globally saved station targets before calculating any proposal', async () => {
  const script = source('components/AutomaticSchedule.vue'),
    calls = []
  const context = vm.createContext({
    day: ref(''),
    preview: ref(),
    quotaSettings: ref(),
    savedNotice: ref(''),
    error: ref(''),
    offlineCount: ref(2),
    onlineCount: ref(3),
    dialog: { value: { showModal() {} } },
    serial: 0,
    controller: undefined,
    disposed: false,
    AbortController,
    loading: ref(false),
    shanghaiToday: () => '2026-10-22',
    axios: {
      get: async (url) => {
        calls.push(url)
        return { data: { offline_count: 4, online_count: 6, revision: 2 } }
      },
    },
    createPreview: () => calls.push([context.offlineCount.value, context.onlineCount.value]),
  })
  vm.runInContext(
    script.slice(script.indexOf('async function open()'), script.indexOf('function close()')),
    context,
  )
  await context.open()
  assert.deepEqual(calls, ['/api/inspection-schedule/quotas', [4, 6]])
  assert.equal(context.quotaSettings.value.revision, 2)
})

test('calculating changed targets saves the shared revision and refreshes the scheduling board', async () => {
  const script = source('components/AutomaticSchedule.vue'),
    calls = []
  const context = vm.createContext({
    quotaSettings: ref({ offline_count: 2, online_count: 3, revision: 0 }),
    offlineCount: ref(4),
    onlineCount: ref(3),
    day: ref('2026-10-22'),
    serial: 0,
    controller: undefined,
    disposed: false,
    AbortController,
    loading: ref(false),
    error: ref(''),
    stale: ref(true),
    replaceConfirmed: ref(false),
    preview: ref(),
    window: { dispatchEvent: (event) => calls.push(event.type) },
    Event: class {
      constructor(type) {
        this.type = type
      }
    },
    axios: {
      post: async (_url, body) => {
        calls.push(body)
        return {
          data: { groups: [], quota_settings: { offline_count: 4, online_count: 3, revision: 1 } },
        }
      },
    },
  })
  vm.runInContext(
    script.slice(
      script.indexOf('async function createPreview()'),
      script.indexOf('async function confirm()'),
    ),
    context,
  )
  await context.createPreview()
  assert.equal(calls[0].save_quotas, true)
  assert.equal(calls[0].quota_revision, 0)
  assert.equal(calls[1], 'inspection-schedule-changed')
  assert.equal(context.quotaSettings.value.revision, 1)
  await context.createPreview()
  assert.equal(calls[2].save_quotas, false)
  assert.equal(calls[2].quota_revision, 1)
  assert.equal(calls.length, 3)
})

test('waiting cards show names and numeric red badges, not old station names or dates', () => {
  const script = source('components/InspectionSchedulePanel.vue')
  const card = script.slice(
    script.indexOf('v-for="item in shelf"'),
    script.indexOf('<p v-if="!shelf.length"'),
  )
  assert.match(card, /item.name/)
  assert.match(card, /class="shelf-count"/)
  assert.match(card, /item.remaining \?\? 0/)
  assert.doesNotMatch(card, /item.sourceName|item.day/)
  assert.match(script, /background: #d93445/)
  const { descriptor } = parse(script)
  assert.deepEqual(
    compileTemplate({
      source: descriptor.template.content,
      id: 'shelf-quota',
      filename: 'InspectionSchedulePanel.vue',
    }).errors,
    [],
  )
})

test('shared quota updates refresh an active board but do not interrupt an open cell edit', () => {
  const script = source('components/InspectionSchedulePanel.vue')
  let reads = 0
  const context = vm.createContext({
    active: true,
    lastSyncedAt: 50,
    loading: ref(false),
    shelfSaving: ref(false),
    saving: ref(false),
    dialog: { value: { open: false } },
    loadBoard: async () => {
      reads++
    },
  })
  vm.runInContext(
    script.slice(script.indexOf('function invalidateLinkedBoard()'), script.indexOf('</script>')),
    context,
  )
  context.invalidateLinkedBoard()
  assert.equal(reads, 1)
  assert.equal(context.lastSyncedAt, 0)
  context.dialog.value.open = true
  context.invalidateLinkedBoard()
  assert.equal(reads, 1)
  context.dialog.value.open = false
  context.active = false
  context.invalidateLinkedBoard()
  assert.equal(reads, 1)
})
