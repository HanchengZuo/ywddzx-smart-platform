import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate } from '@vue/compiler-sfc'

test('equipment topic template compiles after formatting', () => {
  const filename = new URL('../src/components/EquipmentReportTopics.vue', import.meta.url)
  const { descriptor, errors } = parse(readFileSync(filename, 'utf8'))
  assert.deepEqual(errors, [])
  const result = compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'equipment-topics-test' })
  assert.deepEqual(result.errors, [])
})
