import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'

for (const file of ['ServiceReportConfig.vue', 'ServiceReportHtml.vue'])
  test(`${file} compiles template, bindings and responsive styles`, () => {
    const source = readFileSync(new URL('../src/components/' + file, import.meta.url), 'utf8')
    const { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: 'service-report' })
    assert.deepEqual(
      compileTemplate({
        source: descriptor.template.content,
        id: 'service-report',
        compilerOptions: { bindingMetadata: script.bindings },
      }).errors,
      [],
    )
    for (const style of descriptor.styles)
      assert.deepEqual(
        compileStyle({ source: style.content, id: 'service-report', scoped: true }).errors,
        [],
      )
  })
test('service configuration uses shared date props, save-only manual controls and separately permission-gated AI calls', () => {
  const source = readFileSync(
    new URL('../src/components/ServiceReportConfig.vue', import.meta.url),
    'utf8',
  )
  const { descriptor } = parse(source)
  assert.match(descriptor.scriptSetup.content, /generate_inspection_reports|props.canGenerate/)
  assert.match(
    descriptor.scriptSetup.content,
    /axios.get\('\/api\/inspection-reports\/service-config'/,
  )
  assert.match(
    descriptor.scriptSetup.content,
    /axios.put\('\/api\/inspection-reports\/service-config'/,
  )
  assert.match(
    descriptor.scriptSetup.content,
    /axios.post\(\s*'\/api\/inspection-reports\/service-analysis'/,
  )
  assert.match(descriptor.template.content, /问题具体表现/)
  assert.match(descriptor.template.content, /最近保存/)
  assert.match(descriptor.template.content, /role="alert"/)
  const parent = readFileSync(
    new URL('../src/views/inspection/ReportGeneratorView.vue', import.meta.url),
    'utf8',
  )
  assert.match(parent, /<ServiceReportConfig v-if="isOnSiteServiceReport"/)
  assert.match(parent, /<ServiceReportHtml :report="report"/)
  assert.doesNotMatch(
    parent,
    /servicePreviousRectification|serviceDeepAnalysis|serviceProblemSummary/,
  )
})
