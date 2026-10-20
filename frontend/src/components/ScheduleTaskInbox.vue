<template>
  <button type="button" class="task-banner" :class="{ compact }" :title="agendaLabel" @click="open">
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
            我的巡检待办 <span>{{ total }}</span>
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
          现场为当日行程，次日自动归档，不要求生成记录销项；视频任务需同站同表有巡检记录才完成，不要求审核，历史未完成项持续保留。实际执行人与计划分别留存。
        </p>
        <section class="agenda-card">
          <span>{{ currentAgenda?.day || today }} · 我的档期</span
          ><strong>{{ agendaLabel }}</strong>
          <div>
            <b class="field">现场 {{ currentAgenda?.offline?.count || 0 }} 项</b
            ><b>视频 {{ currentAgenda?.online?.count || 0 }} 项</b
            ><b class="late">其中历史未完成 {{ currentAgenda?.online?.overdue || 0 }} 项</b>
          </div>
        </section>
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
            @click="activeTab = tab.key"
          >
            {{ tab.name }}
          </button>
        </nav>
        <p v-if="loading && !tasks.length" class="empty" role="status">正在核对巡检任务…</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <div class="task-cards">
          <article v-for="group in groups" :key="group.key" class="task-group" :class="group.mode">
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
                      ? '今日行程 · 次日归档'
                      : '今天安排'
                }}</small
              >
            </div>
            <div v-for="task in group.tasks" :key="task.id" class="task-item">
              <span>{{ task.table_name }}</span
              ><button
                v-if="canRegister && task.mode === 'online' && task.station_id && task.table_id"
                type="button"
                @click="register(task)"
              >
                前往登记 →
              </button>
            </div>
          </article>
        </div>
        <p v-if="!loading && !groups.length" class="empty">当前分类没有巡检待办。</p>
        <p v-if="total > tasks.length" class="method">
          当前显示最早的{{ tasks.length }}项，完成后继续展示剩余任务。
        </p>
        <p v-if="!canRegister && groups.some((group) => group.mode === 'online')" class="error">
          当前账号没有巡检登记权限，请联系管理员处理。
        </p>
      </div>
    </dialog></Teleport
  >
</template>
<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { useRouter } from 'vue-router'
import { createAdaptivePolling } from '@/utils/adaptivePolling'
import { taskGroups } from '@/utils/staffScheduling'
const props = defineProps({
  compact: { type: Boolean, default: false },
  count: { type: Number, required: true },
  agenda: { type: Object, default: null },
})
const emit = defineEmits(['count'])
const titleId = 'schedule-inbox-' + useId()
const router = useRouter(),
  dialog = ref(null),
  tasks = ref([]),
  total = ref(props.count),
  today = ref(''),
  loading = ref(false),
  error = ref('')
const loadedAgenda = ref(null),
  activeTab = ref('all')
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
const tabs = [
  { key: 'all', name: '全部' },
  { key: 'offline', name: '今日现场' },
  { key: 'online', name: '今日视频' },
  { key: 'overdue', name: '历史视频未完成' },
]
const groups = computed(() =>
  taskGroups(
    tasks.value.filter(
      (task) =>
        activeTab.value === 'all' ||
        (activeTab.value === 'overdue'
          ? task.mode === 'online' && task.scheduled_date < today.value
          : task.mode === activeTab.value && task.scheduled_date === today.value),
    ),
  ),
)
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
      signal: controller.signal,
      timeout: 15000,
    })
    if (ticket !== serial || disposed) return
    tasks.value = data.tasks
    total.value = data.count
    today.value = data.today
    loadedAgenda.value = data.agenda || null
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
  canRun: () => !disposed && !document.hidden && navigator.onLine && dialog.value?.open,
})
function open() {
  dialog.value.showModal()
  load()
  polling.start()
}
function close() {
  serial++
  controller?.abort()
  loading.value = false
  polling.pause()
  dialog.value?.close()
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
})
onBeforeUnmount(() => {
  disposed = true
  serial++
  controller?.abort()
  polling.dispose()
  dialog.value?.close()
  document.removeEventListener('visibilitychange', visibility)
  window.removeEventListener('online', visibility)
  window.removeEventListener('offline', visibility)
})
</script>
<style scoped>
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
