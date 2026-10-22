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
          {{ day }} · 今日未设置的档期默认有空，已标记没空者不参与。当天实绩自上海时间 17:00
          后参与派工校验，早间录入不阻止排班；已有站点安排仍不覆盖。现场按已保存外勤组整行派站，视频每站一人统一完成安全、计量、现场。
        </p>
        <p class="method">
          现场先补足当月计量年度计划的片区站数，再均衡季度片区覆盖，并让同组站点彼此靠近。缺失坐标的站点不自动派现场任务。可在页面“计量年度计划”维护月度配额；视频仍按本季度工作量安排。
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
          <details
            v-if="preview.metering_plan?.regions?.some((r) => r.target)"
            class="coverage-panel"
          >
            <summary>当月计量年度计划 · 优先派站依据</summary>
            <div class="coverage-grid">
              <div
                v-for="r in preview.metering_plan.regions.filter((r) => r.target)"
                :key="r.region"
              >
                <strong>{{ r.region }}</strong
                ><b>目标 {{ r.target }}站</b
                ><small
                  >已查 {{ r.completed }} · 预留 {{ r.reserved }} · 本次 {{ r.proposed }}</small
                >
              </div>
            </div>
          </details>
          <div class="preview-summary">
            <span
              ><b>{{ preview.available_count }}</b> 可派工人员</span
            ><span
              ><b>{{ preview.groups.length }}</b> 站点任务组</span
            ><span
              ><b>{{ preview.cell_count }}</b> 排班单元格</span
            ><small>{{ preview.quarter }}平衡口径</small>
          </div>
          <details v-if="preview.regional_coverage?.length" class="coverage-panel">
            <summary>现场片区覆盖均衡 · 查看本次分配依据</summary>
            <p>
              本季度有任一现场检查记录即计覆盖，不依赖审核。今日及未来已有计划仅作预留，不算实绩；在此基础上优先补齐低覆盖片区，再缩小组内站点距离。
            </p>
            <div class="coverage-grid">
              <div
                v-for="region in preview.regional_coverage"
                :key="region.region"
                :class="{ chosen: region.selected }"
              >
                <strong>{{ region.region }}</strong
                ><b title="当前实绩覆盖率 → 含计划预留及本次派工的预计覆盖率"
                  >{{ region.current_rate }}% → {{ region.projected_rate }}%</b
                >
                <small
                  >已查 {{ region.checked }}/{{ region.total }}站 · 预留 {{ region.reserved }}站 ·
                  本次 {{ region.selected }}站</small
                >
              </div>
            </div>
          </details>
          <div v-if="preview.groups.length" class="proposal-list">
            <article v-for="group in proposalGroups" :key="group.key">
              <div class="proposal-person">
                <strong>{{ group.group_name || group.person.display_name }}</strong
                ><span :class="group.mode"
                  >{{ group.mode === 'offline' ? '现场巡检' : '视频巡检' }} ·
                  {{ group.stations.length }}站</span
                >
              </div>
              <p v-if="group.team_members">
                {{ group.team_members.map((p) => p.display_name).join('、') }}
              </p>
              <ol
                class="proposal-stations"
                :aria-label="(group.group_name || group.person.display_name) + '负责的站点'"
              >
                <li v-for="station in group.stations" :key="station.station_id">
                  <b>{{ station.region }} · {{ station.station_name }}</b>
                  <p>
                    {{
                      [...station.cells, ...(station.metering_cells || [])]
                        .map((c) => c.label)
                        .join('、')
                    }}<b v-if="station.metering_priority"> · 计量计划优先</b>
                  </p>
                  <small v-if="group.mode === 'offline'">{{ station.address }}</small>
                </li>
              </ol>
              <p v-if="group.mode === 'offline'">
                组内站点最远直线距离 {{ group.cluster_max_km }} km · 非行车路线
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
import { computed, onBeforeUnmount, ref } from 'vue'
import { shanghaiToday } from '@/utils/staffScheduling'
import { groupScheduleProposals } from '@/utils/scheduleProposals'
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
const proposalGroups = computed(() => groupScheduleProposals(preview.value?.groups))
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
.coverage-panel {
  margin: 14px 0;
  padding: 14px;
  border: 1px solid #b7d4df;
  border-radius: 12px;
  background: #f3f9fb;
  color: #31596b;
}
.coverage-panel summary {
  cursor: pointer;
  font-weight: 700;
}
.coverage-panel p {
  font-size: 13px;
  line-height: 1.7;
}
.coverage-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 8px;
}
.coverage-grid > div {
  display: grid;
  gap: 5px;
  padding: 10px;
  background: #fff;
  border: 1px solid #dce8ee;
  border-radius: 8px;
}
.coverage-grid > .chosen {
  border-color: #2d93a9;
  background: #e8f7f8;
}
.coverage-grid b {
  color: #12647b;
}
.coverage-grid small {
  line-height: 1.5;
}
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
.proposal-stations {
  display: grid;
  gap: 10px;
  padding: 0 0 0 24px;
  margin: 12px 0;
}
.proposal-stations li {
  padding: 7px 8px;
  background: #f4f8fc;
  border-radius: 6px;
}
.proposal-stations li::marker {
  color: #467bad;
  font-weight: 700;
}
.proposal-stations p {
  margin: 4px 0;
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
