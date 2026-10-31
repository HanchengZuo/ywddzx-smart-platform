<template>
  <button
    ref="trigger"
    type="button"
    class="task-banner"
    :class="{ compact }"
    :title="agendaLabel"
    @click="open"
  >
    <span class="task-icon">班</span
    ><span
      ><strong
        >今日安排 <b v-if="count" aria-live="polite">{{ count }}</b></strong
      ><small>{{ agendaLabel }}</small></span
    >
  </button>
  <Teleport to="body"
    ><dialog
      ref="dialog"
      class="tasks-dialog"
      :aria-labelledby="titleId"
      @cancel.prevent="close"
      @click="backdrop"
    >
      <header>
        <div>
          <small>MY INSPECTION TASKS</small>
          <h3 :id="titleId">
            我的巡检待办 <span>待完成 {{ total }} 项</span>
          </h3>
        </div>
        <button
          type="button"
          class="inbox-close"
          aria-label="关闭巡检待办"
          title="关闭"
          @click="close"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="m6 6 12 12M18 6 6 18"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
            />
          </svg>
        </button>
      </header>
      <div class="tasks-body">
        <p class="method">
          与巡检排班采用同一覆盖口径：同站、同检查表在对应季度、年度或月份内有巡检记录即完成，不要求审核，也不限定录入人。现场和视频未完成项跨日分别进入历史分类；整站只有全部检查表完成才算完成。
          视频任务可按站报告异常，填写原因后该站本月三张视频检查表异常免检，不计为已检查。
        </p>
        <section class="agenda-card">
          <span>{{ currentAgenda?.day || today }} · 我的档期</span
          ><strong>{{ agendaLabel }}</strong>
        </section>
        <div class="inbox-metrics" aria-label="检查表任务完成概况">
          <div class="metric-done">
            <small>今日已完成</small
            ><strong
              >{{ metrics.todayCompleted }}<em> / {{ metrics.todayTotal }} 项</em></strong
            >
          </div>
          <div>
            <small>今日待完成</small><strong>{{ metrics.todayPending }}<em> 项</em></strong>
            <small v-if="metrics.todayExempted">另有 {{ metrics.todayExempted }} 项异常免检</small>
          </div>
          <div class="metric-history">
            <small>历史现场未完成</small><strong>{{ metrics.historyOffline }}<em> 项</em></strong>
          </div>
          <div class="metric-history">
            <small>历史视频未完成</small><strong>{{ metrics.historyOnline }}<em> 项</em></strong>
          </div>
        </div>
        <section v-if="currentAgenda?.field_team" class="crew-card" aria-label="今日外勤小组成员">
          <div>
            <small>今日同行</small><strong>{{ currentAgenda.field_team.name }}</strong>
          </div>
          <div class="crew-members">
            <span v-for="person in currentAgenda.field_team.members" :key="person.id">
              {{ person.display_name
              }}<small>{{
                person.id === currentAgenda.field_team.leader_id ? '带队' : '组员'
              }}</small>
            </span>
          </div>
        </section>
        <nav class="task-tabs" aria-label="待办分类">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            :class="{ active: activeTab === tab.key }"
            :aria-pressed="activeTab === tab.key"
            @click="chooseTab(tab.key)"
          >
            {{ tab.name }}
            <b :class="{ zero: !tab.pending }" :title="`待完成 ${tab.pending} 项`">{{
              tab.pending
            }}</b>
          </button>
        </nav>
        <p v-if="loading" class="sync-note" role="status">正在核对巡检任务与最新记录…</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <div class="task-cards" :aria-busy="loading">
          <article
            v-for="group in groups"
            :key="group.key"
            class="task-group"
            :class="[group.mode, { 'station-exception': group.exempted }]"
          >
            <div class="task-heading">
              <span :class="group.mode">{{
                group.mode === 'offline' ? '现场巡检' : '视频巡检'
              }}</span
              ><strong>{{ group.station_name }}</strong
              ><small :class="{ overdue: group.scheduled_date < today }"
                >{{ group.scheduled_date }} ·
                {{
                  group.scheduled_date < today
                    ? '历史未完成'
                    : group.mode === 'offline'
                      ? '今日现场'
                      : '今日视频'
                }}</small
              >
            </div>
            <div class="station-completion" :class="{ done: !group.pending && !group.exempted }">
              <div>
                <strong>{{
                  group.exempted
                    ? '整站视频异常 · 无需再检查'
                    : !group.pending
                      ? '整站已完成'
                      : group.completed
                        ? '部分完成'
                        : '待检查'
                }}</strong
                ><span
                  >{{
                    group.exempted
                      ? `异常免检 ${group.exempted}/${group.total} 项`
                      : `已完成 ${group.completed}/${group.total} 项`
                  }}<span v-if="group.pending"> · 剩余 {{ group.pending }} 项</span></span
                >
              </div>
              <div
                class="station-progress-track"
                role="progressbar"
                :aria-label="`${group.station_name}检查表完成进度`"
                :aria-valuemin="0"
                :aria-valuemax="group.total"
                :aria-valuenow="group.completed + group.exempted"
              >
                <i :style="{ width: group.percent + '%' }"></i>
              </div>
            </div>
            <section
              v-if="group.exception"
              class="video-exception-note"
              aria-label="整站视频异常原因"
            >
              <strong>异常原因</strong>
              <p>{{ group.exception.exception_reason }}</p>
              <small
                >{{ group.exception.exception_reporter }} ·
                {{ group.exception.exception_reported_at }}
                登记。原派工及已有巡检记录均保留。</small
              >
            </section>
            <div v-else-if="group.mode === 'online' && group.pending" class="station-actions">
              <span>本站无法正常视频检查？可整站报告异常。</span>
              <button type="button" class="report-exception" @click="openException(group)">
                报告视频异常
              </button>
            </div>
            <p v-if="group.plan_team" class="original-crew">
              原派工：{{ group.plan_team.name }} ·
              {{ group.plan_team.members.map((p) => p.display_name).join('、') }}
            </p>
            <div v-for="task in group.tasks" :key="task.id" class="task-item" :class="task.status">
              <span class="task-check" aria-hidden="true">{{
                task.status === 'exception' ? '—' : task.status === 'completed' ? '✓' : '·'
              }}</span>
              <div class="task-label">
                <strong>{{ task.table_name }}</strong>
                <small v-if="task.record_count > 0"
                  >{{ task.last_inspection_date }} · 巡检记录 #{{ task.completion_inspection_id
                  }}<span v-if="task.record_count > 1"> 等 {{ task.record_count }} 条</span></small
                >
                <small v-else-if="task.status === 'exception'"
                  >整站异常免检，无需提交本表巡检记录</small
                >
                <small v-else>尚无对应周期内的巡检记录</small>
                <small class="coverage-window"
                  >覆盖周期 {{ task.coverage_from }} 至 {{ task.coverage_to }}</small
                >
              </div>
              <span class="task-state">{{
                task.status === 'exception'
                  ? '异常免检'
                  : task.status === 'completed'
                    ? '已完成'
                    : '未完成'
              }}</span>
              <button
                v-if="
                  canRegister &&
                  task.mode === 'online' &&
                  task.status === 'pending' &&
                  task.station_id &&
                  task.table_id
                "
                type="button"
                @click="register(task)"
              >
                前往登记 →
              </button>
            </div>
          </article>
        </div>
        <p v-if="!loading && !groups.length" class="empty">当前分类没有巡检待办。</p>
        <div v-if="totalGroups > pageSize" class="task-pagination" aria-label="站点任务分页">
          <span>第 {{ page }} / {{ totalPages }} 页 · 共 {{ totalGroups }} 个站点任务组</span>
          <button type="button" :disabled="loading || page === 1" @click="goPage(page - 1)">
            上一页
          </button>
          <button type="button" :disabled="loading || page >= totalPages" @click="goPage(page + 1)">
            下一页
          </button>
        </div>
        <p
          v-if="!canRegister && groups.some((group) => group.mode === 'online' && group.pending)"
          class="error"
        >
          当前账号没有巡检登记权限，请联系管理员处理。
        </p>
      </div>
    </dialog>
    <dialog
      ref="exceptionDialog"
      class="video-exception-dialog"
      :aria-labelledby="titleId + '-exception'"
      @cancel.prevent="closeException"
    >
      <form @submit.prevent="saveException">
        <header>
          <small>VIDEO INSPECTION EXCEPTION</small>
          <h3 :id="titleId + '-exception'">报告整站视频异常</h3>
          <p>{{ exceptionTarget?.station_name }} · {{ exceptionTarget?.scheduled_date }}</p>
        </header>
        <div class="exception-form-body">
          <p class="exception-warning">
            提交后，该站本月安全、计量、现场三张视频检查表均无需再完成。排班表将整站置灰，保留原派工和操作记录，不计为已检查。请核实后提交。
          </p>
          <label :for="titleId + '-reason'">异常原因 <span>必填</span></label>
          <textarea
            :id="titleId + '-reason'"
            v-model="exceptionReason"
            maxlength="500"
            rows="4"
            required
            :disabled="exceptionSaving"
            placeholder="例如：站点监控故障，无法查看视频。请说明具体情况。"
          ></textarea>
          <small class="reason-count">{{ exceptionReason.length }}/500</small>
          <p v-if="exceptionError" class="error" role="alert">{{ exceptionError }}</p>
        </div>
        <footer>
          <button type="button" :disabled="exceptionSaving" @click="closeException">取消</button
          ><button
            type="submit"
            class="exception-submit"
            :disabled="exceptionSaving || !exceptionReason.trim()"
          >
            {{ exceptionSaving ? '正在保存…' : '确认整站异常免检' }}
          </button>
        </footer>
      </form>
    </dialog></Teleport
  >
</template>
<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { useRouter } from 'vue-router'
import { createAdaptivePolling } from '@/utils/adaptivePolling'
import { taskProgressGroups, inboxMetrics } from '@/utils/inspectionTaskProgress'
const props = defineProps({
  compact: { type: Boolean, default: false },
  count: { type: Number, required: true },
  agenda: { type: Object, default: null },
})
const emit = defineEmits(['count'])
const titleId = 'schedule-inbox-' + useId()
const router = useRouter(),
  trigger = ref(null),
  dialog = ref(null),
  tasks = ref([]),
  total = ref(props.count),
  today = ref(''),
  loading = ref(false),
  error = ref('')
const loadedAgenda = ref(null),
  activeTab = ref('all')
const summary = ref(null),
  page = ref(1),
  pageSize = 24,
  totalGroups = ref(0)
const totalPages = computed(() => Math.max(1, Math.ceil(totalGroups.value / pageSize)))
const metrics = computed(() => inboxMetrics(summary.value))
const currentAgenda = computed(() => loadedAgenda.value || props.agenda)
const agendaLabel = computed(() => {
  const agenda = currentAgenda.value
  if (agenda?.assignment) return agenda.assignment.group_name
  return agenda?.available === false
    ? '没空 · ' + (agenda.reason || '未填原因')
    : agenda?.available === true
      ? '今日有空 · 等待安排'
      : '档期未确认'
})
const tabs = computed(() =>
  [
    { key: 'all', name: '全部' },
    { key: 'today_offline', name: '今日现场' },
    { key: 'today_online', name: '今日视频' },
    { key: 'history_offline', name: '历史现场未完成' },
    { key: 'history_online', name: '历史视频未完成' },
  ].map((tab) => ({
    ...tab,
    pending: tab.key === 'all' ? total.value : summary.value?.buckets?.[tab.key]?.pending || 0,
  })),
)
const groups = computed(() => taskProgressGroups(tasks.value))
const exceptionDialog = ref(null),
  exceptionTarget = ref(null),
  exceptionReason = ref(''),
  exceptionSaving = ref(false),
  exceptionError = ref('')
function openException(group) {
  const task = group.tasks.find((item) => item.status === 'pending')
  if (!task || group.mode !== 'online') return
  exceptionTarget.value = task
  exceptionReason.value = ''
  exceptionError.value = ''
  exceptionDialog.value.showModal()
}
function closeException() {
  if (!exceptionSaving.value) exceptionDialog.value?.close()
}
async function saveException() {
  if (exceptionSaving.value || !exceptionTarget.value || !exceptionReason.value.trim()) return
  exceptionSaving.value = true
  exceptionError.value = ''
  try {
    await axios.post(
      `/api/my-schedule-tasks/${exceptionTarget.value.id}/video-exception`,
      { reason: exceptionReason.value.trim() },
      { timeout: 15000 },
    )
    exceptionDialog.value?.close()
    serial++
    controller?.abort()
    loading.value = false
    await load()
    window.dispatchEvent(new Event('inspection-schedule-changed'))
    window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
  } catch (err) {
    if (!disposed)
      exceptionError.value = err.response?.data?.error || '保存结果未确认，请刷新核对后重试。'
  } finally {
    exceptionSaving.value = false
  }
}
let permissions = {}
try {
  permissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch {
  /* Server also checks registration access. */
}
const canRegister =
  (localStorage.getItem('user_role') || localStorage.getItem('role')) === 'root' ||
  Boolean(permissions.submit_inspections)
let disposed = false,
  controller,
  serial = 0
async function load() {
  if (disposed || loading.value || !dialog.value?.open) return
  const ticket = ++serial
  controller = new AbortController()
  loading.value = true
  try {
    const { data } = await axios.get('/api/my-schedule-tasks', {
      params: { bucket: activeTab.value, page: page.value, page_size: pageSize },
      signal: controller.signal,
      timeout: 15000,
    })
    if (ticket !== serial || disposed) return
    tasks.value = data.tasks
    total.value = data.count
    today.value = data.today
    loadedAgenda.value = data.agenda || null
    summary.value = data
    page.value = data.page || 1
    totalGroups.value = data.total_groups || 0
    error.value = ''
    emit('count', data.count)
  } catch (err) {
    if (ticket === serial && !disposed && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '任务暂时无法读取，请重试。'
  } finally {
    if (ticket === serial) loading.value = false
  }
}
const polling = createAdaptivePolling({
  task: load,
  canRun: () =>
    !disposed &&
    !document.hidden &&
    navigator.onLine &&
    dialog.value?.open &&
    !exceptionDialog.value?.open,
})
function changeView(bucket, number) {
  serial++
  controller?.abort()
  loading.value = false
  activeTab.value = bucket
  page.value = number
  tasks.value = []
  load()
}
function chooseTab(bucket) {
  if (bucket !== activeTab.value) changeView(bucket, 1)
}
function goPage(number) {
  if (number >= 1 && number <= totalPages.value) changeView(activeTab.value, number)
}
function scheduleChanged() {
  if (dialog.value?.open) load()
}
function open() {
  if (dialog.value?.open) return
  dialog.value.showModal()
  load()
  polling.start()
}
function openFromNotification() {
  // Header contains desktop and mobile instances; only the visible one may open.
  if (trigger.value?.getClientRects().length) open()
}
function close() {
  serial++
  controller?.abort()
  loading.value = false
  polling.pause()
  dialog.value?.close()
  exceptionDialog.value?.close()
  loadedAgenda.value = null
}
function backdrop(event) {
  if (event.target === dialog.value) {
    const r = dialog.value.getBoundingClientRect()
    if (
      event.clientX < r.left ||
      event.clientX > r.right ||
      event.clientY < r.top ||
      event.clientY > r.bottom
    )
      close()
  }
}
function register(task) {
  close()
  router.push({
    path: '/inspection/register',
    query: {
      schedule_task: task.id,
      station_id: task.station_id,
      inspection_table_id: task.table_id,
    },
  })
}
function visibility() {
  if (document.hidden || !navigator.onLine) polling.pause()
  else if (dialog.value?.open) polling.start({ immediate: true })
}
onMounted(() => {
  document.addEventListener('visibilitychange', visibility)
  window.addEventListener('online', visibility)
  window.addEventListener('offline', visibility)
  window.addEventListener('inspection-schedule-changed', scheduleChanged)
  window.addEventListener('inspection-sign-pending-refresh', scheduleChanged)
  window.addEventListener('inspection-tasks-open', openFromNotification)
})
onBeforeUnmount(() => {
  disposed = true
  serial++
  controller?.abort()
  polling.dispose()
  dialog.value?.close()
  exceptionDialog.value?.close()
  document.removeEventListener('visibilitychange', visibility)
  window.removeEventListener('online', visibility)
  window.removeEventListener('offline', visibility)
  window.removeEventListener('inspection-schedule-changed', scheduleChanged)
  window.removeEventListener('inspection-sign-pending-refresh', scheduleChanged)
  window.removeEventListener('inspection-tasks-open', openFromNotification)
})
</script>
<style scoped>
.video-exception-dialog {
  width: min(560px, calc(100vw - 24px));
  max-height: 90dvh;
  padding: 0;
  border: 1px solid #aab7c4;
  border-radius: 16px;
  color: #273e50;
  box-shadow: 0 24px 80px #10283e45;
}
.video-exception-dialog::backdrop {
  background: #152b487a;
}
.video-exception-dialog header {
  display: block;
  padding: 23px 24px 18px;
  background: #263e53;
  color: white;
}
.video-exception-dialog header small {
  display: block;
  color: #bdd0df;
  font-size: 10px;
  letter-spacing: 1px;
}
.video-exception-dialog h3 {
  margin: 8px 0;
  font-size: 21px;
}
.video-exception-dialog header p {
  margin: 0;
  font-size: 13px;
  color: #d7e2eb;
  overflow-wrap: anywhere;
}
.exception-form-body {
  padding: 20px 24px;
}
.exception-warning {
  margin: 0 0 20px;
  padding: 12px;
  background: #fff7e9;
  border-left: 3px solid #d39b44;
  font-size: 13px;
  line-height: 1.8;
  color: #78582f;
}
.exception-form-body label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 9px;
}
.exception-form-body label span {
  color: #a33935;
  font-size: 11px;
  margin-left: 6px;
}
.exception-form-body textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  min-height: 105px;
  max-height: 220px;
  border: 1px solid #aebfd0;
  border-radius: 8px;
  padding: 11px;
  font: inherit;
  font-size: 14px;
  line-height: 1.7;
}
.reason-count {
  display: block;
  text-align: right;
  color: #718293;
  margin-top: 4px;
}
.video-exception-dialog footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 15px 24px;
  background: #f2f5f8;
  border-top: 1px solid #d4dee6;
}
.video-exception-dialog button,
.station-actions button {
  font: inherit;
  font-size: 13px;
  padding: 9px 13px;
  border: 1px solid #aebdcb;
  border-radius: 7px;
  background: white;
  color: #344c62;
  cursor: pointer;
}
.video-exception-dialog .exception-submit {
  color: white;
  border-color: #3a526a;
  background: #3a526a;
}
.video-exception-dialog button:disabled {
  opacity: 0.55;
  cursor: wait;
}
.station-actions {
  padding: 10px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  background: #f5f7fa;
  border-top: 1px solid #d7e1e9;
  font-size: 12px;
  color: #60758a;
}
.video-exception-note {
  padding: 13px 15px;
  color: #45576a;
  background: #e9edf2;
  border-top: 1px solid #c1cbd6;
  font-size: 13px;
}
.video-exception-note p {
  margin: 7px 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.7;
}
.video-exception-note small {
  color: #64778a;
  font-size: 11px;
  line-height: 1.7;
}
.station-exception .station-completion strong {
  color: #5c6a79;
}
.station-exception .station-progress-track i {
  background: #8c9baa;
}
.task-item.exception .task-check,
.task-item.exception .task-state {
  color: #526171;
  border-color: #b9c3ce;
  background: #e8edf2;
}
.tasks-dialog > header {
  background: #173e58;
  color: #fff;
  border-bottom: 3px solid #dfb24b;
}
.tasks-dialog > header small,
.tasks-dialog h3 span {
  color: #b9dbe7;
}
.inbox-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}
.inbox-metrics > div {
  padding: 13px;
  border: 1px solid #c5d8e9;
  border-top: 3px solid #387baa;
  border-radius: 9px;
  background: #f1f6fc;
}
.inbox-metrics small {
  display: block;
  color: #476580;
  font-size: 12px;
}
.inbox-metrics strong {
  display: block;
  margin-top: 8px;
  color: #23527a;
  font-size: 23px;
}
.inbox-metrics em {
  font-size: 11px;
  font-style: normal;
  font-weight: 400;
}
.inbox-metrics .metric-done {
  border-color: #a2c9b7;
  border-top-color: #2e8664;
  background: #eff9f3;
}
.metric-done strong {
  color: #24694b;
}
.inbox-metrics .metric-history {
  border-top-color: #c1813b;
  background: #fff8ed;
}
.task-tabs b {
  display: inline-flex;
  min-width: 17px;
  height: 17px;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  border-radius: 9px;
  color: #a23435;
  background: #ffe6e3;
  font-size: 10px;
}
.task-tabs b.zero {
  color: #527386;
  background: #e2ebf1;
}
.station-completion {
  padding: 12px 14px;
  background: #f8fafc;
  border-top: 1px solid #d9e4ec;
}
.station-completion > div:first-child {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: #6c7c89;
  margin-bottom: 8px;
}
.station-completion strong {
  color: #906123;
}
.station-completion.done strong {
  color: #206d4c;
}
.station-progress-track {
  height: 6px;
  border-radius: 4px;
  background: #dee9ef;
  overflow: hidden;
}
.station-progress-track i {
  display: block;
  height: 100%;
  background: #339077;
  border-radius: inherit;
}
.original-crew {
  margin: 0;
  padding: 9px 14px;
  border-top: 1px solid #e1e9ef;
  font-size: 11px;
  line-height: 1.7;
  color: #826235;
  background: #fffcf6;
}
.task-item .task-check {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border: 1px solid #c7a277;
  border-radius: 50%;
  color: #ad7332;
  background: #fff8e9;
  flex-shrink: 0;
  font-size: 17px;
}
.task-item.completed .task-check {
  background: #e4f5ec;
  color: #21704e;
  border-color: #7db89b;
  font-size: 12px;
}
.task-label {
  flex: 1;
  min-width: 0;
}
.task-label strong {
  font-size: 12px;
  color: #284b65;
  line-height: 1.7;
}
.task-label small {
  display: block;
  font-size: 10px;
  color: #6b7e8e;
  line-height: 1.7;
}
.task-item.completed .task-label > small:first-of-type {
  color: #247452;
}
.task-item .task-state {
  padding: 4px 7px;
  color: #995b27;
  border: 1px solid #e3c7a1;
  border-radius: 5px;
  background: #fff4e2;
  white-space: nowrap;
  font-size: 10px;
}
.task-item.completed .task-state {
  color: #1d6f4b;
  border-color: #9ac7ae;
  background: #e9f7ee;
}
.task-pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}
.task-pagination span {
  margin-right: auto;
  font-size: 11px;
  color: #637d90;
}
.sync-note {
  font-size: 12px;
  color: #2a6d8e;
  padding: 8px 12px;
  background: #edf6fb;
  border-radius: 6px;
}
@media (max-width: 760px) {
  .inbox-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .task-group .task-item {
    display: grid;
    grid-template-columns: 22px minmax(0, 1fr) auto;
    gap: 8px;
  }
  .task-item button {
    grid-column: 2 / -1;
    justify-self: end;
  }
  .task-pagination {
    flex-wrap: wrap;
  }
}
.tasks-dialog .inbox-close {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  padding: 0;
  border-radius: 50%;
  background: #edf3f9;
  color: #476581;
  flex-shrink: 0;
  transition:
    background 0.15s,
    color 0.15s;
}
.inbox-close:hover {
  background: #dbe8f5;
  color: #214e78;
}
.crew-card {
  padding: 14px 16px;
  margin-bottom: 16px;
  border: 1px solid #ead5ac;
  border-radius: 12px;
  background: linear-gradient(115deg, #fff6e5, #fffcf6);
}
.crew-card > div:first-child {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.crew-card > div > small {
  font-size: 11px;
  color: #987b49;
}
.crew-card strong {
  font-size: 14px;
  color: #805d26;
}
.crew-members {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 12px;
}
.crew-members > span {
  background: white;
  border: 1px solid #eddfc5;
  border-radius: 7px;
  padding: 6px 9px;
  font-size: 12px;
}
.crew-members small {
  margin-left: 5px;
  color: #a28b65;
  font-size: 10px;
}
.task-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.task-group.online {
  grid-column: 1 / -1;
}
.task-group:only-child {
  grid-column: 1 / -1;
}
.task-group.offline .task-heading {
  background: #fff6e7;
}
.task-group.offline .task-heading small {
  flex-basis: 100%;
  margin-left: 0;
}
.task-group.offline .task-item {
  padding: 8px 12px;
}
.task-banner.compact {
  padding: 6px 8px;
  gap: 0;
  min-height: 34px;
  flex-shrink: 0;
}
.task-banner.compact .task-icon,
.task-banner.compact small {
  display: none;
}
.task-banner.compact strong {
  font-size: 11px;
  white-space: nowrap;
}
.compact strong b {
  margin-left: 3px;
  padding: 2px 4px;
}
.task-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 240px;
  padding: 9px 12px;
  border: 1px solid #c7dbef;
  border-radius: 12px;
  background: linear-gradient(110deg, #edf5ff, #fbfdff);
  color: #30577f;
  text-align: left;
  cursor: pointer;
  font: inherit;
}
.agenda-card {
  padding: 16px;
  border: 1px solid #ccdeeb;
  border-radius: 12px;
  background: #f1f7fc;
  margin-bottom: 16px;
}
.agenda-card > span {
  display: block;
  font-size: 11px;
  color: #65809a;
}
.agenda-card > strong {
  display: block;
  margin: 8px 0 14px;
  color: #234e73;
}
.agenda-card > div {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.agenda-card b {
  padding: 6px 8px;
  background: #dbeaff;
  color: #2d6597;
  font-size: 11px;
  border-radius: 6px;
}
.agenda-card .field {
  background: #ffedca;
  color: #9a651d;
}
.agenda-card .late {
  background: #ffe4df;
  color: #ae5338;
}
.task-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-bottom: 16px;
}
.task-tabs .active {
  background: #235f96;
  color: white;
  border-color: #235f96;
}
.task-banner small {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-icon {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  background: #2866b5;
  color: #fff;
  border-radius: 10px;
}
.task-banner strong {
  font-size: 13px;
}
.task-banner b {
  margin-left: 8px;
  padding: 2px 6px;
  background: #c64f40;
  color: #fff;
  border-radius: 5px;
}
.task-banner small {
  display: block;
  margin-top: 5px;
  font-size: 11px;
  color: #8295ab;
}
.task-banner em {
  margin-left: auto;
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}
.tasks-dialog {
  width: min(960px, calc(100vw - 24px));
  max-height: calc(100dvh - 32px);
  padding: 0;
  border: 1px solid #d6e1ed;
  border-radius: 20px;
  margin: auto;
  color: #203a54;
  overflow: hidden;
  box-shadow: 0 24px 80px #18324c44;
}
.tasks-dialog[open] {
  display: flex;
  flex-direction: column;
}
.tasks-dialog::backdrop {
  background: #182c4b66;
  backdrop-filter: blur(4px);
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 24px;
  border-bottom: 1px solid #dfe8f2;
  flex-shrink: 0;
}
header small {
  font-size: 10px;
  letter-spacing: 1px;
  color: #8197ae;
}
h3 {
  margin: 8px 0 0;
  font-size: 22px;
}
h3 span {
  font-size: 14px;
  color: #8a9db3;
  margin-left: 8px;
}
.tasks-body {
  overflow: auto;
  min-height: 0;
  padding: 20px 24px;
}
.method {
  font-size: 12px;
  line-height: 1.8;
  color: #8295ab;
  margin: 0 0 14px;
}
.task-group {
  border: 1px solid #dce7f2;
  border-radius: 12px;
  min-width: 0;
  overflow-wrap: anywhere;
}
.task-heading {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  padding: 14px;
  background: #f7faff;
  border-radius: 12px 12px 0 0;
}
.task-heading > span {
  font-size: 11px;
  padding: 4px 7px;
  border-radius: 5px;
  background: #eaf2ff;
  color: #2866b5;
}
.task-heading > .offline {
  background: #e6f5ef;
  color: #357d62;
}
.task-heading strong {
  font-size: 14px;
}
.task-heading small {
  font-size: 10px;
  margin-left: auto;
  color: #8094ad;
}
.task-heading .overdue {
  color: #b65d40;
}
.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-top: 1px solid #e5edf5;
  font-size: 12px;
}
.task-item span {
  line-height: 1.7;
}
.task-item button {
  white-space: nowrap;
  color: #2866b5;
}
.empty {
  text-align: center;
  padding: 30px;
  font-size: 13px;
  color: #8295ab;
}
.error {
  padding: 12px;
  background: #fff1ed;
  border-radius: 9px;
  color: #b45a43;
  font-size: 12px;
}
button {
  border: 1px solid #d5e1ee;
  padding: 8px 12px;
  border-radius: 8px;
  color: #54718d;
  background: #fff;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button:focus-visible {
  outline: 2px solid #70a1d6;
  outline-offset: 2px;
}
@media (max-width: 600px) {
  header,
  .tasks-body {
    padding: 16px;
  }
  .task-banner {
    padding: 12px;
  }
  .task-banner small {
    max-width: 190px;
    line-height: 1.6;
  }
  .task-banner em {
    font-size: 10px;
  }
  .tasks-dialog {
    width: calc(100vw - 16px);
    max-height: calc(100dvh - 16px);
    border-radius: 15px;
  }
  .task-cards {
    grid-template-columns: minmax(0, 1fr);
  }
  .task-heading small {
    margin-left: 0;
    flex-basis: 100%;
  }
  .task-item {
    align-items: flex-start;
  }
}
@media (min-width: 769px) and (max-width: 1500px) {
  .task-banner {
    gap: 7px;
    padding: 8px;
  }
  .task-banner small {
    display: none;
  }
  .task-icon {
    width: 28px;
    height: 28px;
  }
}
</style>
