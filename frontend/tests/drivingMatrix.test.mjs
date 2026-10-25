import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileStyle } from '@vue/compiler-sfc'
import { PAGE_VISIBILITY_PAGES } from '../src/config/pageVisibilityCatalog.js'
import { schedulingMenuPages } from '../src/config/schedulingCatalog.js'

const source = name => readFileSync(new URL('../src/'+name, import.meta.url), 'utf8')
test('road database page compiles, is read-only and pages data instead of loading all pairs', () => {
  const text = source('views/inspection/DrivingDataView.vue')
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
test('road data follows scheduling map and preserves its independent permission and existing URL', () => {
  const shell=source('App.vue'), router=source('router/index.js')
  assert.match(shell,/schedulingMenuPages\.filter/)
  assert.match(router,/if \(path === '\/management\/driving-matrix'\) return hasPermission\(role, permissions, 'view_driving_matrix'\)/)
  assert.equal(PAGE_VISIBILITY_PAGES.find(p=>p.path==='/management/driving-matrix').title,'路网数据')
  assert.equal(schedulingMenuPages[1].title, '路网数据')
  assert.equal(schedulingMenuPages[1].permission, 'view_driving_matrix')
  assert.equal(schedulingMenuPages[0].title, '排班地图')
  assert.doesNotMatch(shell,/canViewDrivingMatrix|title="路网数据管理"/)
})
test('filter controls provide name search and distance ordering without a second endpoint selector', () => {
  const text=source('views/inspection/DrivingDataView.vue')
  assert.match(text,/v-model="draft.keyword"/)
  assert.match(text,/value="distance_asc"/)
  assert.match(text,/value="distance_desc"/)
  assert.match(text,/<FilterSummary :fields="filterFields" manual/)
  assert.doesNotMatch(text,/counterpart|另一站点/)
})
