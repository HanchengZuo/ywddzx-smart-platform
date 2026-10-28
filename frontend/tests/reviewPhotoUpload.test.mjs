import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate, compileScript } from '@vue/compiler-sfc'
import {
  getImageFilesFromClipboardEvent,
  getImageFilesFromDataTransfer,
} from '../src/utils/imageUpload.js'

test('review drawer compiles and shares registration image utilities', () => {
  const filename = new URL('../src/views/inspection/MyIssuesView.vue', import.meta.url)
  const source = readFileSync(filename, 'utf8')
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  assert.deepEqual(
    compileTemplate({
      source: descriptor.template.content,
      filename: filename.pathname,
      id: 'review',
    }).errors,
    [],
  )
  assert.doesNotThrow(() => compileScript(descriptor, { id: 'review' }))
  assert.match(source, /<InspectionPhotoUpload ref="reviewPhotoUploadRef"/)
  assert.doesNotMatch(source, /processReviewPhoto|reviewSourcePhotos/)
  const uploader = readFileSync(new URL('../src/components/InspectionPhotoUpload.vue', import.meta.url), 'utf8')
  assert.match(uploader, /getImageFilesFromClipboardEvent\(event\)/)
  assert.match(uploader, /window\.removeEventListener\('paste', paste\)/)
  assert.match(uploader, /token === revision/)
})

test('clipboard images use the same extraction path as file drops', () => {
  const first = { name: 'clipboard.png', type: 'image/png' }
  const second = { name: 'photo.jpg', type: 'image/jpeg' }
  const transfer = {
    items: [
      { kind: 'string', type: 'text/plain' },
      { kind: 'file', type: first.type, getAsFile: () => first },
      { kind: 'file', type: second.type, getAsFile: () => second },
    ],
  }
  assert.deepEqual(getImageFilesFromClipboardEvent({ clipboardData: transfer }), [first, second])
  assert.deepEqual(getImageFilesFromDataTransfer(transfer), [first, second])
  assert.deepEqual(getImageFilesFromClipboardEvent({ clipboardData: { files: [first] } }), [first])
})

test('plain text, missing clipboard data and non-image files are not consumed as photos', () => {
  assert.deepEqual(getImageFilesFromClipboardEvent({}), [])
  assert.deepEqual(
    getImageFilesFromClipboardEvent({
      clipboardData: {
        items: [{ kind: 'string', type: 'text/plain' }],
        files: [{ type: 'application/pdf' }],
      },
    }),
    [],
  )
})

test('approval and rejection share one uploader, editor and submit path with separate required validation', () => {
  const source = readFileSync(
    new URL('../src/views/inspection/MyIssuesView.vue', import.meta.url),
    'utf8',
  )
  assert.match(
    source,
    /shouldShowReviewPhotoUpload = computed\(\(\) => reviewAllowsPhoto\(actionForm.value.reviewResult\)\)/,
  )
  assert.match(source, /if \(reviewPhotoRequired && !actionForm.value.reviewPhotoFile\)/)
  assert.match(
    source,
    /if \(reviewAllowsPhoto\(actionForm.value.reviewResult\) && actionForm.value.reviewPhotoFile\)/,
  )
  assert.match(source, /if \(!reviewAllowsPhoto\(value\)\) \{\s+clearReviewFile\(\)/)
  assert.equal((source.match(/id-prefix="review-photo"/g) || []).length, 1)
  assert.equal((source.match(/label="复核照片"/g) || []).length, 1)
  assert.match(
    source,
    /复核照片 <span v-if="!reviewRequiresPhoto\(actionForm.reviewResult, actionDrawer.item\?\.checklist_mode\)" class="optional-field-tag">选填/,
  )
  assert.match(source, /reviewPhotoRequired = reviewRequiresPhoto\(actionForm.value.reviewResult, actionDrawer.value.item\?\.checklist_mode\)/)
  assert.match(source, /视频检查表的复核照片为选填，可不上传/)
  assert.ok(!source.includes('整改不通过将退回站经理重新整改，本次无需上传复核照片。'))
})
