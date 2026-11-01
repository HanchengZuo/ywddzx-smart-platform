import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { certificatePages, canAccessCertificates } from '../src/config/certificateCatalog.js'
import { PAGE_VISIBILITY_GROUPS } from '../src/config/pageVisibilityCatalog.js'

test('certificate defaults apply to station/area roles and independent global grants expand only their operation', () => {
  for (const role of ['root', 'station_manager', 'area_account']) {
    for (const page of certificatePages)
      assert.equal(canAccessCertificates(role, {}, page.path), true)
  }
  for (const role of ['supervisor_manager', 'supervisor_member', 'finance', 'quality_safety']) {
    for (const page of certificatePages)
      assert.equal(canAccessCertificates(role, {}, page.path), false)
    assert.equal(
      canAccessCertificates(role, { view_all_certificates: true }, '/certificates/register'),
      false,
    )
    assert.equal(
      canAccessCertificates(role, { register_all_certificates: true }, '/certificates/ledger'),
      false,
    )
    assert.equal(
      canAccessCertificates(role, { register_all_certificates: true }, '/certificates/register'),
      true,
    )
    assert.equal(
      canAccessCertificates(role, { view_all_certificates: true }, '/certificates/reminders'),
      true,
    )
  }
})

test('certificate menu has the shared order after assessment without old inspection entry', () => {
  assert.deepEqual(
    certificatePages.map((p) => p.title),
    ['证照登记', '证照台账', '证照提醒'],
  )
  const i = PAGE_VISIBILITY_GROUPS.findIndex((g) => g.key === 'certificates')
  assert.equal(PAGE_VISIBILITY_GROUPS[i - 1].key, 'assessment')
  assert.ok(
    !PAGE_VISIBILITY_GROUPS.find((g) => g.key === 'inspection').pages.some(
      (p) => p.path === '/inspection/certificates',
    ),
  )
})

test('certificate registration/ledger/reminders compile with shared image and search controls', () => {
  const source = readFileSync(
    new URL('../src/views/certificates/CertificatesView.vue', import.meta.url),
    'utf8',
  )
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'certificates' })
  assert.deepEqual(
    compileTemplate({
      source: descriptor.template.content,
      filename: 'CertificatesView.vue',
      id: 'certificates',
      compilerOptions: { bindingMetadata: script.bindings },
    }).errors,
    [],
  )
  assert.match(source, /InspectionPhotoUpload/)
  assert.match(source, /InspectionPhotoPreview/)
  assert.match(source, /InspectionFilterSelect/)
  assert.ok(!source.includes('axios.delete'))
})
