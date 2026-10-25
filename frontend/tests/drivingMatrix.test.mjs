import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileStyle } from '@vue/compiler-sfc'
import { PAGE_VISIBILITY_PAGES } from '../src/config/pageVisibilityCatalog.js'

const source = name => readFileSync(new URL('../src/'+name, import.meta.url), 'utf8')
test('road database page compiles, is read-only and pages data instead of loading all pairs', () => {
  const text = source('views/management/DrivingMatrixView.vue')
  const { descriptor } = parse(text)
  assert.doesNotThrow(() => compileScript(descriptor,{ id:'road-matrix',inlineTemplate:true }))
  for (const style of descriptor.styles) assert.deepEqual(compileStyle({ source:style.content,id:'road-matrix',scoped:true }).errors,[])
  assert.match(text,/axios\.get\('\/api\/management\/driving-matrix'/)
  assert.doesNotMatch(text,/axios\.(post|put|delete)|restapi\.amap|AMAP_KEY/)
  assert.match(text,/page_size|\/ 30/)
  assert.match(text,/createAdaptivePolling/)
  assert.match(text,/controller\?\.abort/)
  assert.match(text,/开始查询/)
})
test('management menu, permission navigation and route enforce the independent view grant', () => {
  const shell=source('App.vue'), router=source('router/index.js')
  assert.match(shell,/hasPermissionKey\('view_driving_matrix'\)/)
  assert.match(router,/if \(path === '\/management\/driving-matrix'\) return hasPermission\(role, permissions, 'view_driving_matrix'\)/)
  assert.equal(PAGE_VISIBILITY_PAGES.find(p=>p.path==='/management/driving-matrix').title,'路网数据管理')
  assert.ok(shell.indexOf("go('/management/driving-matrix')") < shell.indexOf("go('/management/ai-models')"))
})
