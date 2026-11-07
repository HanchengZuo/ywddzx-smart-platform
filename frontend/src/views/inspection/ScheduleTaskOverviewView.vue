<template>
  <div class="overview">
    <header class="hero">
      <div>
        <p class="kicker">排班系统 / TEAM TASKS</p>
        <h2>待办总览</h2>
        <p>从全员进度到逐站检查表，一处查看今日派工与历史未完成任务。</p>
      </div>
      <div class="hero-meta">
        <span>只读视图</span>
        <time v-if="day" :datetime="day">{{ day }} · 北京时间</time>
      </div>
    </header>

    <div v-if="error" class="notice error" role="alert">
      {{ error }} <button type="button" class="plain" @click="refresh">重试</button>
    </div>
    <p v-if="loading && !day" class="notice" role="status">正在核对全员巡检任务与最新记录…</p>

    <template v-if="day">
      <section class="metrics" aria-label="全员任务概况">
        <article v-for="item in cards" :key="item.label" class="metric" :class="item.tone">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}<small> {{ item.unit }}</small></strong>
          <p>{{ item.note }}</p>
        </article>
      </section>
      <section class="roster" :aria-busy="loading">
        <div class="roster-head">
          <div>
            <p class="section-kicker">人员与进度</p>
            <h3>全员巡检待办</h3>
            <p>每项对应一名人员的一张检查表；多人共同派工时分别计数。</p>
          </div>
          <button type="button" class="plain" :disabled="loading" @click="refresh">{{ loading ? '刷新中…' : '刷新数据' }}</button>
        </div>
        <div class="filters">
          <nav aria-label="筛选任务类别">
            <button v-for="tab in tabs" :key="tab.key" type="button" :aria-pressed="bucket === tab.key"
              @click="bucket = tab.key">{{ tab.label }}</button>
          </nav>
          <div class="search-tools">
            <input v-model="keyword" type="search" aria-label="搜索人员姓名" placeholder="搜索姓名" />
            <select v-model="state" aria-label="筛选待办状态">
              <option value="all">全部进度</option>
              <option value="pending">有未完成项</option>
              <option value="clear">无未完成项</option>
            </select>
          </div>
        </div>
        <div class="result-line">显示 {{ rows.length }} / {{ people.length }} 人 · 待完成项较多者优先</div>
        <table v-if="rows.length" class="task-table" :class="{ single: bucket !== 'all' }" aria-label="人员待办进度">
          <thead><tr>
            <th scope="col">人员</th>
            <th v-for="column in columns" :key="column.key" scope="col">{{ column.label }}</th>
            <th scope="col">待完成</th><th scope="col">明细</th>
          </tr></thead>
          <tbody><tr v-for="person in rows" :key="person.id" class="data-row-guide">
            <th scope="row" class="person">
              <span class="avatar" aria-hidden="true">{{ person.name.slice(0, 1) }}</span>
              <span><strong>{{ person.name }}</strong><small v-if="person.position">{{ person.position }}</small></span>
            </th>
            <td v-for="column in columns" :key="column.key" class="bucket-cell" :class="column.tone">
              <small class="mobile-label">{{ column.label }}</small>
              <template v-if="person.buckets[column.key]?.total">
                <div class="cell-numbers">
                  <span>{{ person.buckets[column.key].completed }} / {{ person.buckets[column.key].total }} 已完成</span>
                  <small v-if="person.buckets[column.key].exempted">免检 {{ person.buckets[column.key].exempted }}</small>
                </div>
                <div class="track" aria-hidden="true">
                  <i :style="{ width: percent(person.buckets[column.key], 'completed') }"></i>
                  <i class="exempt-bar" :style="{ width: percent(person.buckets[column.key], 'exempted') }"></i>
                </div>
              </template>
              <span v-else class="muted">无任务</span>
            </td>
            <td><span class="chip" :class="{ outstanding: person.counts.pending }">{{ person.counts.pending }} 项</span></td>
            <td class="detail-cell"><button class="plain" type="button" :aria-label="'查看' + person.name + '的待办明细'"
              @click="openPerson(person)">查看明细 <span aria-hidden="true">›</span></button></td>
          </tr></tbody>
        </table>
        <p v-else class="notice">{{ people.length ? '没有符合当前筛选的人员。' : '当前没有人员或巡检待办记录。' }}</p>
        <details class="method">
          <summary>统计口径</summary>
          <p>今日显示全部当日任务，历史只保留仍有未完成项的站点任务组，不计未来排班。覆盖周期内，现场同站同表有记录即完成，视频须在「巡检记录」中确认完成。不要求审核、站经理签名或由派工人录入，异常免检不计为完成。</p>
        </details>
      </section>
    </template>

    <Teleport to="body">
      <dialog ref="dialog" class="person-dialog" aria-labelledby="person-task-title" @close="resetDetail" @click.self="closePerson">
        <header>
          <div>
            <p class="section-kicker">个人任务明细</p>
            <h3 id="person-task-title">{{ selectedPerson?.name }} · 巡检待办</h3>
            <p>{{ tabs.find(tab => tab.key === detailBucket)?.label }} · {{ detailDay || day }}</p>
          </div>
          <button type="button" class="plain" aria-label="关闭人员明细" autofocus @click="closePerson">关闭</button>
        </header>
        <div class="detail-content" :aria-busy="detailLoading">
          <p v-if="detailLoading" class="notice" role="status">正在核对该人员的任务…</p>
          <div v-else-if="detailError" class="notice error" role="alert">
            {{ detailError }} <button type="button" class="plain" @click="loadDetail(detailPage)">重试</button>
          </div>
          <p v-else-if="!groups.length" class="notice">此分类下没有巡检任务。</p>
          <template v-else>
            <article v-for="group in groups" :key="group.key" class="station-group" :class="group.mode">
              <div class="station-head">
                <div><p>{{ group.scheduled_date }} · {{ group.mode === 'offline' ? '现场' : '视频' }}</p>
                  <h4>{{ group.station_name }}</h4></div>
                <span class="chip" :class="{ outstanding: group.pending }">{{ group.pending ? '待完成 ' + group.pending + ' 项' : '无未完成项' }}</span>
              </div>
              <p v-if="group.plan_team?.name" class="team-name">
                {{ group.plan_team.name }}<template v-if="group.plan_team.members.length"> · {{ group.plan_team.members.map(p => p.display_name).join('、') }}</template>
              </p>
              <ul>
                <li v-for="task in group.tasks" :key="task.id">
                  <div>
                    <strong>{{ task.table_name }}</strong>
                    <small v-if="task.status === 'completed'">巡检记录 · {{ task.last_inspection_date }}</small>
                    <small v-else-if="task.status === 'exception'">{{ task.exception_reason || '已登记异常免检' }}<template v-if="task.exception_reporter"> · {{ task.exception_reporter }}</template></small>
                    <small v-else-if="task.unconfirmed_count">视频记录已登记，待检查人确认</small>
                    <small v-else>覆盖周期 {{ task.coverage_from }} 至 {{ task.coverage_to }}</small>
                  </div>
                  <span :class="['chip', task.status]">{{ task.status === 'pending' && task.unconfirmed_count ? '待确认' : statusLabels[task.status] }}</span>
                </li>
              </ul>
            </article>
          </template>
        </div>
        <footer v-if="detailTotal">
          <span>第 {{ detailPage }} / {{ detailPages }} 页 · {{ detailTotal }} 个站点任务组</span>
          <div v-if="detailPages > 1" class="pager">
            <button class="plain" type="button" :disabled="detailPage <= 1 || detailLoading" @click="loadDetail(detailPage - 1)">上一页</button>
            <button class="plain" type="button" :disabled="detailPage >= detailPages || detailLoading" @click="loadDetail(detailPage + 1)">下一页</button>
          </div>
        </footer>
      </dialog>
    </Teleport>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { taskProgressGroups } from '@/utils/inspectionTaskProgress'
import { filterPeople, overviewMetrics, taskBuckets } from '@/utils/scheduleTaskOverview'

const endpoint = '/api/schedule-task-overview'
const tabs = [{ key: 'all', label: '全部任务' }, ...taskBuckets]
const statusLabels = { pending: '待完成', completed: '已完成', exception: '异常免检' }
const people = ref([]), day = ref(''), loading = ref(false), error = ref('')
const keyword = ref(''), bucket = ref('all'), state = ref('all')
const columns = computed(() => taskBuckets.filter(column => bucket.value === 'all' || column.key === bucket.value))
const rows = computed(() => filterPeople(people.value, { keyword: keyword.value, bucket: bucket.value, state: state.value }))
const cards = computed(() => {
  const m = overviewMetrics(people.value)
  return [
    { label: '总览人员', value: m.people, unit: '人', tone: 'people', note: m.pendingPeople + ' 人有待完成任务' },
    { label: '今日待完成', value: m.todayPending, unit: '项', tone: 'pending', note: '现场与视频今日派工' },
    { label: '今日已完成', value: m.todayCompleted, unit: '项', tone: 'completed', note: '另有 ' + m.todayExempted + ' 项异常免检' },
    { label: '历史未完成', value: m.historyPending, unit: '项', tone: 'history', note: '现场 ' + m.historyOffline + ' · 视频 ' + m.historyOnline },
  ]
})
const dialog = ref(null), selectedPerson = ref(null), detailBucket = ref('all')
const detailTasks = ref([]), detailDay = ref(''), detailLoading = ref(false), detailError = ref('')
const detailPage = ref(1), detailTotal = ref(0), pageSize = 12
const detailPages = computed(() => Math.max(1, Math.ceil(detailTotal.value / pageSize)))
const groups = computed(() => taskProgressGroups(detailTasks.value))
let listRequest, detailRequest

const percent = (counts, key) => (100 * counts[key] / counts.total) + '%'
const errorMessage = (err, fallback) => err.response?.data?.error || fallback

function accessRevoked(err) {
  if (![401, 403].includes(err.response?.status)) return false
  listRequest?.abort()
  detailRequest?.abort()
  people.value = []
  day.value = ''
  closePerson()
  error.value = errorMessage(err, '当前账号无权查看待办总览。')
  return true
}

async function refresh() {
  listRequest?.abort()
  const request = new AbortController()
  listRequest = request
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get(endpoint, { signal: request.signal })
    if (request.signal.aborted) return
    if (!Array.isArray(data?.people) || !data.today) throw new Error('Invalid overview response')
    people.value = data.people
    day.value = data.today
  } catch (err) {
    if (!request.signal.aborted && !accessRevoked(err)) error.value = errorMessage(err, '待办总览暂时无法读取，请稍后重试。')
  } finally {
    if (listRequest === request) loading.value = false
  }
}

async function loadDetail(page) {
  detailRequest?.abort()
  const request = new AbortController()
  detailRequest = request
  detailLoading.value = true
  detailError.value = ''
  detailTasks.value = []
  detailPage.value = page
  try {
    const { data } = await axios.get(endpoint + '/' + selectedPerson.value.id, {
      signal: request.signal, params: { bucket: detailBucket.value, page, page_size: pageSize },
    })
    if (request.signal.aborted) return
    detailTasks.value = data.tasks
    detailDay.value = data.today
    detailPage.value = data.page
    detailTotal.value = data.total_groups
  } catch (err) {
    if (!request.signal.aborted && !accessRevoked(err)) detailError.value = errorMessage(err, '明细读取失败，请稍后重试。')
  } finally {
    if (detailRequest === request) detailLoading.value = false
  }
}

function openPerson(person) {
  selectedPerson.value = person
  detailBucket.value = bucket.value
  detailDay.value = ''
  detailTotal.value = 0
  dialog.value.showModal()
  loadDetail(1)
}
function resetDetail() {
  if (dialog.value?.open) return
  detailRequest?.abort()
  selectedPerson.value = null
  detailTasks.value = []
}
function closePerson() { if (dialog.value?.open) dialog.value.close() }

onMounted(refresh)
onBeforeUnmount(() => { listRequest?.abort(); detailRequest?.abort() })
</script>

<style scoped>
.overview { --ink:#18354a; --muted:#516a7d; --line:#dce6ee; color:var(--ink); display:grid; gap:16px; padding-bottom:20px; min-width:0 }
.hero { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; padding:25px 28px; color:#fff; border-radius:18px; background:radial-gradient(ellipse at 95% 0%,#277575,transparent 65%),linear-gradient(120deg,#102d45,#17465d); border-bottom:3px solid #68b4a8 }
.hero h2 { margin:7px 0; color:inherit; font-size:clamp(25px,3vw,34px); letter-spacing:.04em }
.hero p { margin:0; color:#d6e9ef; font-size:14px; line-height:1.6 }
.hero .kicker { color:#a8dad3; font-size:12px; font-weight:700; letter-spacing:.11em }
.hero-meta { display:grid; gap:8px; justify-items:end; font-size:12px; white-space:nowrap }
.hero-meta span { border:1px solid #77aaa9; padding:4px 9px; border-radius:6px; font-weight:650 }
.metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:11px }
.metric { --accent:#326684; display:grid; gap:4px; padding:13px 16px; border:1px solid var(--line); border-top:3px solid var(--accent); border-radius:12px; background:linear-gradient(135deg,#fff 55%,#eff6f8) }
.metric.pending { --accent:#a8581c }.metric.completed { --accent:#197265 }.metric.history { --accent:#3e6494 }
.metric > span { font-weight:650; font-size:13px }
.metric strong { color:var(--accent); font-size:clamp(22px,2.7vw,33px); font-variant-numeric:tabular-nums; line-height:1.2 }
.metric small,.metric p { font-size:12px; color:var(--muted); margin:0; font-weight:500 }
.roster { background:#fff; border:1px solid var(--line); border-radius:16px; overflow:hidden; box-shadow:0 10px 28px #243a5410 }
.roster-head { padding:18px 20px 14px; display:flex; justify-content:space-between; align-items:center; gap:12px }
.roster h3,.person-dialog h3 { margin:4px 0; color:#18354a; font-size:20px }
.roster-head p,.person-dialog header p { color:#516a7d; font-size:13px; margin:0; line-height:1.6 }
.roster-head .section-kicker,.person-dialog .section-kicker { color:#217266; font-size:11px; font-weight:750; letter-spacing:.1em }
.plain { cursor:pointer; border:1px solid #c8d7e4; border-radius:8px; color:#214661; background:#fff; padding:7px 10px; font-weight:650; font-size:12px; white-space:nowrap }
.plain:hover { background:#edf5fa; border-color:#7a9eb9 }.plain:disabled { opacity:.55; cursor:default }
.filters { display:flex; justify-content:space-between; flex-wrap:wrap; gap:9px; padding:0 20px 12px }
.filters nav,.search-tools,.pager { display:flex; gap:6px; flex-wrap:wrap }
.filters nav button { cursor:pointer; border:1px solid #dce6ee; background:#f3f7fa; color:#35546c; padding:7px 10px; border-radius:8px; font-weight:650; font-size:13px }
.filters nav button[aria-pressed="true"] { color:#fff; background:#1c5971; border-color:#1c5971 }
.search-tools input,.search-tools select { min-height:34px; border:1px solid #c8d7e4; border-radius:8px; padding:5px 9px; font-size:13px; color:#18354a; background:#fff }
.search-tools input { width:135px }
.result-line { padding:8px 20px; background:#f1f6f9; color:#4c6477; font-size:12px; border-top:1px solid var(--line) }
.task-table { width:100%; border-collapse:collapse; font-size:13px; text-align:left }
.task-table thead { background:#173a52; color:#fff }
.task-table th,.task-table td { padding:10px 9px }.task-table th:first-child { padding-left:18px }.task-table td:last-child { padding-right:18px }
.task-table tbody tr:nth-child(even) { background:#f7fafc }
.task-table tbody tr + tr { border-top:1px solid #e5edf3 }
.person { white-space:nowrap }
.person > span:last-child { display:inline-grid; gap:3px; vertical-align:middle; text-align:left }
.person small,.cell-numbers small,.muted { color:#516a7d; font-weight:500 }
.avatar { display:inline-grid; place-items:center; width:28px; height:28px; margin-right:7px; border-radius:8px; color:#175f60; background:#dbefeb; vertical-align:middle }
.cell-numbers { display:flex; gap:4px 7px; flex-wrap:wrap; font-weight:650; font-variant-numeric:tabular-nums }
.track { height:5px; margin-top:6px; border-radius:8px; overflow:hidden; display:flex; background:#e0eaf0 }
.track i { background:#319188 }.video .track i { background:#487db6 }.track i.exempt-bar { background:#8d9aab }
.chip { display:inline-block; flex:none; white-space:nowrap; background:#e9f3ee; color:#245849; padding:4px 7px; border-radius:6px; font-size:12px; font-weight:700 }
.chip.outstanding,.chip.pending { background:#fff0db; color:#854816 }.chip.exception { background:#edf0f4; color:#4c5f73 }
.mobile-label { display:none }
.method { border-top:1px solid var(--line); color:#486175; padding:10px 20px; font-size:12px; line-height:1.6 }
.method summary { cursor:pointer; font-weight:650 }.method p { margin:8px 0 0 }
.notice { margin:0; padding:18px; color:#50687a; text-align:center; background:#fff; border-radius:11px }
.notice.error { background:#fff4ee; border:1px solid #f0c9b7; color:#833c22 }
.notice .plain { margin-left:7px }
.person-dialog { border:1px solid #c7dce7; border-radius:16px; padding:0; width:min(740px,calc(100vw - 28px)); max-height:min(820px,calc(100dvh - 28px)); color:#18354a; box-shadow:0 20px 66px #102d4560; overflow:hidden }
.person-dialog[open] { display:flex; flex-direction:column }.person-dialog::backdrop { background:#102c46a6 }
.person-dialog header,.person-dialog footer { display:flex; justify-content:space-between; align-items:center; gap:8px; padding:13px 18px; background:#f2f7fa; border-bottom:1px solid #dae7ee }
.person-dialog footer { border-bottom:0; border-top:1px solid #dae7ee; font-size:12px; flex-wrap:wrap }
.detail-content { overflow:auto; min-height:0; padding:14px 18px; display:grid; gap:10px }
.station-group { border:1px solid #dce6ee; border-left:3px solid #29867a; border-radius:10px; padding:10px 13px }
.station-group.online { border-left-color:#4778b4 }
.station-head { display:flex; align-items:center; justify-content:space-between; gap:8px }
.station-head p,.team-name { color:#516a7d; font-size:12px; margin:0 }
.station-head h4 { margin:4px 0 7px; font-size:17px }.team-name { margin-bottom:7px }
.station-group ul { padding:0; margin:0; list-style:none }
.station-group li { display:flex; justify-content:space-between; align-items:center; gap:8px; border-top:1px solid #e2eaf0; padding:8px 0; font-size:13px }
.station-group li small { display:block; margin-top:2px; color:#516a7d; overflow-wrap:anywhere }
@media (max-width: 850px) {
  .hero { padding:18px; align-items:flex-start; flex-direction:column; gap:10px }.hero-meta { display:flex; align-items:center; flex-wrap:wrap }
  .metrics { grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px }.metric { padding:10px 12px }
  .roster-head,.filters,.result-line,.method { padding-left:12px; padding-right:12px }
  .roster-head { align-items:flex-start }
  .task-table,.task-table tbody { display:block }.task-table thead { position:absolute; clip-path:inset(50%); width:1px; height:1px; overflow:hidden }
  .task-table tr { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; padding:10px 12px }
  .task-table th:first-child,.task-table td,.task-table td:last-child { padding:0 }
  .task-table .person { grid-column:1 / -1; text-align:left }
  .task-table .bucket-cell { background:#edf4f8; border-radius:7px; padding:6px 7px; min-width:0 }
  .single .bucket-cell { grid-column:1 / -1 }.mobile-label { display:block; color:#496678; font-weight:650; margin-bottom:2px }
  .detail-cell { justify-self:end }
  .person-dialog header,.person-dialog footer,.detail-content { padding:11px }
}
</style>
