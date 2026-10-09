import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate, compileScript } from '@vue/compiler-sfc'
import { getImageFilesFromClipboardEvent, getImageFilesFromDataTransfer } from '../src/utils/imageUpload.js'

test('review drawer compiles and shares registration image utilities', () => {
  const filename = new URL('../src/views/inspection/MyIssuesView.vue', import.meta.url)
  const source = readFileSync(filename, 'utf8')
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'review' }).errors, [])
  assert.doesNotThrow(() => compileScript(descriptor, { id: 'review' }))
  assert.match(source, /getImageFilesFromClipboardEvent\(event\)/)
  assert.match(source, /window\.removeEventListener\('paste', handleReviewPhotoPaste\)/)
  assert.match(source, /sequence !== reviewPhotoSequence/)
})

test('clipboard images use the same extraction path as file drops', () => {
  const first = { name: 'clipboard.png', type: 'image/png' }
  const second = { name: 'photo.jpg', type: 'image/jpeg' }
  const transfer = { items: [
    { kind: 'string', type: 'text/plain' },
    { kind: 'file', type: first.type, getAsFile: () => first },
    { kind: 'file', type: second.type, getAsFile: () => second },
  ] }
  assert.deepEqual(getImageFilesFromClipboardEvent({ clipboardData: transfer }), [first, second])
  assert.deepEqual(getImageFilesFromDataTransfer(transfer), [first, second])
  assert.deepEqual(getImageFilesFromClipboardEvent({ clipboardData: { files: [first] } }), [first])
})

test('plain text, missing clipboard data and non-image files are not consumed as photos', () => {
  assert.deepEqual(getImageFilesFromClipboardEvent({}), [])
  assert.deepEqual(getImageFilesFromClipboardEvent({ clipboardData: {
    items: [{ kind: 'string', type: 'text/plain' }], files: [{ type: 'application/pdf' }],
  } }), [])
})
