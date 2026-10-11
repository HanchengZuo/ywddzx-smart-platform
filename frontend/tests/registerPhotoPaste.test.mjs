import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { parse, compileTemplate, compileScript } from '@vue/compiler-sfc'
import { getImageFilesFromClipboardEvent } from '../src/utils/imageUpload.js'

const filename = new URL('../src/views/inspection/RegisterView.vue', import.meta.url)
const source = readFileSync(filename, 'utf8')
const handlerSource = source.match(/const handlePhotoPaste = async \(event\) => \{[\s\S]*?\n\}/)[0]

const setup = (overrides = {}) => {
  const uploads = []
  let scrollCount = 0
  const context = {
    hasPermission: true,
    showIssueFields: { value: true },
    submitting: { value: false },
    photoEditorVisible: { value: false },
    issuePhotoPreviewVisible: { value: false },
    isPhotoDragActive: { value: true },
    photoDragDepth: 2,
    getImageFilesFromClipboardEvent,
    processSelectedImages: async (files) => { uploads.push(files); return true },
    scrollToIssuePhotoUpload: async () => { scrollCount++ },
    ...overrides
  }
  const paste = runInNewContext(`${handlerSource}; handlePhotoPaste`, context)
  const event = (files = [{ name: 'clipboard.png', type: 'image/png' }]) => ({
    defaultPrevented: false,
    clipboardData: { files },
    preventDefault() { this.defaultPrevented = true }
  })
  return { paste, event, uploads, context, scrollCount: () => scrollCount }
}

test('problem and highlight modes paste without navigation through the same upload path', async () => {
  for (const mode of ['yes', 'highlight']) {
    const state = setup({ normalizedHasIssue: { value: mode } })
    const event = state.event()
    await state.paste(event)
    assert.equal(event.defaultPrevented, true)
    assert.equal(state.uploads.length, 1)
    assert.equal(state.uploads[0][0].name, 'clipboard.png')
    assert.equal(state.scrollCount(), 1)
    assert.equal(state.context.photoDragDepth, 0)
    assert.equal(state.context.isPhotoDragActive.value, false)
  }
})

test('dropzone paste bubbling to window uploads the image only once', async () => {
  const state = setup()
  const event = state.event()
  await state.paste(event)
  await state.paste(event)
  assert.equal(state.uploads.length, 1)
})

test('text-only paste is untouched and does not invoke photo processing', async () => {
  const state = setup()
  for (const event of [state.event([]), state.event([{ type: 'application/pdf' }]), state.event()]) {
    if (event.clipboardData.files[0]?.type === 'image/png') delete event.clipboardData
    await state.paste(event)
    assert.equal(event.defaultPrevented, false)
  }
  assert.equal(state.uploads.length, 0)
})

test('hidden upload, denied permission, submission and photo modals do not capture paste', async () => {
  for (const overrides of [
    { hasPermission: false },
    { showIssueFields: { value: false } },
    { submitting: { value: true } },
    { photoEditorVisible: { value: true } },
    { issuePhotoPreviewVisible: { value: true } }
  ]) {
    const state = setup(overrides)
    const event = state.event()
    await state.paste(event)
    assert.equal(event.defaultPrevented, false)
    assert.equal(state.uploads.length, 0)
  }
})

test('registration compiles and both listeners share the handler with unmount cleanup', () => {
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'register-paste' }).errors, [])
  assert.doesNotThrow(() => compileScript(descriptor, { id: 'register-paste' }))
  assert.match(source, /@paste="handlePhotoPaste"/)
  assert.match(source, /window\.addEventListener\('paste', handlePhotoPaste\)/)
  assert.match(source, /window\.removeEventListener\('paste', handlePhotoPaste\)/)
  assert.doesNotMatch(source, /handleWindowPhotoPaste/)
})
