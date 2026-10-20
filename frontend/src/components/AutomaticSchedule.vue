<template>
  <button v-if="allowed" type="button" class="auto-trigger" @click="open">今日一键排班</button>
  <Teleport to="body"
    ><dialog
      ref="dialog"
      class="auto-dialog"
      aria-labelledby="auto-schedule-title"
      @cancel.prevent="close"
      @click="backdrop"
    >
      <header>
        <div>
          <small>平衡派工 / DAILY DISPATCH</small>
          <h3 id="auto-schedule-title">今日一键排班</h3>
        </div>
        <button type="button" :disabled="saving" aria-label="关闭自动排班" @click="close">×</button>
      </header>
      <div class="auto-body">
        <p class="method">
          {{ day }} ·
          仅选择档期明确有空、今天没有站点安排或实绩的人员。现场按已保存外勤组整行派站，视频每格一人，不覆盖已有计划。
        </p>
        <p class="method">
          现场从{{
            SCHEDULE_ORIGIN
          }}出发，按坐标聚类并优化往返距离；只作顺路参考，不含实时路况、道路和过江通道。缺失坐标的站点不自动派现场任务。视频按本季度工作量优先安排较少者。
        </p>
        <div class="quota-controls">
          <label
            >现场每组站点数<input
              v-model.number="offlineCount"
              type="number"
              min="1"
              max="10"
              :disabled="loading || saving"
              @input="stale = true"
          /></label>
          <label
            >视频每人站点数<input
              v-model.number="onlineCount"
              type="number"
              min="1"
              max="10"
              :disabled="loading || saving"
              @input="stale = true"
          /></label>
          <small>调整数量后点击“重新预览”</small>
        </div>
        <p v-if="loading" role="status" class="empty">正在核对档期、巡检记录和本季度任务量…</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <template v-if="preview">
          <div class="preview-summary">
            <span
              ><b>{{ preview.available_count }}</b> 可派工人员</span
            ><span
              ><b>{{ preview.groups.length }}</b> 站点任务组</span
            ><span
              ><b>{{ preview.cell_count }}</b> 排班单元格</span
            ><small>{{ preview.quarter }}平衡口径</small>
          </div>
          <div v-if="preview.groups.length" class="proposal-list">
            <article v-for="group in preview.groups" :key="group.mode + ':' + group.station_id">
              <div class="proposal-person">
                <strong>{{ group.group_name || group.person.display_name }}</strong
                ><span :class="group.mode">{{
                  group.mode === 'offline' ? '现场巡检' : '视频巡检'
                }}</span>
              </div>
              <p v-if="group.team_members">
                {{ group.team_members.map((p) => p.display_name).join('、') }}
              </p>
              <b>{{ group.region }} · {{ group.station_name }}</b>
              <p>{{ group.cells.map((c) => c.label).join('、') }}</p>
              <p v-if="group.mode === 'offline'">
                路线第 {{ group.route_order }} 站 · 本组往返直线距离约
                {{ group.route_km }} km<br />{{ group.address }}
              </p>
              <small
                >本季度现场 {{ group.before.offline }} → {{ group.after.offline }} 组 · 视频
                {{ group.before.online }} → {{ group.after.online }} 组</small
              >
            </article>
          </div>
          <p v-else class="empty">
            没有可以自动安排的组合。请先设置今日人员有空，或核对当前季度 / 月份是否还有待排班项目。
          </p>
          <p v-for="warning in preview.warnings" :key="warning" class="method">{{ warning }}</p>
          <details v-if="preview.excluded.length" class="excluded">
            <summary>未参与自动派工的人员（{{ preview.excluded.length }}）</summary>
            <p v-for="person in preview.excluded" :key="person.name">
              {{ person.name }} · {{ person.reason }}
            </p>
          </details>
        </template>
      </div>
      <footer>
        <span>确认后同步个人待办，并转到本季度 / 本月排班。</span
        ><button type="button" :disabled="loading || saving" @click="createPreview">重新预览</button
        ><button
          type="button"
          class="primary"
          :disabled="loading || saving || !preview?.groups.length || stale"
          @click="confirm"
        >
          {{ saving ? '正在保存…' : '确认派工' }}
        </button>
      </footer>
    </dialog></Teleport
  >
</template>
<script setup>
import axios from 'axios'
import { onBeforeUnmount, ref } from 'vue'
import { shanghaiToday } from '@/utils/staffScheduling'
const SCHEDULE_ORIGIN = '上海市浦东新区世纪大道1200号'
const emit = defineEmits(['scheduled'])
let permissions = {}
try {
  permissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch {
  /* API checks effective permissions. */
}
const allowed =
  (localStorage.getItem('user_role') || localStorage.getItem('role')) === 'root' ||
  permissions.edit_inspection_schedule
const dialog = ref(null),
  preview = ref(null),
  loading = ref(false),
  saving = ref(false),
  error = ref(''),
  stale = ref(false),
  day = ref(shanghaiToday())
const offlineCount = ref(2),
  onlineCount = ref(3)
let controller,
  disposed = false,
  serial = 0
function open() {
  day.value = shanghaiToday()
  preview.value = null
  dialog.value.showModal()
  createPreview()
}
function close() {
  if (saving.value) return
  serial++
  controller?.abort()
  loading.value = false
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
async function createPreview() {
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  stale.value = true
  try {
    const { data } = await axios.post(
      '/api/inspection-schedule/auto',
      {
        action: 'preview',
        day: day.value,
        offline_count: offlineCount.value,
        online_count: onlineCount.value,
      },
      { signal: controller.signal, timeout: 60000 },
    )
    if (ticket === serial && !disposed) {
      preview.value = data
      stale.value = false
    }
  } catch (err) {
    if (ticket === serial && !disposed && err.code !== 'ERR_CANCELED')
      error.value = err.response?.data?.error || '自动排班预览失败，请重试。'
  } finally {
    if (ticket === serial) loading.value = false
  }
}
async function confirm() {
  if (saving.value || loading.value || stale.value || !preview.value?.groups.length) return
  saving.value = true
  error.value = ''
  try {
    const { data } = await axios.post(
      '/api/inspection-schedule/auto',
      {
        action: 'confirm',
        day: day.value,
        token: preview.value.token,
        offline_count: offlineCount.value,
        online_count: onlineCount.value,
      },
      { timeout: 120000 },
    )
    if (!disposed) {
      dialog.value.close()
      emit('scheduled', data)
      window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
    }
  } catch (err) {
    if (!disposed) {
      error.value = err.response?.data?.error || '未确认派工结果，请重新预览核对，避免重复派工。'
      stale.value = true
    }
  } finally {
    saving.value = false
  }
}
onBeforeUnmount(() => {
  disposed = true
  serial++
  controller?.abort()
  dialog.value?.close()
})
</script>
<style scoped>
.quota-controls {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  align-items: end;
  padding: 16px;
  background: #eef4fa;
  border-radius: 12px;
  margin: 14px 0;
}
.quota-controls label {
  display: grid;
  gap: 8px;
  color: #3d5e7b;
  font-size: 12px;
}
.quota-controls input {
  width: 100px;
  padding: 9px;
  border: 1px solid #bfd0e1;
  border-radius: 7px;
  font: inherit;
}
.quota-controls small {
  font-size: 11px;
  color: #738aa0;
}
.auto-trigger {
  border: 1px solid #2866b5;
  background: #2866b5;
  color: #fff;
  border-radius: 10px;
  padding: 12px 16px;
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  white-space: nowrap;
}
.auto-dialog {
  width: min(940px, calc(100vw - 24px));
  max-height: calc(100dvh - 32px);
  padding: 0;
  border: 1px solid #d6e1ed;
  border-radius: 20px;
  margin: auto;
  color: #203a54;
  box-shadow: 0 24px 80px #18324c44;
  overflow: hidden;
}
.auto-dialog[open] {
  display: flex;
  flex-direction: column;
}
.auto-dialog::backdrop {
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
  background: linear-gradient(120deg, #edf5ff, #fff);
}
header small {
  font-size: 10px;
  letter-spacing: 1px;
  color: #6483a5;
}
h3 {
  margin: 8px 0 0;
  font-size: 22px;
}
.auto-body {
  padding: 20px 24px;
  overflow: auto;
  min-height: 0;
}
.method {
  font-size: 12px;
  color: #71859c;
  line-height: 1.8;
  margin: 0 0 10px;
}
.preview-summary {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  align-items: center;
  padding: 16px;
  background: #f2f7fd;
  border-radius: 12px;
  margin: 18px 0;
  font-size: 12px;
  color: #56738f;
}
.preview-summary b {
  font-size: 23px;
  color: #2c6096;
  margin-right: 4px;
}
.preview-summary small {
  margin-left: auto;
  color: #8399ad;
}
.proposal-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.proposal-list article {
  padding: 16px;
  border: 1px solid #dce6f1;
  border-radius: 12px;
}
.proposal-person {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.proposal-person strong {
  font-size: 16px;
}
.proposal-person span {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  background: #eaf2ff;
  color: #2866b5;
}
.proposal-person .offline {
  background: #e8f6f2;
  color: #287764;
}
.proposal-list b {
  font-size: 13px;
}
.proposal-list p {
  font-size: 12px;
  line-height: 1.6;
  color: #71849b;
}
.proposal-list small {
  font-size: 11px;
  color: #8899ae;
}
.excluded {
  margin-top: 18px;
  font-size: 12px;
  color: #8394a8;
}
.excluded summary {
  cursor: pointer;
}
.excluded p {
  display: inline-block;
  margin: 10px 14px 0 0;
}
.error {
  background: #fff0ed;
  color: #b04d39;
  border-radius: 10px;
  padding: 12px;
  font-size: 13px;
}
.empty {
  text-align: center;
  padding: 32px 8px;
  font-size: 13px;
  color: #8394a8;
}
footer {
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
  border-top: 1px solid #dfe8f2;
  flex-shrink: 0;
}
footer span {
  flex: 1;
  font-size: 11px;
  color: #899bb0;
}
button {
  font: inherit;
  border: 1px solid #d5e1ee;
  padding: 9px 12px;
  border-radius: 8px;
  color: #54718d;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button:focus-visible {
  outline: 2px solid #70a1d6;
  outline-offset: 2px;
}
.primary {
  background: #2866b5;
  color: #fff;
  border-color: #2866b5;
}
@media (max-width: 650px) {
  .proposal-list {
    grid-template-columns: 1fr;
  }
  header,
  .auto-body,
  footer {
    padding: 16px;
  }
  h3 {
    font-size: 20px;
  }
  footer span {
    flex-basis: 100%;
  }
  .preview-summary {
    gap: 10px;
  }
  .preview-summary small {
    margin-left: 0;
    width: 100%;
  }
  .auto-dialog {
    width: calc(100vw - 16px);
    max-height: calc(100dvh - 16px);
    border-radius: 15px;
  }
}
</style>
