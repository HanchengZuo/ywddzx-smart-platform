<template>
  <button type="button" class="task-banner" @click="open">
    <span class="task-icon">班</span
    ><span
      ><strong
        >巡检待办 <b>{{ count }}</b></strong
      ><small>今天的安排与逾期未完成任务；有巡检记录后自动销项</small></span
    ><em>查看任务 →</em>
  </button>
  <Teleport to="body"
    ><dialog
      ref="dialog"
      class="tasks-dialog"
      aria-labelledby="schedule-inbox-title"
      @cancel.prevent="close"
      @click="backdrop"
    >
      <header>
        <div>
          <small>MY INSPECTION TASKS</small>
          <h3 id="schedule-inbox-title">
            我的巡检待办 <span>{{ total }}</span>
          </h3>
        </div>
        <button type="button" aria-label="关闭巡检待办" @click="close">×</button>
      </header>
      <div class="tasks-body">
        <p class="method">
        按计划日期、站点分组。同站同表产生本周期的巡检记录即自动完成，不要求审核，也不限制录入人；提前或跨周期补做也可完成。实际执行人仍以记录为准。未完成不会因日期过期而消失，重新派工或取消会留痕。
        </p>
        <p v-if="loading && !tasks.length" class="empty" role="status">正在核对巡检任务…</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <article v-for="group in groups" :key="group.key" class="task-group">
          <div class="task-heading">
            <span :class="group.mode">{{ group.mode === 'offline' ? '现场巡检' : '视频巡检' }}</span
            ><strong>{{ group.station_name }}</strong
            ><small :class="{ overdue: group.scheduled_date < today }"
              >{{ group.scheduled_date }} ·
              {{ group.scheduled_date < today ? '逾期未完成' : '今天安排' }}</small
            >
          </div>
          <div v-for="task in group.tasks" :key="task.id" class="task-item">
            <span>{{ task.table_name }}</span
            ><button
              v-if="canRegister && task.station_id && task.table_id"
              type="button"
              @click="register(task)"
            >
              前往登记 →
            </button>
          </div>
        </article>
        <p v-if="!loading && !total" class="empty">所有巡检待办已完成。</p>
        <p v-if="total > tasks.length" class="method">
          当前显示最早的{{ tasks.length }}项，完成后继续展示剩余任务。
        </p>
        <p v-if="!canRegister" class="error">当前账号没有巡检登记权限，请联系管理员处理。</p>
      </div>
      <footer>
        <span>{{ synced ? '最近核对 ' + synced : '可见时自动核对完成情况' }}</span
        ><button type="button" :disabled="loading" @click="load">核对完成情况</button
        ><button type="button" @click="close">关闭</button>
      </footer>
    </dialog></Teleport
  >
</template>
<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createAdaptivePolling } from '@/utils/adaptivePolling'
import { taskGroups } from '@/utils/staffScheduling'
const props = defineProps({ count: { type: Number, required: true } })
const emit = defineEmits(['count'])
const router = useRouter(),
  dialog = ref(null),
  tasks = ref([]),
  total = ref(props.count),
  today = ref(''),
  loading = ref(false),
  error = ref(''),
  synced = ref('')
const groups = computed(() => taskGroups(tasks.value))
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
    error.value = ''
    synced.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
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
.task-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  margin-bottom: 14px;
  padding: 12px 16px;
  border: 1px solid #c7dbef;
  border-radius: 12px;
  background: linear-gradient(110deg, #edf5ff, #fbfdff);
  color: #30577f;
  text-align: left;
  cursor: pointer;
  font: inherit;
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
  background: #fff0e4;
  color: #b27125;
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
  width: min(800px, calc(100vw - 24px));
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
  margin-bottom: 14px;
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
footer {
  padding: 16px 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-top: 1px solid #dfe8f2;
  flex-shrink: 0;
}
footer span {
  flex: 1;
  font-size: 11px;
  color: #8b9db0;
}
@media (max-width: 600px) {
  header,
  .tasks-body,
  footer {
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
  footer {
    flex-wrap: wrap;
  }
  footer span {
    flex-basis: 100%;
  }
  .task-heading small {
    margin-left: 0;
    flex-basis: 100%;
  }
  .task-item {
    align-items: flex-start;
  }
}
</style>
