<template>
  <div class="staff-page">
    <header class="staff-head surface">
      <div>
        <span class="kicker">排班系统 / STAFF AVAILABILITY</span>
        <h2>人员档期</h2>
        <p>先确认谁有空，再安排巡检；历史工作方式由巡检记录自动呈现。</p>
      </div>
      <span class="access">{{ board?.can_edit ? '可维护档期' : '只读查看' }}</span>
    </header>
    <section class="surface">
      <div class="week-controls">
        <div class="week-picker">
          <button type="button" @click="moveWeek(-7)">上一周</button
          ><label>查看日期<input v-model="week" type="date" aria-label="人员档期查看日期" /></label
          ><button type="button" @click="moveWeek(7)">下一周</button
          ><button type="button" @click="week = shanghaiToday()">本周</button>
        </div>
        <span class="legend"
          ><i class="free"></i>有空 <i class="busy"></i>没空 <i class="unknown"></i>未确认</span
        >
      </div>
      <p class="help">
        仅展示官方工作日，包含调休上班的周六、周日。未确认有空不参与派工；没空原因最多4个字。过去日期只读，显示实际现场或视频巡检（不要求审核）。
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
      <div v-if="board?.can_edit" class="batch-bar">
        <label
          ><input
            type="checkbox"
            :checked="selectedPeople.length === board.people.length"
            @change="
              selectedPeople = $event.target.checked ? board.people.map((p) => p.display_name) : []
            "
          />
          全选人员</label
        >
        <label
          ><input
            type="checkbox"
            :checked="futureDays.length > 0 && selectedDays.length === futureDays.length"
            :disabled="!futureDays.length"
            @change="selectedDays = $event.target.checked ? futureDays.map((d) => d.day) : []"
          />
          本周可编辑工作日</label
        >
        <span>已选 {{ selectedPeople.length }} 人 × {{ selectedDays.length }} 天</span>
        <button
          class="primary"
          type="button"
          :disabled="!canBatch || loading || !!error"
          @click="openBatch"
        >
          批量设置档期
        </button>
      </div>
      <p v-if="loading && !board" role="status" class="empty">正在读取人员档期…</p>
      <div v-else-if="board?.days.length" class="staff-grid" :aria-busy="loading">
        <table>
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
                <label
                  ><input
                    v-if="board.can_edit && day.day >= board.today"
                    v-model="selectedDays"
                    type="checkbox"
                    :value="day.day"
                    :aria-label="'选择' + day.day"
                  /><b>{{ day.day.slice(5) }}</b
                  ><small
                    >{{ day.weekday }}{{ day.day === board.today ? ' · 今天' : '' }}</small
                  ></label
                >
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="person in board.people" :key="person.display_name">
              <th scope="row" class="person-name">
                <label
                  ><input
                    v-if="board.can_edit"
                    v-model="selectedPeople"
                    type="checkbox"
                    :value="person.display_name"
                  /><span
                    >{{ person.display_name }}<small v-if="!person.id">待匹配账号</small></span
                  ></label
                >
              </th>
              <td class="position">{{ person.position }}</td>
              <td
                v-for="day in board.days"
                :key="day.day"
                class="day-cell"
                :class="cellClass(person.cells[day.day], day.day)"
              >
                <button
                  type="button"
                  :disabled="loading || !!error"
                  :aria-label="
                    person.display_name +
                    '，' +
                    day.day +
                    '，' +
                    label(person.cells[day.day], day.day)
                  "
                  @click="openCell(person, day)"
                >
                  <small class="mobile-date">{{ day.day.slice(5) }} {{ day.weekday }}</small>
                  <b>{{ label(person.cells[day.day], day.day) }}</b>
                  <small v-if="person.cells[day.day].reason">{{
                    person.cells[day.day].reason
                  }}</small>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else-if="board" class="empty">此周没有已发布的工作日。</p>
      <footer class="staff-footer">
        人员按指定名单顺序展示；档期、排班由所有获授权用户共享，修改会记录操作人。已派工日期若要标记没空，须先改派或取消任务。
      </footer>
    </section>
    <Teleport to="body"
      ><dialog
        ref="dialog"
        class="staff-dialog"
        aria-labelledby="staff-edit-title"
        @cancel.prevent="close"
        @click="backdrop"
      >
        <template v-if="edits.length"
          ><header>
            <div>
              <small>人员档期</small>
              <h3 id="staff-edit-title">
                {{
                  edits.length === 1
                    ? edits[0].person_name + ' · ' + edits[0].day
                    : '批量设置 ' + edits.length + ' 个档期'
                }}
              </h3>
            </div>
            <button type="button" :disabled="saving" aria-label="关闭档期设置" @click="close">
              ×
            </button>
          </header>
          <div class="dialog-body">
            <template v-if="editable">
              <div class="status-picker">
                <button
                  type="button"
                  :aria-pressed="available"
                  class="free"
                  :disabled="saving"
                  @click="available = true"
                >
                  有空 · 可排班</button
                ><button
                  type="button"
                  :aria-pressed="!available"
                  class="busy"
                  :disabled="saving"
                  @click="available = false"
                >
                  没空 · 不派工
                </button>
              </div>
              <label v-if="!available" class="reason"
                >原因（选填，最多4字）<input
                  v-model="reason"
                  :disabled="saving"
                  maxlength="4"
                  placeholder="如：休假、培训、出差"
              /></label>
              <p>保存将统一应用到选中档期；已有排班、版本变化或任何一格校验失败时，整批不保存。</p>
            </template>
            <p v-else>此日期只读。历史现场、视频巡检来自当日实际记录，不会改写档期。</p>
            <p v-if="savedMeta">{{ savedMeta }}</p>
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
      </dialog></Teleport
    >
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { offsetDay, shanghaiToday } from '@/utils/staffScheduling'
import { createAdaptivePolling } from '@/utils/adaptivePolling'
const week = ref(shanghaiToday()),
  board = ref(null),
  loading = ref(false),
  saving = ref(false)
const error = ref(''),
  notice = ref(''),
  blocked = ref(false),
  selectedPeople = ref([]),
  selectedDays = ref([])
const edits = ref([]),
  available = ref(true),
  reason = ref(''),
  savedMeta = ref(''),
  editable = ref(false)
const dialog = ref(null),
  saveError = ref(''),
  conflict = ref(false)
let controller,
  serial = 0,
  disposed = false,
  timer
const futureDays = computed(() =>
  (board.value?.days || []).filter((d) => d.day >= board.value.today),
)
const canBatch = computed(() => selectedPeople.value.length && selectedDays.value.length)
function cellClass(cell, day) {
  return cell.actual_modes.length
    ? 'actual'
    : day < board.value.today
      ? 'past'
      : cell.available === true
        ? 'free'
        : cell.available === false
          ? 'busy'
          : 'unknown'
}
function label(cell, day) {
  if (cell.actual_modes.length)
    return cell.actual_modes
      .map((v) => (v.mode === 'offline' ? '现场巡检' : '视频巡检'))
      .join(' / ')
  if (day < board.value.today) return '无巡检记录'
  return cell.available === true ? '有空' : cell.available === false ? '没空' : '未确认'
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
    selectedDays.value = selectedDays.value.filter(
      (day) => data.days.some((d) => d.day === day) && day >= data.today,
    )
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
async function showEditor(cells, allow, meta = '') {
  edits.value = cells
  available.value = true
  reason.value = ''
  savedMeta.value = meta
  editable.value = allow
  saveError.value = ''
  conflict.value = false
  if (cells.length === 1) {
    const value = board.value.people.find((p) => p.display_name === cells[0].person_name).cells[
      cells[0].day
    ]
    available.value = value.available !== false
    reason.value = value.reason
  }
  await nextTick()
  dialog.value.showModal()
}
function openCell(person, day) {
  const value = person.cells[day.day]
  showEditor(
    [{ person_name: person.display_name, day: day.day, revision: value.revision }],
    board.value.can_edit && day.day >= board.value.today,
    value.updated_at ? `${value.updated_by_name} · ${value.updated_at} 保存` : '此档期尚未设置。',
  )
}
function openBatch() {
  const cells = []
  for (const person of board.value.people.filter((p) =>
    selectedPeople.value.includes(p.display_name),
  )) {
    for (const day of futureDays.value.filter((d) => selectedDays.value.includes(d.day)))
      cells.push({
        person_name: person.display_name,
        day: day.day,
        revision: person.cells[day.day].revision,
      })
  }
  if (cells.length) showEditor(cells, true)
}
function close() {
  if (!saving.value) {
    dialog.value?.close()
    edits.value = []
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
  if (saving.value || !editable.value || conflict.value) return
  saving.value = true
  saveError.value = ''
  try {
    await axios.put(
      '/api/staff-availability',
      { cells: edits.value, available: available.value, reason: reason.value },
      { timeout: 30000 },
    )
    if (disposed) return
    dialog.value.close()
    edits.value = []
    notice.value = '档期已保存，可在巡检排班选择有空人员。'
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
const polling = createAdaptivePolling({
  task: load,
  canRun: () =>
    !disposed &&
    !document.hidden &&
    navigator.onLine &&
    !saving.value &&
    !blocked.value &&
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
  selectedDays.value = []
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
.staff-page {
  --staff-sticky-top: -24px;
  display: grid;
  gap: 18px;
  min-width: 0;
  color: #203a54;
  container-type: inline-size;
}
.surface {
  background: #fff;
  border: 1px solid #dbe5ef;
  border-radius: 20px;
  box-shadow: 0 12px 30px #18324c08;
}
.staff-head {
  padding: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: linear-gradient(125deg, #f4f9ff, #fff 65%);
}
.kicker {
  font-size: 11px;
  letter-spacing: 1px;
  color: #2769a0;
  font-weight: 750;
}
h2 {
  font-size: 30px;
  margin: 10px 0;
}
p {
  font-size: 13px;
  line-height: 1.8;
  color: #6b7e93;
}
.access {
  padding: 8px 12px;
  background: #f1f6fc;
  border-radius: 8px;
  font-size: 12px;
  white-space: nowrap;
}
.week-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 20px 22px 4px;
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
}
.help,
.warning,
.error,
.notice {
  margin: 12px 22px;
}
.warning {
  color: #a57126;
  background: #fff7e7;
  padding: 10px 12px;
  border-radius: 9px;
}
.error {
  color: #b14838;
  background: #fff1ed;
  padding: 10px 12px;
  border-radius: 9px;
}
.notice {
  color: #287755;
}
.legend {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #6b7e93;
}
.legend i {
  width: 9px;
  height: 9px;
  border-radius: 3px;
  margin-left: 8px;
}
.free {
  background: #e8f7ef;
  color: #23734f;
}
.busy {
  background: #fff0ee;
  color: #b7463a;
}
.unknown {
  background: #f0f3f7;
  color: #7f8fa1;
}
.legend .free {
  background: #5db38b;
}
.legend .busy {
  background: #d8796d;
}
.legend .unknown {
  background: #b7c2ce;
}
.batch-bar {
  padding: 12px 22px;
  background: #f7faff;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  border-block: 1px solid #e0e8f2;
  font-size: 12px;
}
.batch-bar label {
  display: flex;
  align-items: center;
  gap: 6px;
}
.batch-bar > span {
  color: #7488a0;
  margin-left: auto;
}
.staff-grid table {
  width: 100%;
  border-spacing: 0;
  table-layout: fixed;
  border-collapse: separate;
  font-size: 12px;
}
.name-col {
  width: 142px;
}
.position-col {
  width: 84px;
}
th,
td {
  border-bottom: 1px solid #e1e8f0;
  border-right: 1px solid #e1e8f0;
  text-align: center;
  padding: 0;
}
thead th {
  position: sticky;
  top: var(--staff-sticky-top);
  z-index: 2;
  height: 64px;
  background: #edf3fa;
  color: #42617e;
}
thead label {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 5px;
}
thead small {
  width: 100%;
  font-weight: 400;
  color: #7b8ea3;
}
thead .today {
  background: #ddebf9;
}
.person-name {
  padding: 10px 14px;
  text-align: left;
  font-weight: 650;
  background: #fcfdff;
}
.person-name label {
  display: flex;
  align-items: center;
  gap: 8px;
}
.person-name small {
  display: block;
  color: #ba8270;
  font-weight: 400;
  font-size: 10px;
  margin-top: 4px;
}
.position {
  color: #7a8fa3;
}
.day-cell button {
  width: 100%;
  min-height: 53px;
  background: none;
  border: 0;
  border-radius: 0;
  color: inherit;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font: inherit;
  cursor: pointer;
  padding: 7px 4px;
}
.day-cell button b {
  font-weight: 600;
}
.day-cell small {
  font-size: 10px;
}
.day-cell button:hover {
  box-shadow: inset 0 0 0 2px #86afd5;
}
.past {
  color: #94a3b5;
  background: #fafbfd;
}
.actual {
  color: #28689c;
  background: #eaf3ff;
}
.mobile-date {
  display: none;
}
.staff-footer {
  padding: 16px 22px;
  font-size: 11px;
  color: #8596aa;
  line-height: 1.8;
}
.empty {
  text-align: center;
  padding: 50px 16px;
}
button,
input {
  font: inherit;
}
button {
  border: 1px solid #d6e1ed;
  border-radius: 8px;
  padding: 8px 12px;
  background: #fff;
  color: #4b6782;
  cursor: pointer;
  font-size: 12px;
}
input[type='date'],
.reason input {
  border: 1px solid #d6e1ed;
  border-radius: 8px;
  padding: 8px;
  min-width: 0;
  background: #fff;
  color: #345574;
}
input[type='checkbox'] {
  accent-color: #2866b5;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.primary {
  background: #2866b5;
  color: #fff;
  border-color: #2866b5;
}
button:focus-visible,
input:focus-visible {
  outline: 2px solid #70a1d6;
  outline-offset: 2px;
}
.staff-dialog {
  width: min(580px, calc(100vw - 24px));
  max-height: calc(100dvh - 24px);
  padding: 0;
  border: 1px solid #d6e1ed;
  border-radius: 18px;
  color: #203a54;
  margin: auto;
  box-shadow: 0 24px 80px #18324c44;
}
.staff-dialog::backdrop {
  background: #182c4b66;
  backdrop-filter: blur(4px);
}
.staff-dialog[open] {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.staff-dialog header,
.staff-dialog footer {
  flex-shrink: 0;
}
.dialog-body {
  min-height: 0;
  overflow: auto;
}
@media (max-width: 900px) {
  .staff-page {
    --staff-sticky-top: -16px;
  }
}
.staff-dialog header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 22px;
  border-bottom: 1px solid #e2eaf3;
}
.staff-dialog header small {
  color: #7b8da3;
}
.staff-dialog h3 {
  margin: 8px 0 0;
  font-size: 19px;
}
.dialog-body {
  padding: 22px;
}
.status-picker {
  display: flex;
  gap: 12px;
}
.status-picker button {
  flex: 1;
  padding: 16px 8px;
  border: 2px solid transparent;
}
.status-picker button[aria-pressed='true'] {
  border-color: currentColor;
  font-weight: 700;
}
.reason {
  display: grid;
  gap: 8px;
  font-size: 13px;
  margin-top: 18px;
}
.staff-dialog footer {
  padding: 16px 22px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid #e2eaf3;
}
.dialog-body .error {
  margin: 12px 0 0;
}
@container (max-width:760px) {
  .staff-head {
    padding: 18px;
    align-items: flex-start;
    flex-direction: column;
  }
  h2 {
    font-size: 26px;
  }
  .week-controls {
    padding: 16px 16px 0;
  }
  .help,
  .warning,
  .error,
  .notice {
    margin: 12px 16px;
  }
  .batch-bar {
    padding: 12px 16px;
    gap: 12px;
  }
  .staff-grid {
    padding: 12px;
    background: #f5f8fc;
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
    grid-template-columns: 1fr 1fr;
    background: #e1e8f0;
    gap: 1px;
    border: 1px solid #dbe4f0;
    border-radius: 12px;
    overflow: clip;
    margin-bottom: 12px;
  }
  .staff-grid th,
  .staff-grid td {
    border: 0;
    min-width: 0;
  }
  .person-name,
  .position {
    padding: 14px;
    background: #fff;
  }
  .position {
    text-align: right;
  }
  .day-cell button {
    min-height: 84px;
  }
  .mobile-date {
    display: block;
    font-size: 10px;
    color: #8797a9;
  }
  .access {
    font-size: 11px;
  }
}
</style>
