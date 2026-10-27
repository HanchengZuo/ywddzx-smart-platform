import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { paginateByHeight } from '../src/utils/heightPagination.js'

test('height-based pages fill available space including card gaps without losing standards', () => {
  assert.deepEqual(paginateByHeight([100,120,90,100],232),[{start:0,end:2},{start:2,end:4}])
  assert.deepEqual(paginateByHeight([100,120],231),[{start:0,end:1},{start:1,end:2}])
  assert.deepEqual(paginateByHeight([],500),[])
  assert.deepEqual(paginateByHeight([800,80,90],300),[{start:0,end:1},{start:1,end:3}])
  assert.deepEqual(paginateByHeight([0,NaN,undefined],332),[{start:0,end:2},{start:2,end:3}])
  assert.deepEqual(paginateByHeight([20,30],0),[{start:0,end:1},{start:1,end:2}])
})

test('variable content lengths and viewport budgets preserve exact ordered coverage', () => {
  const heights=Array.from({length:137},(_,i)=>60+(i*89)%250)
  for(const budget of [160,900,2000,3100]) {
    const pages=paginateByHeight(heights,budget)
    const covered=pages.flatMap(({start,end})=>Array.from({length:end-start},(_,i)=>start+i))
    assert.deepEqual(covered,heights.map((_,i)=>i))
    for(const {start,end} of pages) {
      assert.ok(end>start)
      const used=heights.slice(start,end).reduce((sum,n)=>sum+n,0)+(end-start-1)*12
      assert.ok(used<=budget || end-start===1)
    }
  }
  assert.ok(paginateByHeight(heights,3100)[0].end>5,'wide directory layout should show more than the old five cards')
})

for(const file of ['views/inspection/IssuesView.vue','views/inspection/HighlightsView.vue',
  'views/inspection/ChecklistOriginalsView.vue','components/ExternalStandardCard.vue']) {
  test(`${file} compiles with real template bindings`,()=>{
    const source=readFileSync(new URL('../src/'+file,import.meta.url),'utf8')
    const {descriptor,errors}=parse(source)
    assert.deepEqual(errors,[])
    const script=compileScript(descriptor,{id:'single-scroll'})
    assert.deepEqual(compileTemplate({source:descriptor.template.content,id:'single-scroll',filename:file,
      compilerOptions:{bindingMetadata:script.bindings}}).errors,[])
  })
}
