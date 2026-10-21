import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { baseParse } from '@vue/compiler-dom'

const pagePath = new URL('../src/views/inspection/SchedulingMapView.vue', import.meta.url)
const source = readFileSync(pagePath, 'utf8')
const elements = []
function visit(node) {
  if (node.type === 1) elements.push(node)
  for (const child of node.children || []) visit(child)
}
visit(baseParse(parse(source).descriptor.template.content))
const expression = (node, name, arg) => node.props.find(prop => prop.type === 7 && prop.name === name && (!arg || prop.arg?.content === arg))?.exp?.content
const byClass = value => elements.find(node => node.props.some(prop => prop.type === 6 && prop.name === 'class' && prop.value?.content.split(' ').includes(value)))

for (const file of ['views/inspection/SchedulingMapView.vue', 'components/SchedulingMapCanvas.vue']) {
  test(`${file} compiles with actual bindings and its inline or external scoped styles`, () => {
    const path = new URL('../src/' + file, import.meta.url)
    const { descriptor, errors } = parse(readFileSync(path, 'utf8'))
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: 'scheduling-layout' })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: 'scheduling-layout', compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
    for (const style of descriptor.styles) {
      const content = style.src ? readFileSync(new URL(style.src, path), 'utf8') : style.content
      assert.deepEqual(compileStyle({ source: content, id: 'scheduling-layout', scoped: style.scoped }).errors, [])
    }
  })
}

test('period edits still auto-load while station and region filters stay local and controls remain correctly labelled', () => {
  for (const model of ['draft.year', 'draft.quarter', 'draft.month', 'region', 'keyword']) {
    assert.ok(elements.some(node => expression(node, 'model') === model), model)
  }
  for (const [model, label] of [['draft.year', '年份'], ['draft.quarter', '季度'], ['draft.month', '月份'], ['region', '站点所属地']]) {
    const control = elements.find(node => expression(node, 'model') === model)
    assert.ok(control.props.some(prop => prop.name === 'aria-label' && prop.value?.content === label))
  }
  assert.match(source, /watch\(requestedKey,.*loader.select\(draft.value\)/)
  assert.equal((source.match(/axios\.get\(/g) || []).length, 1)
  assert.match(source, /axios.get\('\/api\/scheduling-map', \{ params:query,signal,timeout:15000 \}\)/)
  assert.doesNotMatch(source, /@submit|查看未检查站点|更新当前周期覆盖/)
  const map = elements.find(node => node.tag === 'SchedulingMapCanvas')
  assert.equal(expression(map, 'bind', 'stations'), 'visibleStations')
  assert.equal(expression(map, 'bind', 'viewport-key'), 'viewportKey')
  assert.equal(expression(map, 'bind', 'selected-id'), 'selectedId')
  assert.equal(expression(byClass('station-row'), 'on', 'click'), 'selectStation(station)')
})

test('clearing filters changes only the two local drafts, not the period, source data or network', () => {
  const code = source.match(/function clearFilters\(\) \{[\s\S]*?\n\}/)[0]
  const scope = vm.createContext({ region: { value: '浦东' }, keyword: { value: '国郃' } })
  vm.runInContext(code, scope)
  scope.clearFilters()
  assert.equal(scope.region.value, '')
  assert.equal(scope.keyword.value, '')
  assert.doesNotMatch(code, /axios|loader|draft|result|fetch\(|summary/)
  assert.equal(expression(byClass('clear-filters'), 'if'), 'region || keyword')
  assert.equal(expression(byClass('clear-filters'), 'on', 'click'), 'clearFilters')
})

test('displayed totals keep the returned-period attribution and never imply completion without visible tables or stations', () => {
  assert.match(byClass('stats-heading').loc.source, /result.period.label/)
  assert.match(byClass('stats-heading').loc.source, /loading && pendingChange/)
  assert.match(byClass('coverage-stats').loc.source, /summary.remaining/)
  assert.match(byClass('filter-context').loc.source, /关键词仅筛选地图和清单，不改变上方覆盖统计/)
  const empty = byClass('list-empty')
  const complete = expression(empty, 'bind', 'class')
  for (const [tables, total, keyword, expected] of [[false, 100, '', false], [true, 0, '', false], [true, 100, '不存在', false], [true, 100, '', true]]) {
    assert.equal(vm.runInNewContext(`(${complete}).complete`, { result: { has_tables: tables }, summary: { total }, mapKeyword: keyword }), expected)
  }
  assert.match(source, /unlocated:!stationCoordinates\(station\)/)
  assert.match(source, /缺少坐标 · 保留在待检查清单/)
})

test('independent authorization, cache and polling teardown remain in place', () => {
  assert.equal(expression(byClass('scheduling-page'), 'if'), 'allowed')
  assert.match(source, /Boolean\(permissions.view_scheduling_map\)/)
  assert.match(source, /canRun:.*allowed && !document.hidden && navigator.onLine && !blocked.value/)
  assert.match(source, /loader.dispose\(\)/)
  assert.match(source, /polling.dispose\(\)/)
  assert.match(source, /clearTimeout\(keywordTimer\)/)
})

test('main labels, selected tabs, header copy and warning notes have normal-text contrast', () => {
  const css = readFileSync(new URL('../src/styles/schedulingMap.css', import.meta.url), 'utf8')
  const luminance = hex => hex.match(/\w\w/g).map(channel => {
    const number = parseInt(channel, 16) / 255
    return number <= .04045 ? number / 12.92 : ((number + .055) / 1.055) ** 2.4
  }).reduce((sum, number, index) => sum + number * [.2126, .7152, .0722][index], 0)
  for (const [foreground, background] of [['405a70', 'ffffff'], ['19364d', 'ffffff'], ['ffffff', '173f5d'], ['e0edf6', '164d6b'], ['79521a', 'fff7e8']]) {
    assert.ok(css.includes('#' + foreground) || foreground === 'ffffff')
    assert.ok(css.includes('#' + background) || background === 'ffffff')
    const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
    assert.ok((values[0] + .05) / (values[1] + .05) >= 4.5)
  }
})
