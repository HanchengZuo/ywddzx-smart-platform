import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import {
  createManualPreviewCache,
  filterManualDocuments,
  formatManualSize,
} from '../src/utils/manualLibrary.js'
import { PAGE_VISIBILITY_GROUPS } from '../src/config/pageVisibilityCatalog.js'

const source = readFileSync(new URL('../src/views/SystemManualView.vue', import.meta.url), 'utf8')
const png = () => new Blob(['fake-png'], { type: 'image/png' })

test('manual searches titles, descriptions, categories and tags without mutating original list', () => {
  const documents = [
    { title: '巡检流程', category: '流程', description: '确认到整改', tags: ['PDF', '审核'] },
    { title: '申诉说明', category: '申诉', description: '片区终审', tags: ['时限'] },
  ]
  assert.equal(filterManualDocuments(documents, '').length, 2)
  assert.deepEqual(filterManualDocuments(documents, 'pdf 审核'), [documents[0]])
  assert.deepEqual(filterManualDocuments(documents, '申诉 时限'), [documents[1]])
  assert.deepEqual(filterManualDocuments(documents, '无关'), [])
  assert.equal(documents.length, 2)
  assert.equal(formatManualSize(81348), '79 KB')
  assert.equal(formatManualSize(1782579), '1.7 MB')
})

test('preview cache shares pending requests, caches switches and revokes all object URLs on exit', async () => {
  const fetched = [],
    revoked = []
  const cache = createManualPreviewCache(
    async (url, options) => {
      fetched.push([url, options.signal])
      return png()
    },
    {
      createObjectURL: () => `blob:${fetched.length}`,
      revokeObjectURL: (url) => revoked.push(url),
    },
  )
  const first = cache.load('one', '/one')
  assert.equal(cache.load('one', '/one'), first)
  assert.equal(await first, 'blob:1')
  assert.equal(await cache.load('two', '/two'), 'blob:2')
  assert.equal(await cache.load('one', '/one'), 'blob:1')
  assert.equal(fetched.length, 2)
  cache.dispose()
  assert.deepEqual(revoked, ['blob:1', 'blob:2'])
  assert.ok(fetched.every(([, signal]) => signal.aborted))
  await assert.rejects(cache.load('one', '/one'), { name: 'AbortError' })
})

test('late preview results after leaving never create an object URL', async () => {
  let complete,
    created = 0
  const cache = createManualPreviewCache(
    () =>
      new Promise((resolve) => {
        complete = resolve
      }),
    {
      createObjectURL: () => {
        created++
        return 'blob:unexpected'
      },
      revokeObjectURL() {},
    },
  )
  const pending = cache.load('one', '/one')
  await Promise.resolve()
  cache.dispose()
  complete(png())
  await assert.rejects(pending, { name: 'AbortError' })
  assert.equal(created, 0)
})

test('failed and non-image preview requests can be retried, never rendered as HTML', async () => {
  let calls = 0
  const cache = createManualPreviewCache(
    async () => {
      if (++calls === 1) throw new Error('offline')
      return calls === 2 ? new Blob(['<html>'], { type: 'text/html' }) : png()
    },
    { createObjectURL: () => 'blob:valid', revokeObjectURL() {} },
  )
  await assert.rejects(cache.load('one', '/one'), /offline/)
  await assert.rejects(cache.load('one', '/one'), /not a PNG/)
  assert.equal(await cache.load('one', '/one'), 'blob:valid')
  cache.dispose()
})

test('manual is a signed-in common menu without role or individual permission gates', () => {
  const common = PAGE_VISIBILITY_GROUPS.find((group) => group.key === 'common')
  assert.deepEqual(
    common.pages.map((page) => page.path),
    ['/system-manual', '/feedback'],
  )
  const router = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  const accessBody = router
    .split('const canAccessPath = ')[1]
    .split('\n\nconst resolveFallbackPath')[0]
  const canAccess = new Function(
    'isSupervisorRole',
    'operationsPages',
    'hasPermission',
    `return (${accessBody})`,
  )(
    () => false,
    [],
    () => false,
  )
  for (const role of [
    'root',
    'station_manager',
    'area_account',
    'supervisor',
    'supervisor_manager',
    'quality',
    'unknown',
  ]) {
    assert.equal(canAccess('/system-manual', role, {}), true)
  }
  assert.match(router, /SystemManualView.vue/)
  const fallbackBody = router.split('const resolveFallbackPath = ')[1].split('\n\nconst verifyStoredAuthToken')[0]
  const fallback = new Function('isSupervisorRole', 'operationsPages', 'canAccessPath', `return (${fallbackBody})`)(
    () => false, [], canAccess,
  )
  assert.equal(fallback('reader', {}, (path) => path === '/system-manual'), '/system-manual')
  const app = readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8')
  assert.match(app, /canViewSystemManual.value \|\| canViewFeedback.value/)
  assert.ok(app.indexOf("go('/system-manual')") < app.indexOf("go('/feedback')"))
})

test('manual SFC compiles with real bindings, mobile layout and common pan/zoom component', () => {
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'system-manual' })
  assert.deepEqual(
    compileTemplate({
      source: descriptor.template.content,
      filename: 'SystemManualView.vue',
      id: 'system-manual',
      compilerOptions: { bindingMetadata: script.bindings },
    }).errors,
    [],
  )
  assert.match(source, /InspectionPhotoPreview/)
  assert.match(source, /version === previewVersion/)
  assert.match(source, /previewCache.dispose\(\)/)
  assert.match(source, /downloadController\?\.abort\(\)/)
  assert.match(source, /max-width: 760px/)
  assert.ok(!source.includes('v-html'))
  assert.ok(!source.includes('auth_token'))
})
