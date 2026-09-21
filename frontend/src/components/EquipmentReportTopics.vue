<template>
  <section class="equipment-topics">
    <header class="panel-heading">
      <div>
        <small class="eyebrow">EQUIPMENT ANALYSIS</small>
        <h3>设备设施选题与依据</h3>
        <p>从共性、差异与风险三个维度审阅报告选题。</p>
      </div>
      <span class="shared-badge">全局共享设置</span>
    </header>
    <p v-if="error" role="alert" class="error">
      {{ error }} <button @click="load">重试读取</button>
    </p>
    <p v-else-if="loading">正在读取选题依据...</p>
    <div class="topic-cards">
      <button
        v-for="item in tabs"
        :key="item.key"
        class="topic-card"
        :class="item.key"
        :disabled="loading || !!error"
        @click="open(item.key)"
      >
        <span class="card-top"
          ><span class="topic-symbol" aria-hidden="true">{{ item.symbol }}</span
          ><span class="mode-badge">{{
            item.key === 'high' ? '只读依据' : '可调整选题'
          }}</span></span
        >
        <span class="card-title">{{ item.label }}</span>
        <span class="card-description">{{ item.description }}</span>
        <span class="card-bottom"
          ><span
            ><strong>{{ loading ? '—' : count(item.key) }}</strong
            ><small>{{ item.key === 'high' ? '个高频类别' : '项已选问题' }}</small></span
          ><span class="card-action"
            >{{ item.key === 'high' ? '查看依据' : '审阅选题' }}
            <span aria-hidden="true">→</span></span
          ></span
        >
      </button>
    </div>
    <div class="panel-notes">
      <p v-if="!analysis.generated">首次生成后展示 AI 选题，也可先手动设置特性、严重问题。</p>
      <p v-else>选题来源：{{ analysis.source_generated_at || '最近生成报告' }}</p>
      <p>保存不调用 AI；重新生成报告后应用选题。</p>
      <small>{{ savedLabel }}</small>
    </div>
    <p
      v-for="warning in analysis.selection_warnings || []"
      :key="warning"
      role="alert"
      class="error"
    >
      {{ warning }}
    </p>
    <Teleport to="body">
      <div v-if="active" class="equipment-topic-overlay" @click.self="close">
        <section
          ref="dialogElement"
          role="dialog"
          aria-modal="true"
          :aria-label="activeTitle"
          class="equipment-topic-dialog"
          :class="active"
          tabindex="-1"
          @keydown="onDialogKeydown"
        >
          <header class="dialog-heading">
            <div class="dialog-title">
              <span class="topic-symbol" aria-hidden="true">{{ activeTab.symbol }}</span>
              <div>
                <small class="eyebrow">{{
                  active === 'high' ? 'AI 选题 · 规范原文溯源' : 'AI 辅助 · 人工审阅'
                }}</small>
                <h3>{{ activeTitle }}</h3>
              </div>
            </div>
            <button
              class="close-button"
              :disabled="saving"
              aria-label="关闭选题面板"
              @click="close"
            >
              关闭 <span aria-hidden="true">×</span>
            </button>
          </header>
          <p v-if="error" role="alert" class="error dialog-error">{{ error }}</p>
          <template v-if="active === 'high'">
            <div class="dialog-info">
              <strong>{{ count('high') }} 个高频类别</strong
              ><span>原因直接引用规范参考表原文，不由 AI 编写。展开类别查看关联证据。</span>
            </div>
            <div class="dialog-body">
              <details
                v-for="(group, index) in analysis.high_groups || []"
                :key="group.phrase"
                class="evidence-group"
                :open="index === 0"
              >
                <summary>
                  <span class="group-index">{{ String(index + 1).padStart(2, '0') }}</span
                  ><span class="group-title">{{ group.phrase }}</span
                  ><span class="count-badge">{{ group.issues.length }} 项证据</span
                  ><span class="group-chevron" aria-hidden="true">⌄</span>
                </summary>
                <div class="group-content">
                  <div class="cause">
                    <strong>问题产生原因 <small>规范参考表原文</small></strong>
                    <p>{{ group.causes.join('\n') }}</p>
                  </div>
                  <div class="evidence-grid">
                    <article v-for="issue in group.issues" :key="issue.issue_id" class="issue-card">
                      <div class="issue-content">
                        <div class="issue-meta">
                          <span class="issue-id">#{{ issue.issue_id }}</span
                          ><span>{{ issue.management_unit }}</span>
                        </div>
                        <h4>{{ issue.station_name }}</h4>
                        <p>{{ issue.description }}</p>
                      </div>
                      <button
                        v-if="issue.issue_photo"
                        class="photo"
                        :aria-label="`查看问题 ${issue.issue_id} 的照片`"
                        @click="$emit('photo', issue)"
                      >
                        <img
                          :src="resolveImage(issue.issue_photo)"
                          alt="问题照片"
                          loading="lazy"
                        /><span>放大查看</span>
                      </button>
                    </article>
                  </div>
                </div>
              </details>
              <div v-if="!analysis.high_groups?.length" class="empty-state">
                <strong>暂无高频选题</strong>
                <p>生成报告后，可在这里查看高频类别、规范原因与问题证据。</p>
              </div>
            </div>
            <footer class="dialog-footer">
              <span>只读依据，不修改报告选题。</span
              ><button class="primary-button" @click="close">完成查看</button>
            </footer>
          </template>
          <template v-else>
            <div class="selection-toolbar">
              <div class="filters">
                <label class="search-field"
                  ><span>搜索问题</span
                  ><input v-model="keyword" placeholder="ID、站点、描述或检查短语" type="search"
                /></label>
                <label class="unit-field"
                  ><span>所属片区</span
                  ><select v-model="unit">
                    <option value="">全部片区</option>
                    <option v-for="name in units" :key="name">{{ name }}</option>
                  </select></label
                >
                <label class="selected-toggle"
                  ><input v-model="selectedOnly" type="checkbox" />仅看已选</label
                >
                <button
                  class="reset-button"
                  :disabled="!keyword && !unit && !selectedOnly"
                  @click="resetFilters"
                >
                  清空筛选
                </button>
              </div>
              <div class="selection-summary">
                <span
                  >当前 <b>{{ visibleIssues.length }}</b> 项
                  <span class="summary-divider">/</span> 已选
                  <b>{{ draft[active].length }}</b> 项</span
                ><span>{{
                  active === 'special'
                    ? '高频类别不可重复选为特性问题'
                    : '请依据实际风险确认严重问题'
                }}</span>
              </div>
            </div>
            <div class="dialog-body">
              <article
                v-for="issue in visibleIssues"
                :key="issue.issue_id"
                class="issue-card selectable"
                :class="{
                  chosen: draft[active].includes(issue.issue_id),
                  locked: active === 'special' && highIds.has(issue.issue_id),
                }"
              >
                <label class="selection-check"
                  ><input
                    v-model="draft[active]"
                    type="checkbox"
                    :value="issue.issue_id"
                    :disabled="saving || (active === 'special' && highIds.has(issue.issue_id))"
                    :aria-label="`选择问题 ${issue.issue_id} ${issue.station_name}`"
                /></label>
                <div class="issue-content">
                  <div class="issue-meta">
                    <span class="issue-id">#{{ issue.issue_id }}</span
                    ><span>{{ issue.management_unit }}</span
                    ><span
                      v-if="active === 'special' && highIds.has(issue.issue_id)"
                      class="status-badge locked-badge"
                      >高频类别 · 不可选</span
                    ><span v-else-if="draft[active].includes(issue.issue_id)" class="status-badge"
                      >已选入报告</span
                    >
                  </div>
                  <h4>{{ issue.station_name }}</h4>
                  <span class="phrase-label">{{ issue.phrase }}</span>
                  <p>{{ issue.description }}</p>
                </div>
                <button
                  v-if="issue.issue_photo"
                  class="photo"
                  :aria-label="`查看问题 ${issue.issue_id} 的照片`"
                  @click="$emit('photo', issue)"
                >
                  <img :src="resolveImage(issue.issue_photo)" alt="问题照片" loading="lazy" /><span
                    >放大查看</span
                  >
                </button>
              </article>
              <div v-if="!visibleIssues.length" class="empty-state">
                <strong>没有符合条件的问题</strong>
                <p>尝试清空筛选，或关闭“仅看已选”查看其他问题。</p>
              </div>
            </div>
            <footer class="dialog-footer">
              <div>
                <strong>{{ isDirty ? '有未保存的选题调整' : '已与保存设置一致' }}</strong
                ><span>保存不调用 AI，重新生成报告后生效。</span>
              </div>
              <div class="footer-actions">
                <button :disabled="saving" @click="close">取消</button
                ><button
                  class="primary-button"
                  :disabled="saving || loading || !isDirty"
                  @click="save"
                >
                  {{ saving ? '正在保存...' : `保存选题（${draft[active].length}）` }}
                </button>
              </div>
            </footer>
          </template>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
const props = defineProps({
  month: String,
  dateFrom: String,
  dateTo: String,
  generatedAt: String,
  librarySignature: String,
  savedLabel: String,
  resolveImage: { type: Function, required: true },
})
const emit = defineEmits(['change', 'saved', 'photo'])
const analysis = ref({}),
  loading = ref(false),
  saving = ref(false),
  error = ref(''),
  active = ref('')
const keyword = ref(''),
  unit = ref(''),
  selectedOnly = ref(false),
  draft = ref({ special: [], severe: [] })
let requestId = 0
const dialogElement = ref(null)
let previousFocus = null
const tabs = [
  {
    key: 'high',
    label: '高频问题',
    symbol: '频',
    description: '查看反复出现的问题类别，追溯规范原因与关联证据。',
  },
  {
    key: 'special',
    label: '特性问题',
    symbol: '特',
    description: '关注片区少见的差异问题，补选或调整代表性案例。',
  },
  {
    key: 'severe',
    label: '严重问题',
    symbol: '重',
    description: '核查重点风险问题，人工确认需要着重通报的选题。',
  },
]
const activeTab = computed(() => tabs.find((t) => t.key === active.value) || tabs[0])
const activeTitle = computed(() => tabs.find((t) => t.key === active.value)?.label || '')
const isDirty = computed(() =>
  ['special', 'severe'].some(
    (key) =>
      JSON.stringify([...draft.value[key]].sort((a, b) => a - b)) !==
      JSON.stringify([...(analysis.value[key + '_issue_ids'] || [])].sort((a, b) => a - b)),
  ),
)
const highIds = computed(
  () => new Set((analysis.value.high_groups || []).flatMap((g) => g.issues.map((i) => i.issue_id))),
)
const units = computed(() => [
  ...new Set((analysis.value.issues || []).map((i) => i.management_unit)),
])
const visibleIssues = computed(() =>
  (analysis.value.issues || []).filter(
    (i) =>
      (!unit.value || i.management_unit === unit.value) &&
      (!selectedOnly.value || draft.value[active.value]?.includes(i.issue_id)) &&
      `${i.issue_id} ${i.station_name} ${i.description} ${i.phrase}`.includes(keyword.value.trim()),
  ),
)
const count = (key) =>
  key === 'high'
    ? (analysis.value.high_groups || []).length
    : (analysis.value[key + '_issue_ids'] || []).length
const params = () => ({ month: props.month, date_from: props.dateFrom, date_to: props.dateTo })
function adopt(value) {
  analysis.value = value
  draft.value = {
    special: [...(value.special_issue_ids || [])],
    severe: [...(value.severe_issue_ids || [])],
  }
  emit('change', value)
}
async function load() {
  const id = ++requestId
  active.value = ''
  emit('change', null)
  if (!props.dateFrom || !props.dateTo) {
    loading.value = false
    analysis.value = {}
    return
  }
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/equipment-analysis', {
      params: params(),
    })
    if (id === requestId) adopt(response.data.analysis || {})
  } catch (err) {
    if (id === requestId) error.value = err.response?.data?.error || '选题读取失败。'
  } finally {
    if (id === requestId) loading.value = false
  }
}
function resetFilters() {
  keyword.value = ''
  unit.value = ''
  selectedOnly.value = false
}
function open(key) {
  if (loading.value || error.value) return
  draft.value = {
    special: [...(analysis.value.special_issue_ids || [])],
    severe: [...(analysis.value.severe_issue_ids || [])],
  }
  previousFocus = document.activeElement
  active.value = key
  keyword.value = ''
  unit.value = ''
  selectedOnly.value = false
  nextTick(() => dialogElement.value?.focus())
}
function close() {
  if (!saving.value) {
    active.value = ''
    previousFocus?.focus?.()
  }
}
function onDialogKeydown(event) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    close()
  }
  if (event.key !== 'Tab') return
  const targets = [
    ...dialogElement.value.querySelectorAll(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), summary',
    ),
  ]
  const first = targets[0],
    last = targets[targets.length - 1]
  if (
    event.shiftKey &&
    (document.activeElement === first || document.activeElement === dialogElement.value)
  ) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}
async function save() {
  const id = requestId
  saving.value = true
  error.value = ''
  try {
    const response = await axios.put('/api/inspection-reports/equipment-analysis', {
      ...params(),
      special_issue_ids: draft.value.special,
      severe_issue_ids: draft.value.severe,
    })
    if (id === requestId) {
      adopt(response.data.analysis)
      active.value = ''
      previousFocus?.focus?.()
      emit('saved')
    }
  } catch (err) {
    if (id === requestId) error.value = err.response?.data?.error || '保存失败。'
  } finally {
    saving.value = false
  }
}
watch(
  () => [props.month, props.dateFrom, props.dateTo, props.generatedAt, props.librarySignature],
  load,
  { immediate: true },
)
onBeforeUnmount(() => {
  requestId++
})
</script>

<style scoped>
.equipment-topics,
.equipment-topic-dialog {
  --accent: #206aaf;
  --tint: #eef6ff;
  --edge: #cadff3;
  color: #20384d;
  font-family: inherit;
  box-sizing: border-box;
}
.special {
  --accent: #13776d;
  --tint: #edf8f5;
  --edge: #bcded6;
}
.severe {
  --accent: #b54a43;
  --tint: #fff3f0;
  --edge: #f0cbc6;
}
.high {
  --accent: #206aaf;
  --tint: #eef6ff;
  --edge: #cadff3;
}
.equipment-topics {
  padding: 26px;
  border: 1px solid #d8e4ee;
  border-radius: 18px;
  background: linear-gradient(125deg, #f4f9fd, #fff 65%);
}
button,
input,
select {
  font: inherit;
  box-sizing: border-box;
}
button {
  cursor: pointer;
  border-radius: 9px;
  border: 1px solid #cddbe5;
  padding: 9px 15px;
  background: white;
  color: #35546b;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
button:focus-visible,
input:focus-visible,
select:focus-visible,
summary:focus-visible {
  outline: 3px solid #8ebce4;
  outline-offset: 3px;
}
h3,
h4,
p {
  margin: 0;
}
h3 {
  font-size: 20px;
  line-height: 1.5;
  color: #163b57;
}
p {
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.eyebrow {
  font-size: 10px;
  letter-spacing: 1.5px;
  font-weight: 700;
  color: #647f95;
}
.panel-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.panel-heading h3 {
  margin: 5px 0;
}
.panel-heading p {
  color: #6c8090;
  font-size: 13px;
}
.shared-badge {
  border: 1px solid #d9e6ef;
  background: #fff;
  border-radius: 20px;
  padding: 6px 11px;
  font-size: 11px;
  white-space: nowrap;
  color: #526f85;
}
.topic-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin: 22px 0 16px;
}
.topic-card {
  display: flex;
  flex-direction: column;
  padding: 20px;
  text-align: left;
  border-radius: 15px;
  border: 1px solid var(--edge);
  background: linear-gradient(145deg, var(--tint), #fff 70%);
  min-width: 0;
}
.topic-card:hover:not(:disabled) {
  border-color: var(--accent);
  box-shadow: 0 7px 20px #173b5910;
}
.card-top,
.card-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  width: 100%;
}
.topic-symbol {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  background: var(--accent);
  color: white;
  font-size: 18px;
  font-weight: 700;
  border-radius: 12px;
}
.mode-badge {
  color: var(--accent);
  font-size: 11px;
  background: white;
  border: 1px solid var(--edge);
  padding: 4px 8px;
  border-radius: 6px;
}
.card-title {
  font-size: 18px;
  font-weight: 700;
  margin: 17px 0 7px;
  color: #203b50;
}
.card-description {
  font-size: 12px;
  line-height: 1.85;
  color: #667b8b;
  flex: 1;
}
.card-bottom {
  border-top: 1px solid var(--edge);
  margin-top: 19px;
  padding-top: 15px;
}
.card-bottom strong {
  font-size: 30px;
  color: var(--accent);
  font-weight: 650;
  line-height: 1;
}
.card-bottom small {
  font-size: 11px;
  color: #6b8191;
  margin-left: 7px;
}
.card-action {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
}
.card-action span {
  margin-left: 7px;
}
.panel-notes {
  display: flex;
  gap: 4px 20px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #6b8090;
}
.panel-notes small {
  flex-basis: 100%;
  font-size: 11px;
  margin-top: 4px;
}
.error {
  background: #fff2ef;
  border: 1px solid #f3d1ca;
  border-radius: 9px;
  color: #ae4030;
  padding: 10px 14px;
  font-size: 13px;
  margin: 10px 0;
}
.equipment-topic-overlay {
  position: fixed;
  inset: 0;
  background: #0d253a80;
  backdrop-filter: blur(5px);
  z-index: 1300;
  display: grid;
  place-items: center;
  padding: 24px;
  box-sizing: border-box;
}
.equipment-topic-dialog {
  display: flex;
  flex-direction: column;
  width: min(1120px, 100%);
  height: min(850px, 90dvh);
  max-height: 90dvh;
  overflow: hidden;
  background: #f5f8fb;
  border: 1px solid #d9e4ed;
  border-radius: 20px;
  box-shadow: 0 30px 100px #09233650;
  outline: none;
}
.dialog-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 22px 26px;
  background: white;
  border-bottom: 1px solid #dce7ee;
  flex-shrink: 0;
}
.dialog-title {
  display: flex;
  align-items: center;
  gap: 14px;
}
.dialog-title h3 {
  margin-top: 3px;
}
.close-button {
  font-size: 12px;
}
.close-button span {
  margin-left: 12px;
  font-size: 20px;
  line-height: 1;
}
.dialog-error {
  margin: 10px 24px;
  flex-shrink: 0;
}
.dialog-info {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 16px 26px;
  background: var(--tint);
  font-size: 12px;
  color: #5e778d;
  flex-shrink: 0;
}
.dialog-info strong {
  white-space: nowrap;
  color: var(--accent);
}
.dialog-body {
  padding: 20px 26px;
  overflow: auto;
  overscroll-behavior: contain;
  min-height: 0;
  flex: 1;
  scrollbar-gutter: stable;
}
.evidence-group {
  background: white;
  border: 1px solid #dce7ee;
  border-radius: 13px;
  margin-bottom: 14px;
  overflow: hidden;
}
.evidence-group summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px;
  cursor: pointer;
  list-style: none;
}
.evidence-group summary::-webkit-details-marker {
  display: none;
}
.group-index {
  font-size: 12px;
  background: var(--tint);
  color: var(--accent);
  padding: 7px;
  border-radius: 7px;
  font-variant-numeric: tabular-nums;
}
.group-title {
  flex: 1;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.count-badge {
  font-size: 11px;
  color: var(--accent);
  white-space: nowrap;
}
.group-chevron {
  color: #6d879b;
  transition: transform 0.15s;
}
.evidence-group[open] .group-chevron {
  transform: rotate(180deg);
}
.group-content {
  padding: 0 18px 18px;
}
.cause {
  padding: 16px 18px;
  background: #f2f7fc;
  border-left: 3px solid #7fa8cd;
  border-radius: 0 9px 9px 0;
  margin-bottom: 16px;
}
.cause strong {
  font-size: 12px;
  color: #3a5b74;
}
.cause small {
  font-size: 10px;
  font-weight: 400;
  margin-left: 10px;
  color: #7b90a1;
}
.cause p {
  font-size: 13px;
  color: #455e73;
  margin-top: 7px;
}
.evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.issue-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  min-width: 0;
  border: 1px solid #dee7ef;
  border-radius: 12px;
  background: white;
  padding: 18px;
}
.issue-content {
  flex: 1;
  min-width: 0;
}
.issue-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 10px;
  font-size: 11px;
  color: #7b8fa1;
}
.issue-id {
  font-weight: 700;
  color: #496881;
  font-variant-numeric: tabular-nums;
}
.issue-card h4 {
  font-size: 15px;
  line-height: 1.6;
  margin: 5px 0;
  color: #233f54;
}
.issue-card p {
  font-size: 13px;
  color: #4c6172;
  margin-top: 8px;
}
.phrase-label {
  display: inline-block;
  background: #f2f5f8;
  color: #637d90;
  font-size: 11px;
  line-height: 1.6;
  border-radius: 5px;
  padding: 3px 7px;
}
.photo {
  width: 112px;
  padding: 0;
  border: 1px solid #dce5ed;
  overflow: hidden;
  flex-shrink: 0;
  background: #f7f9fb;
}
.photo img {
  display: block;
  width: 100%;
  height: 90px;
  object-fit: contain;
}
.photo span {
  display: block;
  text-align: center;
  font-size: 10px;
  padding: 5px;
  background: white;
  color: #648298;
}
.evidence-grid .issue-card {
  flex-wrap: wrap;
}
.evidence-grid .issue-content {
  flex-basis: 100%;
}
.evidence-grid .photo {
  width: 100%;
  max-width: 160px;
}
.selection-toolbar {
  padding: 18px 26px 12px;
  background: white;
  border-bottom: 1px solid #e0e9f0;
  flex-shrink: 0;
}
.filters {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}
.search-field {
  flex: 1;
  min-width: 0;
}
.search-field span,
.unit-field span {
  display: block;
  font-size: 11px;
  color: #60788c;
  margin-bottom: 6px;
}
.filters input[type='search'],
.filters select {
  width: 100%;
  height: 40px;
  padding: 8px 10px;
  border: 1px solid #d6e2ec;
  border-radius: 8px;
  background: #fbfcfe;
  font-size: 13px;
  color: #34556e;
}
.unit-field {
  width: 185px;
}
.selected-toggle {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 40px;
  font-size: 12px;
  color: #4a687c;
  white-space: nowrap;
}
.reset-button {
  font-size: 12px;
  height: 40px;
  white-space: nowrap;
}
.selection-summary {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 13px;
  font-size: 11px;
  color: #7c8d9c;
}
.selection-summary b {
  color: var(--accent);
  font-size: 13px;
}
.summary-divider {
  margin: 0 10px;
  color: #c0ccd6;
}
.selectable {
  margin-bottom: 12px;
}
.selectable.chosen {
  border-color: var(--edge);
  box-shadow: inset 3px 0 var(--accent);
  background: linear-gradient(100deg, var(--tint), white 60%);
}
.selectable.locked {
  background: #f3f5f7;
}
.selection-check {
  padding: 4px 0;
  flex-shrink: 0;
  cursor: pointer;
}
input[type='checkbox'] {
  width: 17px;
  height: 17px;
  accent-color: var(--accent);
  margin: 0;
}
.status-badge {
  font-size: 10px;
  padding: 3px 6px;
  border-radius: 5px;
  background: var(--tint);
  color: var(--accent);
  border: 1px solid var(--edge);
}
.locked-badge {
  background: #eceff2;
  color: #778894;
  border-color: #dce3e8;
}
.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 26px;
  background: white;
  border-top: 1px solid #dce7ee;
  flex-shrink: 0;
}
.dialog-footer strong {
  display: block;
  font-size: 12px;
  color: #456278;
  margin-bottom: 4px;
}
.dialog-footer span {
  font-size: 11px;
  color: #7b8fa0;
}
.footer-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}
.primary-button {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}
.empty-state {
  text-align: center;
  padding: 60px 15px;
  color: #6b8599;
}
.empty-state strong {
  font-size: 16px;
  color: #3f617b;
}
.empty-state p {
  font-size: 13px;
  margin-top: 10px;
}
@media (max-width: 900px) {
  .topic-cards {
    gap: 10px;
  }
  .topic-card {
    padding: 15px;
  }
  .card-bottom {
    align-items: flex-start;
    flex-direction: column;
  }
  .evidence-grid {
    grid-template-columns: 1fr;
  }
  .filters {
    flex-wrap: wrap;
  }
  .search-field {
    min-width: 210px;
  }
  .selection-summary {
    flex-wrap: wrap;
  }
}
@media (max-width: 640px) {
  .equipment-topics {
    padding: 18px;
  }
  .panel-heading {
    flex-wrap: wrap;
    gap: 8px;
  }
  .shared-badge {
    padding: 4px 9px;
  }
  .topic-cards {
    grid-template-columns: 1fr;
    margin: 16px 0;
  }
  .topic-card {
    padding: 17px;
  }
  .card-title {
    margin-top: 12px;
  }
  .card-bottom {
    flex-direction: row;
    align-items: center;
    margin-top: 13px;
    padding-top: 12px;
  }
  .equipment-topic-overlay {
    padding: 8px;
  }
  .equipment-topic-dialog {
    height: 95dvh;
    max-height: 95dvh;
    border-radius: 15px;
  }
  .dialog-heading {
    padding: 16px;
  }
  .dialog-title {
    gap: 10px;
  }
  .dialog-title h3 {
    font-size: 18px;
  }
  .dialog-title .eyebrow {
    font-size: 9px;
    letter-spacing: 0.5px;
  }
  .dialog-info {
    padding: 12px 16px;
    flex-wrap: wrap;
    gap: 6px;
  }
  .dialog-body {
    padding: 14px;
  }
  .selection-toolbar {
    padding: 12px 16px;
  }
  .search-field {
    min-width: 100%;
  }
  .unit-field {
    width: calc(100% - 115px);
  }
  .selected-toggle {
    margin-left: auto;
  }
  .filters {
    gap: 8px;
  }
  .filters input[type='search'],
  .filters select {
    font-size: 16px;
  }
  .reset-button {
    height: 30px;
    padding: 4px 9px;
  }
  .selection-summary {
    gap: 6px;
  }
  .issue-card {
    padding: 13px;
    gap: 10px;
    flex-wrap: wrap;
  }
  .selectable .issue-content {
    flex-basis: calc(100% - 32px);
  }
  .selectable .photo {
    margin-left: 27px;
    width: 120px;
  }
  .group-content {
    padding: 0 12px 12px;
  }
  .evidence-group summary {
    padding: 14px 12px;
    gap: 8px;
    flex-wrap: wrap;
  }
  .group-title {
    min-width: 60%;
  }
  .count-badge {
    margin-left: 40px;
  }
  .group-chevron {
    margin-left: auto;
  }
  .cause {
    padding: 12px;
  }
  .cause small {
    display: block;
    margin: 4px 0 0;
  }
  .dialog-footer {
    padding: 12px 16px;
    flex-wrap: wrap;
    gap: 12px;
  }
  .footer-actions {
    width: 100%;
  }
  .footer-actions button {
    flex: 1;
    min-height: 42px;
  }
  .dialog-error {
    margin: 8px 14px;
  }
}
@media (prefers-reduced-motion: reduce) {
  button,
  .group-chevron {
    transition: none;
  }
}
</style>
