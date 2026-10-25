import test from 'node:test'
import assert from 'node:assert/strict'
import postcss from 'postcss'
import desktopDensity, { compactPixels } from '../build/desktopDensity.js'
import { COMPACT_DENSITY_MEDIA, REGULAR_DENSITY_MEDIA, densityMediaMode } from '../src/utils/uiDensity.js'

test('desktop density scales authored pixels without changing images, labels, percentages or viewport geometry', () => {
  assert.equal(compactPixels('14px 24px 1px -10px .5px'), '11.2px 19.2px 0.8px -8px 0.4px')
  assert.equal(compactPixels('calc(100dvh - 24px) min(100%, 960px) 2rem 1em'),
    'calc(100dvh - 19.2px) min(100%, 768px) 2rem 1em')
  const literals = 'url("/photo-100px.png") url(/photo-20px.png) "宽度 20px" \'16px\' var(--gap-20px)'
  assert.equal(compactPixels(literals), literals)
  assert.equal(compactPixels('url("/photo)20px.png") 20px'), 'url("/photo)20px.png") 16px')
})

test('desktop and mobile retain separate responsive rules, animations and viewport-sized overlays', async () => {
  const source = `:root{font-size:16px;--gap:20px}
    .panel{font-size:14px;padding:20px;width:100%;height:100dvh}
    @media(max-width:1100px){.panel{padding:12px}}
    @media(max-width:768px){.panel{padding:8px}}
    @keyframes enter{from{transform:translateY(20px)}to{transform:translateY(0)}}
    .overlay{position:fixed;inset:0;width:100vw}
    @container(max-width:400px){.cell{gap:10px}}`
  const result = await postcss([desktopDensity()]).process(source, { from: undefined })
  const [regular, compact] = result.root.nodes
  assert.equal(regular.params, REGULAR_DENSITY_MEDIA)
  assert.equal(compact.params, COMPACT_DENSITY_MEDIA)
  assert.equal(regular.nodes[0].first.value, '16px')
  assert.equal(compact.nodes[0].first.value, '12.8px')
  assert.equal(regular.nodes[2].params, '(max-width:1100px)')
  assert.equal(compact.nodes[2].params, '(max-width:880px)')
  assert.equal(compact.nodes[3].params, '(max-width:614.4px)')
  assert.match(compact.toString(), /translateY\(16px\)/)
  assert.match(compact.toString(), /height:100dvh/)
  assert.match(compact.toString(), /position:fixed;inset:0;width:100vw/)
  assert.match(compact.toString(), /@container\(max-width:320px\)/)
  assert.doesNotMatch(result.css, /\bzoom\s*:|scale\(0\.8\)/)
})

test('print and exported reports retain the regular document dimensions', async () => {
  const { readFileSync } = await import('node:fs')
  const exporter = readFileSync(new URL('../src/utils/reportHtmlExport.js', import.meta.url), 'utf8')
  assert.equal(REGULAR_DENSITY_MEDIA, `not ${COMPACT_DENSITY_MEDIA}`)
  assert.match(COMPACT_DENSITY_MEDIA, /^screen and/)
  assert.match(exporter, /densityMediaMode\(rule\.conditionText\)/)
  assert.match(exporter, /density === 'compact'\) return ''/)
  assert.match(exporter, /density === 'regular'\) return readRules\(rule\.cssRules\)/)
  for (const value of [COMPACT_DENSITY_MEDIA, 'screen and (width >= 769px)']) {
    assert.equal(densityMediaMode(value), 'compact')
  }
  for (const value of [REGULAR_DENSITY_MEDIA, 'not screen and (width >= 769px)']) {
    assert.equal(densityMediaMode(value), 'regular')
  }
  assert.equal(densityMediaMode('(max-width: 768px)'), null)
  assert.equal(densityMediaMode('screen and (min-width: 900px)'), null)
})
