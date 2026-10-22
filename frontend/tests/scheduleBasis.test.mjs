import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { scheduleBasis } from '../src/utils/scheduleBasis.js'

const field = (station_id, metering_priority = false) => ({
  mode: 'offline',
  station_id,
  metering_priority,
})
const preview = (groups, regions = []) => ({ groups, metering_plan: { regions } })

test('metering alone is applied when all selected field stations are quota-priority', () => {
  const basis = scheduleBasis(
    preview([field(1, true), field(2, true)], [{ target: 3, completed: 1 }]),
  )
  assert.equal(basis.metering.applied, true)
  assert.equal(basis.metering.count, 2)
  assert.equal(basis.coverage.applied, false)
  assert.match(basis.coverage.label, /仅计量优先/)
})

test('mixed final selection reports priority first and remaining coverage stations separately', () => {
  const basis = scheduleBasis(
    preview([field(1, true), field(2), field(3)], [{ target: 2, completed: 1 }]),
  )
  assert.deepEqual([basis.metering.count, basis.coverage.count], [1, 2])
  assert.ok(basis.metering.applied && basis.coverage.applied)
  assert.match(basis.coverage.detail, /先保留 1.*剩余名额.*2 站/)
})

test('completed current-month targets skip metering and use ordinary regional coverage', () => {
  const basis = scheduleBasis(
    preview(
      [field(1)],
      [
        { target: 3, completed: 3 },
        { target: 0, completed: 0 },
      ],
    ),
  )
  assert.equal(basis.metering.applied, false)
  assert.match(basis.metering.label, /本月已完成/)
  assert.equal(basis.coverage.applied, true)
})

test('unmet configuration alone does not falsely mark metering adopted', () => {
  const basis = scheduleBasis(preview([field(1)], [{ target: 3, completed: 0, reserved: 0 }]))
  assert.equal(basis.metering.applied, false)
  assert.match(basis.metering.detail, /尚未完成.*没有选入/)
  assert.equal(basis.coverage.applied, true)
  const reserved = scheduleBasis(preview([field(1)], [{ target: 3, completed: 1, reserved: 2 }]))
  assert.match(reserved.metering.label, /计划已预留/)
})

test('no monthly target goes straight to coverage; video tasks never count as field selection', () => {
  const basis = scheduleBasis(
    preview([field(1), { mode: 'online', station_id: 2 }], [{ target: 0 }]),
  )
  assert.match(basis.metering.label, /本月无目标/)
  assert.equal(basis.coverage.count, 1)
  const videoOnly = scheduleBasis(preview([{ mode: 'online', station_id: 2 }]))
  assert.equal(videoOnly.metering.applied, false)
  assert.equal(videoOnly.coverage.applied, false)
  assert.equal(scheduleBasis().coverage.count, 0)
})

test('repeated station entries count once per selection basis without mutating server data', () => {
  const data = preview([field(1, true), field(1, true), field(2), field(2)])
  const original = structuredClone(data)
  const basis = scheduleBasis(data)
  assert.deepEqual([basis.metering.count, basis.coverage.count], [1, 1])
  assert.deepEqual(data, original)
})

test('basis panels precede the scheme summary immediately above concrete plans; template compiles', () => {
  const source = readFileSync(
    new URL('../src/components/AutomaticSchedule.vue', import.meta.url),
    'utf8',
  )
  const { descriptor } = parse(source)
  const rendered = compileTemplate({
    source: descriptor.template.content,
    filename: 'AutomaticSchedule.vue',
    id: 'basis-test',
  })
  assert.deepEqual(rendered.errors, [])
  const markers = [
    '当月计量年度计划 · 优先派站依据',
    '现场片区覆盖均衡 · 查看本次分配依据',
    'class="scheme-summary"',
    '<template v-for="mode',
  ]
  const positions = markers.map((marker) => source.indexOf(marker))
  assert.ok(
    positions.every(
      (position, index) => position >= 0 && (!index || position > positions[index - 1]),
    ),
  )
  assert.match(source, /width: min\(1280px/)
  assert.match(source, /stale \? '方案待重新计算'/)
})
