import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import {
  parseHelpBody,
  filterHelpArticles,
  blankHelpContent,
  helpStatus,
} from '../src/utils/helpContent.js'

test('help paragraphs, steps, lists and notes retain text without evaluating HTML or URLs', () => {
  const blocks = parseHelpBody(
    '## 操作入口\n1. 打开菜单\n2. 提交整改\n\n- 注意状态\n> 照片选填\n<script>alert(1)</script>\n第二行',
  )
  assert.equal(blocks[0].type, 'heading')
  assert.deepEqual(blocks[1].items, ['打开菜单', '提交整改'])
  assert.equal(blocks[2].type, 'list')
  assert.equal(blocks[3].type, 'note')
  assert.equal(blocks[4].text, '<script>alert(1)</script>\n第二行')
  assert.equal(parseHelpBody('## 同名\n## 同名')[1].id, 'section-1')
})

test('article search covers actual body, intersects category, and distinguishes drafts', () => {
  const articles = [
    {
      content: {
        title: '提交整改',
        category: '整改复核',
        summary: '操作步骤',
        body: '可选复核照片',
        tags: ['站点'],
      },
    },
    {
      content: { title: '申诉', category: '问题申诉', summary: '审批', body: '片区审核', tags: [] },
    },
  ]
  assert.deepEqual(filterHelpArticles(articles, '照片 站点', '整改复核'), [articles[0]])
  assert.deepEqual(filterHelpArticles(articles, '照片', '问题申诉'), [])
  assert.equal(helpStatus({ archived: true }), '已下架')
  assert.equal(helpStatus({ published_at: '', has_draft: true }), '未发布草稿')
  assert.equal(helpStatus({ published_at: '2026-10-18', has_draft: true }), '有未发布修改')
  const first = blankHelpContent(),
    second = blankHelpContent()
  first.tags.push('x')
  assert.deepEqual(second.tags, [])
})

for (const filename of ['HelpArticleBody', 'HelpDocumentEditor']) {
  test(filename + ' compiles with safe text rendering and actual bindings', () => {
    const source = readFileSync(
      new URL(`../src/components/${filename}.vue`, import.meta.url),
      'utf8',
    )
    const { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: filename })
    assert.deepEqual(
      compileTemplate({
        source: descriptor.template.content,
        filename: filename + '.vue',
        id: filename,
        compilerOptions: { bindingMetadata: script.bindings },
      }).errors,
      [],
    )
    assert.ok(!source.includes('v-html'))
    if (filename === 'HelpDocumentEditor') {
      assert.match(source, /revision: props.item\?\.revision/)
      assert.match(source, /save\('draft'\)/)
      assert.match(source, /showModal\(\)/)
      assert.match(source, /onBeforeRouteLeave/)
    }
  })
}
