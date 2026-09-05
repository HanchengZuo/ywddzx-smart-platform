import test from 'node:test'
import assert from 'node:assert/strict'
import { reviewOptionsFor, reviewRequiresPhoto, isReviewReturned, rectificationDraftFor } from '../src/utils/issueWorkflow.js'

test('both returned branches start blank without changing historical records', () => {
  for (const review_result of ['整改不通过', '驳回站级无法整改']) {
    const item = { review_result, rectification_result: '已整改', rectification_note: '上一轮说明', rectification_photo: '/old.jpg' }
    const original = { ...item }
    assert.deepEqual(rectificationDraftFor(item), { rectificationResult: '', rectificationNote: '', rectificationPhotoFile: null, rectificationPhotoPreview: '' })
    assert.deepEqual(item, original)
  }
})

test('reviewing a submitted round retains its photo and explanation', () => {
  const draft = rectificationDraftFor({ rectification_result: '已整改', rectification_note: '本轮说明', rectification_photo: '/photo.jpg' }, path => `resolved:${path}`)
  assert.equal(draft.rectificationResult, '已整改')
  assert.equal(draft.rectificationNote, '本轮说明')
  assert.equal(draft.rectificationPhotoPreview, 'resolved:/photo.jpg')
})

test('review options are exclusive to the station submission branch', () => {
  assert.deepEqual(reviewOptionsFor('已整改'), ['整改通过', '整改不通过'])
  for (const value of ['站级无法整改', '站经无法整改']) assert.deepEqual(reviewOptionsFor(value), ['通过站级无法整改', '驳回站级无法整改'])
})
test('only ordinary approval requires a photo; both rejection paths return', () => {
  assert.ok(reviewRequiresPhoto('整改通过'))
  for (const value of ['整改不通过', '通过站级无法整改', '驳回站级无法整改']) assert.equal(reviewRequiresPhoto(value), false)
  assert.ok(isReviewReturned('整改不通过'))
  assert.ok(isReviewReturned('驳回站级无法整改'))
  assert.equal(isReviewReturned('通过站级无法整改'), false)
})
