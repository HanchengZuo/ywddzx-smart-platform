<template>
  <section class="schedule-panel" :aria-label="title">
    <header class="panel-head">
      <div class="panel-identity">
        <span class="mode-icon" :class="mode">{{ mode === 'offline' ? '季' : '月' }}</span>
        <div>
          <h3>{{ title }}</h3>
          <p>{{ mode === 'offline' ? '季度覆盖 · 六类现场检查' : '月度覆盖 · 三类视频检查' }}</p>
        </div>
      </div>
      <div class="period-controls">
        <label
          >年份<select v-model.number="draft.year" :aria-label="title + '年份'">
            <option v-for="year in years" :key="year" :value="year">{{ year }}年</option>
          </select></label
        ><label v-if="mode === 'offline'"
          >季度<select v-model.number="draft.quarter" aria-label="现场检查季度">
            <option v-for="quarter in 4" :key="quarter" :value="quarter">
              第{{ quarter }}季度
            </option>
          </select></label
        ><label v-else
          >月份<select v-model.number="draft.month" aria-label="视频检查月份">
            <option v-for="month in 12" :key="month" :value="month">{{ month }}月</option>
          </select></label
        >
      </div>
    </header>
    <div class="board-toolbar">
      <div class="board-stats">
        <span
          ><b>{{ counts.completed }}</b> 已检查</span
        ><span
          ><b>{{ counts.assigned }}</b> 已排班</span
        ><span
          ><b>{{ counts.unassigned }}</b> 待排班</span
        ><small>按单元格计数</small>
      </div>
      <span class="sync-state" role="status"
        >{{
          loading
            ? '正在核对排班…'
            : error
              ? '数据未更新 · 暂停编辑'
              : !online
                ? '离线保留结果 · 暂停编辑'
                : `已同步 ${updatedTime || '—'}`
        }}<em v-if="board && !board.can_edit"> · 只读</em></span
      >
    </div>
    <div class="board-filters">
      <input
        v-model.trim="keyword"
        type="search"
        :aria-label="title + '搜索站点'"
        placeholder="搜索站点名称"
      /><select v-model="region" :aria-label="title + '片区'">
        <option value="">全部可见片区</option>
        <option v-for="value in regions" :key="value" :value="value">{{ value }}</option></select
      ><select v-model="state" :aria-label="title + '排班状态'">
        <option value="">全部状态</option>
        <option value="unassigned">有待排班项</option>
        <option value="assigned">有已排班项</option>
        <option value="completed">有已检查项</option></select
      ><button
        v-if="keyword || region || state"
        type="button"
        class="text-button"
        @click="clearFilters"
      >
        清除筛选</button
      ><span>{{ rows.length }} 个站点</span>
    </div>
    <div v-if="error" class="panel-error" role="alert">
      {{ error
      }}<button
        v-if="!blocked"
        type="button"
        class="text-button"
        :disabled="loading"
        @click="retryBoard"
      >
        重试
      </button>
    </div>
    <div v-if="notice" class="panel-notice" role="status">{{ notice }}</div>
    <div
      class="matrix-scroll"
      tabindex="0"
      :aria-label="title + '排班表，可横向及纵向滚动'"
      :aria-busy="loading"
    >
      <table class="schedule-matrix" :class="mode">
        <caption class="sr-only">
          {{
            title
          }}
          {{
            board?.period.label
          }}，黄色为有巡检记录的已检查项。
        </caption>
        <colgroup>
          <col class="index-col" />
          <col class="region-col" />
          <col class="station-col" />
          <col v-for="column in board?.columns || []" :key="column.key" class="check-col" />
        </colgroup>
        <thead>
          <tr>
            <th class="fixed-index" scope="col">序号</th>
            <th class="fixed-region" scope="col">片区</th>
            <th class="fixed-station" scope="col">加油站</th>
            <th
              v-for="column in board?.columns || []"
              :key="column.key"
              scope="col"
              :title="column.full_name"
            >
              {{ column.label }}<small v-if="!column.table_id">未启用或不可见</small>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!board && loading">
            <td colspan="9" class="empty-cell">正在读取本周期排班表…</td>
          </tr>
          <tr v-else-if="!rows.length">
            <td :colspan="(board?.columns.length || 0) + 3" class="empty-cell">
              {{
                error
                  ? '暂时无法读取，请重试。'
                  : keyword || region || state
                    ? '没有匹配的站点，请调整筛选条件。'
                    : '当前范围没有纳入本计划的可见名单站点。'
              }}
            </td>
          </tr>
          <tr
            v-for="row in rows"
            :key="row.station_id"
            :class="{ 'region-start': row.sequence === 1 || regionStarts.has(row.station_id) }"
          >
            <td class="fixed-index">{{ row.sequence }}</td>
            <td class="fixed-region">{{ row.region }}</td>
            <th scope="row" class="fixed-station">{{ row.station_name }}</th>
            <td
              v-for="column in board.columns"
              :key="column.key"
              :class="['matrix-cell', row.cells[column.key].status]"
            >
              <button
                type="button"
                class="cell-button"
                :disabled="
                  loading ||
                  !online ||
                  !!error ||
                  blocked ||
                  row.cells[column.key].status === 'unavailable'
                "
                :aria-label="`${row.station_name}，${column.label}，${scheduleStatusLabels[row.cells[column.key].status]}${inspectorPreview(row.cells[column.key]) ? '，' + inspectorPreview(row.cells[column.key]) : ''}`"
                @click="openCell(row, column)"
              >
                <span class="cell-names">{{
                  inspectorPreview(row.cells[column.key]) ||
                  (row.cells[column.key].status === 'completed'
                    ? '未记录检查人'
                    : row.cells[column.key].status === 'unavailable'
                      ? '不可安排'
                      : canEdit
                        ? '＋ 选择检查人'
                        : '尚未排班')
                }}</span>
                <small v-if="row.cells[column.key].status === 'completed'"
                  >已检查 · {{ row.cells[column.key].last_inspection_date }}</small
                ><small v-else-if="row.cells[column.key].status === 'assigned'"
                  >已排班{{ canEdit ? ' · 点击调整' : '' }}</small
                >
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <footer class="panel-footer">
      <span>{{ board?.period.label || '当前周期' }} · 保留名单序号和顺序，黄色单元格不可改派。</span
      ><span>{{ canEdit ? '点击未检查单元格安排检查人' : '当前为只读查看' }}</span>
    </footer>
    <Teleport to="body">
      <dialog
        ref="dialog"
        class="schedule-cell-dialog"
        :aria-labelledby="dialogId"
        @cancel.prevent="closeCell"
        @click="onBackdrop"
        @close="selection = null"
      >
        <template v-if="selection && currentCell">
          <header class="cell-dialog-head">
            <div>
              <span class="dialog-kicker"
                >{{ board?.period.label }} · {{ selection.column.label }}</span
              >
              <h3 :id="dialogId">{{ selection.row.region }} · {{ selection.row.station_name }}</h3>
            </div>
            <button
              type="button"
              class="dialog-close"
              aria-label="关闭排班单元格"
              :disabled="saving"
              @click="closeCell"
            >
              ×
            </button>
          </header>
          <div class="cell-dialog-body">
            <div v-if="currentCell.status === 'completed'" class="completion-note">
              <strong>本周期已有巡检记录，已锁定</strong>
              <p>
                共 {{ currentCell.record_count }} 条记录，最近检查
                {{ currentCell.last_inspection_date }}。以下为实际检查人，与原排班人分开保留。
              </p>
              <div class="people-tags">
                <span v-for="person in currentCell.completed_inspectors" :key="person.id"
                  >{{ person.display_name }} <small>{{ person.username }}</small></span
                ><span v-if="!currentCell.completed_inspectors.length">未记录检查人</span>
              </div>
            </div>
            <div class="saved-info">
              <span>{{ currentCell.status === 'completed' ? '原排班人员' : '当前保存排班' }}</span
              ><strong>{{
                currentCell.assignees.map((person) => person.display_name).join('、') || '尚未分配'
              }}</strong
              ><small v-if="currentCell.updated_at"
                >{{ currentCell.updated_by_name }} · {{ currentCell.updated_at }} 保存</small
              >
            </div>
            <template v-if="scheduleCellEditable(currentCell, canEdit)">
              <label class="search-people"
                >选择检查人<input
                  v-model.trim="peopleKeyword"
                  type="search"
                  placeholder="搜索姓名或用户名"
                  aria-label="搜索检查人"
                  :disabled="saving || conflict"
              /></label>
              <p class="selection-count">
                已选择 {{ selectedIds.length }} 人，可多选；清空后保存即取消排班。
              </p>
              <fieldset :disabled="saving || conflict" class="people-options">
                <section v-for="group in peopleGroups" :key="group.role">
                  <h4>
                    {{ group.label }} <span>{{ group.people.length }}</span>
                  </h4>
                  <label
                    v-for="person in group.people"
                    :key="person.id"
                    class="person-option"
                    :class="{ selected: selectedIds.includes(person.id) }"
                    ><input v-model="selectedIds" type="checkbox" :value="person.id" /><span
                      ><b>{{ person.display_name }}</b
                      ><small>{{ person.username }}</small></span
                    ><em v-if="selectedIds.includes(person.id)">已选</em></label
                  >
                </section>
                <p v-if="!peopleGroups.some((group) => group.people.length)" class="no-people">
                  没有匹配的启用督导组账号。
                </p>
              </fieldset>
              <p v-if="unavailableSelected.length" class="dialog-error">
                原排班包含已停用或非督导组账号：{{
                  unavailableSelected.map((person) => person.display_name).join('、')
                }}。<button
                  type="button"
                  class="text-button"
                  :disabled="saving || conflict"
                  @click="
                    selectedIds = selectedIds.filter(
                      (id) => !unavailableSelected.some((person) => person.id === id),
                    )
                  "
                >
                  移除这些人员
                </button>
              </p>
            </template>
            <p v-else-if="currentCell.status !== 'completed'" class="readonly-note">
              当前仅可查看排班，编辑权限由Root独立分配。
            </p>
          </div>
          <footer class="cell-dialog-footer">
            <p v-if="saveError" class="dialog-error" role="alert">{{ saveError }}</p>
            <div>
              <span>只保存此单元格，暂不推送待办</span
              ><button type="button" class="secondary-button" :disabled="saving" @click="closeCell">
                关闭</button
              ><button
                v-if="conflict && currentCell.status !== 'completed'"
                type="button"
                class="primary-button"
                :disabled="loading"
                @click="reloadSelection"
              >
                载入最新排班</button
              ><button
                v-else-if="scheduleCellEditable(currentCell, canEdit)"
                type="button"
                class="primary-button"
                :disabled="saving || loading || !changed || !!unavailableSelected.length"
                @click="saveSelection"
              >
                {{ saving ? '保存中…' : '保存排班' }}
              </button>
            </div>
          </footer>
        </template>
      </dialog>
    </Teleport>
  </section>
</template>

<script setup>
import axios from 'axios'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { createAdaptivePolling } from '@/utils/adaptivePolling'
import { coverageQuery, currentCoveragePeriod } from '@/utils/schedulingCoverage'
import {
  filterScheduleRows,
  inspectorPreview,
  scheduleCellEditable,
  scheduleCounts,
  scheduleStatusLabels,
} from '@/utils/inspectionSchedule'

const props = defineProps({ mode: { type: String, required: true } })
const title = props.mode === 'offline' ? '现场检查排班' : '视频检查排班'
const draft = ref({ ...currentCoveragePeriod(), mode: props.mode })
const years = Array.from({ length: 101 }, (_, i) => 2100 - i)
const board = ref(null),
  loading = ref(false),
  saving = ref(false),
  blocked = ref(false)
const error = ref(''),
  notice = ref(''),
  keyword = ref(''),
  region = ref(''),
  state = ref('')
const updatedTime = ref(''),
  online = ref(navigator.onLine)
const dialog = ref(null),
  selection = ref(null),
  selectedIds = ref([]),
  peopleKeyword = ref('')
const saveError = ref(''),
  conflict = ref(false)
const dialogId = 'schedule-cell-' + useId()
let controller,
  disposed = false,
  serial = 0,
  switchTimer,
  trigger
const canEdit = computed(() =>
  Boolean(board.value?.can_edit && online.value && !error.value && !blocked.value),
)
const rows = computed(() =>
  filterScheduleRows(board.value?.rows || [], region.value, keyword.value, state.value),
)
const regions = computed(() => [...new Set((board.value?.rows || []).map((row) => row.region))])
const counts = computed(() => scheduleCounts(rows.value))
const regionStarts = computed(
  () =>
    new Set(
      rows.value
        .filter((row, index) => index === 0 || row.region !== rows.value[index - 1].region)
        .map((row) => row.station_id),
    ),
)
const currentCell = computed(
  () =>
    board.value?.rows.find((row) => row.station_id === selection.value?.row.station_id)?.cells[
      selection.value?.column.key
    ],
)
const peopleGroups = computed(() =>
  [
    { role: 'supervisor_manager', label: '督导组管理人员' },
    { role: 'supervisor', label: '督导组组员' },
  ].map((group) => ({
    ...group,
    people: (board.value?.inspectors || []).filter(
      (person) =>
        person.role === group.role &&
        [person.display_name, person.username]
          .join(' ')
          .toLowerCase()
          .includes(peopleKeyword.value.toLowerCase()),
    ),
  })),
)
const unavailableSelected = computed(() =>
  (currentCell.value?.assignees || []).filter(
    (person) =>
      selectedIds.value.includes(person.id) &&
      !board.value?.inspectors.some((option) => option.id === person.id),
  ),
)
const changed = computed(
  () =>
    JSON.stringify([...selectedIds.value].sort((a, b) => a - b)) !==
    JSON.stringify([...(selection.value?.originalIds || [])].sort((a, b) => a - b)),
)
const clearFilters = () => {
  keyword.value = ''
  region.value = ''
  state.value = ''
}

async function loadBoard() {
  if (disposed || blocked.value || !online.value) return
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  try {
    const response = await axios.get('/api/inspection-schedule', {
      params: coverageQuery(draft.value),
      signal: controller.signal,
      timeout: 15000,
    })
    if (disposed || ticket !== serial) return
    board.value = response.data
    if (selection.value && !currentCell.value) {
      closeCell(true)
      notice.value = '原站点已不在当前可见计划名单内，已关闭编辑，请核对站点档案。'
    }
    error.value = ''
    updatedTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    if (region.value && !regions.value.includes(region.value)) region.value = ''
    return true
  } catch (err) {
    if (disposed || ticket !== serial || err.code === 'ERR_CANCELED') return
    error.value = err.response?.data?.error || '排班表读取失败，保留上次结果，请重试。'
    if ([401, 403].includes(err.response?.status)) {
      blocked.value = true
      board.value = null
      closeCell(true)
    }
    throw err
  } finally {
    if (!disposed && ticket === serial) loading.value = false
  }
}
async function retryBoard() {
  try {
    await loadBoard()
  } catch {
    /* The panel keeps its error and retry action. */
  }
}
function copySelection() {
  if (!currentCell.value) return
  selectedIds.value = currentCell.value.assignees.map((person) => person.id)
  selection.value.originalIds = [...selectedIds.value]
  selection.value.revision = currentCell.value.revision
  saveError.value = ''
  conflict.value = false
}
async function openCell(row, column) {
  if (
    loading.value ||
    !online.value ||
    error.value ||
    blocked.value ||
    row.cells[column.key].status === 'unavailable'
  )
    return
  trigger = document.activeElement
  selection.value = { row, column }
  peopleKeyword.value = ''
  copySelection()
  await nextTick()
  if (!disposed && selection.value && !dialog.value.open) dialog.value.showModal()
}
async function closeCell(force = false) {
  if (saving.value && force !== true) return
  if (
    force !== true &&
    changed.value &&
    currentCell.value?.status !== 'completed' &&
    !window.confirm('排班调整尚未保存，确定放弃吗？')
  )
    return
  dialog.value?.close()
  selection.value = null
  await nextTick()
  if (!disposed && trigger?.isConnected) trigger.focus({ preventScroll: true })
}
function onBackdrop(event) {
  if (event.target !== dialog.value) return
  const r = dialog.value.getBoundingClientRect()
  if (
    event.clientX < r.left ||
    event.clientX > r.right ||
    event.clientY < r.top ||
    event.clientY > r.bottom
  )
    closeCell()
}
async function reloadSelection() {
  try {
    if (await loadBoard()) copySelection()
  } catch {
    /* Error remains in the panel. */
  }
}
async function saveSelection() {
  if (
    !scheduleCellEditable(currentCell.value, canEdit.value) ||
    saving.value ||
    loading.value ||
    !changed.value ||
    conflict.value
  )
    return
  saving.value = true
  saveError.value = ''
  try {
    await axios.put(
      '/api/inspection-schedule',
      {
        ...coverageQuery(draft.value),
        station_id: selection.value.row.station_id,
        column_key: selection.value.column.key,
        inspector_ids: selectedIds.value,
        revision: selection.value.revision,
      },
      { timeout: 15000 },
    )
    if (disposed) return
    notice.value = '排班已保存，暂不推送检查人待办。'
    await closeCell(true)
    await loadBoard()
  } catch (err) {
    if (disposed) return
    saveError.value =
      err.response?.data?.error || '未能确认排班保存结果，请载入最新排班后核对，避免重复覆盖。'
    conflict.value = err.response?.status === 409 || !err.response
    if (err.response?.status === 409) {
      try {
        await loadBoard()
      } catch {
        /* Keep conflict and data error visible. */
      }
    }
    if (err.response?.status === 403) {
      error.value = saveError.value
      blocked.value = true
    }
  } finally {
    saving.value = false
    polling.start()
  }
}
const polling = createAdaptivePolling({
  task: loadBoard,
  canRun: () => !disposed && !document.hidden && online.value && !blocked.value && !saving.value,
})
function visibilityChanged() {
  online.value = navigator.onLine
  if (document.hidden || !online.value) polling.pause()
  else polling.start({ immediate: true })
}
watch(
  () => JSON.stringify(coverageQuery(draft.value)),
  () => {
    serial++
    controller?.abort()
    board.value = null
    error.value = ''
    notice.value = ''
    loading.value = online.value
    clearTimeout(switchTimer)
    switchTimer = setTimeout(() => {
      loadBoard().catch(() => {})
    }, 180)
  },
)
onMounted(() => {
  loadBoard().catch(() => {})
  polling.start()
  document.addEventListener('visibilitychange', visibilityChanged)
  window.addEventListener('online', visibilityChanged)
  window.addEventListener('offline', visibilityChanged)
})
onBeforeUnmount(() => {
  disposed = true
  serial++
  controller?.abort()
  clearTimeout(switchTimer)
  polling.dispose()
  dialog.value?.close()
  document.removeEventListener('visibilitychange', visibilityChanged)
  window.removeEventListener('online', visibilityChanged)
  window.removeEventListener('offline', visibilityChanged)
})
</script>

<style scoped>
.schedule-panel {
  background: #fff;
  border: 1px solid #dbe5ef;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 12px 30px #18324c08;
  color: #203a54;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  padding: 22px 24px;
  border-bottom: 1px solid #e7edf4;
}
.panel-identity {
  display: flex;
  align-items: center;
  gap: 12px;
}
.mode-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 13px;
  background: #eaf1ff;
  color: #2a63b4;
  font-weight: 800;
}
.mode-icon.online {
  background: #e6f5f3;
  color: #29786e;
}
h3 {
  margin: 0;
  font-size: 20px;
}
.panel-identity p {
  margin: 6px 0 0;
  color: #78879b;
  font-size: 12px;
}
.period-controls {
  display: flex;
  gap: 12px;
}
.period-controls label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #62748a;
}
select,
input[type='search'] {
  min-height: 38px;
  border: 1px solid #d5e0ed;
  border-radius: 9px;
  padding: 7px 10px;
  background: #fff;
  color: #30475f;
  font: inherit;
  font-size: 13px;
}
.board-toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 24px;
  background: #fbfcff;
}
.board-stats {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 18px;
  font-size: 12px;
  color: #66788d;
}
.board-stats b {
  margin-right: 4px;
  font-size: 21px;
  color: #345a81;
}
.board-stats small {
  color: #94a1b2;
}
.sync-state {
  align-self: center;
  font-size: 11px;
  color: #71849a;
}
.sync-state em {
  font-style: normal;
  color: #b27d28;
}
.board-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 14px 24px;
}
.board-filters input {
  width: 210px;
}
.board-filters > span {
  margin-left: auto;
  font-size: 12px;
  color: #71849a;
}
.matrix-scroll {
  max-height: 620px;
  max-height: min(66vh, 720px);
  overflow: auto;
  border-block: 1px solid #dce5f0;
  scrollbar-gutter: stable;
  scroll-padding: 48px 0 0 310px;
}
.schedule-matrix {
  border-collapse: separate;
  border-spacing: 0;
  width: 100%;
  table-layout: fixed;
  min-width: 1160px;
}
.schedule-matrix.online {
  min-width: 780px;
}
.index-col {
  width: 52px;
}
.region-col {
  width: 100px;
}
.station-col {
  width: 158px;
}
.check-col {
  width: auto;
}
.schedule-matrix th,
.schedule-matrix td {
  border-bottom: 1px solid #e1e8f0;
  border-right: 1px solid #e1e8f0;
  height: 66px;
  padding: 0;
  text-align: center;
  font-size: 12px;
  font-weight: 450;
  background: #fff;
}
.schedule-matrix thead th {
  position: sticky;
  top: 0;
  z-index: 3;
  height: 48px;
  padding: 8px;
  background: #edf3fa;
  color: #42617e;
  font-weight: 750;
}
.schedule-matrix thead small {
  display: block;
  margin-top: 4px;
  font-size: 10px;
  color: #8c9bad;
  font-weight: 400;
}
.schedule-matrix .fixed-index,
.schedule-matrix .fixed-region,
.schedule-matrix .fixed-station {
  position: sticky;
  z-index: 2;
  background: #fcfdff;
}
.schedule-matrix .fixed-index {
  left: 0;
  color: #7a8b9e;
}
.schedule-matrix .fixed-region {
  left: 52px;
  padding: 8px;
}
.schedule-matrix .fixed-station {
  left: 152px;
  padding: 8px 12px;
  text-align: left;
  font-weight: 650;
  box-shadow: 3px 0 5px #18324c08;
}
.schedule-matrix thead .fixed-index,
.schedule-matrix thead .fixed-region,
.schedule-matrix thead .fixed-station {
  z-index: 5;
  background: #e8f0fa;
}
.schedule-matrix .region-start > * {
  border-top: 2px solid #becfe1;
}
.cell-button {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 5px;
  width: 100%;
  min-height: 65px;
  padding: 9px 7px;
  border: 0;
  background: transparent;
  color: #42617e;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}
.cell-names {
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.cell-button small {
  font-size: 10px;
  color: #8797a9;
}
.cell-button:hover:not(:disabled) {
  box-shadow: inset 0 0 0 2px #81a9d5;
}
.cell-button:disabled {
  cursor: default;
  opacity: 0.65;
}
.schedule-matrix .completed {
  background: #fff2be;
}
.completed .cell-button {
  color: #7d5a15;
}
.completed .cell-button small {
  color: #ad8943;
}
.schedule-matrix .assigned {
  background: #edf5ff;
}
.assigned .cell-names {
  color: #285fa4;
  font-weight: 650;
}
.schedule-matrix .unavailable {
  background: repeating-linear-gradient(-45deg, #fafbfd, #fafbfd 5px, #f1f4f7 5px, #f1f4f7 6px);
}
.panel-footer {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 24px;
  font-size: 11px;
  color: #7e8da0;
}
.panel-error,
.panel-notice {
  padding: 12px 24px;
  font-size: 13px;
  line-height: 1.7;
}
.panel-error {
  background: #fff2ee;
  color: #ac4c37;
}
.panel-notice {
  background: #eef8f3;
  color: #327359;
}
.empty-cell {
  padding: 32px !important;
  color: #8191a4;
}
.text-button {
  background: none;
  border: 0;
  color: #2866a5;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  padding: 8px;
}
.schedule-cell-dialog {
  width: min(660px, calc(100vw - 28px));
  max-width: none;
  max-height: min(860px, calc(100dvh - 28px));
  padding: 0;
  border: 1px solid #d6e1ed;
  border-radius: 20px;
  margin: auto;
  color: #203a54;
  overflow: hidden;
  box-shadow: 0 24px 80px #18324c44;
}
.schedule-cell-dialog[open] {
  display: flex;
  flex-direction: column;
}
.schedule-cell-dialog::backdrop {
  background: #182c4b66;
  backdrop-filter: blur(4px);
}
.cell-dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 22px 24px;
  border-bottom: 1px solid #e0e8f2;
  flex-shrink: 0;
  background: linear-gradient(120deg, #f1f7ff, #fff);
}
.dialog-kicker {
  color: #557da9;
  font-size: 12px;
}
.cell-dialog-head h3 {
  margin-top: 10px;
}
.dialog-close {
  background: #f1f5fa;
  color: #61778d;
  border: 0;
  border-radius: 9px;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  font-size: 26px;
  cursor: pointer;
}
.cell-dialog-body {
  min-height: 0;
  padding: 20px 24px;
  overflow: auto;
  overscroll-behavior: contain;
}
.saved-info {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid #dfe8f2;
  border-radius: 12px;
  background: #f8fbff;
}
.saved-info > span {
  color: #7e8da0;
  font-size: 11px;
}
.saved-info > strong {
  font-size: 14px;
  font-weight: 650;
}
.saved-info small {
  color: #7e8da0;
  font-size: 11px;
}
.search-people {
  display: grid;
  gap: 9px;
  margin-top: 20px;
  font-size: 13px;
  font-weight: 650;
}
.selection-count {
  font-size: 12px;
  color: #74869b;
}
.people-options {
  padding: 0;
  margin: 0;
  border: 0;
  min-width: 0;
}
.people-options h4 {
  margin: 18px 0 10px;
  font-size: 12px;
  color: #687e97;
}
.people-options h4 span {
  margin-left: 6px;
  color: #9da9b7;
}
.person-option {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #e0e7f0;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
}
.person-option.selected {
  border-color: #85b0e2;
  background: #f0f6ff;
}
.person-option input {
  width: 17px;
  height: 17px;
  accent-color: #2866b5;
}
.person-option span {
  display: grid;
  gap: 4px;
  flex: 1;
}
.person-option b {
  font-size: 13px;
  font-weight: 650;
}
.person-option small {
  font-size: 11px;
  color: #8b98a8;
}
.person-option em {
  font-size: 10px;
  color: #4776a8;
  font-style: normal;
}
.cell-dialog-footer {
  flex-shrink: 0;
  border-top: 1px solid #e1e8f0;
  padding: 14px 24px;
  background: #fff;
}
.cell-dialog-footer > div {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}
.cell-dialog-footer > div > span {
  flex: 1;
  color: #8b98a8;
  font-size: 11px;
}
.primary-button,
.secondary-button {
  min-height: 40px;
  padding: 8px 16px;
  border-radius: 9px;
  border: 1px solid #d6e1ed;
  background: #fff;
  color: #49647f;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.primary-button {
  background: #2866b5;
  border-color: #2866b5;
  color: #fff;
}
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
button:focus-visible,
input:focus-visible,
select:focus-visible,
.matrix-scroll:focus-visible {
  outline: 2px solid #70a1d6;
  outline-offset: 2px;
}
.dialog-error {
  color: #b05038;
  font-size: 12px;
  line-height: 1.7;
  margin: 0 0 10px;
}
.completion-note {
  padding: 14px;
  background: #fff7d7;
  border: 1px solid #efda8c;
  border-radius: 12px;
  margin-bottom: 14px;
}
.completion-note strong {
  font-size: 14px;
  color: #8a681f;
}
.completion-note p {
  font-size: 12px;
  line-height: 1.8;
  color: #9b814b;
}
.people-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.people-tags span {
  padding: 6px 10px;
  border-radius: 7px;
  border: 1px solid #eddda8;
  background: #fffaf0;
  font-size: 12px;
}
.people-tags small {
  color: #a59472;
}
.readonly-note,
.no-people {
  font-size: 12px;
  color: #7c8da2;
  line-height: 1.8;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
@media (max-width: 760px) {
  .panel-head {
    align-items: stretch;
    flex-direction: column;
    gap: 16px;
    padding: 18px 16px;
  }
  .period-controls {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .period-controls label {
    display: grid;
    gap: 6px;
  }
  .board-toolbar,
  .board-filters {
    padding: 12px 16px;
  }
  .board-stats {
    gap: 12px;
  }
  .board-stats b {
    font-size: 18px;
  }
  .board-stats small {
    width: 100%;
  }
  .board-filters input {
    width: 100%;
  }
  .board-filters select {
    flex: 1;
    min-width: 0;
  }
  .matrix-scroll {
    max-height: 65vh;
    scroll-padding-left: 234px;
  }
  .schedule-matrix {
    min-width: 1030px;
  }
  .index-col {
    width: 38px;
  }
  .region-col {
    width: 76px;
  }
  .station-col {
    width: 120px;
  }
  .check-col {
    width: auto;
  }
  .schedule-matrix .fixed-region {
    left: 38px;
  }
  .schedule-matrix .fixed-station {
    left: 114px;
  }
  .schedule-matrix.online {
    min-width: 630px;
  }
  .panel-footer {
    padding: 12px 16px;
  }
  .cell-dialog-head,
  .cell-dialog-body,
  .cell-dialog-footer {
    padding: 16px;
  }
  .cell-dialog-footer > div > span {
    flex-basis: 100%;
  }
  .schedule-cell-dialog {
    width: calc(100vw - 16px);
    max-height: calc(100dvh - 16px);
    border-radius: 15px;
  }
  h3 {
    font-size: 18px;
  }
}
</style>
