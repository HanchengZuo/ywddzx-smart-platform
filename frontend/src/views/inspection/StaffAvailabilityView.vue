<template>
  <div class="staff-page">
    <header class="staff-head surface">
      <div>
        <span class="kicker">排班系统 / STAFF AVAILABILITY</span>
        <h2>人员档期</h2>
        <p>谁有空、谁在现场、谁做视频，一眼看清本周安排。</p>
      </div>
      <div class="head-meta">
        <div class="head-actions">
          <DailyInspectionTeams
            v-if="board"
            :can-edit="board.can_edit"
            @opened="teamsOpened"
            @closed="teamsClosed"
            @saved="onTeamsSaved"
          />
          <span class="access">{{ board?.can_edit ? '可维护档期' : '只读查看' }}</span>
        </div>
        <small>工作日排班 · 全局共享</small>
      </div>
    </header>
    <section class="surface staff-board">
      <div class="week-controls">
        <div class="week-picker">
          <button type="button" aria-label="查看上一周" @click="moveWeek(-7)">← 上一周</button>
          <label>查看日期<input v-model="week" type="date" aria-label="人员档期查看日期" /></label>
          <button type="button" aria-label="查看下一周" @click="moveWeek(7)">下一周 →</button>
          <button type="button" class="this-week" @click="week = shanghaiToday()">本周</button>
        </div>
        <div class="week-caption">
          <strong>{{ weekCaption }}</strong>
          <small>{{ board?.days.length || 0 }} 个工作日 · 点击单个档期查看或设置</small>
        </div>
      </div>
      <div v-if="board" class="staff-stats" :aria-label="'今日档期概况 · ' + board.today">
        <div v-for="item in summaryItems" :key="item.key" :class="'stat-' + item.key">
          <span>{{ item.label }}</span
          ><strong>{{ stats[item.key] }}</strong
          ><small>{{ item.hint }}</small>
        </div>
      </div>
      <div class="legend" aria-label="档期颜色说明">
        <span v-for="item in legendItems" :key="item.key" :class="'tone-' + item.key"
          ><i></i>{{ item.label }}</span
        >
        <small>“已排班”为计划，“实绩”为实际巡检记录</small>
      </div>
      <p class="help">
        仅展示官方工作日（含调休上班日）。当天未设置的档期自动记为有空，提前设置的没空及原因不变；未来仍可逐格设置。实绩和历史派工只读，点击查看委派站点、检查表与完成进度。历史没空及原因原样保留，仅无派工、无实绩的历史档期可补录。
      </p>
      <p v-if="board && !board.calendar_known" class="warning">
        此周官方工作日日历不完整，未发布的日期不会猜测为工作日。请同步法定节假日日历后再安排。
      </p>
      <p v-if="board?.people.some((p) => !p.id)" class="warning">
        未唯一匹配启用督导组账号：{{
          board.people
            .filter((p) => !p.id)
            .map((p) => p.display_name)
            .join('、')
        }}。这些人员暂不能派工，请在用户数据管理核对姓名和账号。
      </p>
      <div v-if="error" class="error" role="alert">
        {{ error }} <button v-if="!blocked" type="button" @click="load">重试</button>
      </div>
      <p v-if="notice" class="notice" role="status">{{ notice }}</p>
      <p v-if="loading && !board" role="status" class="empty">正在读取人员档期…</p>
      <div v-else-if="board?.days.length" class="staff-grid" :aria-busy="loading">
        <table>
          <caption class="sr-only">
            人员工作日档期。逐个单元格设置，无批量操作。
          </caption>
          <colgroup>
            <col class="name-col" />
            <col class="position-col" />
            <col v-for="day in board.days" :key="day.day" />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">姓名 / 日期</th>
              <th scope="col">岗位</th>
              <th
                v-for="day in board.days"
                :key="day.day"
                scope="col"
                :class="{ today: day.day === board.today }"
              >
                <b>{{ day.day.slice(5).replace('-', ' / ') }}</b>
                <small>{{ day.weekday }}<em v-if="day.day === board.today">今天</em></small>
              </th>
            </tr>
          </thead>
          <tbody v-for="group in staffGroups" :key="group.label">
            <tr class="staff-divider">
              <th :colspan="board.days.length + 2" scope="rowgroup">
                {{ group.label }}<span>{{ group.people.length }} 人</span>
              </th>
            </tr>
            <tr
              v-for="person in group.people"
              :key="person.display_name"
              class="staff-person-row"
              :class="{ 'is-self': isCurrentPerson(person, board.current_user_id) }"
            >
              <th scope="row" class="person-name">
                <span
                  >{{ person.display_name
                  }}<em v-if="isCurrentPerson(person, board.current_user_id)" class="self-badge"
                    >本人</em
                  ><small v-if="!person.id">待匹配账号</small></span
                >
              </th>
              <td class="position">
                <span :class="{ manager: person.position === '管理人员' }">{{
                  person.position
                }}</span>
              </td>
              <td
                v-for="day in board.days"
                :key="day.day"
                class="day-cell"
                :class="{ 'today-cell': day.day === board.today }"
              >
                <button
                  type="button"
                  class="staff-cell"
                  :class="[
                    'tone-' + state(person, day).tone,
                    { 'is-actual': state(person, day).stage === '实绩' },
                    { 'is-self': isCurrentPerson(person, board.current_user_id) },
                  ]"
                  :disabled="loading || !!error"
                  :aria-label="
                    person.display_name + '，' + day.day + '，' + state(person, day).label
                  "
                  @click="openCell(person, day)"
                >
                  <small class="mobile-date">{{ day.day.slice(5) }} {{ day.weekday }}</small>
                  <span class="cell-stage"
                    ><i></i>{{ state(person, day).stage
                    }}<em v-if="person.cells[day.day].read_only">只读</em></span
                  >
                  <b>{{ state(person, day).label }}</b>
                  <small
                    v-if="person.cells[day.day].field_group_names?.length"
                    class="field-group-label"
                  >
                    {{ person.cells[day.day].field_group_names.join('、') }}
                  </small>
                  <small class="cell-detail">{{ state(person, day).detail || '—' }}</small>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else-if="board" class="empty">此周没有已发布的工作日。</p>
      <footer class="staff-footer">
        <strong>逐格维护 · 修改留痕</strong>
        <span
          >档期与排班由所有获授权用户共享。历史补录保留来源；已有派工或分组的人员不能直接标记没空，以免与已确认的安排冲突。</span
        >
      </footer>
    </section>
    <Teleport to="body">
      <dialog
        ref="dialog"
        class="staff-dialog"
        aria-labelledby="staff-edit-title"
        @cancel.prevent="close"
        @click="backdrop"
        @close="selection = null"
      >
        <template v-if="selection">
          <header>
            <div>
              <small>人员档期 / {{ editable ? '设置单日安排' : '查看档期' }}</small>
              <h3 id="staff-edit-title">{{ selection.person_name }} · {{ selection.day }}</h3>
            </div>
            <button type="button" :disabled="saving" aria-label="关闭档期设置" @click="close">
              ×
            </button>
          </header>
          <div class="dialog-body">
            <p v-if="detailLoading" class="edit-hint" role="status">正在核对原派工与最新实绩…</p>
            <p v-if="detailError" class="error" role="alert">
              {{ detailError }} <button type="button" @click="loadDetail">重新读取详情</button>
            </p>
            <div
              v-if="selectionState"
              class="current-arrangement"
              :class="'tone-' + selectionState.tone"
            >
              <strong>{{ selectionState.label }}</strong
              ><span
                >{{ selectionState.stage }} ·
                {{ selectionState.detail || '此日没有实际巡检记录' }}</span
              >
            </div>
            <StaffDispatchDetails v-if="detail" :cell="detail.cell" :records="detail.records" />
            <template v-if="editable">
              <div v-if="historical" class="status-picker history-picker" aria-label="补录历史档期">
                <button
                  v-for="item in historyOptions"
                  :key="item.value"
                  type="button"
                  :class="item.value"
                  :aria-pressed="historyStatus === item.value"
                  :disabled="saving"
                  @click="historyStatus = item.value"
                >
                  <b>{{ item.label }}</b
                  ><small>{{ item.hint }}</small>
                </button>
              </div>
              <div v-else class="status-picker" aria-label="选择当天档期">
                <button
                  type="button"
                  :aria-pressed="available"
                  class="free"
                  :disabled="saving"
                  @click="available = true"
                >
                  <b>有空</b><small>允许安排巡检</small>
                </button>
                <button
                  type="button"
                  :aria-pressed="!available"
                  class="busy"
                  :disabled="saving"
                  @click="available = false"
                >
                  <b>没空</b><small>当天不参与派工</small>
                </button>
              </div>
              <label v-if="historical ? historyStatus === 'busy' : !available" class="reason"
                >原因（选填，最多4字）<input
                  v-model="reason"
                  :disabled="saving"
                  maxlength="4"
                  placeholder="如：休假、培训、出差"
              /></label>
              <p v-if="historical" class="edit-hint">
                历史补录仅修改此人的档期显示，不会新增、删除或修改实际巡检记录。选择“自动记录”可恢复按原始巡检记录展示。
              </p>
              <p v-else class="edit-hint">
                仅保存此人这一天的档期，不会影响其他人员或日期。已有排班需先改派或取消，才能标记没空。
              </p>
            </template>
            <p v-else-if="detail" class="edit-hint readonly-explanation">
              {{ detail.cell.read_only_reason || '当前账号只有查看权限，不能修改档期。' }}
            </p>
            <p v-if="originalRecords" class="edit-hint">原始巡检记录：{{ originalRecords }}</p>
            <p v-if="savedMeta" class="saved-meta">{{ savedMeta }}</p>
            <p v-if="saveError" class="error" role="alert">{{ saveError }}</p>
          </div>
          <footer>
            <button type="button" :disabled="saving" @click="close">关闭</button
            ><button
              v-if="editable"
              type="button"
              class="primary"
              :disabled="saving || conflict"
              @click="save"
            >
              {{ saving ? '保存中…' : '保存档期' }}
            </button>
          </footer>
        </template>
      </dialog>
    </Teleport>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  offsetDay,
  shanghaiToday,
  staffCellPresentation,
  staffTodaySummary,
  isCurrentPerson,
} from '@/utils/staffScheduling'
import { createAdaptivePolling } from '@/utils/adaptivePolling'
import DailyInspectionTeams from '@/components/DailyInspectionTeams.vue'
import StaffDispatchDetails from '@/components/StaffDispatchDetails.vue'
const week = ref(shanghaiToday()),
  board = ref(null),
  loading = ref(false),
  saving = ref(false)
const error = ref(''),
  notice = ref(''),
  blocked = ref(false)
const selection = ref(null),
  selectionState = ref(null),
  available = ref(true),
  reason = ref(''),
  savedMeta = ref(''),
  editable = ref(false)
const historyStatus = ref('auto'),
  originalRecords = ref(''),
  teamsOpen = ref(false)
const historical = computed(() =>
  Boolean(
    selection.value &&
    selection.value.day < (detail.value?.today || board.value?.today || shanghaiToday()),
  ),
)
const staffGroups = computed(() =>
  ['管理人员', '大学生'].map((label) => ({
    label,
    people: (board.value?.people || []).filter((p) => p.position === label),
  })),
)
const historyOptions = [
  { value: 'offline', label: '现场巡检', hint: '人工补录' },
  { value: 'online', label: '视频巡检', hint: '人工补录' },
  { value: 'busy', label: '没空', hint: '可填写原因' },
  { value: 'auto', label: '自动记录', hint: '恢复原始巡检记录' },
]
const dialog = ref(null),
  saveError = ref(''),
  conflict = ref(false)
const detail = ref(null),
  detailLoading = ref(false),
  detailError = ref('')
let detailController,
  detailSerial = 0
let controller,
  serial = 0,
  disposed = false,
  timer
const summaryItems = [
  { key: 'free', label: '有空待排', hint: '今日有空未安排 · 人' },
  { key: 'busy', label: '没空', hint: '今日没空 · 人' },
  { key: 'unknown', label: '未确认', hint: '今日待确认 · 人' },
  { key: 'offline', label: '现场巡检', hint: '今日计划 / 实绩 · 人' },
  { key: 'online', label: '视频巡检', hint: '今日计划 / 实绩 · 人' },
]
const legendItems = [
  { key: 'free', label: '有空' },
  { key: 'busy', label: '没空' },
  { key: 'unknown', label: '未确认' },
  { key: 'offline', label: '现场' },
  { key: 'online', label: '视频' },
  { key: 'mixed', label: '现场 + 视频' },
]
const stats = computed(() => staffTodaySummary(board.value))
const weekCaption = computed(() => (board.value ? board.value.week + ' 起的一周' : '工作日档期'))
function state(person, day) {
  return staffCellPresentation(person.cells[day.day], day.day, board.value.today)
}
async function load() {
  if (blocked.value || disposed) return
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  try {
    const { data } = await axios.get('/api/staff-availability', {
      params: { week: week.value },
      signal: controller.signal,
      timeout: 15000,
    })
    if (ticket !== serial || disposed) return
    board.value = data
    error.value = ''
  } catch (err) {
    if (ticket !== serial || disposed || err.code === 'ERR_CANCELED') return
    error.value = err.response?.data?.error || '档期读取失败，请重试。'
    if ([401, 403].includes(err.response?.status)) {
      blocked.value = true
      board.value = null
    }
  } finally {
    if (ticket === serial) loading.value = false
  }
}
function moveWeek(offset) {
  week.value = offsetDay(
    board.value?.week || (/^\d{4}-\d{2}-\d{2}$/.test(week.value) ? week.value : shanghaiToday()),
    offset,
  )
}
async function openCell(person, day) {
  const value = person.cells[day.day]
  selection.value = { person_name: person.display_name, day: day.day, revision: value.revision }
  selectionState.value = state(person, day)
  available.value = value.available !== false
  reason.value = value.reason
  historyStatus.value = value.history_status || 'auto'
  originalRecords.value = (value.actual_modes || [])
    .map((m) => (m.mode === 'offline' ? '现场' : '视频') + m.count + '张检查表')
    .join('、')
  savedMeta.value = value.updated_at
    ? person.display_name + '的档期由' + value.updated_by_name + '于' + value.updated_at + '保存'
    : '此档期尚未设置。'
  editable.value = false
  detail.value = null
  detailError.value = ''
  saveError.value = ''
  conflict.value = false
  polling.pause()
  await nextTick()
  if (!disposed) {
    dialog.value.showModal()
    await loadDetail()
  }
}
async function loadDetail() {
  if (!selection.value || disposed) return
  const selected = { ...selection.value },
    ticket = ++detailSerial
  detailController?.abort()
  detailController = new AbortController()
  detailLoading.value = true
  editable.value = false
  detailError.value = ''
  try {
    const { data } = await axios.get('/api/staff-availability/detail', {
      params: { person_name: selected.person_name, day: selected.day },
      signal: detailController.signal,
      timeout: 15000,
    })
    if (disposed || ticket !== detailSerial || !selection.value) return
    detail.value = data
    const value = data.cell
    selection.value.revision = value.revision
    selectionState.value = staffCellPresentation(value, data.day, data.today)
    available.value = value.available !== false
    reason.value = value.reason
    historyStatus.value = value.history_status || 'auto'
    savedMeta.value = value.updated_at
      ? `${selected.person_name}的档期由${value.updated_by_name}于${value.updated_at}保存`
      : '此档期尚未设置。'
    originalRecords.value = ''
    editable.value = Boolean(
      data.can_edit && !value.read_only && !value.has_actual && !value.actual_modes?.length,
    )
  } catch (err) {
    if (!disposed && ticket === detailSerial && err.code !== 'ERR_CANCELED')
      detailError.value = err.response?.data?.error || '无法核对实绩，暂不能调整档期，请重试。'
  } finally {
    if (ticket === detailSerial) detailLoading.value = false
  }
}
function close() {
  if (!saving.value) {
    detailSerial++
    detailController?.abort()
    detailLoading.value = false
    detail.value = null
    dialog.value?.close()
    selection.value = null
    polling.start()
  }
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
async function save() {
  if (saving.value || !editable.value || conflict.value || !selection.value) return
  saving.value = true
  saveError.value = ''
  try {
    await axios.put(
      '/api/staff-availability',
      {
        cells: [selection.value],
        ...(historical.value
          ? { history_status: historyStatus.value }
          : { available: available.value }),
        reason: reason.value,
      },
      { timeout: 30000 },
    )
    if (disposed) return
    const wasHistorical = historical.value
    dialog.value.close()
    selection.value = null
    notice.value = wasHistorical
      ? '历史档期已保存，原始巡检记录保持不变。'
      : '档期已保存，可在巡检排班选择有空人员。'
    await load()
  } catch (err) {
    if (!disposed) {
      conflict.value = err.response?.status === 409
      saveError.value =
        (err.response?.data?.error || '保存失败，请重试。') +
        (conflict.value ? ' 请关闭并重新选择。' : '')
      if (conflict.value) await load()
    }
  } finally {
    saving.value = false
    polling.start()
  }
}
async function onTeamsSaved(data) {
  if (!data.adjusted) week.value = data.day
  await nextTick()
  clearTimeout(timer)
  await load()
  notice.value = '今日巡检分组已保存，可在表格查看各人的带队分组。'
}
function teamsOpened() {
  teamsOpen.value = true
  polling.pause()
}
function teamsClosed() {
  teamsOpen.value = false
  polling.start()
}
const polling = createAdaptivePolling({
  task: load,
  canRun: () =>
    !disposed &&
    !document.hidden &&
    navigator.onLine &&
    !saving.value &&
    !blocked.value &&
    !teamsOpen.value &&
    !dialog.value?.open,
})
function visibility() {
  if (document.hidden || !navigator.onLine) polling.pause()
  else polling.start({ immediate: true })
}
watch(week, () => {
  serial++
  controller?.abort()
  clearTimeout(timer)
  board.value = null
  notice.value = ''
  timer = setTimeout(load, 180)
})
onMounted(() => {
  load()
  polling.start()
  document.addEventListener('visibilitychange', visibility)
  window.addEventListener('online', visibility)
  window.addEventListener('offline', visibility)
})
onBeforeUnmount(() => {
  detailSerial++
  detailController?.abort()
  disposed = true
  serial++
  controller?.abort()
  clearTimeout(timer)
  polling.dispose()
  dialog.value?.close()
  document.removeEventListener('visibilitychange', visibility)
  window.removeEventListener('online', visibility)
  window.removeEventListener('offline', visibility)
})
</script>

<style scoped>
.cell-stage em {
  font-style: normal;
  font-size: 9px;
  padding: 1px 4px;
  border: 1px solid currentColor;
  border-radius: 4px;
  opacity: 0.75;
}
.self-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 2px 5px;
  border-radius: 5px;
  color: #075e63;
  background: #c9f2eb;
  font-size: 10px;
  font-style: normal;
  white-space: nowrap;
}
.staff-person-row.is-self .person-name {
  box-shadow: inset 4px 0 #12858a;
  background: #e8f7f4;
}
.staff-cell.is-self {
  outline: 2px solid #12858a;
  outline-offset: -3px;
}
.field-group-label {
  display: block;
  width: fit-content;
  max-width: 100%;
  padding: 3px 7px;
  border: 1px solid #d6982e;
  border-radius: 5px;
  background: #fff0c6;
  color: #764509;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.staff-page {
  --staff-sticky-top: -24px;
  display: grid;
  gap: 18px;
  min-width: 0;
  color: #18344f;
  container-type: inline-size;
}
.surface {
  background: #fff;
  border: 1px solid #cbd9e7;
  border-radius: 18px;
  box-shadow: 0 8px 28px #102b4510;
}
.staff-head {
  padding: 26px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  background:
    radial-gradient(ellipse at 90% 0, #296d87 0, transparent 55%),
    linear-gradient(115deg, #102e4c, #194763);
  border-color: #173f5d;
  color: #fff;
  border-bottom: 4px solid #e7ae42;
}
.kicker {
  font-size: 10px;
  letter-spacing: 2px;
  color: #9bd6e2;
  font-weight: 700;
}
h2 {
  font-size: 30px;
  margin: 10px 0;
  letter-spacing: 2px;
}
.staff-head p {
  margin: 0;
  color: #c2d5e4;
  font-size: 13px;
  line-height: 1.8;
}
.head-meta {
  display: grid;
  gap: 12px;
  justify-items: end;
  flex-shrink: 0;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
}
.access {
  padding: 8px 14px;
  background: #ffffff12;
  border: 1px solid #ffffff3b;
  border-radius: 7px;
  font-size: 12px;
}
.head-meta small {
  color: #abc7db;
  font-size: 11px;
}
.week-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  padding: 22px;
}
.week-picker {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.week-picker label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #51687e;
}
.week-caption {
  display: grid;
  gap: 6px;
  text-align: right;
  font-size: 13px;
}
.week-caption small {
  font-size: 11px;
  color: #627a90;
}
.staff-stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 0 22px 18px;
  border: 1px solid #d7e2ed;
  border-radius: 10px;
}
.staff-stats > div {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  padding: 14px 16px;
  border-top: 3px solid var(--stat-color, #64748b);
  border-right: 1px solid #dce5ee;
}
.staff-stats > div:first-child {
  border-radius: 10px 0 0 0;
}
.staff-stats > div:last-child {
  border-right: 0;
  border-radius: 0 10px 0 0;
}
.staff-stats span {
  align-self: center;
  font-size: 12px;
  color: #415c75;
}
.staff-stats strong {
  font-size: 25px;
  color: var(--stat-color);
  font-variant-numeric: tabular-nums;
}
.staff-stats small {
  grid-column: 1 / -1;
  color: #6b8196;
  font-size: 10px;
}
.stat-free {
  --stat-color: #137b54;
}
.stat-busy {
  --stat-color: #c03c43;
}
.stat-unknown {
  --stat-color: #697c92;
}
.stat-offline {
  --stat-color: #ac6314;
}
.stat-online {
  --stat-color: #2468c4;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 18px;
  margin: 0 22px;
  padding: 12px 0;
  border-block: 1px solid #e0e7f0;
}
.legend > span {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  color: #456078;
  background: none;
}
.legend i {
  height: 10px;
  width: 10px;
  border-radius: 3px;
  background: var(--tone);
}
.legend > small {
  margin-left: auto;
  color: #6b8196;
  font-size: 10px;
}
.tone-free {
  --tone: #16845c;
  --tone-bg: #dff2e7;
  --tone-ink: #12653f;
  --tone-line: #a4d9bd;
}
.tone-busy {
  --tone: #d14650;
  --tone-bg: #fbe4e6;
  --tone-ink: #a52c38;
  --tone-line: #edb4bb;
}
.tone-unknown {
  --tone: #8b9db1;
  --tone-bg: #eef2f7;
  --tone-ink: #566d83;
  --tone-line: #d5dfe9;
}
.tone-offline {
  --tone: #c7811a;
  --tone-bg: #ffedc9;
  --tone-ink: #895013;
  --tone-line: #e4bd70;
}
.tone-online {
  --tone: #3175d1;
  --tone-bg: #deebff;
  --tone-ink: #2056a3;
  --tone-line: #a7c7f1;
}
.tone-mixed {
  --tone: #0e8494;
  --tone-bg: #d7f0f2;
  --tone-ink: #11636c;
  --tone-line: #91cfd7;
}
.tone-past {
  --tone: #a6b4c1;
  --tone-bg: #f7f9fb;
  --tone-ink: #8394a3;
  --tone-line: #e5eaf0;
}
.help {
  margin: 12px 22px;
  color: #60778d;
  font-size: 12px;
  line-height: 1.9;
}
.warning,
.error,
.notice {
  margin: 12px 22px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.8;
}
.warning {
  color: #926121;
  background: #fff5df;
  border-left: 3px solid #d69c36;
}
.error {
  color: #b23442;
  background: #ffedf0;
}
.notice {
  color: #166849;
  background: #e8f5ec;
  border-left: 3px solid #2d966b;
}
.staff-grid table {
  width: 100%;
  border-spacing: 0;
  table-layout: fixed;
  font-size: 12px;
}
.name-col {
  width: 124px;
}
.position-col {
  width: 90px;
}
th,
td {
  border-bottom: 1px solid #dce5ee;
  border-right: 1px solid #dce5ee;
  text-align: center;
  padding: 0;
}
tr > :last-child {
  border-right: 0;
}
thead th {
  position: sticky;
  top: var(--staff-sticky-top);
  z-index: 2;
  height: 68px;
  background: #173c59;
  color: #fff;
  font-size: 12px;
  border-color: #31526c;
  box-shadow: 0 2px 0 #1c6680;
}
thead th b {
  font-size: 14px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 1px;
}
thead small {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  color: #b7cede;
  font-size: 10px;
  font-weight: 400;
}
thead em {
  color: #fff;
  background: #247e96;
  border-radius: 4px;
  padding: 1px 4px;
  font-size: 9px;
  font-style: normal;
}
thead .today {
  background: #155c72;
  box-shadow:
    inset 0 3px #5ac8cf,
    0 2px #1c6680;
}
.person-name {
  padding: 14px;
  text-align: left;
  font-weight: 700;
  background: #f5f8fc;
  font-size: 13px;
}
.person-name small {
  display: block;
  color: #a06b3b;
  font-weight: 400;
  font-size: 10px;
  margin-top: 5px;
}
.position {
  background: #fafcfe;
}
.position span {
  display: inline-block;
  padding: 4px 6px;
  background: #edf2f8;
  color: #63758c;
  border: 1px solid #dce5ee;
  border-radius: 5px;
  font-size: 10px;
}
.position .manager {
  color: #224f79;
  background: #e5eef8;
  border-color: #bfcee2;
}
.staff-divider th {
  text-align: left;
  padding: 12px 16px;
  font-size: 13px;
  letter-spacing: 1px;
  color: #1a5273;
  background: #dfeaf3;
  border-top: 3px solid #3c7895;
  border-bottom: 1px solid #bdd1e0;
}
.staff-divider span {
  margin-left: 10px;
  font-size: 10px;
  letter-spacing: 0;
  font-weight: 400;
  color: #557992;
}
.status-picker.history-picker {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.history-picker .offline {
  color: #895013;
  background: #fff1d3;
}
.history-picker .online {
  color: #2056a3;
  background: #e6efff;
}
.history-picker .busy {
  color: #ac3340;
  background: #fce9ec;
}
.history-picker .auto {
  color: #5a7086;
  background: #eef3f8;
}
.day-cell {
  padding: 6px;
  background: #fff;
}
.today-cell {
  background: #f0f8fb;
}
.staff-cell {
  width: 100%;
  min-height: 76px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 5px;
  padding: 10px 12px;
  border: 1px solid var(--tone-line);
  border-left: 4px solid var(--tone);
  border-radius: 7px;
  color: var(--tone-ink);
  background: var(--tone-bg);
  font: inherit;
  cursor: pointer;
  text-align: left;
  transition:
    box-shadow 140ms ease,
    border-color 140ms ease;
}
.staff-cell b {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
}
.cell-stage {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 9px;
  opacity: 0.85;
}
.cell-stage i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--tone);
}
.cell-detail {
  font-size: 10px;
  line-height: 1.5;
  opacity: 0.85;
  overflow-wrap: anywhere;
}
.staff-cell:hover:not(:disabled) {
  border-color: var(--tone);
  box-shadow: 0 2px 8px #14334c16;
}
.staff-cell:focus-visible {
  outline: 2px solid #206d9c;
  outline-offset: 2px;
}
.staff-cell:disabled {
  cursor: wait;
  opacity: 0.65;
}
.staff-cell.is-actual {
  border-top: 2px solid var(--tone);
}
tbody tr:hover .person-name {
  background: #e8eff7;
}
.mobile-date {
  display: none;
}
.staff-footer {
  padding: 16px 22px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 11px;
  line-height: 1.8;
  color: #697e92;
}
.staff-footer strong {
  color: #315a79;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
.empty {
  text-align: center;
  padding: 50px 20px;
  color: #6d8398;
  font-size: 13px;
}
.staff-dialog {
  width: min(680px, calc(100vw - 24px));
  max-width: none;
  max-height: calc(100dvh - 24px);
  padding: 0;
  margin: auto;
  border: 1px solid #cbd8e5;
  border-radius: 16px;
  color: #1c3b55;
  box-shadow: 0 24px 80px #0d263b55;
}
.staff-dialog[open] {
  display: flex;
  flex-direction: column;
}
.staff-dialog::backdrop {
  background: #102b4866;
  backdrop-filter: blur(4px);
}
.staff-dialog header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 22px;
  background: #163c58;
  color: #fff;
  flex-shrink: 0;
  border-bottom: 3px solid #e7ae42;
}
.staff-dialog header small {
  font-size: 10px;
  color: #acd0df;
  letter-spacing: 1px;
}
.staff-dialog h3 {
  margin: 8px 0 0;
  font-size: 19px;
}
.dialog-body {
  padding: 22px;
  overflow-y: auto;
  min-height: 0;
}
.current-arrangement {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px 14px;
  color: var(--tone-ink);
  background: var(--tone-bg);
  border-left: 4px solid var(--tone);
  border-radius: 7px;
  margin-bottom: 18px;
}
.current-arrangement strong {
  font-size: 13px;
}
.current-arrangement span {
  font-size: 11px;
}
.status-picker {
  display: flex;
  gap: 12px;
}
.status-picker button {
  flex: 1;
  display: grid;
  gap: 6px;
  padding: 18px 10px;
  border: 2px solid #dce4ed;
  text-align: center;
}
.status-picker b {
  font-size: 17px;
}
.status-picker small {
  font-size: 10px;
}
.status-picker .free {
  color: #176447;
  background: #e6f5ec;
}
.status-picker .busy {
  color: #ac3340;
  background: #fce9ec;
}
.status-picker button[aria-pressed='true'] {
  border-color: currentColor;
  box-shadow: inset 0 -3px currentColor;
}
.reason {
  display: grid;
  gap: 8px;
  margin-top: 18px;
  font-size: 12px;
  color: #4c667e;
}
.edit-hint,
.saved-meta {
  font-size: 11px;
  color: #667d92;
  line-height: 1.8;
  margin: 14px 0 0;
}
.saved-meta {
  padding-top: 12px;
  border-top: 1px dashed #d8e3ed;
}
.staff-dialog footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 22px;
  border-top: 1px solid #dce5ee;
  flex-shrink: 0;
  background: #f7faff;
}
.dialog-body .error {
  margin: 12px 0 0;
}
button {
  border: 1px solid #cddae8;
  border-radius: 7px;
  padding: 9px 12px;
  background: #fff;
  color: #365775;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
button:focus-visible {
  outline: 2px solid #277aa4;
  outline-offset: 2px;
}
button.primary,
button.this-week {
  background: #1e6786;
  color: #fff;
  border-color: #1e6786;
}
.staff-dialog header button {
  color: #d7e9f1;
  background: #ffffff0f;
  border-color: #ffffff33;
}
input {
  min-width: 0;
  border: 1px solid #c7d6e5;
  padding: 9px 10px;
  border-radius: 7px;
  color: #22415a;
  background: #fff;
  font: inherit;
  font-size: 12px;
}
@media (prefers-reduced-motion: reduce) {
  .staff-cell {
    transition: none;
  }
}
@media (max-width: 900px) {
  .staff-page {
    --staff-sticky-top: 42px;
  }
}
@container (max-width: 1000px) {
  .staff-cell {
    padding: 8px;
    min-height: 78px;
  }
  .cell-detail {
    font-size: 9px;
  }
  .staff-stats > div {
    padding: 12px 10px;
  }
  .name-col {
    width: 104px;
  }
  .position-col {
    width: 76px;
  }
}
@container (max-width: 760px) {
  .staff-head {
    padding: 20px;
    flex-direction: column;
    align-items: flex-start;
  }
  .head-meta small {
    display: none;
  }
  h2 {
    font-size: 26px;
  }
  .staff-head p {
    font-size: 12px;
  }
  .week-controls {
    padding: 16px;
    gap: 14px;
  }
  .week-caption {
    text-align: left;
  }
  .week-picker {
    gap: 6px;
  }
  .week-picker label {
    flex-wrap: wrap;
  }
  .week-picker button {
    padding: 9px;
    font-size: 11px;
  }
  .staff-stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin-inline: 16px;
  }
  .staff-stats > div {
    border-bottom: 1px solid #dce5ee;
  }
  .staff-stats strong {
    font-size: 22px;
  }
  .legend {
    margin-inline: 16px;
    gap: 10px 14px;
  }
  .legend > small {
    margin-left: 0;
    width: 100%;
  }
  .help,
  .warning,
  .error,
  .notice {
    margin: 12px 16px;
  }
  .staff-grid {
    padding: 12px;
    background: #eef3f8;
  }
  .staff-grid table,
  .staff-grid tbody {
    display: block;
  }
  .staff-grid colgroup {
    display: none;
  }
  .staff-grid thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
  .staff-grid tr {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    padding: 12px;
    background: #fff;
    border: 1px solid #cddae6;
    border-radius: 12px;
    margin-bottom: 12px;
    box-shadow: 0 3px 8px #18324c08;
  }
  .staff-grid th,
  .staff-grid td {
    border: 0;
    min-width: 0;
  }
  .staff-grid .staff-divider {
    display: block;
    padding: 0;
    background: transparent;
    border: 0;
    box-shadow: none;
    border-radius: 0;
    margin: 12px 0;
  }
  .staff-grid .staff-divider th {
    display: block;
    padding: 10px 6px;
    background: none;
    border-bottom: 2px solid #8db0c7;
  }
  .person-name,
  .position {
    padding: 2px 2px 6px;
    background: #fff;
  }
  .position {
    text-align: right;
  }
  .day-cell,
  .today-cell {
    padding: 0;
    background: none;
  }
  .staff-cell {
    min-height: 104px;
  }
  .mobile-date {
    display: block;
    font-size: 10px;
    line-height: 1.4;
  }
  .access {
    font-size: 10px;
    padding: 7px 9px;
  }
  .staff-footer {
    padding: 16px;
  }
}
@container (max-width: 380px) {
  .staff-head {
    flex-direction: column;
    gap: 12px;
  }
  .head-meta {
    justify-items: start;
  }
  .staff-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .week-picker label {
    order: -1;
    width: 100%;
  }
  .week-picker input {
    flex: 1;
  }
}
</style>
