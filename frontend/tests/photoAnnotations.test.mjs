import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createPhotoAnnotation,
  DEFAULT_ANNOTATION_LINE_WIDTH,
  renderIssuePhotoComposition,
} from '../src/utils/imageComposer.js'

test('rectangles normalize reverse drags and keep the stroke within the canvas', () => {
  const box = createPhotoAnnotation(
    'rectangle',
    { x: 900, y: 700 },
    { x: -100, y: -50 },
    1200,
    800,
    12,
  )
  assert.deepEqual(box, {
    color: '#ef4444',
    lineWidth: 12,
    type: 'rectangle',
    x: 6,
    y: 6,
    w: 894,
    h: 694,
  })
  const edge = createPhotoAnnotation('rectangle', { x: 0, y: 0 }, { x: 1300, y: 900 }, 1200, 800)
  assert.equal(edge.lineWidth, DEFAULT_ANNOTATION_LINE_WIDTH)
  assert.equal(edge.x + edge.w + edge.lineWidth / 2, 1200)
})

test('circles keep a selectable width, bounded radius and do not exceed the image', () => {
  const circle = createPhotoAnnotation(
    'circle',
    { x: 100, y: 100 },
    { x: 500, y: 500 },
    1200,
    800,
    4,
  )
  assert.equal(circle.lineWidth, 4)
  assert.equal(circle.r, 98)
  assert.equal(
    createPhotoAnnotation('circle', { x: 500, y: 400 }, { x: 510, y: 400 }, 1200, 800, 99)
      .lineWidth,
    16,
  )
})

test('render and export path draws legacy circles plus rectangles with their own stroke widths', () => {
  const calls = []
  const ctx = {
    save() {},
    restore() {},
    fillRect() {},
    beginPath() {},
    arc(...args) {
      calls.push(['circle', ...args, this.lineWidth])
    },
    rect(...args) {
      calls.push(['rectangle', ...args, this.lineWidth])
    },
    stroke() {},
  }
  renderIssuePhotoComposition({ getContext: () => ctx }, [], {
    width: 1200,
    height: 800,
    items: [],
    circles: [{ x: 100, y: 100, r: 30, lineWidth: 8 }],
    annotations: [{ type: 'rectangle', x: 200, y: 200, w: 150, h: 100, lineWidth: 12 }],
  })
  assert.equal(calls.length, 2)
  assert.equal(calls[0][0], 'circle')
  assert.equal(calls[0].at(-1), 8)
  assert.deepEqual(calls[1], ['rectangle', 200, 200, 150, 100, 12])
})
