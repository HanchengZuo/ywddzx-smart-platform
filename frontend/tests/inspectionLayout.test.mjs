import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'

const read = (name) => readFileSync(new URL(`../src/views/inspection/${name}.vue`, import.meta.url), 'utf8')

for (const name of ['IssuesView', 'StationMapView']) {
  test(`${name} layout compiles with actual script bindings and scoped styles`, () => {
    const filename = `${name}.vue`
    const { descriptor, errors } = parse(read(name), { filename })
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: name })
    const template = compileTemplate({
      source: descriptor.template.content,
      filename,
      id: name,
      compilerOptions: { bindingMetadata: script.bindings },
    })
    assert.deepEqual(template.errors, [])
    for (const style of descriptor.styles) {
      assert.deepEqual(compileStyle({ source: style.content, filename, id: name, scoped: true }).errors, [])
    }
  })
}

test('export modal opens after rendering, avoids duplicate showModal, and closes for native focus restoration', async () => {
  const source = read('IssuesView')
  const start = source.indexOf('watch(() => exportDialog.value.visible,')
  const watcher = source.slice(start, source.indexOf('\nlet exportPollTimer', start))
  const dialog = {
    open: false,
    opens: 0,
    closes: 0,
    showModal() { this.open = true; this.opens++ },
    close() { this.open = false; this.closes++ },
  }
  const element = { value: dialog }
  let sync
  vm.runInNewContext(watcher, {
    watch: (_get, callback) => { sync = callback },
    exportModalRef: element,
    nextTick: async () => {},
  })
  await sync(true)
  assert.equal(dialog.opens, 1)
  await sync(true)
  assert.equal(dialog.opens, 1)
  await sync(false)
  assert.equal(dialog.closes, 1)
  assert.equal(dialog.open, false)
  await sync(true)
  assert.equal(dialog.opens, 2)
  element.value = null
  await assert.doesNotReject(sync(true))
  await assert.doesNotReject(sync(false))
})
