import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate, compileScript } from '@vue/compiler-sfc'

test('equipment topic template compiles after formatting', () => {
  const filename = new URL('../src/components/EquipmentReportTopics.vue', import.meta.url)
  const { descriptor, errors } = parse(readFileSync(filename, 'utf8'))
  assert.deepEqual(errors, [])
  const result = compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'equipment-topics-test' })
  assert.deepEqual(result.errors, [])
})

for (const name of ['EquipmentReportPhrases','EquipmentStationTopics']) test(`${name} compiles with actual bindings`,()=>{
  const filename=new URL(`../src/components/${name}.vue`,import.meta.url)
  const {descriptor,errors}=parse(readFileSync(filename,'utf8'))
  assert.deepEqual(errors,[])
  const script=compileScript(descriptor,{id:name})
  assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:filename.pathname,id:name,compilerOptions:{bindingMetadata:script.bindings}}).errors,[])
})
