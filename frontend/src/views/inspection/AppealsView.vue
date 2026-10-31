<template>
  <div class="appeals-page">
    <header class="surface page-heading">
      <div>
        <span class="eyebrow">巡检系统 / APPEAL WORKSPACE</span>
        <h2>申诉空间</h2>
        <p>让每一次申诉有依据、有进度、有反馈。</p>
      </div>
      <div class="heading-process" aria-label="申诉流程">
        <span>站点申请</span><i>→</i><span>片区初审</span><i>→</i><span>质安部终审</span
        ><small>仅展示当前账号可查看的数据 · 每个问题限申诉一次</small>
      </div>
    </header>
    <div v-if="notice" class="notice" role="status">
      {{ notice }}<button @click="notice = ''" aria-label="关闭提示">×</button>
    </div>
    <nav class="stage-tabs" aria-label="申诉分类">
      <button
        v-for="(tab, index) in tabs"
        :key="tab.key"
        type="button"
        :class="['stage-tab', { active: stage === tab.key }]"
        :aria-pressed="stage === tab.key"
        @click="setStage(tab.key)"
      >
        <span class="tab-icon">{{ ['初', '终', '结'][index] }}</span
        ><span class="tab-copy"
          ><strong>{{ tab.label }}</strong
          ><small>{{ tab.hint }}</small></span
        >
        <span :class="['tab-count', { unread: tab.key === 'ended' && counts[tab.count] }]"
          >{{ counts[tab.count] || 0
          }}<small>{{ tab.key === 'ended' ? '未读' : '条' }}</small></span
        >
      </button>
    </nav>
    <p class="stage-scope">分类数量按全部可见记录统计，不随筛选改变；已结束记录显示未读数。</p>
    <form class="surface filter-panel" @submit.prevent="applyFilters">
      <header class="section-heading">
        <div>
          <h3>筛选申诉</h3>
          <p>按条件查询全部可见记录，不限于当前页。</p>
        </div>
        <span class="scope-note">调整条件后点击「开始筛选」</span>
      </header>
      <FilterSummary :fields="filterFields" manual />
      <div class="filter-grid">
        <label class="keyword-field" :data-set="!!keyword"
          >关键词<input
            v-model="keyword"
            maxlength="200"
            placeholder="问题ID、站点、问题描述、申诉或审核原因"
        /></label>
        <label :data-set="!!filters.region"
          >所属片区<select v-model="filters.region">
            <option value="">全部可见片区</option>
            <option v-for="region in filterOptions.regions" :key="region" :value="region">
              {{ region }}
            </option>
          </select></label
        >
        <label :data-set="!!filters.table_id"
          >检查表<select v-model="filters.table_id">
            <option value="">全部检查表</option>
            <option v-for="table in filterOptions.tables" :key="table.id" :value="String(table.id)">
              {{ table.name }}
            </option>
          </select></label
        >
        <label :data-set="!!filters.date_from"
          >申诉开始日期<input v-model="filters.date_from" type="date"
        /></label>
        <label :data-set="!!filters.date_to"
          >申诉结束日期<input v-model="filters.date_to" type="date"
        /></label>
        <label v-if="archive" :data-set="!!filters.outcome"
          >处理结果<select v-model="filters.outcome">
            <option value="">全部处理结果</option>
            <option value="approved">申诉通过</option>
            <option value="rejected">申诉被拒绝</option>
            <option value="cancelled">申诉已取消</option>
          </select></label
        >
        <label v-if="archive" class="unread-field"
          ><input v-model="filters.unread" type="checkbox" />仅看未读结果</label
        >
      </div>
      <footer class="filter-actions">
        <span v-if="filterError" class="error" role="alert">{{ filterError }}</span
        ><span v-else class="muted">申诉日期按发起时间筛选，结束日期包含当天。</span>
        <div>
          <button type="button" :disabled="loading" @click="resetFilters">重置条件</button
          ><button class="primary" :disabled="loading">
            {{ loading ? '正在筛选…' : '开始筛选' }}
          </button>
        </div>
      </footer>
    </form>
    <section :aria-busy="loading" class="results" aria-label="申诉记录">
      <header class="results-heading">
        <div>
          <h3>
            {{ tabs.find((tab) => tab.key === stage)?.label }} <span>{{ total }} 条</span>
          </h3>
          <p>
            {{
              archive
                ? '查看处理结果后，消除当前账号的该条未读提醒。'
                : '进行中的申诉持续计入菜单提醒，查看不会减少数量。'
            }}
          </p>
        </div>
        <span class="muted">按申诉发起顺序倒序排列</span>
      </header>
      <div v-if="loading" class="surface empty loading-state" role="status">
        <span class="loading-line"></span>正在读取申诉记录…
      </div>
      <div v-else-if="error" class="surface empty" role="alert">
        <h3>暂时无法读取记录</h3>
        <p class="error">{{ error }}</p>
        <button @click="load">重新加载</button>
      </div>
      <template v-else>
        <article v-for="item in items" :key="item.id" :class="['surface appeal-card', item.status]">
          <header class="card-heading">
            <div>
              <div class="record-meta">
                <span class="issue-number">问题 #{{ item.issue_id }}</span
                ><span>申诉 #{{ item.id }}</span
                ><span v-if="item.unread" class="unread-dot">未读结果</span>
              </div>
              <h3>
                {{ item.station_name
                }}<span class="region-tag">{{ item.region || '未填写片区' }}</span>
              </h3>
            </div>
            <span :class="['status', item.status]">{{ labels[item.status] || item.status }}</span>
          </header>
          <div class="record-facts">
            <span><b>检查表</b>{{ item.table_name }}</span
            ><span><b>检查时间</b>{{ item.inspection_time }}</span
            ><span><b>申诉人</b>{{ item.submitted_name || '—' }}</span
            ><span><b>发起时间</b>{{ item.created_at || '—' }}</span>
          </div>
          <div class="evidence-layout">
            <div class="evidence-copy">
              <section class="description-block">
                <h4>问题描述</h4>
                <p>{{ item.description || '暂无问题描述' }}</p>
              </section>
              <section class="appeal-reason">
                <h4>站点申诉理由</h4>
                <p>{{ item.reason || '暂无申诉理由' }}</p>
              </section>
            </div>
            <button v-if="item.photo_path" class="photo" @click="photo = imageUrl(item.photo_path)">
              <img :src="imageUrl(item.photo_path)" alt="问题照片，点击放大" loading="lazy" /><span
                >查看问题照片</span
              >
            </button>
          </div>
          <WorkflowDeadline
            v-if="!archive && item.review_deadline_ms"
            :deadline="item.review_deadline_ms"
            :server-now="item.server_now_ms"
            :title="item.status === 'area_pending' ? '片区独立审核倒计时' : '质安部独立审核倒计时'"
            :hint="reviewDeadlineHint(item)"
            :expired-hint="reviewDeadlineHint(item, true)"
            @expired="expiredReviews.add(reviewDeadlineKey(item))"
          />
          <p
            v-if="!archive && item.review_deadline_enabled && !item.review_deadline_ms"
            class="outcome"
          >
            本阶段截止时间待同步，可能缺少对应年份工作日历。暂不自动判定，仍可人工审核。
          </p>
          <p v-if="item.timeout_at" class="outcome">
            本申诉由系统按超时规则处理，并非人员主动审核。{{
              item.timeout_stage === 'area_pending' ? item.area_reason : item.quality_reason
            }}
          </p>
          <button
            v-if="archive"
            class="result-toggle"
            :aria-expanded="expanded.has(item.id)"
            :disabled="reading !== null"
            @click="viewResult(item)"
          >
            {{ expanded.has(item.id) ? '收起处理结果' : '查看处理结果'
            }}<span v-if="item.unread" class="count-badge">未读</span
            ><span aria-hidden="true">{{ expanded.has(item.id) ? '−' : '+' }}</span>
          </button>
          <AppealProgress
            v-if="!archive || expanded.has(item.id)"
            :item="item"
            :reviewers="qualityReviewers"
          />
          <footer class="card-footer">
            <span class="muted"
              >当前问题状态 <strong>{{ item.issue_status }}</strong></span
            ><button
              v-if="item.can_decide"
              class="primary"
              :disabled="
                item.review_deadline_enabled &&
                expiredReviews.has(reviewDeadlineKey(item)) &&
                item.review_policy?.timeout_action !== 'manual'
              "
              @click="openDecision(item)"
            >
              审核申诉 →</button
            ><span v-else-if="!archive" class="readonly-note">当前阶段仅可查看</span>
          </footer>
        </article>
        <div v-if="!items.length" class="surface empty">
          <span class="empty-symbol" aria-hidden="true">申</span>
          <h3>暂无符合条件的申诉</h3>
          <p>可切换处理分类，或调整筛选条件后重新查询。</p>
          <button v-if="hasAppliedFilters" @click="resetFilters">清空筛选条件</button>
        </div>
      </template>
    </section>
    <nav class="pagination" aria-label="申诉分页">
      <span>共 {{ total }} 条 · 每页 20 条</span>
      <div>
        <button :disabled="loading || page <= 1" @click="changePage(-1)">上一页</button
        ><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 20)) }}</span
        ><button :disabled="loading || page * 20 >= total" @click="changePage(1)">下一页</button>
      </div>
    </nav>
    <Teleport to="body">
      <div v-if="selected" class="overlay" @click.self="!saving && (selected = null)">
        <form
          ref="decisionDialog"
          class="decision surface"
          role="dialog"
          aria-modal="true"
          aria-labelledby="decision-title"
          tabindex="-1"
          @submit.prevent="decide"
        >
          <header class="decision-heading">
            <div>
              <span class="eyebrow">申诉审核 / 问题 #{{ selected.issue_id }}</span>
              <h3 id="decision-title">
                {{ selected.status === 'area_pending' ? '片区初审' : '质安部终审' }}
              </h3>
            </div>
            <button
              type="button"
              class="close-button"
              aria-label="关闭审核弹窗"
              :disabled="saving"
              @click="selected = null"
            >
              ×
            </button>
          </header>
          <p class="decision-station">{{ selected.station_name }} · {{ selected.region }}</p>
          <div class="appeal-reason">
            <h4>站点申诉理由</h4>
            <p>{{ selected.reason }}</p>
          </div>
          <fieldset :disabled="saving">
            <legend>审核决定（必选）</legend>
            <div class="decision-choices">
              <label :class="{ chosen: decision === 'approve' }"
                ><input v-model="decision" type="radio" value="approve" />通过申诉</label
              ><label :class="['reject-choice', { chosen: decision === 'reject' }]"
                ><input v-model="decision" type="radio" value="reject" />拒绝申诉</label
              >
            </div>
          </fieldset>
          <p class="outcome">
            {{
              decision === 'reject'
                ? '问题将离开待处理申诉，回到站点继续整改。'
                : selected.status === 'area_pending'
                  ? '通过后转交授权质安部账号终审，仍暂停整改。'
                  : '通过后问题状态为已销毁，不再要求整改，历史记录保留。'
            }}
          </p>
          <label
            >审核原因（必填）<textarea
              v-model="reason"
              rows="4"
              maxlength="4000"
              :disabled="saving"
              placeholder="说明判断依据，便于站点了解处理结果"
            ></textarea></label
          ><span class="text-count">{{ reason.length }} / 4000</span>
          <p v-if="decisionError" class="error" role="alert">{{ decisionError }}</p>
          <footer>
            <button type="button" :disabled="saving" @click="selected = null">取消</button
            ><button class="primary" :disabled="saving || !decision || !reason.trim()">
              {{ saving ? '正在提交…' : '确认提交审核结果' }}
            </button>
          </footer>
        </form>
      </div>
      <InspectionPhotoPreview v-if="photo" :url="photo" title="问题照片" @close="photo = ''" />
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import AppealProgress from '../../components/AppealProgress.vue'
import WorkflowDeadline from '../../components/WorkflowDeadline.vue'
import InspectionPhotoPreview from '../../components/InspectionPhotoPreview.vue'
import FilterSummary from '../../components/FilterSummary.vue'
const expiredReviews = ref(new Set())
const reviewDeadlineKey = (item) => `${item.id}:${item.review_deadline_ms}`
const reviewDeadlineHint = (item, expired = false) => {
  const action = item.review_policy?.timeout_action
  return `${expired ? '期限已结束，等待低频后台任务处理。' : '各级独立计时，非工作日暂停。'}${action === 'approve' ? (item.status === 'area_pending' ? '超时自动通过片区初审，转交质安部重新计时。' : '超时自动通过终审，问题已销毁。') : action === 'reject' ? '系统按期扫描时自动拒绝申诉，恢复整改。' : '当前规则不自动决策，仍需人工审核。'} 自动处理可能延后数小时，超时阶段及待办理账号均留痕。`
}
const route = useRoute(),
  router = useRouter()
const items = ref([]),
  total = ref(0),
  page = ref(1),
  archive = ref(false),
  keyword = ref('')
const stage = ref('area_pending')
const tabs = [
  {
    key: 'area_pending',
    label: '待片区处理申诉',
    count: 'area_pending',
    hint: '所属片区核实申诉依据',
  },
  {
    key: 'quality_pending',
    label: '待质安部处理申诉',
    count: 'quality_pending',
    hint: '授权质安部账号作出终审',
  },
  { key: 'ended', label: '已结束记录', count: 'unread_ended', hint: '查看最终结果与处理过程' },
]
const labels = {
  area_pending: '待片区初审',
  quality_pending: '待质安部终审',
  approved: '申诉通过',
  rejected: '申诉被拒绝',
  cancelled: '申诉已取消',
}
const emptyFilters = () => ({
  region: '',
  table_id: '',
  date_from: '',
  date_to: '',
  outcome: '',
  unread: false,
})
const filters = ref(emptyFilters()),
  applied = ref({ ...emptyFilters(), keyword: '' })
const filterOptions = ref({ regions: [], tables: [] }),
  optionsLoaded = ref(false),
  filterError = ref('')
const effectiveFilters = (source) => ({
  ...source,
  outcome: archive.value ? source.outcome : '',
  unread: archive.value && source.unread,
})
const filterFields = computed(() => {
  const draft = effectiveFilters({ ...filters.value, keyword: keyword.value }),
    previous = effectiveFilters(applied.value)
  const definitions = [
    ['keyword', '关键词'],
    ['region', '片区'],
    ['table_id', '检查表'],
    ['date_from', '申诉开始'],
    ['date_to', '申诉结束'],
  ]
  if (archive.value) definitions.push(['outcome', '处理结果'], ['unread', '未读结果'])
  const display = (key, value) =>
    key === 'table_id'
      ? filterOptions.value.tables.find((table) => String(table.id) === value)?.name || value
      : key === 'outcome'
        ? labels[value] || ''
        : key === 'unread'
          ? value
            ? '仅看未读'
            : ''
          : value
  return definitions.map(([key, label]) => ({
    key,
    label,
    value: display(key, draft[key]),
    applied: display(key, previous[key]),
    changed: draft[key] !== previous[key],
  }))
})
const hasAppliedFilters = computed(() =>
  Object.values(effectiveFilters(applied.value)).some(Boolean),
)
const counts = ref({ active: 0, area_pending: 0, quality_pending: 0, unread_ended: 0, total: 0 }),
  expanded = ref(new Set()),
  reading = ref(null),
  qualityReviewers = ref([])
const loading = ref(false),
  error = ref(''),
  notice = ref(''),
  selected = ref(null),
  decision = ref(''),
  reason = ref(''),
  saving = ref(false),
  decisionError = ref(''),
  photo = ref('')
const imageUrl = (path) =>
  !path
    ? ''
    : /^https?:\/\//.test(path) || path.startsWith('/storage/')
      ? path
      : `/storage/${path.replace(/^\//, '')}`
const decisionDialog = ref(null)
let previousFocus
watch(selected, async (value) => {
  if (typeof document === 'undefined') return
  if (value) {
    previousFocus = document.activeElement
    await nextTick()
    if (selected.value) decisionDialog.value?.querySelector('button')?.focus()
  } else if (previousFocus?.isConnected) previousFocus.focus()
})
let requestId = 0,
  controller
async function load() {
  const id = ++requestId
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const active = effectiveFilters(applied.value)
    const params = {
      page: page.value,
      archive: archive.value ? 1 : 0,
      stage: archive.value ? undefined : stage.value,
      keyword: active.keyword,
    }
    for (const key of ['region', 'table_id', 'date_from', 'date_to', 'outcome'])
      if (active[key]) params[key] = active[key]
    if (active.unread) params.unread = '1'
    if (!optionsLoaded.value) params.include_filters = '1'
    const { data } = await axios.get('/api/issue-appeals', { params, signal: controller.signal })
    if (id !== requestId) return
    items.value = data.items
    total.value = data.total
    counts.value = data.counts
    qualityReviewers.value = data.quality_reviewers || []
    if (data.filter_options) {
      filterOptions.value = data.filter_options
      optionsLoaded.value = true
    }
    if (page.value > 1 && !items.value.length) {
      page.value = Math.max(1, Math.min(page.value - 1, Math.ceil(total.value / 20)))
      return load()
    }
  } catch (err) {
    if (id === requestId && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '申诉记录读取失败。'
  } finally {
    if (id === requestId) loading.value = false
  }
}
function applyFilters() {
  filterError.value = ''
  if (
    filters.value.date_from &&
    filters.value.date_to &&
    filters.value.date_from > filters.value.date_to
  ) {
    filterError.value = '申诉开始日期不能晚于结束日期。'
    return
  }
  applied.value = { ...filters.value, keyword: keyword.value.trim() }
  keyword.value = applied.value.keyword
  page.value = 1
  return load()
}
function resetFilters() {
  filters.value = emptyFilters()
  keyword.value = ''
  return applyFilters()
}
function changePage(offset) {
  if (loading.value) return
  page.value = Math.max(1, Math.min(Math.max(1, Math.ceil(total.value / 20)), page.value + offset))
  return load()
}
function setStage(value) {
  stage.value = value
  archive.value = value === 'ended'
  expanded.value.clear()
  page.value = 1
  return load()
}
async function viewResult(item) {
  if (reading.value !== null) return
  if (expanded.value.has(item.id)) {
    expanded.value.delete(item.id)
    return
  }
  expanded.value.add(item.id)
  if (!item.unread) return
  reading.value = item.id
  try {
    const { data } = await axios.post(`/api/issue-appeals/${item.id}/read`, {
      version: item.notification_version,
    })
    item.unread = false
    counts.value = data.counts
    window.dispatchEvent(new Event('my-pending-rectification-refresh'))
  } catch (err) {
    expanded.value.delete(item.id)
    error.value = err.response?.data?.error || '标记已读失败，请重新查看。'
  } finally {
    reading.value = null
  }
}
function openDecision(item) {
  selected.value = item
  decision.value = ''
  reason.value = ''
  decisionError.value = ''
}
async function decide() {
  if (saving.value || !selected.value || !decision.value || !reason.value.trim()) return
  saving.value = true
  decisionError.value = ''
  try {
    const { data } = await axios.post(`/api/issue-appeals/${selected.value.id}/decision`, {
      decision: decision.value,
      reason: reason.value.trim(),
      stage: selected.value.status,
    })
    notice.value = data.message
    selected.value = null
    window.dispatchEvent(new Event('my-pending-rectification-refresh'))
    await load()
  } catch (err) {
    decisionError.value = err.response?.data?.error || '审核提交失败。'
  } finally {
    saving.value = false
  }
}
function keydown(event) {
  if (event.key === 'Tab' && selected.value && !photo.value && decisionDialog.value) {
    const focusable = [
      ...decisionDialog.value.querySelectorAll(
        'button:not(:disabled), input:not(:disabled), textarea:not(:disabled)',
      ),
    ].filter((node) => !node.matches(':disabled'))
    const first = focusable[0],
      last = focusable.at(-1)
    if (!first) {
      event.preventDefault()
      decisionDialog.value.focus()
      return
    }
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }
  if (event.key === 'Escape') {
    photo.value = ''
    if (!saving.value) selected.value = null
  }
}
onMounted(() => {
  if (route.query.submitted === '1') {
    notice.value = '问题已进入申诉空间，等待所属片区审核反馈。'
    router.replace({ path: route.path, query: {} })
  }
  load()
  window.addEventListener('keydown', keydown)
})
onBeforeUnmount(() => {
  requestId++
  controller?.abort()
  window.removeEventListener('keydown', keydown)
})
</script>

<style scoped>
.appeals-page {
  --ink: #18394f;
  display: grid;
  gap: 20px;
  color: var(--ink);
  min-width: 0;
}
.surface {
  background: #fff;
  border: 1px solid #d5e2ec;
  border-radius: 18px;
  padding: 24px;
  box-shadow: 0 5px 20px #20385d05;
  min-width: 0;
}
.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  padding: 30px;
  background: linear-gradient(115deg, #13334e, #225f70);
  color: #fff;
  border: 0;
  border-bottom: 4px solid #d6ac58;
}
.eyebrow {
  color: #34738e;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
}
.page-heading .eyebrow {
  color: #a7d8e0;
}
.page-heading h2 {
  font-size: 30px;
  margin: 12px 0;
  letter-spacing: 0.04em;
}
.page-heading p {
  color: #d0e3ed;
  margin: 0;
}
.heading-process {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
  max-width: 430px;
}
.heading-process > span {
  padding: 8px 12px;
  background: #ffffff10;
  border: 1px solid #ffffff30;
  border-radius: 8px;
  font-size: 13px;
}
.heading-process i {
  font-style: normal;
  color: #98c6d4;
}
.heading-process small {
  width: 100%;
  text-align: right;
  color: #bed4df;
  margin-top: 5px;
  font-size: 12px;
}
h3,
h4,
p {
  margin: 0;
}
p {
  line-height: 1.75;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
.muted,
.scope-note {
  color: #63788c;
  font-size: 13px;
}
.stage-scope {
  margin-top: -8px;
  color: #6a7f91;
  font-size: 12px;
}
button {
  border: 1px solid #c9d8e5;
  background: #fff;
  color: #294b65;
  border-radius: 9px;
  padding: 10px 16px;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  transition:
    background 0.16s,
    border-color 0.16s;
}
button:hover:not(:disabled) {
  border-color: #438caa;
  background: #eef7fb;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
button:focus-visible,
input:focus-visible,
select:focus-visible,
textarea:focus-visible {
  outline: 3px solid #7ebbd6;
  outline-offset: 2px;
}
.primary {
  background: #1b6c90;
  border-color: #1b6c90;
  color: #fff;
}
.primary:hover:not(:disabled) {
  background: #145776;
  color: #fff;
}
.stage-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.stage-tab {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  text-align: left;
  border-color: #d5e2ec;
  border-radius: 14px;
}
.tab-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #edf3f7;
  color: #476e87;
  flex-shrink: 0;
}
.tab-copy {
  display: grid;
  gap: 6px;
}
.tab-copy strong {
  font-size: 16px;
}
.tab-copy small {
  color: #698093;
  font-size: 12px;
  font-weight: 400;
}
.tab-count {
  margin-left: auto;
  font-size: 26px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.tab-count small {
  margin-left: 4px;
  font-size: 11px;
  font-weight: 400;
}
.tab-count.unread {
  color: #bb3b42;
}
.stage-tab.active {
  border-color: #238298;
  background: #edf8f8;
  box-shadow: inset 0 3px #238298;
}
.stage-tab.active .tab-icon {
  background: #1c7186;
  color: #fff;
}
.section-heading,
.results-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.section-heading h3,
.results-heading h3 {
  font-size: 18px;
}
.section-heading p,
.results-heading p {
  font-size: 13px;
  color: #63788c;
  margin-top: 5px;
}
.results-heading {
  margin: 4px 0 0;
}
.results-heading h3 span {
  font-size: 14px;
  color: #1b738a;
  margin-left: 10px;
  font-weight: 500;
}
.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.keyword-field {
  grid-column: span 2;
}
label {
  display: grid;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  min-width: 0;
}
input,
select,
textarea {
  font: inherit;
  font-size: 14px;
  font-weight: 400;
  color: #203f56;
  border: 1px solid #cbd9e7;
  padding: 11px 12px;
  border-radius: 8px;
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  background: #fff;
}
input::placeholder,
textarea::placeholder {
  color: #8393a2;
}
label[data-set='true'] input,
label[data-set='true'] select {
  border-color: #5ca4ba;
  background: #f2fafb;
}
.unread-field {
  display: flex;
  align-items: center;
  align-self: end;
  height: 42px;
}
.unread-field input {
  width: 16px;
  height: 16px;
  accent-color: #1c7186;
}
.filter-actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-top: 20px;
  border-top: 1px solid #e6edf3;
  padding-top: 16px;
}
.filter-actions > div {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}
.results {
  display: grid;
  gap: 18px;
}
.appeal-card {
  padding: 0;
  overflow: hidden;
  border-top: 3px solid #408da6;
}
.appeal-card.approved {
  border-top-color: #4b9c7c;
}
.appeal-card.rejected {
  border-top-color: #c77955;
}
.card-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 22px 24px 16px;
}
.record-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  color: #738599;
  font-size: 12px;
}
.issue-number {
  color: #276580;
  font-weight: 700;
  background: #edf5fa;
  padding: 4px 8px;
  border-radius: 5px;
}
.card-heading h3 {
  font-size: 21px;
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.region-tag {
  font-size: 12px;
  font-weight: 500;
  color: #577183;
  border-left: 1px solid #cbd9e5;
  padding-left: 12px;
}
.unread-dot {
  color: #b73b46;
}
.unread-dot::before {
  content: '';
  display: inline-block;
  width: 6px;
  height: 6px;
  background: #d54e5e;
  border-radius: 50%;
  margin-right: 5px;
}
.status {
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  border-radius: 7px;
  background: #eaf3fc;
  color: #276e9e;
  white-space: nowrap;
}
.status.quality_pending {
  background: #eef1f9;
  color: #455c88;
}
.status.rejected {
  color: #9d4b25;
  background: #fff1e7;
}
.status.approved {
  color: #21715a;
  background: #eaf7f0;
}
.status.cancelled {
  background: #f1f3f5;
  color: #627083;
}
.record-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 24px;
  padding: 12px 24px;
  background: #f6f9fc;
  border-block: 1px solid #e6edf3;
  font-size: 13px;
  color: #435d72;
}
.record-facts > span {
  display: flex;
  gap: 8px;
  min-width: 0;
  overflow-wrap: anywhere;
}
.record-facts b {
  color: #778899;
  font-weight: 400;
  flex-shrink: 0;
}
.evidence-layout {
  display: flex;
  gap: 24px;
  padding: 22px 24px;
  align-items: flex-start;
}
.evidence-copy {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 16px;
}
h4 {
  font-size: 13px;
  color: #536d82;
  margin-bottom: 7px;
}
.description-block p {
  font-size: 15px;
  font-weight: 500;
  color: #243e53;
}
.appeal-reason {
  background: #f1f7fa;
  border-left: 3px solid #71a9bc;
  border-radius: 0 8px 8px 0;
  padding: 13px 16px;
}
.appeal-reason h4 {
  color: #236880;
}
.appeal-reason p {
  font-size: 14px;
  color: #3f5c70;
}
.photo {
  padding: 6px;
  width: 160px;
  flex-shrink: 0;
  cursor: zoom-in;
  display: grid;
  gap: 6px;
  border-color: #d8e5ed;
}
.photo img {
  width: 100%;
  height: 116px;
  object-fit: contain;
  background: #f6f8fa;
}
.photo span {
  font-size: 12px;
  font-weight: 400;
  color: #377b96;
}
.appeal-card :deep(.appeal-progress) {
  margin: 0 24px 22px;
}
.appeal-card :deep(.workflow-deadline) {
  margin: 0 24px 18px;
}
.appeal-card > .outcome {
  margin: 0 24px 18px;
}
.result-toggle {
  margin: 0 24px 20px;
  display: flex;
  gap: 10px;
  align-items: center;
}
.count-badge {
  padding: 2px 6px;
  background: #c94350;
  color: white;
  border-radius: 12px;
  font-size: 11px;
}
.card-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  background: #fafcfe;
  border-top: 1px solid #e5edf4;
  padding: 14px 24px;
}
.card-footer strong {
  color: #3e5b71;
  margin-left: 8px;
}
.readonly-note {
  color: #81909e;
  font-size: 12px;
}
.pagination,
.pagination > div {
  display: flex;
  gap: 16px;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #657c90;
}
.empty {
  padding: 42px 20px;
  text-align: center;
  color: #718398;
}
.empty h3 {
  font-size: 17px;
  margin: 12px 0 6px;
  color: #3d5b70;
}
.empty p {
  font-size: 14px;
  margin-bottom: 16px;
}
.empty-symbol {
  display: inline-grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: #eaf3f8;
  color: #5f8ba4;
  font-weight: 700;
}
.loading-state {
  position: relative;
  overflow: hidden;
}
.loading-line {
  position: absolute;
  top: 0;
  left: 0;
  height: 3px;
  width: 40%;
  background: #3297b3;
  animation: loading 1.3s ease-in-out infinite;
}
@keyframes loading {
  to {
    transform: translateX(260%);
  }
}
.notice,
.outcome {
  background: #eaf5fa;
  color: #246187;
  padding: 14px;
  border-radius: 10px;
  font-size: 13px;
}
.notice {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.notice button {
  border: 0;
  background: none;
}
.error {
  color: #b42318;
  font-size: 14px;
}
.overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  background: #13223a99;
  display: grid;
  place-items: center;
  padding: 20px;
}
.decision {
  color: #18394f;
  width: min(620px, 100%);
  max-height: 90dvh;
  overflow-y: auto;
  box-sizing: border-box;
}
.decision-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}
.decision-heading h3 {
  margin-top: 8px;
  font-size: 23px;
}
.close-button {
  padding: 3px 10px;
  font-size: 24px;
  font-weight: 400;
  background: #f4f7f9;
}
.decision-station {
  font-weight: 600;
  margin: 16px 0;
}
.decision fieldset {
  border: 0;
  padding: 0;
  margin: 22px 0 0;
}
.decision legend {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
}
.decision-choices {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.decision-choices label {
  display: flex;
  align-items: center;
  border: 1px solid #d3e0e9;
  border-radius: 9px;
  padding: 14px;
  cursor: pointer;
}
.decision-choices input {
  width: 16px;
  accent-color: #237d80;
}
.decision-choices .chosen {
  border-color: #368c82;
  background: #edf8f5;
  color: #276d5d;
}
.decision-choices .reject-choice.chosen {
  border-color: #cc8174;
  background: #fff4f1;
  color: #a54936;
}
.decision .outcome {
  margin: 16px 0;
}
.text-count {
  display: block;
  text-align: right;
  color: #82909e;
  font-size: 12px;
  margin-top: 6px;
}
.decision footer {
  display: flex;
  gap: 10px;
  justify-content: end;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #e2ebf2;
}
@media (min-width: 1280px) {
  .filter-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
}
@media (max-width: 1100px) {
  .heading-process {
    display: none;
  }
  .stage-tab {
    padding: 16px 12px;
    gap: 10px;
  }
  .tab-copy strong {
    font-size: 14px;
  }
  .tab-copy small {
    display: none;
  }
  .tab-count {
    font-size: 22px;
  }
  .tab-icon {
    width: 34px;
    height: 34px;
  }
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 700px) {
  .appeals-page {
    gap: 14px;
  }
  .surface {
    padding: 16px;
    border-radius: 14px;
  }
  .page-heading {
    padding: 22px 18px;
  }
  .page-heading h2 {
    font-size: 26px;
  }
  .page-heading p {
    font-size: 13px;
  }
  .stage-tabs {
    gap: 7px;
  }
  .stage-tab {
    padding: 12px 9px;
    flex-wrap: wrap;
    gap: 8px;
    align-content: flex-start;
  }
  .tab-icon {
    display: none;
  }
  .tab-copy strong {
    font-size: 13px;
    line-height: 1.6;
  }
  .tab-copy {
    min-height: 42px;
  }
  .tab-count {
    margin-left: 0;
    width: 100%;
    font-size: 23px;
  }
  .section-heading .scope-note,
  .results-heading > .muted {
    display: none;
  }
  .filter-grid {
    gap: 14px 10px;
  }
  input,
  select,
  textarea {
    font-size: 16px;
    padding: 10px 8px;
  }
  .filter-grid > label:nth-child(2),
  .filter-grid > label:nth-child(3) {
    grid-column: span 2;
  }
  .filter-actions {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }
  .filter-actions > div {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .appeal-card {
    padding: 0;
  }
  .card-heading {
    padding: 18px 16px 14px;
    align-items: flex-start;
  }
  .card-heading h3 {
    font-size: 19px;
  }
  .status {
    padding: 6px 8px;
    font-size: 12px;
  }
  .record-meta {
    gap: 6px;
  }
  .record-facts {
    padding: 12px 16px;
    gap: 8px;
    display: grid;
  }
  .evidence-layout {
    padding: 16px;
    gap: 14px;
    flex-direction: column;
  }
  .photo {
    width: 150px;
  }
  .appeal-card :deep(.appeal-progress) {
    margin: 0 16px 18px;
  }
  .appeal-card :deep(.workflow-deadline),
  .appeal-card > .outcome {
    margin: 0 16px 16px;
  }
  .result-toggle {
    margin-inline: 16px;
  }
  .card-footer {
    padding: 12px 16px;
    flex-wrap: wrap;
  }
  .pagination {
    flex-direction: column;
    gap: 12px;
  }
  .pagination > div {
    gap: 18px;
  }
  .overlay {
    padding: 12px;
  }
  .decision {
    padding: 20px 16px;
  }
  .decision-choices label {
    padding: 12px;
  }
  .decision footer button {
    padding-inline: 12px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .loading-line {
    animation: none;
    width: 100%;
  }
  button {
    transition: none;
  }
}
</style>
