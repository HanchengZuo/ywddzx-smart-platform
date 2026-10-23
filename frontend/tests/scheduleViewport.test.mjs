import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { scrollScheduleToFilters } from '../src/utils/scheduleViewport.js'

test('tab changes scroll only the content viewport, respecting border and sticky-header offset', () => {
  const calls = []
  const content = {
    scrollTop: 1600,
    clientTop: 1,
    getBoundingClientRect: () => ({ top: 92 }),
    scrollTo: (value) => calls.push(value),
  }
  const panel = {
    closest: (selector) => {
      assert.equal(selector, '.content')
      return content
    },
    getBoundingClientRect: () => ({ top: -830 }),
  }
  const original = globalThis.getComputedStyle
  globalThis.getComputedStyle = (el) => {
    assert.equal(el, panel)
    return { scrollMarginTop: '108px' }
  }
  try {
    scrollScheduleToFilters(panel)
    assert.deepEqual(calls, [{ top: 569 }])
    content.scrollTop = 0
    scrollScheduleToFilters(panel)
    assert.deepEqual(calls[1], { top: 0 })
  } finally {
    if (original) globalThis.getComputedStyle = original
    else delete globalThis.getComputedStyle
  }
})

test('missing/cached-away panels never fall back to scrolling the document', () => {
  assert.doesNotThrow(() => scrollScheduleToFilters(null))
  assert.doesNotThrow(() => scrollScheduleToFilters({ closest: () => null }))
})

test('notebook shell allows action wrapping without splitting labels or constraining content height', () => {
  const source = readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const css = descriptor.styles.map((s) => s.content).join('\n')
  const block = (selector) =>
    css.slice(css.indexOf(selector + ' {'), css.indexOf('}', css.indexOf(selector + ' {')))
  assert.match(block('.header'), /flex-wrap: wrap/)
  assert.match(block('.header'), /min-height: 76px/)
  assert.doesNotMatch(block('.header'), /\n\s*height: 76px/)
  for (const name of ['.header-title', '.header-user-name', '.header-logout-button'])
    assert.match(block(name), /white-space: nowrap/)
  for (const name of ['.main', '.content']) assert.match(block(name), /min-height: 0/)
  assert.match(block('.header-user-area'), /flex-wrap: wrap/)
  assert.match(block('.header-user-area'), /max-width: 100%/)
})

test('accessible table captions cannot escape the content scroll container or create page-bottom whitespace', () => {
  const source = readFileSync(
    new URL('../src/components/InspectionSchedulePanel.vue', import.meta.url),
    'utf8',
  )
  assert.match(source, /\.matrix-content\s*\{\s*position: relative;/)
  assert.match(source, /\.sr-only\s*\{\s*position: absolute;\s*top: 0;\s*left: 0;/)
  assert.match(source, /<caption class="sr-only">/)
  const page = readFileSync(
    new URL('../src/views/inspection/InspectionScheduleView.vue', import.meta.url),
    'utf8',
  )
  assert.doesNotMatch(page, /\.scrollIntoView\(/)
  assert.match(page, /scrollScheduleToFilters\(document.getElementById/)
  const { descriptor } = parse(page)
  const script = compileScript(descriptor, { id: 'schedule-viewport' })
  assert.deepEqual(
    compileTemplate({
      source: descriptor.template.content,
      filename: 'InspectionScheduleView.vue',
      id: 'schedule-viewport',
      compilerOptions: { bindingMetadata: script.bindings },
    }).errors,
    [],
  )
  for (const style of descriptor.styles)
    assert.deepEqual(
      compileStyle({ source: style.content, id: 'schedule-viewport', scoped: style.scoped }).errors,
      [],
    )
})
