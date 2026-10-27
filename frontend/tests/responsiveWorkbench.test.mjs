import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import postcss from 'postcss'
import { parse } from '@vue/compiler-sfc'
import config from '../vite.config.js'

const source=file=>readFileSync(new URL('../'+file,import.meta.url),'utf8')
const responsive=postcss.parse(source('src/styles/workspaceResponsive.css'))

test('normal authored sizes are no longer rewritten by a Vite/PostCSS density plugin',()=>{
  assert.equal(config.css?.postcss,undefined)
  const {descriptor}=parse(source('src/App.vue'))
  const css=postcss.parse(descriptor.styles.map(s=>s.content).join('\n'))
  const value=(selector,prop)=>css.nodes.find(node=>node.selector===selector)?.nodes.find(node=>node.prop===prop)?.value
  assert.equal(value(':root','font-size'),'16px')
  assert.equal(value('.sidebar','width'),'272px')
  assert.equal(value('.header-title','font-size'),'24px')
  assert.equal(value('.content','padding'),'24px')
  assert.doesNotMatch(source('vite.config.js'),/desktopDensity|compactPixels/)
})

test('adaptive workspace spacing responds to both width and height without scaling coordinates',()=>{
  const media=responsive.nodes.filter(node=>node.name==='media')
  assert.ok(media.some(node=>node.params.includes('max-width: 1600px')&&node.params.includes('max-height: 800px')))
  for(const rule of media)assert.match(rule.params,/min-width: (?:769|901)px/)
  responsive.walkDecls(decl=>{
    assert.ok(!['zoom','transform','scale'].includes(decl.prop))
    assert.notEqual(decl.prop,'--density')
  })
  assert.doesNotMatch(responsive.toString(),/device-pixel-ratio|resolution|userAgent|font-size:\s*80%/)
  assert.match(responsive.toString(),/\.sidebar:not\(\.collapsed\)/)
  assert.match(responsive.toString(),/flex-basis: 100%/)
})

test('workspace overrides cannot shrink report documents or teleported editors',()=>{
  responsive.walkRules(rule=>{
    for(const selector of rule.selectors){
      assert.ok(selector.startsWith('.layout')||selector.startsWith('.login-'),selector)
    }
  })
  const exporter=source('src/utils/reportHtmlExport.js')
  assert.doesNotMatch(exporter,/uiDensity|densityMediaMode|density ===/)
  assert.match(exporter,/rule\.conditionText\}\{\$\{readRules\(rule\.cssRules\)\}/)
  assert.match(exporter,/clone\.querySelectorAll\('details'\)/)
})

test('mobile touch targets retain the safe 16px text-entry size rather than inheriting a reduced root',()=>{
  const app=source('src/App.vue')
  assert.match(app,/@media \(hover: none\) and \(pointer: coarse\), \(max-width: 768px\)/)
  assert.match(app,/font-size: 16px !important;/)
  assert.doesNotMatch(source('src/main.js'),/\.style\.zoom|devicePixelRatio|scale\(0\.8\)/)
})
