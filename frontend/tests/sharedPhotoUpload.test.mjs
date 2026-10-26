import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { createAutoIssuePhotoComposition } from '../src/utils/imageComposer.js'

const filename = new URL('../src/components/InspectionPhotoUpload.vue', import.meta.url)
const source = readFileSync(filename, 'utf8')
const script = parse(source).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\n/gm, '')
const image = name => new File(['image'], name, { type: 'image/png' })
function setup(overrides = {}) {
  const props = reactive({ modelValue: null, label: '复核照片', idPrefix: 'review-photo', active: true, disabled: false })
  const updates = [], notices = [], released = [], scope = effectScope(), cleanup = []
  let urls = 0
  const api = scope.run(() => runInNewContext(`${script}\n;({addFiles, clear, remove, saveEditor, photos, composition, processing, finalFile, editorVisible, previewVisible})`, {
    ref, computed, watch, nextTick, File, Date, Math, Promise, window: { removeEventListener() {} },
    defineProps: () => props,
    defineEmits: () => (event, ...values) => {
      if (event === 'update:modelValue') { updates.push(values[0]); props.modelValue = values[0] }
      if (event === 'notify') notices.push(values)
    },
    defineExpose() {}, onMounted() {}, onBeforeUnmount: callback => cleanup.push(callback),
    createAutoIssuePhotoComposition,
    prepareImageFile: async file => file,
    loadImageFromFile: async () => ({ width: 800, height: 600 }),
    prepareImagePreview: async file => ({ file, previewUrl: `blob:final-${++urls}` }),
    exportIssuePhotoCompositionFile: async (_photos, _layout, name) => new File(['composite'], name, { type: 'image/jpeg' }),
    revokeObjectUrl: url => { if (url) released.push(url) },
    URL: { createObjectURL: () => `blob:source-${++urls}` },
    ...overrides,
  }))
  return { ...api, props, updates, notices, released, close: () => { cleanup.forEach(fn => fn()); scope.stop() } }
}

test('shared component compiles with its actual bindings and responsive styles', () => {
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'shared-upload' })
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'shared-upload', compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  assert.deepEqual(compileStyle({ source: descriptor.styles[0].content, filename: filename.pathname, id: 'shared-upload', scoped: true }).errors, [])
})

test('concurrent additions append rather than replace, stop at three, and can remove/recompose', async () => {
  const state = setup()
  try {
    const first = state.addFiles([image('a.png')]), second = state.addFiles([image('b.png'), image('c.png'), image('d.png')])
    assert.equal(state.processing.value, true)
    await Promise.all([first,second])
    assert.deepEqual(Array.from(state.photos.value, p => p.name), ['a.png','b.png','c.png'])
    assert.equal(state.updates.length, 2)
    assert.equal(state.finalFile.value.type, 'image/jpeg')
    assert.equal(state.processing.value, false)
    assert.ok(state.notices.some(([text]) => text.includes('忽略超出')))
    assert.equal(await state.addFiles([image('e.png')]), false)
    await state.remove(state.photos.value[1].id)
    assert.deepEqual(Array.from(state.photos.value, p => p.name), ['a.png','c.png'])
    assert.equal(state.composition.value.items.length, 2)
    state.clear()
    assert.equal(state.photos.value.length, 0)
    assert.equal(state.updates.at(-1), null)
  } finally { state.close() }
})

test('failed additions preserve the previously submitted image and release only new assets', async () => {
  const state = setup({ prepareImageFile: async file => { if (file.name === 'bad.png') throw new Error('图片损坏'); return file } })
  try {
    await state.addFiles([image('saved.png')])
    const previous = state.finalFile.value
    assert.equal(await state.addFiles([image('new.png'), image('bad.png')]), false)
    assert.equal(state.finalFile.value, previous)
    assert.equal(state.photos.value.length, 1)
    assert.equal(state.updates.length, 1)
    assert.ok(state.notices.some(([text]) => text === '图片损坏'))
  } finally { state.close() }
})

test('clear and unmount invalidate pending work and cannot reattach old photos', async () => {
  for (const action of ['clear', 'close']) {
    let resume
    const deferred = new Promise(resolve => { resume = resolve })
    const state = setup({ prepareImageFile: async file => { await deferred; return file } })
    const work = state.addFiles([image('old.png')])
    await nextTick()
    state[action]()
    resume()
    assert.equal(await work, false)
    assert.equal(state.photos.value.length, 0)
    assert.ok(state.updates.every(value => value === null))
    if (action !== 'close') state.close()
  }
})

test('restored draft preserves original bytes, and denied/hidden/modal upload ignores additions', async () => {
  const state = setup()
  try {
    const draft = image('draft.jpg')
    state.props.modelValue = draft
    await nextTick()
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(state.finalFile.value, draft)
    assert.equal(state.photos.value.length, 1)
    assert.equal(state.updates.length, 0)
    for (const [target, key] of [[state.props,'disabled'], [state,'editorVisible'], [state,'previewVisible']]) {
      if (target === state.props) target[key] = true
      else target[key].value = true
      assert.equal(await state.addFiles([image('ignored.png')]), false)
      if (target === state.props) target[key] = false
      else target[key].value = false
    }
    state.props.active = false
    assert.equal(await state.addFiles([image('ignored.png')]), false)
    assert.equal(state.photos.value.length, 1)
  } finally { state.close() }
})
