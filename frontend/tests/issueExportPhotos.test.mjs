import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate, compileScript } from '@vue/compiler-sfc'

const readSource = (path) => readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')

test('photo exports have no separate permission or management switch', () => {
  for (const path of [
    'views/inspection/IssuesView.vue',
    'views/management/UserDataManagementView.vue',
  ]) {
    const source = readSource(path)
    assert.ok(!source.includes('export_issue_photos'))
    assert.ok(!source.includes('canExportIssuePhotos'))
    assert.ok(!source.includes('导出巡检照片'))
  }
})

test('new exports select all three photo fields but preserve hidden contacts and completed task choices', () => {
  const source = readSource('views/inspection/IssuesView.vue')
  assert.match(
    source,
    /const exportPhotoFieldKeys = \['issue_photo', 'rectification_photo', 'review_photo'\]/,
  )
  assert.match(
    source,
    /hiddenInspectorColumnKeys.has\(option.key\) && hideInspectorContactInfo.value\s+\? false\s+: true/,
  )
  assert.match(
    source,
    /hiddenInspectorColumnKeys.has\(option.key\) && hideInspectorContactInfo.value\s+\? false\s+: Boolean\(includeFields\[option.key\]\)/,
  )
  assert.match(source, /Boolean\(exportDialog.value.includeFields\[key\]\)/)
  assert.match(source, /if \(exportDialog.value.taskId\) return false/)
  assert.match(
    source,
    /if \(hiddenInspectorColumnKeys.has\(option.key\) && hideInspectorContactInfo.value\) return false/,
  )
  assert.match(source, /include_photos: buildExportPhotoOptionsFromFields\(\)/)
  assert.match(source, /photoMode: 'compatible'/)
})

for (const path of [
  'views/inspection/IssuesView.vue',
  'views/management/UserDataManagementView.vue',
]) {
  test(`${path} compiles after permission removal`, () => {
    const { descriptor, errors } = parse(readSource(path))
    assert.deepEqual(errors, [])
    assert.deepEqual(
      compileTemplate({ source: descriptor.template.content, filename: path, id: path }).errors,
      [],
    )
    assert.doesNotThrow(() => compileScript(descriptor, { id: path }))
  })
}
