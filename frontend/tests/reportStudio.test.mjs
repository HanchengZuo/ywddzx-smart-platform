import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { baseParse } from '@vue/compiler-dom'

const path = new URL('../src/views/inspection/ReportGeneratorView.vue',import.meta.url)
const source = readFileSync(path,'utf8')
const { descriptor } = parse(source)
const ast = baseParse(descriptor.template.content)
const elements = []
function visit(node) {
  if(node.type===1) elements.push(node)
  for(const child of node.children || []) visit(child)
}
visit(ast)
const byClass = name => elements.find(node => node.props.some(p=>p.type===6&&p.name==='class'&&p.value?.content.split(' ').includes(name)))
const expression = (node,name,arg) => node.props.find(p=>p.type===7&&p.name===name&&(!arg||p.arg?.content===arg))?.exp?.content
const normalized = value => value?.replace(/\s+/g,' ').trim()

test('report workspace and independent shell stylesheet compile with actual script bindings',()=>{
  const script=compileScript(descriptor,{id:'report-studio'})
  const template=compileTemplate({source:descriptor.template.content,filename:String(path),id:'report-studio',compilerOptions:{bindingMetadata:script.bindings}})
  assert.deepEqual(template.errors,[])
  for(const style of descriptor.styles){
    const content=style.src ? readFileSync(new URL(style.src,path),'utf8') : style.content
    assert.deepEqual(compileStyle({source:content,id:'report-studio',scoped:style.scoped}).errors,[])
  }
})

test('report choice keeps its handler and now exposes selected state; mobile retains selected source names',()=>{
  const card=elements.find(node=>expression(node,'on','click')==='selectReportType(item.key)')
  assert.equal(expression(card,'bind','aria-pressed'),'selectedReportType === item.key')
  assert.match(expression(card,'for'),/reportTypes$/)
  assert.ok(byClass('studio-selected-sources'))
  assert.ok(elements.some(node=>expression(node,'for')==='tableName in currentReportType.target_tables'))
  assert.match(source,/v-for="tableName in item.target_tables"/)
})

test('date saving, generation conditions and force action are unchanged',()=>{
  for(const model of ['reportDateFrom','reportDateTo']){
    const input=elements.find(node=>node.tag==='input'&&expression(node,'model')===model)
    assert.equal(expression(input,'bind','disabled'),'!canGenerateReports || loading')
    assert.equal(expression(input,'on','change'),'handleReportDateRangeChange')
  }
  const button=byClass('period-generate-btn')
  assert.equal(expression(button,'if'),'canGenerateReports')
  assert.equal(expression(button,'on','click'),'startGeneration({ force: true })')
  assert.equal(normalized(expression(button,'bind','disabled')),
    'loading || workspaceSaving || templateUnavailable || !validReportDateRange || (isNonOilReport && !!nonOilRectificationError)')
})

test('all six report types expose HTML reading without generation privileges or a legacy type exclusion',()=>{
  const switches=elements.filter(node=>node.tag==='ReportViewModeSwitch')
  assert.equal(switches.length,2)
  assert.equal(expression(switches[0],'if'),undefined)
  assert.equal(expression(switches[1],'if'),'hasReport')
  for(const toggle of switches){
    assert.equal(expression(toggle,'model'),'reportDisplayMode')
    assert.equal(expression(toggle,'bind','disabled'),undefined)
  }
  assert.doesNotMatch(source,/查看文字汇总|查看HTML报告|返回PPT预览/)
  assert.match(source,/const reportDisplayMode = ref\(isDepartmentView.value \? 'html' : readReportViewMode\(\)\)/)
  assert.match(source,/watch\(reportDisplayMode, \(mode\) => \{ if \(!isDepartmentView.value\) saveReportViewMode\(mode\) \}\)/)
  assert.doesNotMatch(source,/watch\(selectedReportType,.*reportDisplayMode/)
  const ppt=elements.find(node=>node.tag==='section'&&expression(node,'else-if')==="hasReport && reportDisplayMode === 'ppt'")
  assert.ok(ppt)
  assert.ok(byClass('report-document-html'))
  assert.equal(byClass('studio-html-note'),undefined)
  assert.doesNotMatch(source,/HTML阅读版 · 使用最后成功生成的报告数据/)
  const html=elements.find(node=>node.tag==='ReportHtmlContent')
  assert.equal(expression(html,'if'),'isQualityMeasurementReport || isNonOilReport || (isEquipmentFacilitiesReport && report.equipment_analysis)')
  assert.equal(expression(html,'bind','report'),'report')
  assert.equal(expression(html,'bind','report-type'),'selectedReportType')
  assert.doesNotMatch(source,/handleQualitySlideKeydown|currentNonOilSlideUrl|currentQualitySlide/)
  const exp=byClass('export-ppt-btn')
  assert.equal(expression(exp,'on','click'),'exportCurrentReport')
  assert.equal(expression(exp,'bind','disabled'),'!hasReport || loading || templateUnavailable || htmlExporting')
})

test('shared configurations, classification editing and native PPT preview retain all entry points',()=>{
  for(const name of ['openSourceDialog','openSelectionSettingsDialog','openFlowClassificationDialog',
                    'openNonOilIssueLibraryDialog','openNonOilClassificationDialog','openNonOilKeyClassificationDialog']){
    assert.ok(elements.some(node=>expression(node,'on','click')===name),name)
  }
  const preview=elements.find(node=>node.tag==='ReportPptPreview')
  assert.equal(expression(preview,'bind','report-type'),'selectedReportType')
  assert.equal(expression(preview,'bind','snapshot-id'),'Number(selectedSnapshotId)')
  assert.equal(expression(preview,'bind','generated-at'),'reportGeneratedAt')
  assert.equal(expression(preview,'on','ready'),'exportTask = $event')
  assert.ok(elements.some(node=>node.tag==='EquipmentReportTopics'))
  assert.ok(elements.some(node=>node.tag==='NonOilRectificationPeriod'&&expression(node,'bind','readonly')==='!canGenerateReports'))
})

test('generation history remains noninteractive and a configuration mismatch warning remains visible',()=>{
  const item=byClass('report-history-item')
  assert.equal(item.tag,'article')
  assert.equal(expression(item,'on','click'),undefined)
  assert.equal(item.props.some(p=>p.name==='tabindex'||(p.name==='role'&&p.value?.content==='button')),false)
  assert.equal(expression(byClass('workspace-pending-note'),'if'),'hasSavedReportChanges')
  assert.match(source,/当前设置与成稿不同，保存后需重新生成才能应用。/)
})

test('workflow navigation only scrolls and focuses the chosen section, respecting reduced motion',()=>{
  const code=source.slice(source.indexOf('function focusReportSection('),source.indexOf('onMounted(async'))
  for(const reduce of [true,false]){
    const calls=[]
    const context=vm.createContext({document:{getElementById:id=>id==='missing'?null:{scrollIntoView:value=>calls.push(['scroll',value.behavior]),focus:value=>calls.push(['focus',value.preventScroll])}},
      window:{matchMedia:()=>({matches:reduce})}})
    vm.runInContext(code,context)
    context.focusReportSection('report-studio-period')
    assert.deepEqual(calls,[['scroll',reduce?'auto':'smooth'],['focus',true]])
    context.focusReportSection('missing')
    assert.equal(calls.length,2)
  }
  assert.doesNotMatch(code,/axios|fetch\(|startGeneration|saveReport/)
})

test('only actual background jobs are labelled AI generation during initial report reading',()=>{
  assert.match(source,/activeJob \? generationStageMessage : '正在读取报告与已保存配置'/)
  assert.equal(expression(byClass('ai-progress-track'),'if'),'activeJob')
  assert.equal(expression(byClass('ai-stage-list'),'if'),'activeJob')
})
