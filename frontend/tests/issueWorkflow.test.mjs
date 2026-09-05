import test from 'node:test'
import assert from 'node:assert/strict'
import { reviewOptionsFor, reviewRequiresPhoto, isReviewReturned } from '../src/utils/issueWorkflow.js'

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
