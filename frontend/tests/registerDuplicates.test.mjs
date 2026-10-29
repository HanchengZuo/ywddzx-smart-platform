import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const source = readFileSync(new URL('../src/views/inspection/RegisterView.vue', import.meta.url), 'utf8')
const handler = source.match(/const handleSubmit = async \(\) => \{[\s\S]*?\n\}/)[0]
const duplicate = (token = 'signed') => ({ response: { status: 409, data: {
  code: 'duplicate_registration', confirmation_token: token, duplicates: [{ description: '接地锈蚀' }]
} } })
function setup(responses, confirmations = [true], mode = 'yes') {
  const requests = [], toasts = [], notifications = []
  let reset = 0, dialogs = 0
  const context = {
    submitting: { value: false }, photoProcessing: { value: false }, normalizedHasIssue: { value: mode },
    form: { value: { stationId: 1, description: '新问题', isHighlight: mode === 'highlight', inspectionTableId: 2 } },
    selectedStandards: { value: [{ inspection_table_id: 2 }] },
    stations: { value: [] }, stationLocationRef: { value: { confirm: async () => true } },
    imageFile: { value: new Blob(['photo'], { type: 'image/png' }) },
    localStorage: { getItem: () => '7' },
    showSubmitToast: (...args) => toasts.push(args), resetForm: () => reset++,
    buildRegistrationSelections: () => [{ standard_id: '9000' }],
    submitMessageTimer: null, submitMessage: { value: '' }, FormData,
    Event: class { constructor(type) { this.type = type } }, window: { dispatchEvent: event => notifications.push(event.type) },
    confirmDuplicateRegistration: async () => { dialogs++; return confirmations.shift() },
    axios: { post: async (url, data) => {
      requests.push({ url, token: data.get('duplicate_confirmation'), description: data.get('description') })
      const response = responses.shift()
      if (response.response) throw response
      return response
    } }
  }
  return { submit: runInNewContext(`${handler}; handleSubmit`, context), requests, toasts, context,
    notifications, reset: () => reset, dialogs: () => dialogs }
}
const success = { data: { message: '登记成功' } }
test('location reminder cancellation keeps draft and photo, unlocks form, and does not submit', async () => {
  const state = setup([success])
  const photo = state.context.imageFile.value
  state.context.stations.value = [{ id: 1, station_name: '所选站点', longitude: 121.5, latitude: 31.2 }]
  state.context.stationLocationRef.value.confirm = async station => {
    assert.equal(station.id, 1)
    return false
  }
  await state.submit()
  assert.equal(state.requests.length, 0)
  assert.equal(state.reset(), 0)
  assert.equal(state.context.form.value.description, '新问题')
  assert.equal(state.context.imageFile.value, photo)
  assert.equal(state.context.submitting.value, false)
  state.context.stationLocationRef.value.confirm = async () => true
  await state.submit()
  assert.equal(state.requests.length, 1)
})
test('invalid registration is rejected before requesting location', async () => {
  const state = setup([success])
  state.context.form.value.stationId = ''
  state.context.stationLocationRef.value.confirm = () => assert.fail('No location for invalid draft')
  await state.submit()
  assert.equal(state.requests.length, 0)
})
test('cancel duplicate preserves draft and releases submit state without retry', async () => {
  const state = setup([duplicate()], [false])
  await state.submit()
  assert.equal(state.requests.length, 1)
  assert.equal(state.reset(), 0)
  assert.equal(state.context.form.value.description, '新问题')
  assert.equal(state.context.submitting.value, false)
})
test('continue uses acknowledgment and only clears draft after successful save', async () => {
  const state = setup([duplicate(), success])
  await state.submit()
  assert.equal(state.requests[1].token, 'signed')
  assert.equal(state.requests[1].description, '新问题')
  assert.equal(state.reset(), 1)
  assert.equal(state.context.submitting.value, false)
})
test('a concurrent new duplicate asks again with the new acknowledgment', async () => {
  const state = setup([duplicate('first'), duplicate('updated'), success], [true, true])
  await state.submit()
  assert.equal(state.dialogs(), 2)
  assert.equal(state.requests[2].token, 'updated')
  assert.equal(state.reset(), 1)
})
test('unrelated errors do not prompt or discard draft', async () => {
  const state = setup([{ response: { status: 403, data: { error: '无权限' } } }])
  await state.submit()
  assert.equal(state.dialogs(), 0)
  assert.equal(state.reset(), 0)
  assert.equal(state.toasts[0][0], '无权限')
})
test('highlight and no-issue registration retain their original endpoints', async () => {
  for (const mode of ['highlight', 'no']) {
    const state = setup([success], [], mode)
    await state.submit()
    assert.equal(state.requests[0].url, mode === 'highlight' ? '/api/highlights' : '/api/inspection-register')
    assert.equal(state.dialogs(), 0)
    assert.deepEqual(state.notifications, mode === 'highlight' ? [] : ['inspection-sign-pending-refresh'])
  }
})
test('duplicate dialog compiles and supports Escape, focus and mobile scrolling', () => {
  const filename = new URL('../src/components/RegistrationDuplicateDialog.vue', import.meta.url)
  const content = readFileSync(filename, 'utf8')
  const { descriptor, errors } = parse(content)
  assert.deepEqual(errors, [])
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'duplicates' }).errors, [])
  assert.doesNotThrow(() => compileScript(descriptor, { id: 'duplicates' }))
  assert.match(content, /@cancel.prevent="finish\(false\)"/)
  assert.match(content, /autofocus/)
  assert.match(content, /overflow: auto/)
  assert.match(source, /onBeforeUnmount\(\(\) => \{\s+resolveDuplicateWarning\(false\)/)
})
