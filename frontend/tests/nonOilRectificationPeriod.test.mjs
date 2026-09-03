import test from 'node:test'
import assert from 'node:assert/strict'
import {
  defaultRectificationPeriod,
  historicalRectificationPeriod,
  rectificationPeriodError,
} from '../src/utils/nonOilRectificationPeriod.js'

test('calendar-month default follows main start, including year/month end', () => {
  for (const [main, start, end] of [
    ['2026-08-15', '2026-07-15', '2026-08-14'],
    ['2026-07-01', '2026-06-01', '2026-06-30'],
    ['2026-01-01', '2025-12-01', '2025-12-31'],
    ['2026-03-31', '2026-02-28', '2026-03-30'],
    ['2024-03-31', '2024-02-29', '2024-03-30'],
  ])
    assert.deepEqual(defaultRectificationPeriod(main), { date_from: start, date_to: end })
})

test('rejects missing, invalid, reversed and excessively long ranges', () => {
  for (const [start, end] of [
    ['', ''],
    ['2026-02-30', '2026-03-01'],
    ['2026-08-01', '2026-07-01'],
    ['2024-01-01', '2026-01-01'],
  ]) {
    assert.ok(rectificationPeriodError({ date_from: start, date_to: end }))
  }
  assert.equal(rectificationPeriodError({ date_from: '2026-06-01', date_to: '2026-07-31' }), '')
})

test('history restores saved boundaries and supports old month-only reports', () => {
  const saved = { date_from: '2026-05-15', date_to: '2026-06-20' }
  assert.deepEqual(
    historicalRectificationPeriod({ generation_context: { non_oil_rectification_period: saved } }),
    saved,
  )
  assert.deepEqual(historicalRectificationPeriod({ previous_month_rectification: saved }), saved)
  assert.deepEqual(
    historicalRectificationPeriod({ previous_month_rectification: { month: '2024-02' } }),
    { date_from: '2024-02-01', date_to: '2024-02-29' },
  )
  assert.equal(historicalRectificationPeriod({}), null)
})
