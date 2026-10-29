import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { horizontalNavigationState, horizontalNavigationDestination } from '../src/utils/tableHorizontalNavigation.js'

const options = { rect: { left: 300, right: 1400, top: 300, bottom: 5000 },
  viewport: { left: 272, right: 1440, top: 76, bottom: 900 }, scrollWidth: 4000, clientWidth: 1100, scrollLeft: 0 }
test('long table has an accessible bottom-of-viewport control at its actual table width', () => {
  const state = horizontalNavigationState(options)
  assert.deepEqual(state, { visible: true, max: 2900, value: 0, left: 300, top: 836, width: 1100 })
  assert.equal(horizontalNavigationState({ ...options, rect: { ...options.rect, top: -2200 } }).visible, true)
})
test('native scrollbar takes over at the table end; offscreen and non-overflowing tables never show a duplicate', () => {
  for (const change of [
    { rect: { ...options.rect, bottom: 890 } },
    { rect: { ...options.rect, top: 880 } },
    { rect: { ...options.rect, top: -5000, bottom: -100 } },
    { scrollWidth: 1100 }, { clientWidth: 0 },
    { viewport: { ...options.viewport, left: 1300 } },
  ]) assert.equal(horizontalNavigationState({ ...options, ...change }).visible, false)
})
test('sidebar resizing and clipped table bounds keep the bar inside the active workspace', () => {
  const state = horizontalNavigationState({ ...options, rect: { left: 40, right: 1600, top: -50, bottom: 3000 },
    viewport: { left: 272, right: 1200, top: 76, bottom: 720 } })
  assert.equal(state.left, 272); assert.equal(state.width, 928); assert.equal(state.top, 656)
  assert.equal(state.visible, true)
})
test('column changes clamp positions without fabricating extra scroll range', () => {
  assert.equal(horizontalNavigationState({ ...options, scrollLeft: 3000 }).value, 2900)
  assert.equal(horizontalNavigationState({ ...options, scrollLeft: -5 }).value, 0)
  assert.equal(horizontalNavigationState({ ...options, scrollWidth: 1000, scrollLeft: 3000 }).max, 0)
})
test('keyboard and buttons support bounded quick browsing without hijacking tab or vertical navigation', () => {
  for (const [key, expected] of [['Home', 0], ['End', 2900], ['ArrowLeft', 420], ['ArrowRight', 580], ['PageUp', 0], ['PageDown', 1380]]) {
    assert.equal(horizontalNavigationDestination(key, 500, 2900, 1100), expected)
  }
  assert.equal(horizontalNavigationDestination('PageDown', 2800, 2900, 1100), 2900)
  for (const key of ['Tab', 'ArrowUp', 'ArrowDown', 'Escape', 'Enter']) assert.equal(horizontalNavigationDestination(key, 500, 2900, 1100), null)
})
test('navigator compiles with real bindings, accessible controls, batched observation and complete cleanup', () => {
  const source = readFileSync(new URL('../src/components/TableHorizontalNavigator.vue', import.meta.url), 'utf8')
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'table-navigation' })
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'TableHorizontalNavigator.vue', id: 'table-navigation', compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  for (const style of descriptor.styles) assert.deepEqual(compileStyle({ source: style.content, id: 'table-navigation', scoped: true }).errors, [])
  assert.match(source, /requestAnimationFrame\(measure\)/)
  assert.match(source, /cancelAnimationFrame\(frame\)/)
  assert.match(source, /observer\?\.disconnect\(\)/)
  assert.match(source, /source.removeEventListener\('scroll', schedule\)/)
  assert.match(source, /aria-label="问题清单横向位置"/)
  assert.doesNotMatch(source, /setInterval|MutationObserver|addEventListener\('wheel'/)
  const page = readFileSync(new URL('../src/views/inspection/IssuesView.vue', import.meta.url), 'utf8')
  assert.match(page, /:disabled="tableFullscreen \|\| isMobileView \|\| columnSettingsOpen"/)
  assert.match(page, /\.table-scroll\s*\{\s*overflow-x: auto;\s*\}/)
})
