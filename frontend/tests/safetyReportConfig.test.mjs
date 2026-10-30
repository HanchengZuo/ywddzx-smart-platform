import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as vue from 'vue'
import * as safetyUtils from '../src/utils/safetyReportConfig.js'
import {
  manualClassificationChanges,
  safetyFocusSelection,
  safetyFocusCategory,
  safetyFocusName,
  safetyAnalysisReady,
  safetySubgroups,
  safetyClassificationDraft,
  safetyFixedCategories,
  safetySlotLimit,
  safetySelectedGroup,
  safetyRepresentativeIds,
  safetyRepresentativeOrder,
  safetyPptPicks,
  safetyMoveIssue,
  safetyGroupingEdited,
  safetyRequirementChanges,
  safetyUpdatedAt,
  safetyIssueSearch,
  videoTypicalGroups,
  videoTypicalSelection,
  videoTypicalIssue,
} from '../src/utils/safetyReportConfig.js'
import { reportConfigurationDiffers } from '../src/utils/reportConfiguration.js'

test('opening and saving AI evidence does not manufacture manual overrides', () => {
  const baseline = {
    'onsite:设备设施': { assignments: { 1: '接地' }, summaries: { 接地: '接地缺失' } },
  }
  assert.deepEqual(manualClassificationChanges(baseline, baseline, {}), {})
  const draft = structuredClone(baseline)
  draft['onsite:设备设施'].assignments[1] = '维护'
  draft['onsite:设备设施'].summaries.维护 = '连接待维护'
  assert.deepEqual(manualClassificationChanges(draft, baseline, {}), {
    'onsite:设备设施': { assignments: { 1: '维护' }, summaries: { 维护: '连接待维护' } },
  })
  assert.equal(baseline['onsite:设备设施'].assignments[1], '接地')
})

const sourceOf = (name) =>
  readFileSync(new URL(`../src/components/${name}.vue`, import.meta.url), 'utf8')

function componentHarness(name, props = {}, axios = {}) {
  const { descriptor } = parse(sourceOf(name))
  const compiled = compileScript(descriptor, { id: name, genDefaultAs: 'component' })
  const code = compiled.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*\n/gm, '')
  const cleanup = [],
    events = [],
    scope = vue.effectScope()
  const environment = {
    ...vue,
    ...safetyUtils,
    onBeforeUnmount: (fn) => cleanup.push(fn),
    axios: { isCancel: () => false, ...axios },
    SafetyRequirementsPanel: {},
    SafetyEvidencePanel: {},
    document: { activeElement: { focus() {} } },
    setTimeout: () => 0,
    clearTimeout() {},
  }
  const bindings = Object.keys(compiled.imports).concat('document', 'setTimeout', 'clearTimeout')
  const component = new Function(...bindings, `${code}\nreturn component`)(
    ...bindings.map((key) => environment[key]),
  )
  const actualProps = vue.reactive(
    Object.fromEntries(
      Object.entries(component.props).map(([key, definition]) => [
        key,
        Object.hasOwn(props, key)
          ? props[key]
          : typeof definition?.default === 'function' && definition.type !== Function
            ? definition.default()
            : definition?.default,
      ]),
    ),
  )
  const state = scope.run(() =>
    component.setup(actualProps, { expose() {}, emit: (...args) => events.push(args) }),
  )
  return {
    state,
    props: actualProps,
    events,
    dispose() {
      cleanup.forEach((fn) => fn())
      scope.stop()
    },
  }
}

function evidenceFixture() {
  return {
    key: 'onsite:devices',
    mode: 'onsite',
    category: 'devices',
    name: '设备设施',
    slot_limit: 6,
    issues: Array.from({ length: 9 }, (_, index) => ({
      issue_id: index + 1,
      mode: 'onsite',
      topic: '设备设施',
      description: `问题${index + 1}`,
      station_name: '测试站',
      issue_photo: `${index + 1}.jpg`,
      requirement: '应确保接地连接完好。',
      requirement_status: 'ready',
    })),
    analysis: {
      complete: true,
      representatives_ready: true,
      groups: [
        {
          name: '接地',
          summary: '接地缺失',
          issue_ids: [1, 2, 3, 4],
          representative_issue_ids: [4, 2, 1],
          representative_source: 'ai',
        },
        {
          name: '标志',
          summary: '标志缺失',
          issue_ids: [5, 6],
          representative_issue_ids: [6, 5],
          representative_source: 'ai',
        },
        {
          name: '维护',
          summary: '维护不到位',
          issue_ids: [7, 8],
          representative_issue_ids: [8, 7],
          representative_source: 'ai',
        },
        {
          name: '隔离',
          summary: '隔离不到位',
          issue_ids: [9],
          representative_issue_ids: [9],
          representative_source: 'ai',
        },
      ],
    },
  }
}

function configFixture() {
  const category = evidenceFixture()
  return {
    success: true,
    settings: {
      station_ids: null,
      typical_issue_ids: {},
      typical_video_category: '',
      focus_category: '',
      classifications: {},
      requirements_signature: 'canonical-library-v4',
    },
    meta: { revision: 7, updated_by_name: '配置管理员', updated_at: '2026-10-30 10:00:00' },
    data_signature: 'issues-v2',
    categories: [
      category,
      {
        ...structuredClone(category),
        key: 'video:unload',
        mode: 'video',
        category: 'unload',
        slot_limit: 3,
      },
    ],
    issues: category.issues,
    stations: [],
    summary: {},
    focus_categories: [{ name: '设备设施', count: 9 }],
  }
}

test('requirements and evidence components compile, have no all-issues navigation, and precede monthly focus', () => {
  for (const name of ['SafetyReportConfig', 'SafetyRequirementsPanel', 'SafetyEvidencePanel']) {
    const { descriptor, errors } = parse(sourceOf(name))
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: name })
    const compiled = compileTemplate({
      source: descriptor.template.content,
      id: name,
      compilerOptions: { bindingMetadata: script.bindings },
    })
    assert.deepEqual(compiled.errors, [])
  }
  const source = sourceOf('SafetyReportConfig')
  assert.ok(source.indexOf('<SafetyRequirementsPanel') < source.indexOf('04 · 月度重点'))
  assert.doesNotMatch(source, /selectedGroup === ''|评分说明/)
  assert.doesNotMatch(sourceOf('SafetyEvidencePanel'), /全部问题|评分说明/)
  assert.match(sourceOf('SafetyEvidencePanel'), /AI挑选代表问题/)
  assert.match(sourceOf('SafetyEvidencePanel'), /规范要求/)
})

test('exclusive tools use the requested row-major two-by-two order and requirements open in a dialog', () => {
  const source = sourceOf('SafetyReportConfig')
  const positions = [
    '02 · 典型选题',
    '<SafetyRequirementsPanel',
    '04 · 月度重点',
    '05 · 固定章节证据',
  ].map((label) => source.indexOf(label))
  assert.ok(
    positions.every(
      (position, index) => position >= 0 && (!index || position > positions[index - 1]),
    ),
  )
  assert.match(source, /grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/)
  const requirements = sourceOf('SafetyRequirementsPanel')
  assert.match(requirements, /03 · 规范要求/)
  assert.match(requirements, /<Teleport to="body">/)
  assert.match(requirements, /role="dialog"/)
  assert.match(requirements, /@keydown\.tab="trapFocus"/)
  assert.doesNotMatch(requirements, /收起规范要求|aria-expanded/)
})

test('closing the requirements dialog retains unsaved edits and reopening makes no AI request', async () => {
  const calls = []
  const harness = componentHarness(
    'SafetyRequirementsPanel',
    { canGenerate: true, busy: false },
    {
      async get() {
        calls.push('get')
        return {
          data: {
            can_generate: true,
            standards: [{ key: 'onsite:1', requirement: '原要求', status: 'ready' }],
          },
        }
      },
      async post() {
        throw new Error('no paid AI while opening')
      },
    },
  )
  try {
    const s = harness.state
    await s.toggle()
    await vue.nextTick()
    assert.equal(s.expanded.value, true)
    s.draft.value['onsite:1'] = '未保存要求'
    s.close()
    assert.equal(s.expanded.value, false)
    await s.toggle()
    assert.equal(s.draft.value['onsite:1'], '未保存要求')
    assert.deepEqual(calls, ['get'])
    assert.equal(s.changes.value.length, 1)
  } finally {
    harness.dispose()
  }
})

test('materialized representatives never create manual choices, while explicit order and empty selections do', () => {
  const category = evidenceFixture(),
    baseline = { [category.key]: safetyClassificationDraft(category) }
  assert.deepEqual(manualClassificationChanges(structuredClone(baseline), baseline, {}), {})
  const draft = structuredClone(baseline)
  draft[category.key].representatives.接地 = [2, 4]
  assert.deepEqual(manualClassificationChanges(draft, baseline, {}), {
    [category.key]: { assignments: {}, summaries: {}, representatives: { 接地: [2, 4] } },
  })
  draft[category.key].representatives.接地 = []
  assert.deepEqual(manualClassificationChanges(draft, baseline, {})[category.key].representatives, {
    接地: [],
  })
  assert.deepEqual(baseline[category.key].representatives.接地, [4, 2, 1])
  const saved = {
    [category.key]: { assignments: {}, summaries: {}, representatives: { 接地: [2, 4] } },
  }
  assert.deepEqual(manualClassificationChanges(saved, structuredClone(saved), saved), saved)
})

test('PPT picks use highest three monthly subgroups and ordered round-robin fixed slots', () => {
  const category = evidenceFixture(),
    draft = safetyClassificationDraft(category)
  assert.equal(safetyAnalysisReady(category), true)
  assert.deepEqual(
    safetyPptPicks(category, draft).map((pick) => pick.issue_id),
    [4, 6, 8, 9, 2, 5],
  )
  assert.deepEqual(
    safetyPptPicks(category, draft, true).map((pick) => pick.issue_id),
    [4, 6, 8],
  )
  category.slot_limit = 3
  assert.deepEqual(
    safetyPptPicks(category, draft).map((pick) => pick.issue_id),
    [4, 6, 8],
  )
  draft.representatives.接地 = [2, 4]
  assert.equal(safetyPptPicks(category, draft)[0].issue_id, 2)
  assert.deepEqual(safetyRepresentativeIds(category, draft, '接地'), [2, 4])
  category.issues[1].issue_photo = ''
  assert.equal(safetyPptPicks(category, draft)[0].issue_id, 4)
})

test('representative priorities reset to AI on empty and never invent pending AI picks', () => {
  const category = evidenceFixture(),
    draft = safetyClassificationDraft(category)
  draft.representatives.接地 = [2]
  assert.deepEqual(safetyRepresentativeOrder(category, draft, '接地'), [2, 4, 1, 3])
  draft.representatives.接地 = []
  assert.deepEqual(safetyRepresentativeOrder(category, draft, '接地'), [4, 2, 1, 3])
  category.analysis.groups[0].representative_issue_ids = [1, 4, 2]
  category.analysis.groups[0].ai_representative_issue_ids = [4, 2, 1]
  assert.deepEqual(safetyRepresentativeOrder(category, draft, '接地'), [4, 2, 1, 3])
  category.analysis.representatives_ready = false
  assert.deepEqual(safetyPptPicks(category, draft), [])
  draft.representatives.接地 = [2]
  assert.deepEqual(safetyPptPicks(category, draft), [])
  assert.deepEqual(safetyPptPicks(category, draft, false, { representatives: { 接地: [2] } }), [
    { name: '接地', issue_id: 2 },
  ])
})

test('ISO requirement update times are localized for readers', () => {
  assert.match(safetyUpdatedAt('2026-10-30T02:03:04Z'), /10:03:04/)
  assert.doesNotMatch(safetyUpdatedAt('2026-10-30T02:03:04Z'), /T|Z/)
  assert.equal(safetyUpdatedAt(''), '')
})

test('manual reassignment clears incompatible representative IDs and exposes unsaved grouping edits', () => {
  const category = evidenceFixture(),
    baseline = safetyClassificationDraft(category),
    draft = structuredClone(baseline)
  assert.equal(safetyGroupingEdited(draft, baseline), false)
  draft.representatives.接地 = [2, 4]
  assert.equal(safetyGroupingEdited(draft, baseline), false)
  safetyMoveIssue(draft, 2, '标志')
  assert.deepEqual(draft.representatives.接地, [4])
  assert.equal(safetyGroupingEdited(draft, baseline), true)
  const rematerialized = safetyClassificationDraft(category, {
    assignments: { 4: '标志' },
    representatives: { 接地: [4, 2] },
  })
  assert.deepEqual(rematerialized.representatives.接地, [2])
})

test('fixed category navigation excludes typical and topic scopes and obeys slot limits', () => {
  const category = evidenceFixture(),
    video = { ...category, key: 'video:unload', mode: 'video', category: 'unload', slot_limit: 3 }
  assert.deepEqual(
    safetyFixedCategories(
      [
        category,
        video,
        { ...category, category: '__typical__' },
        { ...category, category: 'topic:设备设施' },
      ],
      'onsite',
    ),
    [category],
  )
  assert.deepEqual(safetyFixedCategories([category, video], 'video'), [video])
  assert.equal(safetySlotLimit(category), 6)
  assert.equal(safetySlotLimit(video), 3)
  assert.equal(safetySlotLimit({ mode: 'onsite', category: 'other' }), 6)
  assert.equal(safetySlotLimit({ ...category, category: 'topic:设备设施' }), 3)
  assert.equal(
    safetySelectedGroup(
      [
        { name: '空类', count: 0 },
        { name: '高频', count: 4 },
        { name: '低频', count: 1 },
      ],
      '空类',
    ),
    '高频',
  )
})

test('evidence component selects nonempty groups, supports manual ordering, and retains classes without AI representatives', async () => {
  const category = evidenceFixture()
  const harness = componentHarness('SafetyEvidencePanel', {
    category,
    override: safetyClassificationDraft(category),
    manual: {},
    monthly: false,
    busy: false,
  })
  try {
    const s = harness.state
    assert.equal(s.ready.value, true)
    assert.equal(s.selectedGroup.value, '接地')
    assert.equal(s.visibleIssues.value.length, 4)
    s.moveRepresentative(1, -1)
    assert.deepEqual(harness.events.at(-1), ['representatives', '接地', [2, 4, 1, 3]])
    s.keyword.value = '问题2'
    assert.equal(s.visibleIssues.value.length, 1)
    harness.props.category = { ...structuredClone(category), key: 'video:unload' }
    harness.props.override = safetyClassificationDraft(harness.props.category, {
      assignments: { 1: '标志', 2: '标志', 3: '标志', 4: '标志' },
    })
    await vue.nextTick()
    assert.equal(s.selectedGroup.value, '标志')
    assert.equal(s.keyword.value, '')
    harness.props.monthly = true
    s.toggleRepresentative(5, true)
    assert.deepEqual(harness.events.at(-1), ['representatives', '标志', [6, 5]])
    harness.props.category.analysis.representatives_ready = false
    await vue.nextTick()
    assert.equal(s.ready.value, true)
    assert.deepEqual(s.pptPicks.value, [])
    harness.props.manual = { representatives: { 标志: [5] } }
    harness.props.override.representatives.标志 = [5]
    assert.equal(s.representativesManual.value, true)
    assert.deepEqual(s.representatives.value, [5])
    s.resetRepresentatives()
    assert.deepEqual(harness.events.at(-1), ['representatives', '标志', []])
    harness.props.manual.representatives.标志 = []
    harness.props.override.representatives.标志 = []
    assert.equal(s.representativesManual.value, false)
    assert.deepEqual(s.representatives.value, [])
  } finally {
    harness.dispose()
  }
})

test('requirements changes include only explicitly edited text with per-row source and revision', () => {
  const rows = [
    { key: 'onsite:1', requirement: '原要求', source_signature: 'source1', revision: 3 },
    { key: 'video:2', requirement: '', source_signature: 'source2', revision: 4 },
  ]
  assert.deepEqual(safetyRequirementChanges(rows, { 'onsite:1': '原要求', 'video:2': '' }), [])
  assert.deepEqual(safetyRequirementChanges(rows, { 'onsite:1': '', 'video:2': '新要求' }), [
    { key: 'onsite:1', source_signature: 'source1', revision: 3, requirement: '' },
    { key: 'video:2', source_signature: 'source2', revision: 4, requirement: '新要求' },
  ])
})

test('requirements GET and save do not generate AI; generation is explicit, permission gated and save-first', async () => {
  const catalog = {
    success: true,
    catalog_signature: 'catalog-v2',
    can_generate: true,
    standards: [
      {
        key: 'onsite:1',
        mode: 'onsite',
        requirement: '旧要求',
        source_signature: 'source-v1',
        revision: 4,
        status: 'stale',
        fields: { 检查内容: '接地' },
      },
      {
        key: 'video:2',
        mode: 'video',
        requirement: '',
        source_signature: 'source-v2',
        revision: 1,
        status: 'missing',
        fields: {},
      },
    ],
  }
  const calls = []
  const harness = componentHarness(
    'SafetyRequirementsPanel',
    { canGenerate: false, busy: false },
    {
      async get(url, options) {
        calls.push(['get', url, options])
        return { data: structuredClone(catalog) }
      },
      async put(url, body) {
        calls.push(['put', url, body])
        return {
          data: {
            ...structuredClone(catalog),
            standards: catalog.standards.map((row) => ({
              ...row,
              requirement:
                body.changes.find((change) => change.key === row.key)?.requirement ??
                row.requirement,
            })),
          },
        }
      },
      async post(url, body) {
        calls.push(['post', url, body])
        return { data: { ...structuredClone(catalog), counts: { generated: 2 } } }
      },
    },
  )
  try {
    const s = harness.state
    assert.equal(calls.length, 0)
    s.toggle()
    await vue.nextTick()
    assert.equal(calls[0][0], 'get')
    assert.ok(calls[0][2].signal)
    await s.generate()
    assert.equal(calls.length, 1)
    s.draft.value['onsite:1'] = '人工修订要求'
    harness.props.canGenerate = true
    await s.generate()
    assert.equal(calls.length, 1)
    await s.save()
    assert.deepEqual(calls[1], [
      'put',
      '/api/inspection-reports/safety-requirements',
      {
        catalog_signature: 'catalog-v2',
        changes: [
          {
            key: 'onsite:1',
            source_signature: 'source-v1',
            revision: 4,
            requirement: '人工修订要求',
          },
        ],
      },
    ])
    assert.deepEqual(harness.events, [['saved']])
    await s.generate()
    assert.deepEqual(calls[2], [
      'post',
      '/api/inspection-reports/safety-requirements',
      { catalog_signature: 'catalog-v2' },
    ])
    assert.deepEqual(harness.events, [['saved'], ['saved']])
  } finally {
    harness.dispose()
  }
})

test('requirements conflicts retain edits without emitting saved or retrying AI', async () => {
  const harness = componentHarness(
    'SafetyRequirementsPanel',
    { canGenerate: true, busy: false },
    {
      async put() {
        throw { response: { data: { error: '规范已更新，请重新核对' } } }
      },
    },
  )
  try {
    const s = harness.state
    s.adopt({
      catalog_signature: 'v1',
      standards: [{ key: '1', requirement: '旧要求', revision: 1, source_signature: 's1' }],
    })
    s.draft.value['1'] = '未保存修订'
    await s.save()
    assert.equal(s.error.value, '规范已更新，请重新核对')
    assert.equal(s.draft.value['1'], '未保存修订')
    assert.equal(s.changes.value.length, 1)
    assert.deepEqual(harness.events, [])
  } finally {
    harness.dispose()
  }
})

test('failed requirements generation refreshes completed batches without retrying AI', async () => {
  const calls = []
  const harness = componentHarness(
    'SafetyRequirementsPanel',
    { canGenerate: true, busy: false },
    {
      async post() {
        calls.push('post')
        throw { response: { data: { error: '规范13021需核对参数' } } }
      },
      async get() {
        calls.push('get')
        return {
          data: {
            can_generate: true,
            library_signature: 'after',
            standards: [{ key: 'onsite:1', requirement: '已生成要求', status: 'ready' }],
          },
        }
      },
    },
  )
  try {
    const s = harness.state
    s.adopt({
      can_generate: true,
      catalog_signature: 'source',
      library_signature: 'before',
      standards: [{ key: 'onsite:1', requirement: '', status: 'missing' }],
    })
    await s.generate()
    assert.deepEqual(calls, ['post', 'get'])
    assert.equal(s.error.value, '规范13021需核对参数')
    assert.equal(s.draft.value['onsite:1'], '已生成要求')
    assert.equal(s.pendingCount.value, 0)
    assert.deepEqual(harness.events, [['saved']])
  } finally {
    harness.dispose()
  }
})

test('global save preserves requirements signature and only explicit representative changes', async () => {
  const value = configFixture(),
    calls = []
  const harness = componentHarness(
    'SafetyReportConfig',
    {
      dateFrom: '2026-10-01',
      dateTo: '2026-10-31',
      month: '2026-10',
      canGenerate: true,
      busy: false,
    },
    {
      async get(url, options) {
        calls.push(['get', url])
        return {
          data: url.endsWith('safety-config')
            ? structuredClone(value)
            : {
                analysis: structuredClone(value.categories[0].analysis),
                issues: value.issues,
                revision: 7,
                data_signature: 'issues-v2',
              },
        }
      },
      async put(url, body) {
        calls.push(['put', url, body])
        return { data: { ...structuredClone(value), settings: body.settings } }
      },
      async post(url, body) {
        calls.push(['post', url, body])
        return { data: { analysis: structuredClone(value.categories[0].analysis) } }
      },
    },
  )
  try {
    const s = harness.state
    await s.load()
    await s.open('evidence')
    await vue.nextTick()
    assert.equal(
      calls.some(([method]) => method === 'post'),
      false,
    )
    assert.equal(s.savedLabel.value.includes('配置管理员'), true)
    s.setRepresentatives('接地', [2, 4])
    s.setSummary('接地', '待保存描述')
    await s.analyze()
    assert.equal(
      calls.some(([method]) => method === 'post'),
      false,
    )
    await s.save()
    const body = calls.find(([method]) => method === 'put')[2]
    assert.equal(body.settings.requirements_signature, 'canonical-library-v4')
    assert.equal(body.revision, 7)
    assert.deepEqual(body.settings.classifications, {
      'onsite:devices': {
        assignments: {},
        summaries: { 接地: '待保存描述' },
        representatives: { 接地: [2, 4] },
      },
    })
    await s.open('evidence')
    await vue.nextTick()
    await s.analyze()
    assert.equal(calls.filter(([method]) => method === 'post').length, 1)
    await s.requirementsSaved()
    assert.equal(
      calls.filter(([method, url]) => method === 'get' && url.endsWith('safety-config')).length,
      2,
    )
    assert.equal(harness.events.filter(([event]) => event === 'saved').length, 2)
  } finally {
    harness.dispose()
  }
})

test('switching fixed scopes aborts stale reads and rejects obsolete responses', async () => {
  const value = configFixture(),
    reads = []
  const harness = componentHarness(
    'SafetyReportConfig',
    { dateFrom: '2026-10-01', dateTo: '2026-10-31', busy: false },
    {
      get(url, options) {
        if (url.endsWith('safety-config')) return Promise.resolve({ data: structuredClone(value) })
        return new Promise((resolve) => reads.push({ resolve, options }))
      },
    },
  )
  try {
    const s = harness.state
    await s.load()
    await s.open('evidence')
    assert.equal(reads.length, 1)
    s.selectEvidenceMode('video')
    assert.equal(reads.length, 2)
    assert.equal(reads[0].options.signal.aborted, true)
    reads[0].resolve({
      data: {
        analysis: { groups: [{ name: '过期响应', issue_ids: [1] }] },
        issues: [],
        revision: 7,
        data_signature: 'issues-v2',
      },
    })
    await vue.nextTick()
    assert.equal(s.categoryKey.value, 'video:unload')
    assert.equal(s.focusReading.value, true)
    reads[1].resolve({
      data: {
        analysis: value.categories[1].analysis,
        issues: value.categories[1].issues,
        revision: 7,
        data_signature: 'issues-v2',
      },
    })
    await vue.nextTick()
    assert.equal(s.focusReading.value, false)
    assert.equal(s.focusError.value, '')
    assert.equal(s.currentCategory.value.analysis.groups[0].name, '接地')
  } finally {
    harness.dispose()
  }
})
test('explicit saved choices persist; removing a manual category returns it to AI', () => {
  const saved = { 'video:卸油作业': { assignments: { 2: '手动' }, summaries: {} } }
  assert.deepEqual(manualClassificationChanges(saved, saved, saved), saved)
  const draft = structuredClone(saved)
  delete draft['video:卸油作业'].assignments[2]
  assert.deepEqual(manualClassificationChanges(draft, saved, saved), {})
})
test('safety configuration warning tracks saved inputs and clears after regeneration', () => {
  const dates = { date_from: '2026-09-01', date_to: '2026-09-30' }
  const settings = {
    station_ids: null,
    typical_issue_ids: {},
    focus_category: '',
    classifications: {},
  }
  const report = { month: '2026-09', snapshot: dates, safety_settings: settings }
  const current = { ...dates, type: 'safety_quality', safety_settings: structuredClone(settings) }
  assert.equal(reportConfigurationDiffers(report, current), false)
  current.safety_settings.focus_category = '设备设施'
  assert.equal(reportConfigurationDiffers(report, current), true)
  report.safety_settings = structuredClone(current.safety_settings)
  assert.equal(reportConfigurationDiffers(report, current), false)
})
test('focus selection and issue membership use topics, not inspection-content phrases', () => {
  const topics = [
    { name: '设备设施', count: 4 },
    { name: '污染防治', count: 3 },
  ]
  assert.equal(safetyFocusSelection('油罐操作井', topics), '')
  assert.equal(safetyFocusSelection('设备设施', topics), '设备设施')
  const result = safetyFocusCategory('设备设施', [
    { issue_id: 1, mode: 'onsite', topic: '设备设施', category_name: '油罐操作井' },
    { issue_id: 2, mode: 'onsite', topic: '设备设施', category_name: '配发电' },
    { issue_id: 3, mode: 'onsite', topic: '污染防治', category_name: '设备设施' },
    { issue_id: 4, mode: 'video', topic: '设备设施', category_name: '设备设施' },
  ])
  assert.equal(result.key, 'onsite:topic:设备设施')
  assert.deepEqual(
    result.issues.map((issue) => issue.issue_id),
    [1, 2],
  )
})
test('safety configuration compiles with actual Vue bindings and no automatic AI call', () => {
  const source = readFileSync(
    new URL('../src/components/SafetyReportConfig.vue', import.meta.url),
    'utf8',
  )
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'safety-config' })
  const output = compileTemplate({
    source: descriptor.template.content,
    id: 'safety-config',
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(output.errors, [])
  assert.match(source, /:disabled="!canGenerate \|\| analyzing/)
  assert.match(source, /\/safety-analysis/)
  assert.match(source, /signal: controller.signal/)
})

test('monthly theme defaults to highest frequency and excludes empty catalog entries', () => {
  const options = [
    { name: '空主题', count: 0 },
    { name: '污染防治', count: 3 },
    { name: '设备设施', count: 4 },
  ]
  assert.equal(safetyFocusName('', options), '设备设施')
  assert.equal(safetyFocusName('污染防治', options), '污染防治')
  assert.equal(safetyFocusName('空主题', options), '设备设施')
  assert.equal(safetyFocusName('', []), '')
})

test('analysis is ready only with complete unique coverage, never from manual overrides alone', () => {
  const category = {
    issues: [{ issue_id: 1 }, { issue_id: 2 }],
    analysis: { groups: [{ issue_ids: [1, 2] }] },
  }
  assert.equal(safetyAnalysisReady(category), true)
  category.analysis.groups[0].issue_ids = [1, 1]
  assert.equal(safetyAnalysisReady(category), false)
  category.analysis.groups[0].issue_ids = [1, 99]
  assert.equal(safetyAnalysisReady(category), false)
  category.analysis.groups[0].issue_ids = [1, 2]
  category.analysis.complete = false
  assert.equal(safetyAnalysisReady(category), false)
  assert.equal(safetyAnalysisReady({ issues: [], analysis: { groups: [] } }), false)
})

test('subgroup navigation is isolated to selected theme and supports manual empty categories', () => {
  const category = { issues: [{ issue_id: 1 }, { issue_id: 2 }] }
  const manual = {
    assignments: { 1: '接地', 2: '接地', 3: '其他主题' },
    summaries: { 接地: '接地缺失', 新类别: '' },
  }
  assert.deepEqual(safetySubgroups(category, manual), [
    { name: '接地', count: 2 },
    { name: '新类别', count: 0 },
  ])
})

test('candidate search keeps mode filtering and searches ID, station and description locally', () => {
  const rows = [
    { issue_id: 8534, station_name: '龚路', description: '接地缺失', mode: 'onsite' },
    { issue_id: 9001, station_name: '乐都', description: '警示标志', mode: 'video' },
  ]
  for (const query of ['8534', '龚路', '接地'])
    assert.deepEqual(safetyIssueSearch(rows, query), [rows[0]])
  assert.deepEqual(
    safetyIssueSearch(
      rows.filter((i) => i.mode === 'video'),
      '接地',
    ),
    [],
  )
  assert.deepEqual(safetyIssueSearch(rows, ' '), rows)
})

test('video chooses a category by frequency or saved name, not a single issue', () => {
  const groups = videoTypicalGroups({
    issues: [{ issue_id: 1 }, { issue_id: 2 }, { issue_id: 3 }],
    analysis: {
      groups: [
        { name: '着装', issue_ids: [3] },
        { name: '隔离', issue_ids: [1, 2, 999] },
      ],
    },
  })
  assert.deepEqual(
    groups.map((g) => [g.name, g.count, g.percentage]),
    [
      ['隔离', 2, '66.7'],
      ['着装', 1, '33.3'],
    ],
  )
  assert.equal(videoTypicalSelection('', groups).name, '隔离')
  assert.equal(videoTypicalSelection('着装', groups).name, '着装')
  assert.equal(videoTypicalSelection('旧分类', groups).name, '隔离')
})

test('monthly evidence shows ordered candidates while only the first per top subgroup reaches PPT', () => {
  const category = evidenceFixture()
  const harness = componentHarness('SafetyEvidencePanel', {
    category: { ...category, slot_limit: 3 },
    override: safetyClassificationDraft(category),
    monthly: true,
  })
  try {
    const s = harness.state
    assert.deepEqual(s.representatives.value, [4, 2, 1])
    s.moveRepresentative(1, -1)
    const [, name, order] = harness.events.at(-1)
    assert.deepEqual(order, [2, 4, 1])
    harness.props.override.representatives[name] = order
    harness.props.manual = { representatives: { [name]: order } }
    assert.deepEqual(
      s.pptPicks.value.map((pick) => pick.issue_id),
      [2, 6, 8],
    )
    assert.equal(s.pptPicks.value.filter((pick) => pick.name === name).length, 1)
    s.resetRepresentatives()
    assert.deepEqual(harness.events.at(-1), ['representatives', name, []])
  } finally {
    harness.dispose()
  }
})

test('video photo selection persists without AI and resets when switching the risk category', async () => {
  const value = configFixture(),
    calls = []
  value.issues = [4, 2, 3, 5].map((id) => ({
    issue_id: id,
    mode: 'video',
    station_name: '测试站',
    description: `问题${id}`,
    issue_photo: id === 3 ? '' : `${id}.jpg`,
  }))
  value.categories.push({
    key: 'video:__typical__',
    mode: 'video',
    category: '__typical__',
    issues: value.issues,
    analysis: {
      complete: true,
      groups: [
        { name: '隔离', summary: '隔离不足', issue_ids: [4, 2, 3] },
        { name: '着装', summary: '着装不规范', issue_ids: [5] },
      ],
    },
  })
  const harness = componentHarness(
    'SafetyReportConfig',
    {
      canGenerate: false,
      month: '2026-09',
      dateFrom: '2026-09-01',
      dateTo: '2026-09-30',
    },
    {
      async get() {
        return { data: structuredClone(value) }
      },
      async put(url, body) {
        calls.push(body)
        value.settings = JSON.parse(JSON.stringify(body.settings))
        return { data: structuredClone(value) }
      },
      async post() {
        throw new Error('must not call AI')
      },
    },
  )
  try {
    const s = harness.state
    await s.load()
    await s.open('typical')
    s.selectTypicalMode('video')
    assert.equal(s.typical('video').issue_id, 2)
    assert.equal(videoTypicalIssue(value.issues, s.selectedVideoGroup.value, 3).issue_id, 2)
    assert.equal(videoTypicalIssue(value.issues, s.selectedVideoGroup.value, 5).issue_id, 2)
    s.setTypical('video', 4)
    assert.equal(s.typicalSelection('video'), 4)
    await s.save()
    assert.equal(calls[0].settings.typical_issue_ids.video, 4)
    await s.open('typical')
    assert.equal(s.typical('video').issue_id, 4)
    s.issueKeyword.value = '不存在'
    assert.equal(s.videoCandidates.value.length, 0)
    assert.equal(s.typical('video').issue_id, 4)
    s.chooseVideoCategory('着装')
    assert.equal(s.typicalSelection('video'), '')
    assert.equal(s.typical('video').issue_id, 5)
    s.setTypical('video', 5)
    s.setTypical('video', '')
    assert.equal(s.typicalSelection('video'), '')
    assert.equal(s.typical('video').issue_id, 5)
  } finally {
    harness.dispose()
  }
})

test('new default video selection does not mark an unchanged legacy snapshot dirty', () => {
  const settings = {
    station_ids: null,
    typical_issue_ids: {},
    focus_category: '',
    classifications: {},
  }
  const dates = { date_from: '2026-09-01', date_to: '2026-09-30' }
  const report = { month: '2026-09', snapshot: dates, safety_settings: settings }
  assert.equal(
    reportConfigurationDiffers(report, {
      ...dates,
      type: 'safety_quality',
      safety_settings: { ...settings, typical_video_category: '' },
    }),
    false,
  )
  assert.equal(
    reportConfigurationDiffers(report, {
      ...dates,
      type: 'safety_quality',
      safety_settings: { ...settings, typical_video_category: '着装' },
    }),
    true,
  )
})
