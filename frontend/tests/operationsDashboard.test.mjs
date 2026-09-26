import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate, compileScript } from '@vue/compiler-sfc'
import { operationsPages } from '../src/config/operationsCatalog.js'

for (const component of ['OperationsDashboardView','RegionTable']) {
  test(`${component} compiles`, () => {
    const filename=new URL(`../src/views/operations/${component}.vue`,import.meta.url)
    const {descriptor,errors}=parse(readFileSync(filename,'utf8'))
    assert.deepEqual(errors,[])
    assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:filename.pathname,id:component}).errors,[])
    assert.doesNotThrow(()=>compileScript(descriptor,{id:component}))
  })
}
test('one cockpit permission with guarded redirects from retired menus',()=>{
  assert.equal(operationsPages.length,1)
  assert.equal(operationsPages[0].permission,'view_operations_overview')
  assert.equal(operationsPages[0].title,'运营驾驶舱')
  assert.ok(operationsPages.every(page=>page.path.startsWith('/operations/') && page.permission!=='view_station_map'))
  const router=readFileSync(new URL('../src/router/index.js',import.meta.url),'utf8')
  assert.ok(router.includes('hasPermission(role, permissions, operationsPage.permission)'))
  assert.ok(router.includes("{ path: '/operations/rectification', redirect: '/operations/overview' }"))
  assert.ok(router.includes("{ path: '/operations/insights', redirect: '/operations/overview' }"))
  const catalog=readFileSync(new URL('../src/config/pageVisibilityCatalog.js',import.meta.url),'utf8')
  assert.ok(catalog.includes('...operationsPages.map'))
})
