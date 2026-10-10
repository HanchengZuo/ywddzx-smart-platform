import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { compileScript, compileTemplate, parse } from '@vue/compiler-sfc'
import {
  clearPhotoPointers,
  clampPhotoPosition,
  fitPhoto,
  lockPhotoPreviewScroll,
  resetPhotoPreview,
  zoomPhoto,
} from '../src/utils/photoPreview.js'

test('initial fit shows the whole landscape or portrait photo without distortion', () => {
  assert.deepEqual(fitPhoto({ width: 2400, height: 1200 }, { width: 800, height: 600 }), {
    width: 800,
    height: 400,
  })
  assert.deepEqual(fitPhoto({ width: 1200, height: 2400 }, { width: 800, height: 600 }), {
    width: 300,
    height: 600,
  })
  assert.deepEqual(fitPhoto({ width: 120, height: 60 }, { width: 800, height: 600 }), {
    width: 120,
    height: 60,
  })
  assert.deepEqual(fitPhoto({ width: 0, height: 0 }, { width: 800, height: 600 }), {
    width: 0,
    height: 0,
  })
})

test('zoom keeps the cursor anchor stationary and the image inside reachable bounds', () => {
  const image = { width: 800, height: 600 },
    viewport = { width: 800, height: 600 }
  const result = zoomPhoto({ scale: 1, x: 0, y: 0 }, 2, { x: 100, y: -50 }, image, viewport)
  assert.deepEqual(result, { scale: 2, x: -100, y: 50 })
  assert.deepEqual(zoomPhoto(result, 1, { x: 100, y: -50 }, image, viewport), {
    scale: 1,
    x: 0,
    y: 0,
  })
})

test('zoom is limited to 50-500 percent, including repeated wheel or pinch input', () => {
  const image = { width: 800, height: 600 },
    viewport = { width: 800, height: 600 }
  assert.equal(zoomPhoto({ scale: 1, x: 0, y: 0 }, 100, { x: 0, y: 0 }, image, viewport).scale, 5)
  assert.deepEqual(zoomPhoto({ scale: 3, x: 400, y: -200 }, 0, { x: 0, y: 0 }, image, viewport), {
    scale: 0.5,
    x: 0,
    y: 0,
  })
})

test('drag reaches all enlarged edges and shrinking recenters a small photo', () => {
  const image = { width: 400, height: 600 },
    viewport = { width: 800, height: 600 }
  assert.deepEqual(clampPhotoPosition({ x: 9999, y: -9999 }, 3, image, viewport), {
    x: 200,
    y: -600,
  })
  assert.deepEqual(clampPhotoPosition({ x: 200, y: -600 }, 1, image, viewport), { x: 0, y: 0 })
  assert.deepEqual(clampPhotoPosition({ x: 120, y: -100 }, 3, image, viewport), { x: 120, y: -100 })
})

test('reset clears every captured gesture before rezooming and starting a fresh drag', () => {
  const state = { scale: 3, x: -140, y: 100 }
  const pointers = new Map([
    [1, { x: 200, y: 300 }],
    [2, { x: 500, y: 300 }],
  ])
  const released = []
  const target = {
    hasPointerCapture: (id) => id === 1,
    releasePointerCapture(id) {
      assert.equal(pointers.size, 0)
      released.push(id)
    },
  }
  resetPhotoPreview(state, pointers, target)
  assert.deepEqual(state, { scale: 1, x: 0, y: 0 })
  assert.equal(pointers.size, 0)
  assert.deepEqual(released, [1])
  const image = { width: 800, height: 600 },
    viewport = { width: 800, height: 600 }
  Object.assign(state, zoomPhoto(state, 3, { x: 0, y: 0 }, image, viewport))
  pointers.set(1, { x: 100, y: 100 })
  Object.assign(
    state,
    clampPhotoPosition({ x: state.x + 70, y: state.y - 40 }, state.scale, image, viewport),
  )
  assert.deepEqual(state, { scale: 3, x: 70, y: -40 })
  resetPhotoPreview(state, pointers, target)
  assert.equal(pointers.size, 0)
})

test('gesture cleanup is safe without a mounted viewport and is idempotent', () => {
  const pointers = new Map([[1, { x: 200, y: 300 }]])
  clearPhotoPointers(pointers, null)
  clearPhotoPointers(pointers, null)
  assert.equal(pointers.size, 0)
})

test('viewer blocks native double-click selection and drag and cleans interrupted gestures', () => {
  const source = readFileSync(
    new URL('../src/components/InspectionPhotoPreview.vue', import.meta.url),
    'utf8',
  )
  assert.match(source, /@pointerdown\.prevent="startPointer"/)
  assert.match(source, /@selectstart\.prevent/)
  assert.match(source, /@dragstart\.prevent/)
  assert.match(source, /resetPhotoPreview\(transform, pointers, viewport.value\)/)
  assert.match(source, /window\.addEventListener\('blur', clearGestures\)/)
  assert.match(source, /window\.removeEventListener\('blur', clearGestures\)/)
})

test('nested previews lock background scrolling until the last close and preserve old style', () => {
  const body = { style: { overflow: 'auto' } }
  const releaseFirst = lockPhotoPreviewScroll(body),
    releaseSecond = lockPhotoPreviewScroll(body)
  assert.equal(body.style.overflow, 'hidden')
  releaseFirst()
  releaseFirst()
  assert.equal(body.style.overflow, 'hidden')
  releaseSecond()
  assert.equal(body.style.overflow, 'auto')
  lockPhotoPreviewScroll(body)()
  assert.equal(body.style.overflow, 'auto')
})

test('all photo-lightbox pages use the shared viewer instead of their old implementations', () => {
  const pages = [
    'inspection/MyIssuesView',
    'inspection/IssuesView',
    'inspection/HighlightsView',
    'inspection/RegisterView',
    'inspection/RecordsView',
    'inspection/AppealsView',
    'inspection/StationMapView',
    'inspection/ReportGeneratorView',
    'assessment/StationScoreView',
    'Feedback',
  ]
  for (const page of pages) {
    const source = readFileSync(new URL(`../src/views/${page}.vue`, import.meta.url), 'utf8')
    assert.match(source, /import InspectionPhotoPreview from/, page)
    assert.match(source, /<InspectionPhotoPreview[^>]+@close=/s, page)
    assert.doesNotMatch(
      source,
      /handlePreviewWheel|handleIssuePhotoPreviewWheel|class="(?:report-image-preview|station-image-preview-backdrop|image-preview-backdrop|overlay photo-overlay)"/,
      page,
    )
  }
})

test('shared photo viewer and all consumers compile, including multiple template roots', () => {
  const files = [
    'components/InspectionPhotoPreview',
    ...[
      'inspection/MyIssuesView',
      'inspection/IssuesView',
      'inspection/HighlightsView',
      'inspection/RegisterView',
      'inspection/RecordsView',
      'inspection/AppealsView',
      'inspection/StationMapView',
      'inspection/ReportGeneratorView',
      'assessment/StationScoreView',
      'Feedback',
    ].map((page) => `views/${page}`),
  ]
  for (const file of files) {
    const filename = new URL(`../src/${file}.vue`, import.meta.url)
    const { descriptor, errors } = parse(readFileSync(filename, 'utf8'))
    assert.deepEqual(errors, [], file)
    assert.deepEqual(
      compileTemplate({
        source: descriptor.template.content,
        filename: filename.pathname,
        id: file,
      }).errors,
      [],
      file,
    )
    assert.doesNotThrow(() => compileScript(descriptor, { id: file }), file)
  }
})
