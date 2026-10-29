<template>
  <section class="safety-config" aria-label="安全报告专属配置">
    <p v-if="error" class="safety-error" role="alert">
      {{ error }} <button @click="load">重新读取</button>
    </p>
    <div v-if="loading" role="status">正在核对现场、视频问题与已保存配置…</div>
    <template v-else-if="data">
      <article class="safety-source">
        <div>
          <small>DATA SOURCE</small>
          <h3>本次报告数据来源</h3>
          <p>仅采用审核通过问题；受检站点包含已确认完成的零问题巡检。现场与视频分别统计。</p>
        </div>
        <button :disabled="busy" @click="open('source')">设置来源</button>
        <dl>
          <div v-for="item in metrics" :key="item.key">
            <dt>{{ item.label }}</dt>
            <dd>
              {{ data.summary[item.key] }}<small>{{ item.unit }}</small>
            </dd>
          </div>
        </dl>
      </article>
      <div class="safety-panels">
        <article>
          <small>TYPICAL ISSUES</small>
          <h3>现场与视频典型问题</h3>
          <p>AI 按问题表现频次归类，各选一个代表案例；可人工替换。</p>
          <button :disabled="busy" @click="open('typical')">查看与调整典型问题</button>
        </article>
        <article>
          <small>MONTHLY FOCUS</small>
          <h3>月度重点与问题再分类</h3>
          <p>
            当前重点：{{ data.focus_category || '暂无现场问题' }}。查看 AI
            依据，调整每条问题的表现分类及共性描述。
          </p>
          <button :disabled="busy" @click="open('analysis')">查看与调整分析</button>
        </article>
      </div>
      <small class="safety-saved">{{ savedLabel }}</small>
    </template>
    <Teleport to="body">
      <div v-if="active" class="safety-overlay" @click.self="close" @keydown.esc.stop="close">
        <section
          ref="dialog"
          class="safety-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="safety-dialog-title"
          tabindex="-1"
          @keydown.tab="trapFocus"
        >
          <header>
            <div>
              <small>安全质量检查报告 · 全局共享配置</small>
              <h2 id="safety-dialog-title">{{ titles[active] }}</h2>
            </div>
            <button
              class="safety-close"
              :disabled="saving || analyzing"
              aria-label="关闭"
              @click="close"
            >
              ×
            </button>
          </header>
          <div class="safety-dialog-body">
            <p v-if="dialogError" class="safety-error" role="alert">{{ dialogError }}</p>
            <template v-if="active === 'source'">
              <label class="safety-check"
                ><input
                  type="checkbox"
                  :checked="draft.station_ids === null"
                  @change="setAll($event.target.checked)"
                />使用当前范围全部受检站点</label
              >
              <p>自定义范围下，未勾选的站点不参与本份报告。累计整改统计也采用相同站点范围。</p>
              <input
                v-model="keyword"
                type="search"
                placeholder="搜索片区、站点名称"
                aria-label="搜索来源站点"
              />
              <div class="safety-stations">
                <label
                  v-for="station in visibleStations"
                  :key="station.station_id"
                  class="safety-check"
                  ><input
                    type="checkbox"
                    :checked="
                      draft.station_ids === null || draft.station_ids.includes(station.station_id)
                    "
                    @change="toggleStation(station.station_id, $event.target.checked)"
                  /><span
                    ><b>{{ station.station_name }}</b
                    ><small
                      >{{ station.unit_name }} · 现场 {{ station.onsite_count }} 项 / 视频
                      {{ station.video_count }} 项</small
                    ></span
                  ></label
                >
              </div>
            </template>
            <template v-else-if="active === 'typical'">
              <div class="safety-typicals">
                <article v-for="mode in modes" :key="mode.key">
                  <h3>{{ mode.label }}典型问题</h3>
                  <label
                    >代表案例<select
                      :value="typicalSelection(mode.key)"
                      @change="setTypical(mode.key, $event.target.value)"
                    >
                      <option value="">自动采用最高频问题表现中的代表案例</option>
                      <option
                        v-for="issue in modeIssues(mode.key)"
                        :key="issue.issue_id"
                        :value="issue.issue_id"
                      >
                        #{{ issue.issue_id }} · {{ issue.station_name }} ·
                        {{ issue.description.slice(0, 55) }}
                      </option>
                    </select></label
                  >
                  <template v-if="typical(mode.key)"
                    ><button class="safety-photo" @click="emit('photo', typical(mode.key))">
                      <img :src="resolveImage(typical(mode.key).issue_photo)" alt="典型问题照片" />
                    </button>
                    <p>{{ typical(mode.key).description }}</p>
                    <small
                      >{{ typical(mode.key).station_name }} · #{{
                        typical(mode.key).issue_id
                      }}</small
                    ></template
                  >
                  <p v-else>尚无可用典型问题，生成报告时 AI 自动分析；也可从上方手动指定。</p>
                </article>
              </div>
            </template>
            <template v-else>
              <div class="safety-focus">
                <label
                  >月度重点工作类<select v-model="draft.focus_category" @change="switchFocus">
                    <option value="">自动采用问题数量最高的现场检查内容类别</option>
                    <option
                      v-for="item in data.focus_categories"
                      :key="item.name"
                      :value="item.name"
                    >
                      {{ item.name }}（{{ item.count }}项）
                    </option>
                  </select></label
                >
                <p>
                  概览按检查内容统计；详情沿用模板固定检查主题和编号。风险合规合并风险隐患、合规性管理。
                </p>
              </div>
              <div class="safety-analysis-layout">
                <nav aria-label="分析类别">
                  <button
                    v-for="category in categories"
                    :key="category.key"
                    :class="{ selected: category.key === categoryKey }"
                    @click="categoryKey = category.key"
                  >
                    {{ category.name }}<span>{{ category.issues.length }}</span>
                  </button>
                </nav>
                <article v-if="currentCategory" class="safety-analysis-content">
                  <div class="safety-analysis-heading">
                    <div>
                      <h3>{{ currentCategory.name }}</h3>
                      <small>分类与共性描述用于报告选图及文字，可保存人工调整。</small>
                    </div>
                    <button
                      :disabled="!canGenerate || analyzing || !currentCategory.issues.length"
                      @click="analyze"
                    >
                      {{ analyzing ? 'AI 分析中…' : 'AI 分析此类问题' }}
                    </button>
                  </div>
                  <p v-if="!canGenerate">
                    当前账号无生成 AI 报告权限，可查看与保存人工调整，不能发起 AI 调用。
                  </p>
                  <p v-if="!currentCategory.issues.length">当前范围暂无此类问题。</p>
                  <div v-for="group in groupNames" :key="group" class="safety-summary">
                    <label
                      >{{ group }} · 共性描述<textarea
                        v-model="currentOverride.summaries[group]"
                        maxlength="160"
                        :placeholder="group"
                        rows="2"
                      ></textarea>
                    </label>
                  </div>
                  <div
                    v-for="issue in currentCategory.issues"
                    :key="issue.issue_id"
                    class="safety-issue"
                  >
                    <button
                      v-if="issue.issue_photo"
                      class="safety-photo"
                      @click="emit('photo', issue)"
                    >
                      <img
                        :src="resolveImage(issue.issue_photo)"
                        :alt="`问题 ${issue.issue_id}`"
                        loading="lazy"
                      />
                    </button>
                    <div>
                      <b>#{{ issue.issue_id }} · {{ issue.station_name }}</b>
                      <p>{{ issue.description }}</p>
                      <small>{{ issue.category_name }}</small
                      ><label
                        >问题表现分类<input
                          :value="assignment(issue.issue_id)"
                          maxlength="50"
                          list="safety-group-names"
                          placeholder="尚未分类，可输入新类别"
                          @input="setAssignment(issue.issue_id, $event.target.value)"
                      /></label>
                      <details>
                        <summary>评分说明</summary>
                        {{ issue.requirement || '原规范未维护评分说明' }}
                      </details>
                    </div>
                  </div>
                  <datalist id="safety-group-names">
                    <option v-for="name in groupNames" :key="name" :value="name"></option>
                  </datalist>
                </article>
              </div>
            </template>
          </div>
          <footer>
            <div>
              <small>保存不生成报告。AI 分析优先复用历史；分析结果需保存后再重新生成报告。</small
              ><small>{{ savedLabel }}</small>
            </div>
            <button :disabled="saving || analyzing" @click="close">取消</button
            ><button class="safety-primary" :disabled="saving || analyzing || busy" @click="save">
              {{ saving ? '正在保存…' : '保存配置' }}
            </button>
          </footer>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import { manualClassificationChanges } from '@/utils/safetyReportConfig'
const props = defineProps({
  month: String,
  dateFrom: String,
  dateTo: String,
  generatedAt: String,
  resolveImage: Function,
  canGenerate: Boolean,
  busy: Boolean,
})
const emit = defineEmits(['change', 'saved', 'photo'])
const data = ref(null),
  draft = ref({}),
  loading = ref(false),
  saving = ref(false),
  analyzing = ref(false)
const analysisBaseline = ref({})
const error = ref(''),
  dialogError = ref(''),
  active = ref(''),
  categoryKey = ref(''),
  keyword = ref(''),
  categories = ref([]),
  dialog = ref(null)
const titles = {
  source: '本次报告数据来源',
  typical: '典型问题与代表案例',
  analysis: '月度重点与问题再分类',
}
const modes = [
  { key: 'onsite', label: '现场' },
  { key: 'video', label: '视频' },
]
const metrics = [
  { key: 'region_count', label: '涉及单位', unit: '个' },
  { key: 'station_count', label: '受检站点', unit: '座' },
  { key: 'issue_count', label: '问题总数', unit: '项' },
  { key: 'onsite_count', label: '现场问题', unit: '项' },
  { key: 'video_count', label: '视频问题', unit: '项' },
]
const clone = (value) => JSON.parse(JSON.stringify(value))
const params = () => ({ month: props.month, date_from: props.dateFrom, date_to: props.dateTo })
let sequence = 0,
  timer,
  controller,
  previousFocus
const savedLabel = computed(() =>
  data.value?.meta?.updated_by_name
    ? `最近保存：${data.value.meta.updated_by_name} · ${data.value.meta.updated_at}`
    : '尚未保存人工配置，默认使用全部数据和 AI 自动分析。',
)
const visibleStations = computed(() =>
  (data.value?.stations || []).filter((s) =>
    `${s.station_name} ${s.unit_name}`.includes(keyword.value.trim()),
  ),
)
const currentCategory = computed(() => categories.value.find((c) => c.key === categoryKey.value))
const currentOverride = computed(() => draft.value.classifications[categoryKey.value])
const groupNames = computed(() => [
  ...new Set(Object.values(currentOverride.value?.assignments || {}).filter(Boolean)),
])
const modeIssues = (mode) => (data.value?.issues || []).filter((i) => i.mode === mode)
function typical(mode) {
  const list = modeIssues(mode),
    manual = draft.value.typical_issue_ids[mode]
  const chosen = list.find((i) => i.issue_id === manual)
  if (chosen) return chosen
  const groups =
    categories.value.find((c) => c.key === `${mode}:__typical__`)?.analysis?.groups || []
  for (const group of groups) {
    const issue = list.find((i) => group.issue_ids.includes(i.issue_id) && i.issue_photo)
    if (issue) return issue
  }
  return null
}
function typicalSelection(mode) {
  const id = draft.value.typical_issue_ids[mode]
  return modeIssues(mode).some((issue) => issue.issue_id === id) ? id : ''
}
function setTypical(mode, value) {
  if (value) draft.value.typical_issue_ids[mode] = Number(value)
  else delete draft.value.typical_issue_ids[mode]
}
function adopt(value) {
  data.value = value
  emit('change', value.settings)
}
async function load() {
  const id = ++sequence
  controller?.abort()
  controller = new AbortController()
  if (!props.dateFrom || !props.dateTo || props.dateFrom > props.dateTo) return
  active.value = ''
  loading.value = true
  error.value = ''
  emit('change', null)
  try {
    const response = await axios.get('/api/inspection-reports/safety-config', {
      params: params(),
      signal: controller.signal,
    })
    if (id === sequence) adopt(response.data)
  } catch (err) {
    if (id === sequence && !axios.isCancel(err))
      error.value = err.response?.data?.error || '安全报告配置读取失败。'
  } finally {
    if (id === sequence) loading.value = false
  }
}
function ensureCategory(category) {
  const override = (draft.value.classifications[category.key] ||= {
    assignments: {},
    summaries: {},
  })
  for (const group of category.analysis?.groups || []) {
    for (const id of group.issue_ids)
      if (!override.assignments[id]) override.assignments[id] = group.name
    if (!override.summaries[group.name]) override.summaries[group.name] = group.summary
  }
}
async function open(name) {
  draft.value = clone(data.value.settings)
  categories.value = clone(data.value.categories)
  for (const category of categories.value) ensureCategory(category)
  analysisBaseline.value = clone(draft.value.classifications)
  categoryKey.value = categories.value.at(-1)?.key || ''
  keyword.value = ''
  dialogError.value = ''
  active.value = name
  previousFocus = document.activeElement
  await nextTick()
  dialog.value?.focus()
}
function close() {
  if (saving.value || analyzing.value) return
  active.value = ''
  previousFocus?.focus()
}
function trapFocus(event) {
  const nodes = [
    ...dialog.value.querySelectorAll(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]',
    ),
  ]
  const target = event.shiftKey ? nodes.at(-1) : nodes[0]
  if (document.activeElement === (event.shiftKey ? nodes[0] : nodes.at(-1))) {
    event.preventDefault()
    target?.focus()
  }
}
function setAll(checked) {
  draft.value.station_ids = checked ? null : data.value.stations.map((s) => s.station_id)
}
function toggleStation(id, checked) {
  if (draft.value.station_ids === null)
    draft.value.station_ids = data.value.stations.map((s) => s.station_id)
  draft.value.station_ids = checked
    ? [...new Set([...draft.value.station_ids, id])]
    : draft.value.station_ids.filter((i) => i !== id)
}
function switchFocus() {
  const focus = draft.value.focus_category || data.value.focus_categories[0]?.name
  if (!focus) return
  const key = `onsite:content:${focus}`
  if (!categories.value.some((c) => c.key === key)) {
    const category = {
      key,
      mode: 'onsite',
      category: `content:${focus}`,
      name: `1. 月度重点：${focus}`,
      issues: modeIssues('onsite').filter((i) => i.category_name === focus),
      analysis: {},
    }
    categories.value.push(category)
    ensureCategory(category)
    analysisBaseline.value[key] = clone(draft.value.classifications[key])
  }
  categoryKey.value = key
}
const assignment = (id) => currentOverride.value?.assignments[id] || ''
function setAssignment(id, name) {
  const value = name.trim()
  if (value) currentOverride.value.assignments[id] = value
  else delete currentOverride.value.assignments[id]
}
async function analyze() {
  analyzing.value = true
  dialogError.value = ''
  try {
    const c = currentCategory.value
    const response = await axios.post(
      '/api/inspection-reports/safety-analysis',
      {
        ...params(),
        mode: c.mode,
        category: c.category,
        revision: data.value.meta.revision,
        data_signature: data.value.data_signature,
      },
      { timeout: 300000 },
    )
    c.analysis = response.data.analysis
    draft.value.classifications[c.key] = { assignments: {}, summaries: {} }
    ensureCategory(c)
  } catch (err) {
    dialogError.value = err.response?.data?.error || 'AI 分析未完成，原保存配置不变。请稍后重试。'
  } finally {
    analyzing.value = false
  }
}
async function save() {
  saving.value = true
  dialogError.value = ''
  try {
    // Viewing AI evidence does not turn every generated grouping into a manual override.
    const settings = clone(draft.value)
    settings.classifications =
      active.value === 'analysis'
        ? manualClassificationChanges(
            settings.classifications,
            analysisBaseline.value,
            data.value.settings.classifications,
          )
        : data.value.settings.classifications
    const response = await axios.put('/api/inspection-reports/safety-config', {
      ...params(),
      settings,
      revision: data.value.meta.revision,
      data_signature: data.value.data_signature,
    })
    adopt(response.data)
    active.value = ''
    emit('saved')
    previousFocus?.focus()
  } catch (err) {
    dialogError.value = err.response?.data?.error || '配置保存失败，请重试。'
  } finally {
    saving.value = false
  }
}
watch(
  () => [props.dateFrom, props.dateTo, props.generatedAt],
  () => {
    clearTimeout(timer)
    timer = setTimeout(load, 180)
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  sequence++
  controller?.abort()
  clearTimeout(timer)
})
</script>

<style scoped>
.safety-config {
  color: #294b65;
}
.safety-source {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 18px;
  padding: 24px;
  border: 1px solid #c4d7e5;
  border-radius: 16px;
  background: #f5f9fc;
}
.safety-source > div {
  flex: 1;
}
.safety-config h3 {
  margin: 6px 0 10px;
  font-size: 19px;
  color: #173951;
}
.safety-config p {
  font-size: 14px;
  line-height: 1.7;
  margin: 6px 0 16px;
}
.safety-config small {
  color: #527184;
}
.safety-config button,
.safety-dialog button {
  border: 1px solid #b6cddd;
  border-radius: 9px;
  padding: 10px 16px;
  background: #fff;
  color: #225373;
  font-weight: 600;
  cursor: pointer;
}
.safety-config button:disabled,
.safety-dialog button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.safety-source dl {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  width: 100%;
  margin: 0;
  border-top: 1px solid #cddce8;
  padding-top: 18px;
}
.safety-source dt {
  font-size: 13px;
}
.safety-source dd {
  margin: 6px 0 0;
  font-size: 27px;
  font-weight: 700;
  color: #176c85;
}
.safety-source dd small {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 400;
}
.safety-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
}
.safety-panels article {
  border: 1px solid #c4d7e5;
  border-radius: 14px;
  padding: 22px;
}
.safety-saved {
  display: block;
  margin: 14px 0;
}
.safety-overlay {
  position: fixed;
  inset: 0;
  z-index: 4200;
  background: #102a47a8;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #243f55;
}
.safety-dialog {
  width: min(1240px, 96vw);
  max-height: 90vh;
  background: #fff;
  display: flex;
  flex-direction: column;
  border-radius: 18px;
  box-shadow: 0 24px 90px #061d3d66;
  overflow: hidden;
}
.safety-dialog header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 26px;
  background: #f1f7fb;
  border-bottom: 1px solid #c6d8e6;
}
.safety-dialog h2 {
  margin: 6px 0 0;
  font-size: 22px;
}
.safety-dialog small {
  color: #5a7387;
}
.safety-dialog .safety-close {
  font-size: 25px;
  padding: 3px 12px;
}
.safety-dialog-body {
  overflow: auto;
  padding: 24px;
  min-height: 160px;
}
.safety-dialog input:not([type='checkbox']),
.safety-dialog select,
.safety-dialog textarea {
  width: 100%;
  border: 1px solid #b2c9db;
  border-radius: 8px;
  padding: 10px;
  color: #233e55;
  background: #fff;
  box-sizing: border-box;
  font: inherit;
  margin-top: 7px;
}
.safety-dialog label {
  font-size: 14px;
}
.safety-check {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid #d0dfe9;
  border-radius: 10px;
  background: #f7fafc;
}
.safety-check small {
  display: block;
  margin-top: 4px;
}
.safety-stations {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 18px;
}
.safety-typicals {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
.safety-typicals article {
  border: 1px solid #cbdbe8;
  border-radius: 12px;
  padding: 18px;
}
.safety-typicals img {
  height: 240px !important;
}
.safety-photo {
  padding: 0 !important;
  border: 0 !important;
  background: transparent !important;
}
.safety-photo img {
  max-width: 100%;
  width: 100%;
  height: 110px;
  object-fit: contain;
}
.safety-focus {
  padding: 16px;
  background: #eaf4f8;
  border-radius: 10px;
  margin-bottom: 20px;
}
.safety-focus p {
  font-size: 13px;
  margin-bottom: 0;
}
.safety-analysis-layout {
  display: grid;
  grid-template-columns: 230px 1fr;
  gap: 20px;
}
.safety-analysis-layout nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.safety-analysis-layout nav button {
  text-align: left;
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.safety-analysis-layout nav button.selected {
  background: #175c78;
  color: #fff;
  border-color: #175c78;
}
.safety-analysis-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.safety-analysis-heading h3 {
  margin-top: 0;
}
.safety-summary {
  padding: 12px;
  background: #f2f7fa;
  margin-top: 12px;
  border-radius: 8px;
}
.safety-issue {
  display: grid;
  grid-template-columns: 115px 1fr;
  gap: 16px;
  padding: 20px 0;
  border-bottom: 1px solid #d6e2ea;
}
.safety-issue p {
  white-space: pre-line;
  line-height: 1.6;
}
.safety-issue label {
  display: block;
  margin: 10px 0;
}
.safety-issue details {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-line;
  color: #526c7e;
}
.safety-dialog footer {
  border-top: 1px solid #ccdce7;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  background: #f8fbfd;
}
.safety-dialog footer div {
  flex: 1;
}
.safety-dialog footer small {
  display: block;
  margin: 3px 0;
  font-size: 12px;
}
.safety-dialog .safety-primary {
  background: #17637e;
  color: #fff;
  border-color: #17637e;
}
.safety-error {
  background: #fff1ef;
  color: #a1332a;
  padding: 12px;
  border-radius: 8px;
}
.safety-config button:hover:not(:disabled),
.safety-dialog button:hover:not(:disabled) {
  box-shadow: 0 2px 7px #163f5f26;
}
.safety-dialog :focus-visible {
  outline: 3px solid #64a6d1;
  outline-offset: 2px;
}
@media (max-width: 700px) {
  .safety-overlay {
    padding: 8px;
  }
  .safety-dialog {
    max-height: 96dvh;
    width: 100%;
  }
  .safety-dialog header,
  .safety-dialog-body {
    padding: 16px;
  }
  .safety-panels,
  .safety-typicals {
    grid-template-columns: 1fr;
  }
  .safety-source dl {
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }
  .safety-stations {
    grid-template-columns: 1fr;
  }
  .safety-analysis-layout {
    grid-template-columns: 1fr;
  }
  .safety-analysis-layout nav {
    flex-direction: row;
    overflow-x: auto;
  }
  .safety-analysis-layout nav button {
    flex-shrink: 0;
    max-width: 220px;
  }
  .safety-analysis-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .safety-issue {
    grid-template-columns: 80px 1fr;
  }
  .safety-dialog footer {
    flex-wrap: wrap;
    padding: 12px;
  }
  .safety-dialog footer div {
    flex-basis: 100%;
  }
}
</style>
