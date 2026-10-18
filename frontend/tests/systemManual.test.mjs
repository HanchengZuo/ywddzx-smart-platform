import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { createManualPreviewCache } from '../src/utils/manualLibrary.js'
import { PAGE_VISIBILITY_GROUPS } from '../src/config/pageVisibilityCatalog.js'

const source = readFileSync(new URL('../src/views/HelpDocumentsView.vue', import.meta.url), 'utf8')
const png = () => new Blob(['fake-png'], { type: 'image/png' })

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
    ['/help-documents', '/feedback'],
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
    assert.equal(canAccess('/help-documents', role, {}), true)
  }
  assert.match(router, /HelpDocumentsView.vue/)
  assert.match(router, /redirect: to => \(\{ path: '\/help-documents', query: to.query \}\)/)
  const fallbackBody = router
    .split('const resolveFallbackPath = ')[1]
    .split('\n\nconst verifyStoredAuthToken')[0]
  const fallback = new Function(
    'isSupervisorRole',
    'operationsPages',
    'canAccessPath',
    `return (${fallbackBody})`,
  )(() => false, [], canAccess)
  assert.equal(
    fallback('reader', {}, (path) => path === '/help-documents'),
    '/help-documents',
  )
  const app = readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8')
  assert.match(app, /canViewHelpDocuments.value \|\| canViewFeedback.value/)
  assert.ok(app.indexOf("go('/help-documents')") < app.indexOf("go('/feedback')"))
})

test('manual SFC compiles with real bindings, mobile layout and common pan/zoom component', () => {
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'system-manual' })
  assert.deepEqual(
    compileTemplate({
      source: descriptor.template.content,
      filename: 'HelpDocumentsView.vue',
      id: 'system-manual',
      compilerOptions: { bindingMetadata: script.bindings },
    }).errors,
    [],
  )
  assert.match(source, /HelpArticleBody/)
  assert.match(source, /provide\(HELP_IMAGE_CACHE, cache\)/)
  assert.match(source, /cache.dispose\(\)/)
  assert.ok(!source.includes('查看流程图'))
  assert.ok(!source.includes('参考附件'))
  assert.match(source, /max-width: 760px/)
  assert.ok(!source.includes('v-html'))
  assert.ok(!source.includes('auth_token'))
})

test('invalidating a pending figure cannot let its late rejection erase the new request', async () => {
  const waiting = [],
    revoked = []
  const cache = createManualPreviewCache(() => new Promise((resolve) => waiting.push(resolve)), {
    createObjectURL: () => 'blob:valid',
    revokeObjectURL: (url) => revoked.push(url),
  })
  const stale = cache.load('one', '/one')
  await Promise.resolve()
  cache.invalidate('one')
  const current = cache.load('one', '/one')
  await Promise.resolve()
  waiting[0](png())
  await assert.rejects(stale, { name: 'AbortError' })
  assert.equal(cache.load('one', '/one'), current)
  waiting[1](png())
  assert.equal(await current, 'blob:valid')
  cache.dispose()
  assert.deepEqual(revoked, ['blob:valid'])
})
