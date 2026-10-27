import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { fieldDriverCount, movePreviewStudent } from '../src/utils/dailyTeamPreview.js'

test('group driver count uses current account qualifications, not forged snapshot flags', () => {
  const group = { members: [{ id: 1, has_driving_permit: true }, { id: 2 }, { id: 3 }] }
  assert.equal(fieldDriverCount(group, [{ id: 1, has_driving_permit: false }, { id: 2, has_driving_permit: true }]), 1)
  assert.equal(fieldDriverCount(group, []), 0)
  assert.equal(fieldDriverCount({ members: [] }, [{ id: 2, has_driving_permit: true }]), 0)
})

test('local drag updates the driver warning while leaving the original preview and account facts untouched', () => {
  const leader = { id: 1, position: '管理人员', mode: 'offline', leader_id: 1, group_name: '外勤甲组' }
  const student = { id: 2, position: '大学生', mode: 'offline', leader_id: 1, group_name: '外勤甲组', has_driving_permit: true }
  const preview = { groups: [{ name: '外勤甲组', mode: 'offline', leader_id: 1, members: [leader, student] }] }
  const people = [{ ...leader, available: true, has_driving_permit: false }, { ...student, available: true }]
  const after = movePreviewStudent(preview, people, 2, null)
  assert.equal(fieldDriverCount(after.groups[0], people), 0)
  assert.equal(fieldDriverCount(preview.groups[0], people), 1)
  assert.equal(after.student_leaders[2], null)
  assert.equal(people[1].has_driving_permit, true)
})

for (const file of ['views/management/UserDataManagementView.vue', 'components/UserDirectory.vue', 'components/DailyInspectionTeams.vue']) {
  test(`${file} compiles with real qualification form and grouping bindings`, () => {
    const source = readFileSync(new URL('../src/' + file, import.meta.url), 'utf8')
    const { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: 'driving-permits' })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: 'driving-permits',
      compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
    if (file.includes('UserDataManagement')) {
      assert.match(source, /v-if="isSupervisorRole\(form.role\)"/)
      assert.match(source, /has_driving_permit: false/)
      assert.match(source, /user.has_driving_permit === true/)
      assert.match(source, /has_driving_permit: isSupervisorRole\(form.role\) && form.has_driving_permit/)
    } else if (file.includes('DailyInspectionTeams')) {
      assert.match(source, /!batchAdoptable/)
      assert.match(source, /fieldDriverCount\(group, session.context.people\) > 0/)
      assert.match(source, /driverCount\(group\)/)
      assert.match(source, /movePreviewMember/)
      assert.match(source, /personnelApplyPlan\(sessions.value\[day\]\)/)
    }
  })
}
