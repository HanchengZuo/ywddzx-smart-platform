import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { issueExportFilterChips } from '../src/utils/issueExport.js'

const read = path => readFileSync(new URL('../src/' + path, import.meta.url), 'utf8')
for (const [file, start, end, variable] of [
  ['IssuesView.vue', 'const issueColumnDefinitions =', 'const defaultIssueColumnVisibility', 'issueColumnDefinitions'],
  ['MyIssuesView.vue', 'const myIssueColumnDefinitions =', 'const defaultMyIssueColumnKeys', 'myIssueColumnDefinitions'],
]) {
  test(`${file}: reviewer is a configurable field immediately before review time`, () => {
    const source = read('views/inspection/' + file)
    const columns = new Function(source.slice(source.indexOf(start), source.indexOf(end)) + '; return ' + variable)()
    const index = columns.findIndex(column => column.key === 'review_at')
    assert.equal(columns[index - 1].key, 'reviewer')
    assert.equal(columns[index - 1].label, '问题复核人员')
    assert.equal(columns[index].label, '问题复核时间')
    assert.equal(columns.find(column => column.key === 'review_result').label, '问题复核结果')
    assert.equal(columns.find(column => column.key === 'review_note').label, '问题复核说明')
    assert.equal(columns.find(column => column.key === 'review_photo').label, '问题复核照片')
    assert.doesNotMatch(source, /督导组复核|督导组未通过|督导组未填写/)
  })
}
test('export filter chips do not imply all reviews are by supervisors', () => {
  const chips = issueExportFilterChips({ reviewResult: '整改通过', review_result: '整改不通过' })
  assert.deepEqual(chips.map(chip => chip.label), ['问题复核结果', '问题复核结果'])
})
