import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { REPORT_VIEW_MODE_KEY, readReportViewMode, saveReportViewMode } from '../src/utils/reportViewMode.js'

test('report viewing preference defaults to PPT and preserves either selected mode across reloads', () => {
  const values = new Map()
  const storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) }
  assert.equal(readReportViewMode(storage), 'ppt')
  for (const mode of ['html', 'ppt', 'html']) {
    saveReportViewMode(mode, storage)
    assert.equal(values.get(REPORT_VIEW_MODE_KEY), mode)
    assert.equal(readReportViewMode(storage), mode)
  }
  values.set(REPORT_VIEW_MODE_KEY, 'invalid')
  assert.equal(readReportViewMode(storage), 'ppt')
  assert.equal(values.size, 1, 'only a view preference is stored, not report data or workspace settings')
})

test('blocked storage never prevents report viewing', () => {
  const storage = { getItem() { throw new Error('SecurityError') }, setItem() { throw new Error('QuotaExceededError') } }
  assert.equal(readReportViewMode(storage), 'ppt')
  assert.doesNotThrow(() => saveReportViewMode('html', storage))
})

test('both view choices emit explicit mode updates, expose selected state, and never generate a report', () => {
  const source = readFileSync(new URL('../src/components/ReportViewModeSwitch.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'mode-switch' })
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'ReportViewModeSwitch.vue', id: 'mode-switch', compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  assert.deepEqual(compileStyle({ source: descriptor.styles[0].content, id: 'mode-switch', scoped: true }).errors, [])
  assert.match(source, /value: 'ppt', label: 'PPT报告'/)
  assert.match(source, /value: 'html', label: 'HTML报告'/)
  assert.match(source, /:aria-pressed="modelValue === mode.value"/)
  assert.match(source, /\$emit\('update:modelValue', mode.value\)/)
  assert.doesNotMatch(source, /axios|fetch\(|generate|disabled/)
})

test('scheduling entry points retain their order and handlers with scoped, specified button colors', () => {
  const source = readFileSync(new URL('../src/views/inspection/InspectionScheduleView.vue', import.meta.url), 'utf8')
  assert.match(source, /<MeteringAnnualPlan[^>]+@saved="refreshKey\+\+"[\s\S]*<TodayInspectionDispatch[\s\S]*<AutomaticSchedule[^>]+@scheduled="onScheduled"/)
  assert.match(source, /\.head-actions :deep\(\.plan-trigger\) \{\s*background: #f2f5f8;\s*color: #294b65;/)
  assert.match(source, /\.head-actions :deep\(\.today-dispatch-trigger\) \{\s*background: #d8f0ea;\s*color: #17665f;/)
  assert.match(source, /\.head-actions :deep\(\.auto-trigger\) \{\s*background: #3479ce;\s*color: #fff;/)
  assert.match(source, /height: 44px;[\s\S]*border-radius: 12px;\s*font-weight: 600;/)
  assert.doesNotMatch(source, /全部站点展开|switcher-hint/)
})
