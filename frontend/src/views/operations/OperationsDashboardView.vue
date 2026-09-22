<template>
  <div class="page-shell operations-page">
    <header class="page-header card-surface dashboard-header">
      <div>
        <div class="page-kicker">运营系统 / BUSINESS INTELLIGENCE</div>
        <h2>{{ page.title }}</h2>
        <p>{{ page.description }}</p>
      </div>
      <div class="live-tag"><i></i> 业务实数 · 按权限统计</div>
    </header>

    <form class="card-surface dashboard-filters" @submit.prevent="load">
      <div class="filter-label"><strong>分析区间</strong><span>默认当月，点击后应用</span></div>
      <label>开始日期<input v-model="draft.date_from" type="date" required /></label>
      <span class="date-separator">至</span
      ><label>结束日期<input v-model="draft.date_to" type="date" required /></label>
      <label
        >站点所属地<select v-model="draft.region">
          <option value="">全部可见片区</option>
          <option v-for="region in regionOptions" :key="region">{{ region }}</option>
        </select></label
      >
      <div class="filter-buttons">
        <button type="button" class="btn btn-secondary" @click="reset">本月</button
        ><button class="btn btn-primary" :disabled="loading">
          {{ loading ? '统计中…' : '开始分析' }}
        </button>
      </div>
      <p v-if="dirty" class="dirty">
        筛选条件已调整，点击“开始分析”后生效。当前图表仍为上次分析结果。
      </p>
    </form>
    <div v-if="error" class="notice error" role="alert">
      {{ error }}<button class="btn btn-secondary" @click="load">重试</button>
    </div>
    <div v-if="loading" class="loading card-surface" role="status">
      <span class="loading-track"></span>正在汇总权限范围内的数据，不加载问题全库…
    </div>

    <main v-else-if="data" class="dashboard-content">
      <div class="snapshot">
        <span
          >{{ applied.date_from }} 至 {{ applied.date_to }} ·
          {{ applied.region || '全部可见片区' }}</span
        ><span>统计于 {{ formatTime(data.generated_at) }}</span>
      </div>
      <section class="metric-grid" aria-label="核心指标">
        <article
          v-for="metric in metrics"
          :key="metric.label"
          class="metric card-surface"
          :class="metric.tone"
        >
          <div class="metric-label">{{ metric.label }}</div>
          <div class="metric-value">
            {{ metric.value }}<small>{{ metric.unit }}</small>
          </div>
          <p>{{ metric.hint }}</p>
        </article>
      </section>

      <template v-if="mode === 'overview'">
        <section class="two-columns">
          <article class="card-surface chart-card trend-card">
            <div class="section-head">
              <div>
                <span class="eyebrow">INSPECTION PULSE</span>
                <h3>问题登记趋势</h3>
              </div>
              <span class="legend"><i></i> 已审核有效问题</span>
            </div>
            <p class="muted">按问题登记日期统计；数量反映检查发现，不代表站点经营质量评分。</p>
            <div v-if="trend.length" class="trend-scroll">
              <svg
                viewBox="0 0 720 230"
                role="img"
                :aria-label="`所选期间有效问题${data.summary.valid}项`"
              >
                <g v-for="tick in [0, 1, 2, 3]" :key="tick">
                  <line
                    x1="40"
                    x2="700"
                    :y1="190 - tick * 50"
                    :y2="190 - tick * 50"
                    stroke="#e2e8f0"
                  />
                  <text x="30" :y="194 - tick * 50" text-anchor="end" class="svg-label">
                    {{ Math.round((trendMax * tick) / 3) }}
                  </text>
                </g>
                <path
                  :d="`${trendPath} L ${trendX(trend.length - 1)} 190 L ${trendX(0)} 190 Z`"
                  fill="#e5f3fa"
                />
                <path
                  :d="trendPath"
                  fill="none"
                  stroke="#147da5"
                  stroke-width="3"
                  stroke-linejoin="round"
                />
                <circle
                  v-for="(point, index) in trend"
                  :key="point.day"
                  :cx="trendX(index)"
                  :cy="190 - (point.valid / trendMax) * 150"
                  r="3"
                  fill="#147da5"
                >
                  <title>
                    {{ point.day }}：{{ point.valid }}项有效问题 / 登记{{ point.registered }}项
                  </title>
                </circle>
                <text x="40" y="218" class="svg-label">{{ applied.date_from }}</text>
                <text x="700" y="218" text-anchor="end" class="svg-label">
                  {{ applied.date_to }}
                </text>
              </svg>
            </div>
            <p v-else class="empty">本期间暂无问题登记数据</p>
            <div class="mini-stats">
              <span
                >问题登记 <b>{{ data.summary.total }}</b> 项</span
              ><span
                >审核待办 <b>{{ data.summary.pending_audit }}</b> 项</span
              ><span
                >确认亮点 <b>{{ data.highlights }}</b> 项</span
              >
            </div>
          </article>
          <article class="card-surface chart-card">
            <div class="section-head">
              <div>
                <span class="eyebrow">WORKFLOW SNAPSHOT</span>
                <h3>当前流程分布</h3>
              </div>
              <span class="muted">点击查看明细</span>
            </div>
            <div v-if="data.phases.length" class="phase-list">
              <button
                v-for="row in orderedPhases"
                :key="row.phase"
                class="phase-row"
                @click="showDetails(row.phase, { phase: row.phase })"
              >
                <span><i :style="{ background: phaseColor(row.phase) }"></i>{{ row.phase }}</span
                ><b>{{ row.count }}<small>项 ›</small></b>
              </button>
            </div>
            <p v-else class="empty">暂无问题数据</p>
          </article>
        </section>
        <section class="card-surface chart-card">
          <div class="section-head">
            <div>
              <span class="eyebrow">REGIONAL VIEW</span>
              <h3>片区巡检发现对比</h3>
            </div>
            <span class="muted">有问题站均 = 有效问题 ÷ 有问题站点数</span>
          </div>
          <RegionTable :rows="data.units" @open="openRegion" />
        </section>
      </template>

      <template v-else-if="mode === 'rectification'">
        <section class="card-surface chart-card">
          <div class="section-head">
            <div>
              <span class="eyebrow">ACTION PIPELINE</span>
              <h3>待处理事项分布</h3>
            </div>
            <span class="muted">当前状态快照，不是流量漏斗</span>
          </div>
          <div class="pipeline">
            <button
              v-for="(phase, index) in openPhases"
              :key="phase"
              @click="showDetails(phase, { phase })"
            >
              <span class="step">0{{ index + 1 }}</span
              ><strong>{{ phase }}</strong
              ><b>{{ phaseCount(phase) }}<small>项</small></b
              ><span>查看关联问题 ›</span>
            </button>
          </div>
        </section>
        <section class="two-columns">
          <article class="card-surface chart-card">
            <div class="section-head">
              <div>
                <span class="eyebrow">AGING WATCH</span>
                <h3>待处理问题账龄</h3>
              </div>
            </div>
            <p class="muted">从登记日至今天的自然日天数，不等同于流程超时或考核认定。</p>
            <div v-if="data.ages.length" class="bars">
              <div v-for="row in data.ages" :key="row.label" class="bar-row">
                <span>{{ row.label }}</span>
                <div class="bar-track">
                  <i
                    :style="{
                      width: barWidth(row.count, data.ages, 'count'),
                      background: row.rank === 3 ? '#c77931' : '#168a9a',
                    }"
                  ></i>
                </div>
                <b>{{ row.count }}</b>
              </div>
            </div>
            <p v-else class="empty">本期间登记的问题暂无待处理事项</p>
          </article>
          <article class="card-surface chart-card">
            <div class="section-head">
              <div>
                <span class="eyebrow">FOLLOW-UP LIST</span>
                <h3>优先跟进站点</h3>
              </div>
              <span class="muted">待处理数量前12</span>
            </div>
            <div v-if="data.stations.length" class="station-list">
              <button
                v-for="(row, index) in data.stations"
                :key="row.station_id"
                @click="
                  showDetails(`${row.station_name} · 待处理`, {
                    station_id: row.station_id,
                    open: '1',
                  })
                "
              >
                <span class="rank">{{ index + 1 }}</span
                ><span
                  ><strong>{{ row.station_name }}</strong
                  ><small>{{ row.region }} · 最长账龄{{ row.oldest }}天</small></span
                ><b>{{ row.count }}<small>项 ›</small></b>
              </button>
            </div>
            <p v-else class="empty">暂无待跟进站点</p>
          </article>
        </section>
        <section class="card-surface chart-card">
          <div class="section-head">
            <div>
              <span class="eyebrow">REGIONAL FOLLOW-UP</span>
              <h3>片区闭环进度</h3>
            </div>
          </div>
          <RegionTable :rows="data.units" @open="openRegion" />
        </section>
      </template>

      <template v-else>
        <section class="two-columns insights-columns">
          <article class="card-surface chart-card">
            <div class="section-head">
              <div>
                <span class="eyebrow">BUSINESS MIX</span>
                <h3>检查表问题构成</h3>
              </div>
            </div>
            <div v-if="data.tables.length" class="table-bars">
              <button
                v-for="row in data.tables"
                :key="row.inspection_table_id"
                @click="
                  showDetails(`${row.table_name}（${row.mode}）`, {
                    table_id: row.inspection_table_id,
                    valid: '1',
                  })
                "
              >
                <div>
                  <strong
                    >{{ row.table_name }}<small>（{{ row.mode }}）</small></strong
                  ><b>{{ row.count }} 项</b>
                </div>
                <div class="bar-track">
                  <i :style="{ width: barWidth(row.count, data.tables, 'count') }"></i>
                </div>
                <small
                  >涉及{{ row.stations }}座站 · 占有效问题{{
                    percent(row.count, data.summary.valid)
                  }}%</small
                >
              </button>
            </div>
            <p v-else class="empty">暂无已审核有效问题</p>
          </article>
          <article class="card-surface chart-card">
            <div class="section-head">
              <div>
                <span class="eyebrow">RECURRING FINDINGS</span>
                <h3>高频规范 TOP 15</h3>
              </div>
              <span class="muted">按规范引用次数，不调用AI</span>
            </div>
            <div v-if="data.standards.length" class="standards-list">
              <button
                v-for="(row, index) in data.standards"
                :key="row.standard_key"
                @click="
                  showDetails(`规范 ${row.standard_key}`, {
                    standard_key: row.standard_key,
                    valid: '1',
                  })
                "
              >
                <span class="rank">{{ index + 1 }}</span
                ><span class="standard-copy"
                  ><strong>{{ row.standard_key }}</strong
                  ><span>{{ row.detail || '暂无规范描述' }}</span
                  ><small>涉及{{ row.stations }}座站</small></span
                ><b>{{ row.count }}<small>次 ›</small></b>
              </button>
            </div>
            <p v-else class="empty">暂无规范引用数据</p>
          </article>
        </section>
        <section class="card-surface chart-card">
          <div class="section-head">
            <div>
              <span class="eyebrow">REGIONAL COMPARISON</span>
              <h3>片区问题对比</h3>
            </div>
            <span class="muted">不同检查覆盖下不作绩效排名</span>
          </div>
          <RegionTable :rows="data.units" @open="openRegion" />
        </section>
      </template>
      <details class="card-surface methodology">
        <summary>指标口径与数据说明</summary>
        <p>
          问题按登记日期筛选，展示查询时的最新状态。有效问题仅含审核通过且未销毁的问题；待审核、审核否决及申诉通过销毁的问题不计入有效问题。闭环率
          = 已闭环有效问题 ÷ 全部有效问题，“站级无法整改”单列，不计入闭环。
        </p>
        <p>
          巡检触达按巡检日期统计底层“站点 ×
          检查表”记录，站点去重，包含未发现问题的巡检；列表按月合并展示的数量可能不同。巡检与问题分别沿用各自的数据权限，不能直接相除计算发现率。有问题站均只用于片区内问题密度观察，不代表全部受检站点平均。
        </p>
        <p>
          趋势中的有效问题、闭环状态会随后续审核和整改变化，不是历史时点快照。默认当月，单次最多366天；账龄不扣除节假日，不作为超时考核依据。数据不涉及证照、站点评分，也不调用AI。
        </p>
      </details>
    </main>

    <dialog
      ref="detailDialog"
      class="detail-dialog"
      aria-labelledby="operations-detail-title"
      @click="closeOnBackdrop"
      @close="closeDetails"
    >
      <div class="operations-dialog-head">
        <div>
          <span class="eyebrow">问题明细</span>
          <h3 id="operations-detail-title">{{ detailTitle }}</h3>
          <p>{{ applied.date_from }} 至 {{ applied.date_to }} · 共{{ detail.total }}项</p>
        </div>
        <button class="btn btn-secondary" aria-label="关闭问题明细" @click="detailDialog.close()">
          关闭
        </button>
      </div>
      <div class="dialog-body" :aria-busy="detailLoading">
        <p v-if="detailLoading" class="empty" role="status">正在加载当前页…</p>
        <p v-else-if="detailError" class="error" role="alert">
          {{ detailError }}
          <button class="btn btn-secondary" @click="loadDetails(detail.page)">重试</button>
        </p>
        <div v-else-if="detail.rows.length" class="detail-items">
          <article v-for="row in detail.rows" :key="row.id">
            <header>
              <strong>#{{ row.id }} · {{ row.station_name }}</strong
              ><span class="phase-pill">{{ row.phase }}</span>
            </header>
            <small
              >{{ row.region }} · {{ row.table_name }}（{{ row.mode }}） ·
              {{ row.created_at }}</small
            >
            <p>{{ row.description }}</p>
          </article>
        </div>
        <p v-else class="empty">没有符合条件的问题</p>
      </div>
      <footer class="dialog-footer">
        <span
          >每页20项 · 第{{ detail.page }} / {{ Math.max(1, Math.ceil(detail.total / 20)) }}页</span
        >
        <div>
          <button
            class="btn btn-secondary"
            :disabled="detailLoading || detail.page <= 1"
            @click="loadDetails(detail.page - 1)"
          >
            上一页</button
          ><button
            class="btn btn-primary"
            :disabled="detailLoading || detail.page * 20 >= detail.total"
            @click="loadDetails(detail.page + 1)"
          >
            下一页
          </button>
        </div>
      </footer>
    </dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import { operationsPages } from '../../config/operationsCatalog'
import RegionTable from './RegionTable.vue'

const props = defineProps({ mode: { type: String, required: true } })
const page = computed(
  () => operationsPages.find((item) => item.key === props.mode) || operationsPages[0],
)
const localDate = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const defaults = () => {
  const now = new Date()
  return {
    date_from: localDate(new Date(now.getFullYear(), now.getMonth(), 1)),
    date_to: localDate(now),
    region: '',
  }
}
const draft = ref(defaults()),
  applied = ref(defaults()),
  data = ref(null),
  regionOptions = ref([])
const loading = ref(false),
  error = ref('')
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(applied.value))
const openPhases = ['待验收', '待整改', '待复核', '申诉中']
const phaseOrder = ['待审核', ...openPhases, '已闭环', '站级无法整改', '已销毁', '其他状态']
const orderedPhases = computed(() =>
  [...(data.value?.phases || [])].sort(
    (a, b) => phaseOrder.indexOf(a.phase) - phaseOrder.indexOf(b.phase),
  ),
)
const percent = (value, total) => (total ? ((value / total) * 100).toFixed(1) : '0.0')
const phaseCount = (phase) => data.value?.phases.find((row) => row.phase === phase)?.count || 0
const phaseColor = (phase) =>
  ({
    已闭环: '#138a79',
    已销毁: '#94a3b8',
    待审核: '#a88b50',
    待复核: '#3588bc',
    申诉中: '#c77931',
  })[phase] || '#617aa6'
const barWidth = (value, rows, key) =>
  `${(value / Math.max(1, ...rows.map((row) => Number(row[key])))) * 100}%`
const formatTime = (value) => new Date(value).toLocaleString('zh-CN', { hour12: false })
const metrics = computed(() => {
  if (!data.value) return []
  const s = data.value.summary,
    r = data.value.records
  const closed = {
    label: '有效问题闭环率',
    value: s.valid ? percent(s.closed, s.valid) : '—',
    unit: s.valid ? '%' : '',
    hint: `已闭环${s.closed}项 / 有效问题${s.valid}项`,
    tone: 'teal',
  }
  if (props.mode === 'overview')
    return [
      {
        label: '巡检触达站点',
        value: r ? r.stations : '—',
        unit: '座',
        hint: r ? `底层巡检记录${r.records}条 · 含零问题站点` : '无巡检记录查看权限',
        tone: 'blue',
      },
      {
        label: '已审核有效问题',
        value: s.valid,
        unit: '项',
        hint: `涉及${s.stations}座站点 · 不含待审核及销毁`,
        tone: 'blue',
      },
      closed,
      {
        label: '待处理事项',
        value: s.open,
        unit: '项',
        hint: `验收 / 整改 / 复核 / 申诉 · 30天以上${s.aged}项`,
        tone: 'amber',
      },
    ]
  if (props.mode === 'rectification')
    return [
      {
        label: '待处理事项',
        value: s.open,
        unit: '项',
        hint: '所选期间登记，当前仍需继续处理',
        tone: 'blue',
      },
      {
        label: '账龄30天及以上',
        value: s.aged,
        unit: '项',
        hint: '自登记日起，不代表流程逾期',
        tone: 'amber',
      },
      closed,
      {
        label: '站级无法整改',
        value: s.unable,
        unit: '项',
        hint: '经复核确认，独立统计，不计入闭环',
        tone: 'slate',
      },
    ]
  return [
    {
      label: '已审核有效问题',
      value: s.valid,
      unit: '项',
      hint: '仅审核通过且未销毁',
      tone: 'blue',
    },
    {
      label: '涉及检查表',
      value: data.value.tables.length,
      unit: '张',
      hint: '仅统计存在有效问题的检查表',
      tone: 'teal',
    },
    {
      label: '有问题站点',
      value: s.stations,
      unit: '座',
      hint: '按站点去重，不等于受检站点数',
      tone: 'slate',
    },
    {
      label: '首位规范占比',
      value: percent(data.value.standards[0]?.count || 0, s.valid),
      unit: '%',
      hint: s.valid ? `首位规范：${data.value.standards[0]?.standard_key}` : '暂无有效问题',
      tone: 'amber',
    },
  ]
})
const trend = computed(() => {
  if (!data.value?.trend?.length) return []
  const byDay = new Map(data.value.trend.map((row) => [row.day, row]))
  const rows = [],
    day = new Date(`${applied.value.date_from}T12:00:00`),
    end = new Date(`${applied.value.date_to}T12:00:00`)
  while (day <= end) {
    const key = localDate(day)
    rows.push(byDay.get(key) || { day: key, valid: 0, registered: 0 })
    day.setDate(day.getDate() + 1)
  }
  return rows
})
const trendMax = computed(() => Math.max(3, ...trend.value.map((row) => row.valid)))
const trendX = (index) =>
  trend.value.length === 1 ? 370 : 40 + (index / Math.max(1, trend.value.length - 1)) * 660
const trendPath = computed(() =>
  trend.value
    .map(
      (row, index) =>
        `${index ? 'L' : 'M'} ${trendX(index)} ${190 - (row.valid / trendMax.value) * 150}`,
    )
    .join(' '),
)
let requestController, detailController
async function load() {
  requestController?.abort()
  const controller = new AbortController()
  requestController = controller
  loading.value = true
  error.value = ''
  detailDialog.value?.close()
  const filters = { ...draft.value }
  try {
    const response = await axios.get(`/api/operations/${props.mode}`, {
      params: filters,
      signal: controller.signal,
    })
    if (controller.signal.aborted) return
    data.value = response.data
    applied.value = filters
    regionOptions.value = response.data.regions
  } catch (err) {
    if (!axios.isCancel(err)) {
      error.value = err.response?.data?.error || '看板加载失败，请重试。'
      data.value = null
    }
  } finally {
    if (requestController === controller) loading.value = false
  }
}
function reset() {
  draft.value = defaults()
}
const detailDialog = ref(null),
  detailTitle = ref(''),
  detail = ref({ rows: [], total: 0, page: 1 }),
  detailLoading = ref(false),
  detailError = ref('')
let detailFilters = {}
function showDetails(title, filters) {
  detailTitle.value = title
  detailFilters = { ...filters }
  detail.value = { rows: [], total: 0, page: 1 }
  detailDialog.value.showModal()
  loadDetails(1)
}
function openRegion(region) {
  showDetails(`${region} · 有效问题`, { region, valid: '1' })
}
function closeOnBackdrop(event) {
  if (event.target === detailDialog.value) detailDialog.value.close()
}
function closeDetails() {
  detailController?.abort()
}
async function loadDetails(pageNumber) {
  detailController?.abort()
  const controller = new AbortController()
  detailController = controller
  detailLoading.value = true
  detailError.value = ''
  try {
    const response = await axios.get(`/api/operations/${props.mode}/issues`, {
      params: { ...applied.value, ...detailFilters, page: pageNumber },
      signal: controller.signal,
    })
    if (!controller.signal.aborted) detail.value = response.data
  } catch (err) {
    if (!axios.isCancel(err)) detailError.value = err.response?.data?.error || '明细加载失败。'
  } finally {
    if (detailController === controller) detailLoading.value = false
  }
}
watch(
  () => props.mode,
  () => {
    data.value = null
    regionOptions.value = []
    draft.value = defaults()
    load()
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  requestController?.abort()
  detailController?.abort()
  detailDialog.value?.close()
})
</script>

<style scoped>
.operations-page {
  --ink: #18314e;
  --muted: #64758b;
  --line: #dce6ef;
  --accent: #137da6;
  color: var(--ink);
  display: grid;
  gap: 18px;
  min-width: 0;
}
.card-surface {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 7px 24px #17375206;
}
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 25px 28px;
  background: radial-gradient(ellipse at 100% 0, #e7f4f8, transparent 55%), #fff;
}
.page-kicker,
.eyebrow {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1.6px;
  color: #3883a0;
}
.dashboard-header h2 {
  font-size: 26px;
  margin: 7px 0 8px;
}
.dashboard-header p,
.muted {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.7;
  margin: 0;
}
.live-tag {
  display: flex;
  gap: 8px;
  align-items: center;
  white-space: nowrap;
  font-size: 12px;
  color: #19786f;
  padding: 10px 14px;
  border: 1px solid #c9e7df;
  border-radius: 30px;
  background: #f0faf7;
}
.live-tag i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #1c9b88;
}
.dashboard-filters {
  padding: 20px;
  display: flex;
  align-items: end;
  gap: 14px;
  flex-wrap: wrap;
}
.filter-label {
  display: grid;
  gap: 7px;
  margin-right: auto;
  align-self: center;
}
.filter-label span {
  font-size: 11px;
  color: var(--muted);
}
.dashboard-filters label {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
}
.dashboard-filters input,
.dashboard-filters select {
  height: 40px;
  padding: 8px 10px;
  border: 1px solid #cbd8e4;
  border-radius: 8px;
  background: #fff;
  color: var(--ink);
  font: inherit;
  min-width: 145px;
}
.date-separator {
  align-self: end;
  padding-bottom: 12px;
  color: var(--muted);
}
.filter-buttons {
  display: flex;
  gap: 8px;
}
.dirty {
  flex-basis: 100%;
  color: #986122;
  background: #fff8eb;
  padding: 9px 12px;
  margin: 0;
  border-radius: 8px;
  font-size: 12px;
}
.snapshot {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--muted);
  font-size: 12px;
}
.dashboard-content {
  display: grid;
  gap: 18px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 15px;
}
.metric {
  padding: 22px;
  position: relative;
  overflow: hidden;
  border-top: 3px solid #197daa;
}
.metric.teal {
  border-top-color: #138a79;
}
.metric.amber {
  border-top-color: #c77931;
}
.metric.slate {
  border-top-color: #8190a8;
}
.metric-label {
  font-size: 13px;
  color: #516782;
  font-weight: 600;
}
.metric-value {
  font-size: 38px;
  font-weight: 750;
  letter-spacing: -1px;
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
}
.metric-value small {
  font-size: 13px;
  font-weight: 400;
  letter-spacing: 0;
  margin-left: 7px;
  color: var(--muted);
}
.metric p {
  font-size: 11px;
  color: var(--muted);
  margin: 4px 0 0;
  line-height: 1.7;
}
.two-columns {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}
.chart-card {
  padding: 24px;
  min-width: 0;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}
.section-head h3 {
  font-size: 18px;
  margin: 6px 0 0;
}
.legend {
  font-size: 11px;
  color: var(--muted);
  display: flex;
  gap: 6px;
  align-items: center;
}
.legend i {
  width: 14px;
  height: 3px;
  background: var(--accent);
}
.trend-scroll {
  margin-top: 20px;
}
.trend-scroll svg {
  width: 100%;
  display: block;
}
.svg-label {
  font-size: 11px;
  fill: #74859a;
}
.mini-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
  border-top: 1px solid var(--line);
  padding-top: 15px;
  font-size: 12px;
  color: var(--muted);
}
.mini-stats b {
  font-size: 17px;
  color: var(--ink);
  margin: 0 4px;
}
.phase-list {
  display: grid;
  gap: 3px;
}
.phase-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 12px 7px;
  border: 0;
  border-bottom: 1px solid #edf2f6;
  background: transparent;
  color: var(--ink);
  cursor: pointer;
}
.phase-row > span {
  display: flex;
  gap: 9px;
  align-items: center;
}
.phase-row i {
  height: 8px;
  width: 8px;
  border-radius: 50%;
}
.phase-row b {
  font-size: 20px;
}
.phase-row small,
.station-list b small,
.standards-list b small {
  font-size: 11px;
  font-weight: 400;
  color: var(--muted);
  margin-left: 7px;
}
.phase-row:hover,
.station-list button:hover,
.standards-list button:hover {
  background: #f1f7fb;
}
.pipeline {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.pipeline button {
  display: grid;
  text-align: left;
  gap: 10px;
  padding: 20px;
  border: 1px solid #d5e6ef;
  border-radius: 12px;
  background: linear-gradient(130deg, #f3f9fc, #fff);
  color: var(--ink);
  cursor: pointer;
}
.pipeline button:hover {
  border-color: #248cae;
}
.pipeline .step {
  font-size: 12px;
  letter-spacing: 2px;
  color: #6c97af;
}
.pipeline b {
  font-size: 30px;
}
.pipeline b small {
  font-size: 12px;
  font-weight: 400;
  margin-left: 7px;
}
.pipeline button > span:last-child {
  font-size: 11px;
  color: var(--muted);
}
.bars {
  display: grid;
  gap: 24px;
  margin: 28px 0;
}
.bar-row {
  display: grid;
  grid-template-columns: 95px minmax(0, 1fr) 35px;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.bar-track {
  height: 9px;
  border-radius: 5px;
  background: #edf3f7;
  overflow: hidden;
}
.bar-track i {
  height: 100%;
  display: block;
  background: #268cb1;
  border-radius: 5px;
}
.station-list,
.standards-list {
  display: grid;
  gap: 2px;
}
.station-list button,
.standards-list button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  padding: 12px 4px;
  border: 0;
  border-bottom: 1px solid #edf2f6;
  background: transparent;
  color: var(--ink);
  cursor: pointer;
}
.rank {
  display: grid;
  place-items: center;
  background: #f0f5f9;
  border-radius: 6px;
  font-size: 11px;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  color: #50708c;
}
.station-list button > span:nth-child(2) {
  flex: 1;
  display: grid;
  gap: 6px;
}
.station-list small,
.standard-copy small {
  font-size: 11px;
  color: var(--muted);
}
.station-list strong,
.standard-copy strong {
  font-size: 13px;
}
.station-list b,
.standards-list b {
  white-space: nowrap;
  font-size: 19px;
}
.insights-columns {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
}
.table-bars {
  display: grid;
  gap: 18px;
}
.table-bars button {
  display: grid;
  gap: 10px;
  border: 0;
  background: transparent;
  padding: 8px 0;
  text-align: left;
  color: var(--ink);
  cursor: pointer;
}
.table-bars button > div:first-child {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
}
.table-bars strong {
  font-weight: 500;
}
.table-bars small {
  font-size: 11px;
  color: var(--muted);
}
.standard-copy {
  display: grid;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.standard-copy > span {
  font-size: 12px;
  color: #526881;
  line-height: 1.65;
  overflow-wrap: anywhere;
}
.methodology {
  padding: 18px 22px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.85;
}
.methodology summary {
  cursor: pointer;
  color: #3e5977;
  font-weight: 700;
}
.empty {
  text-align: center;
  color: var(--muted);
  padding: 35px 10px;
  font-size: 13px;
}
.error {
  padding: 16px;
  color: #b33f3f;
  background: #fff3f2;
  border-radius: 12px;
}
.error button {
  margin-left: 12px;
}
.loading {
  padding: 30px;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
}
.loading-track {
  height: 3px;
  max-width: 220px;
  display: block;
  margin: 0 auto 18px;
  background: linear-gradient(90deg, #e7f1f6, #1783ad, #e7f1f6);
  background-size: 200%;
  animation: loading 1.8s linear infinite;
}
.detail-dialog {
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 18px;
  width: min(860px, 94vw);
  max-height: 88dvh;
  color: var(--ink);
  box-shadow: 0 25px 80px #0b213644;
}
.detail-dialog::backdrop {
  background: #10273e80;
  backdrop-filter: blur(3px);
}
.operations-dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
  padding: 22px;
  border-bottom: 1px solid var(--line);
}
.operations-dialog-head h3 {
  margin: 6px 0;
  font-size: 19px;
}
.operations-dialog-head p {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.dialog-body {
  overflow: auto;
  max-height: 58dvh;
  padding: 0 22px;
}
.detail-items article {
  padding: 18px 0;
  border-bottom: 1px solid var(--line);
}
.detail-items header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}
.detail-items small {
  display: block;
  color: var(--muted);
  font-size: 11px;
  margin-top: 8px;
}
.detail-items p {
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.phase-pill {
  padding: 4px 9px;
  border-radius: 20px;
  background: #eef5fa;
  font-size: 11px;
  white-space: nowrap;
}
.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 22px;
  font-size: 12px;
  color: var(--muted);
  gap: 10px;
}
.dialog-footer > div {
  display: flex;
  gap: 8px;
}
button:focus-visible,
input:focus-visible,
select:focus-visible,
summary:focus-visible {
  outline: 2px solid #187fa6;
  outline-offset: 3px;
}
@keyframes loading {
  to {
    background-position: 200% 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .loading-track {
    animation: none;
  }
}
@media (max-width: 1100px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .two-columns {
    grid-template-columns: 1fr;
  }
  .filter-label {
    width: 100%;
  }
  .dashboard-header {
    align-items: start;
    gap: 15px;
  }
  .live-tag {
    font-size: 10px;
  }
  .pipeline {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .dashboard-header {
    padding: 20px;
    display: block;
  }
  .dashboard-header h2 {
    font-size: 23px;
  }
  .live-tag {
    width: fit-content;
    margin-top: 16px;
  }
  .dashboard-filters {
    padding: 16px;
    gap: 12px;
  }
  .dashboard-filters label {
    flex: 1;
    min-width: 0;
  }
  .dashboard-filters input,
  .dashboard-filters select {
    width: 100%;
    min-width: 0;
  }
  .date-separator {
    display: none;
  }
  .dashboard-filters label:last-of-type {
    flex-basis: 100%;
  }
  .filter-buttons {
    width: 100%;
    justify-content: flex-end;
  }
  .metric {
    padding: 16px 12px;
  }
  .metric-value {
    font-size: 30px;
  }
  .metric-label {
    font-size: 12px;
  }
  .chart-card {
    padding: 18px 14px;
  }
  .section-head {
    flex-wrap: wrap;
  }
  .section-head h3 {
    font-size: 17px;
  }
  .snapshot {
    flex-wrap: wrap;
    font-size: 11px;
  }
  .pipeline {
    gap: 8px;
  }
  .pipeline button {
    padding: 15px;
  }
  .pipeline strong {
    font-size: 14px;
  }
  .detail-dialog {
    width: 96vw;
    max-height: 94dvh;
  }
  .operations-dialog-head,
  .dialog-footer {
    padding: 15px;
  }
  .dialog-body {
    padding: 0 15px;
  }
  .dialog-footer {
    flex-wrap: wrap;
  }
  .metric-grid {
    gap: 10px;
  }
  .standards-list button {
    gap: 8px;
  }
  .live-tag i {
    flex-shrink: 0;
  }
}
</style>
