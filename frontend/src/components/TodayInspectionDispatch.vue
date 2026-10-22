<template>
  <button type="button" class="today-dispatch-trigger" @click="open">今日已确认排班</button>
  <Teleport to="body"
    ><dialog
      ref="dialog"
      class="today-dispatch-dialog"
      aria-labelledby="saved-dispatch-title"
      @cancel.prevent="close"
      @click="backdrop"
    >
      <header>
        <div>
          <small>CONFIRMED DISPATCH / 全局共享</small>
          <h3 id="saved-dispatch-title">
            今日已确认排班 <span>{{ data?.day }}</span>
          </h3>
        </div>
        <button type="button" class="close-button" aria-label="关闭今日已确认排班" @click="close">
          ×
        </button>
      </header>
      <div class="dispatch-body">
        <p class="dispatch-explanation">
          实际保存到排班表的今日安排，包含手动派工与智能排班。计划、组员及实绩分别保留；任一检查项完成后整行锁定。
        </p>
        <p v-if="loading" class="load-note" role="status">正在核对今日排班与巡检记录…</p>
        <p v-if="error" class="load-error" role="alert">
          {{ error }} <button type="button" @click="load">重试</button>
        </p>
        <div v-if="data" class="dispatch-modes">
          <section
            v-for="mode in modes"
            :key="mode.key"
            :class="['dispatch-mode', mode.key]"
            :aria-label="mode.title"
          >
            <div class="mode-heading">
              <div>
                <small>{{ mode.key === 'offline' ? 'FIELD TEAMS' : 'VIDEO INSPECTORS' }}</small>
                <h4>{{ mode.title }}</h4>
              </div>
              <strong>{{ mode.groups.length }}{{ mode.key === 'offline' ? '组' : '人' }}</strong>
            </div>
            <article v-for="group in mode.groups" :key="group.key" class="saved-dispatch-group">
              <div class="saved-group-heading">
                <h5>{{ group.name }}</h5>
                <span
                  >{{ group.stations.length }}站 · 已查 {{ group.completed }}/{{
                    group.total
                  }}项</span
                >
              </div>
              <p class="group-people">{{ group.people.map((p) => p.display_name).join('、') }}</p>
              <div
                v-for="station in group.stations"
                :key="station.station_id"
                class="saved-station"
              >
                <strong>{{ station.region }} · {{ station.station_name }}</strong
                ><small v-if="station.locked" class="locked">已开始 · 整行锁定</small>
                <div class="saved-checks">
                  <span v-for="cell in station.cells" :key="cell.key" :class="cell.status"
                    >{{ cell.label }} ·
                    {{
                      cell.status === 'completed'
                        ? '已检查'
                        : cell.status === 'unavailable'
                          ? '不可安排'
                          : '已排班'
                    }}</span
                  >
                </div>
              </div>
            </article>
            <p v-if="!mode.groups.length" class="mode-empty">
              今天暂无已确认的{{ mode.title }}安排。
            </p>
          </section>
        </div>
      </div>
      <footer>打开时核对最新数据，窗口可见时自动更新；这里只查看，不修改派工。</footer>
    </dialog></Teleport
  >
</template>
<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { createAdaptivePolling } from '@/utils/adaptivePolling'
const dialog = ref(null),
  data = ref(null),
  loading = ref(false),
  error = ref('')
const modes = computed(() =>
  ['offline', 'online'].map((key) => ({
    key,
    title: key === 'offline' ? '现场巡检' : '视频巡检',
    groups: (data.value?.groups || []).filter((g) => g.mode === key),
  })),
)
let serial = 0,
  controller,
  disposed = false
async function load() {
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/inspection-schedule/today', {
      signal: controller.signal,
      timeout: 20000,
    })
    if (ticket === serial && !disposed) data.value = response.data
  } catch (err) {
    if (ticket === serial && !disposed && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '今日排班读取失败，请重试。'
  } finally {
    if (ticket === serial) {
      loading.value = false
      if (dialog.value?.open) polling.start()
    }
  }
}
function open() {
  data.value = null
  dialog.value.showModal()
  load()
  polling.start()
}
function close() {
  serial++
  controller?.abort()
  loading.value = false
  dialog.value?.close()
  polling.pause()
}
function backdrop(event) {
  if (event.target !== dialog.value) return
  const r = dialog.value.getBoundingClientRect()
  if (
    event.clientX < r.left ||
    event.clientX > r.right ||
    event.clientY < r.top ||
    event.clientY > r.bottom
  )
    close()
}
const polling = createAdaptivePolling({
  task: load,
  canRun: () =>
    !disposed && !!dialog.value?.open && !loading.value && !document.hidden && navigator.onLine,
})
function changed() {
  if (dialog.value?.open && !loading.value) load()
}
function visibility() {
  if (document.hidden || !navigator.onLine) polling.pause()
  else if (dialog.value?.open) polling.start({ immediate: true })
}
onMounted(() => {
  window.addEventListener('inspection-schedule-changed', changed)
  document.addEventListener('visibilitychange', visibility)
  window.addEventListener('online', visibility)
  window.addEventListener('offline', visibility)
})
onBeforeUnmount(() => {
  disposed = true
  serial++
  controller?.abort()
  polling.dispose()
  window.removeEventListener('inspection-schedule-changed', changed)
  document.removeEventListener('visibilitychange', visibility)
  window.removeEventListener('online', visibility)
  window.removeEventListener('offline', visibility)
  dialog.value?.close()
})
</script>
<style scoped>
.today-dispatch-trigger {
  border: 1px solid #9ab6c9;
  border-radius: 10px;
  min-height: 44px;
  padding: 11px 16px;
  font: inherit;
  font-size: 13px;
  line-height: 1.4;
  font-weight: 700;
  color: #244d69;
  background: #fff;
  cursor: pointer;
  white-space: nowrap;
}
.today-dispatch-dialog {
  width: min(1180px, calc(100vw - 24px));
  max-width: none;
  max-height: calc(100dvh - 32px);
  margin: auto;
  padding: 0;
  border: 1px solid #9db3c6;
  border-radius: 18px;
  overflow: hidden;
  color: #1e3c55;
  box-shadow: 0 28px 80px #102b4955;
}
.today-dispatch-dialog[open] {
  display: flex;
  flex-direction: column;
}
.today-dispatch-dialog::backdrop {
  background: #102b4970;
  backdrop-filter: blur(4px);
}
header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 22px 24px;
  background: #173e58;
  color: #fff;
  border-bottom: 3px solid #e2b34f;
}
header small {
  color: #b5d9e5;
  font-size: 10px;
  letter-spacing: 1px;
}
h3 {
  margin: 8px 0 0;
  font-size: 23px;
}
h3 span {
  font-size: 13px;
  color: #bdd8e6;
  margin-left: 8px;
}
.close-button {
  width: 36px;
  height: 36px;
  border: 1px solid #ffffff40;
  color: white;
  background: #ffffff12;
  border-radius: 10px;
  font-size: 23px;
  cursor: pointer;
}
.dispatch-body {
  padding: 20px 24px;
  overflow: auto;
  min-height: 0;
}
.dispatch-explanation,
.load-note {
  font-size: 12px;
  line-height: 1.8;
  color: #526d81;
  margin: 0 0 16px;
}
.dispatch-modes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: start;
}
.dispatch-mode {
  border: 1px solid #e2c489;
  border-top: 4px solid #c08b2d;
  background: #fff9ed;
  border-radius: 12px;
  padding: 16px;
  min-width: 0;
}
.dispatch-mode.online {
  background: #f0f6ff;
  border-color: #afcbed;
  border-top-color: #3675b6;
}
.mode-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  color: #80551a;
}
.online .mode-heading {
  color: #215e99;
}
.mode-heading small {
  font-size: 9px;
  letter-spacing: 1px;
}
h4 {
  margin: 5px 0 0;
  font-size: 19px;
}
.mode-heading > strong {
  font-size: 22px;
}
.saved-dispatch-group {
  background: white;
  border: 1px solid #d9e2e9;
  border-radius: 10px;
  padding: 14px;
  margin-top: 12px;
}
.saved-group-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
h5 {
  margin: 0;
  font-size: 15px;
}
.saved-group-heading > span {
  font-size: 11px;
  color: #496c83;
}
.group-people {
  color: #647d8f;
  font-size: 12px;
  line-height: 1.7;
  margin: 8px 0 12px;
}
.saved-station {
  border-top: 1px solid #e1e9ef;
  padding: 12px 0 0;
  margin-top: 12px;
}
.saved-station > strong {
  font-size: 13px;
}
.locked {
  display: inline-block;
  color: #226c4d;
  font-size: 10px;
  margin-left: 8px;
}
.saved-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 9px;
}
.saved-checks span {
  font-size: 10px;
  border: 1px solid #dda6a0;
  color: #923a32;
  background: #fff0ed;
  border-radius: 4px;
  padding: 4px 6px;
}
.saved-checks .completed {
  border-color: #8bbba0;
  color: #155437;
  background: #d3f1df;
}
.saved-checks .unavailable {
  background: #eee;
  border-color: #ccc;
  color: #666;
}
.mode-empty {
  padding: 28px 6px;
  color: #748596;
  font-size: 12px;
  text-align: center;
}
.load-error {
  padding: 12px;
  border-radius: 8px;
  color: #983b31;
  background: #fff0eb;
}
footer {
  flex-shrink: 0;
  padding: 14px 24px;
  border-top: 1px solid #d8e3ec;
  color: #667f92;
  font-size: 11px;
  background: #f7faff;
}
@media (max-width: 760px) {
  .dispatch-modes {
    grid-template-columns: 1fr;
  }
  header,
  .dispatch-body {
    padding: 16px;
  }
  h3 {
    font-size: 20px;
  }
  h3 span {
    display: block;
    margin: 6px 0 0;
  }
}
</style>
