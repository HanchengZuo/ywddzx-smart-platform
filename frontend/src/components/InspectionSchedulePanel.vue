<template>
  <section
    :id="'schedule-panel-' + mode"
    class="schedule-panel"
    :class="mode"
    role="tabpanel"
    :aria-labelledby="'schedule-tab-' + mode"
  >
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
          >年份<select
            v-model.number="draft.year"
            :disabled="shelfSaving"
            :aria-label="title + '年份'"
          >
            <option v-for="year in years" :key="year" :value="year">{{ year }}年</option>
          </select></label
        ><label v-if="mode === 'offline'"
          >季度<select
            v-model.number="draft.quarter"
            :disabled="shelfSaving"
            aria-label="现场检查季度"
          >
            <option v-for="quarter in 4" :key="quarter" :value="quarter">
              第{{ quarter }}季度
            </option>
          </select></label
        ><label v-else
          >月份<select
            v-model.number="draft.month"
            :disabled="shelfSaving"
            aria-label="视频检查月份"
          >
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
        <option value="">全部片区</option>
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
    <div v-if="board?.can_edit" class="bulk-toolbar">
      <button
        type="button"
        class="secondary-button"
        :aria-pressed="multiSelect"
        :disabled="loading || shelfSaving || !!error"
        @click="toggleMulti"
      >
        {{ multiSelect ? '退出多选' : '多选排班' }}
      </button>
      <template v-if="multiSelect"
        ><span
          >已选 <b>{{ selectedCells.length }}</b> 格；按站点整行选择</span
        ><button
          type="button"
          class="primary-button"
          :disabled="!selectedCells.length || loading || shelfSaving || !!error"
          @click="openBulk(false)"
        >
          统一安排</button
        ><button
          v-if="clipboard"
          type="button"
          class="secondary-button"
          :disabled="!selectedCells.length || loading || shelfSaving || !!error"
          @click="openBulk(true)"
        >
          粘贴安排</button
        ><button
          v-if="selectedCells.length"
          type="button"
          class="text-button"
          @click="selectedCells = []"
        >
          清空选择
        </button></template
      >
      <span v-else>{{
        mode === 'offline'
          ? '整站安排一个外勤组，实际检查结果独立保留。'
          : '每站一人，安全、计量、现场整行统一安排。'
      }}</span>
      <button type="button" class="secondary-button" @click="openShelf">
        今日调度待选区（{{ shelf.length }}）
      </button>
      <button
        type="button"
        class="secondary-button"
        :disabled="loading || shelfSaving || (!hasTodayPlans && !shelf.length) || !canEdit"
        @click="clearToday"
      >
        一键清空今日{{ mode === 'offline' ? '现场' : '视频' }}排班
      </button>
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
    <div class="matrix-content" :aria-busy="loading">
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
              {{ column.label }}<small v-if="!column.table_id">未启用或定义异常</small>
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
                    : '当前没有纳入本计划的名单站点。'
              }}
            </td>
          </tr>
          <tr
            v-for="row in rows"
            :key="row.station_id"
            class="station-row"
            :class="{ 'region-start': row.sequence === 1 || regionStarts.has(row.station_id) }"
            @dragover.prevent
            @drop.prevent="dropOn(row, $event)"
          >
            <td class="fixed-index">{{ row.sequence }}</td>
            <td class="fixed-region">{{ row.region }}</td>
            <th scope="row" class="fixed-station">
              <label class="station-choice"
                ><input
                  v-if="multiSelect"
                  type="checkbox"
                  :checked="rowSelected(row)"
                  :aria-label="'选择' + row.station_name + '全部可编辑项'"
                  @change="selectRow(row)"
                />{{ row.station_name }}</label
              >
            </th>
            <td
              v-for="column in board.columns"
              :key="column.key"
              :class="[
                'matrix-cell',
                row.cells[column.key].status,
                { 'is-self': !!scheduleSelfRole(row.cells[column.key], board.current_user_id) },
              ]"
              @dragover.prevent
              @drop.stop.prevent="dropOn(row, $event)"
            >
              <button
                type="button"
                class="cell-button"
                :draggable="
                  canEdit && row.cells[column.key].status === 'assigned' && !loading && !shelfSaving
                "
                @dragstart="startAssignmentDrag($event, row)"
                @dragend="dragged = null"
                :class="{ selected: multiSelect && selectedCells.includes(cellKey(row, column)) }"
                :aria-pressed="
                  multiSelect ? selectedCells.includes(cellKey(row, column)) : undefined
                "
                :disabled="
                  loading ||
                  shelfSaving ||
                  !online ||
                  !!error ||
                  blocked ||
                  row.cells[column.key].status === 'unavailable' ||
                  (multiSelect && row.cells[column.key].status === 'completed')
                "
                :aria-label="`${row.station_name}，${column.label}，${scheduleStatusLabels[row.cells[column.key].status]}${inspectorPreview(row.cells[column.key]) ? '，' + inspectorPreview(row.cells[column.key]) : ''}`"
                @click="multiSelect ? selectRow(row) : openCell(row, column)"
              >
                <span class="mobile-column-label" aria-hidden="true">{{ column.label }}</span>
                <span
                  v-if="scheduleSelfRole(row.cells[column.key], board.current_user_id)"
                  class="self-badge"
                  >{{ scheduleSelfRole(row.cells[column.key], board.current_user_id) }}</span
                >
                <span class="cell-names">{{
                  (mode === 'offline' && row.cells[column.key].status === 'assigned'
                    ? row.cells[column.key].plan_team?.name
                    : '') ||
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
                  >{{ row.cells[column.key].scheduled_date || '待补计划日期'
                  }}{{ canEdit ? ' · 调整' : '' }}</small
                >
                <small
                  v-if="
                    row.cells[column.key].status === 'completed' &&
                    row.cells[column.key].assignees.length
                  "
                  class="original-plan"
                >
                  计划：{{
                    row.cells[column.key].plan_team?.name ||
                    row.cells[column.key].assignees.map((p) => p.display_name).join('、')
                  }}
                </small>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <footer class="panel-footer">
      <span>{{ board?.period.label || '当前周期' }} · 保留名单序号和顺序，黄色单元格不可改派。</span
      ><span>{{
        canEdit
          ? mode === 'offline'
            ? '点击任一未检查格安排整行外勤组'
            : '点击任一未检查格安排整站一位检查人'
          : '当前为只读查看'
      }}</span>
    </footer>
    <aside
      v-if="shelfOpen && canEdit"
      class="dispatch-shelf"
      @dragover.prevent
      @drop.prevent="stageDragged"
    >
      <header>
        <div>
          <strong>今日调度待选区</strong
          ><small>{{ mode === 'offline' ? '外勤组 · 整站改派' : '视频 · 整站同人改派' }}</small>
        </div>
        <button type="button" aria-label="收起今日调度待选区" @click="shelfOpen = false">×</button>
      </header>
      <p>
        仅调度今日计划：拖入后整站未检查项一起撤下，拖回目标站整行直接保存，也可点选卡片再点目标位置。今日全局共享，跨日自动清空；一键清空今日排班也会清空本区，调度留痕和实际检查记录保留。
      </p>
      <div
        v-for="item in shelf"
        :key="item.key"
        class="shelf-item"
        role="button"
        tabindex="0"
        :aria-pressed="pickedShelf === item.key"
        :class="{ picked: pickedShelf === item.key }"
        draggable="true"
        @dragstart="startShelfDrag($event, item)"
        @dragend="dragged = null"
        @click="pickedShelf = pickedShelf === item.key ? null : item.key"
        @keydown.enter.self="pickedShelf = pickedShelf === item.key ? null : item.key"
        @keydown.space.self.prevent="pickedShelf = pickedShelf === item.key ? null : item.key"
      >
        <strong>{{ item.name }}</strong
        ><small>{{ item.day }} · {{ item.sourceName || '新增安排' }}</small>
        <button type="button" aria-label="移除待选安排" @click.stop="removeShelf(item.key)">
          ×
        </button>
      </div>
      <p v-if="!shelf.length">
        将任一已排班格拖到这里，整行{{ mode === 'offline' ? '现场' : '视频' }}计划会一起移入待选区。
      </p>
      <button v-if="pickedShelf" type="button" @click="pickedShelf = null">取消选中卡片</button>
      <span v-if="shelfSaving" role="status">正在原子保存改派…</span>
    </aside>
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
              <h3 :id="dialogId">
                {{
                  bulkEdits.length
                    ? '整站排班 · ' + new Set(bulkEdits.map((e) => e.station_id)).size + ' 个站点'
                    : selection.row.region + ' · ' + selection.row.station_name
                }}
              </h3>
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
            <div v-if="!bulkEdits.length" class="saved-info">
              <span>{{ currentCell.status === 'completed' ? '原排班人员' : '当前保存排班' }}</span
              ><strong>{{
                currentCell.assignees.map((person) => person.display_name).join('、') || '尚未分配'
              }}</strong
              ><small v-if="currentCell.updated_at"
                >{{ currentCell.updated_by_name }} · {{ currentCell.updated_at }} 保存</small
              >
            </div>
            <template v-if="scheduleCellEditable(currentCell, canEdit)">
              <p v-if="bulkEdits.length" class="readonly-note">
                统一更新所选单元格的日期和检查人；任一格已完成、档期变化或存在并发修改时，整批不保存。
              </p>
              <label class="search-people"
                >计划日期<select
                  v-model="plannedDate"
                  :disabled="saving || conflict"
                  aria-label="排班计划日期"
                  @change="loadPeople"
                >
                  <option value="">请选择工作日</option>
                  <option v-for="day in dateOptions" :key="day.day" :value="day.day">
                    {{ day.day }} {{ day.weekday }}
                  </option>
                </select></label
              >
              <p v-if="!dateOptions.length" class="dialog-error">
                当前周期没有已发布的未来工作日，只能取消已有排班，不能新派工。
              </p>
              <p v-if="peopleLoading" class="readonly-note" role="status">
                正在核对所选日期的人员档期…
              </p>
              <p v-if="peopleError" class="dialog-error" role="alert">{{ peopleError }}</p>
              <label class="search-people"
                >选择检查人<input
                  v-model.trim="peopleKeyword"
                  type="search"
                  placeholder="搜索姓名或用户名"
                  aria-label="搜索检查人"
                  :disabled="saving || conflict || peopleLoading"
              /></label>
              <p class="selection-count">
                {{
                  mode === 'offline'
                    ? '选择完整外勤组，应用至所选站点全部未检查项。'
                    : '选择一位检查人，统一安排所选站点安全、计量、现场的未检查项。'
                }}
                清空后保存即取消计划，实际记录不变。
              </p>
              <fieldset
                v-if="mode === 'offline'"
                class="field-team-options"
                :disabled="saving || conflict || peopleLoading || !!peopleError"
              >
                <label
                  v-for="group in fieldGroups"
                  :key="group.leader_id"
                  class="team-choice"
                  :class="{
                    selected: sameIds(
                      selectedIds,
                      group.members.map((p) => p.id),
                    ),
                  }"
                >
                  <input
                    type="radio"
                    name="field-team"
                    :checked="
                      sameIds(
                        selectedIds,
                        group.members.map((p) => p.id),
                      )
                    "
                    :disabled="
                      !group.members.every((p) =>
                        personCanSchedule(availablePeople.find((a) => a.id === p.id) || {}, mode),
                      )
                    "
                    @change="selectedIds = group.members.map((p) => p.id)"
                  />
                  <span
                    ><b>{{ group.name }}</b
                    ><small>{{ group.members.map((p) => p.display_name).join('、') }}</small></span
                  >
                </label>
                <p v-if="!fieldGroups.length">此日期未保存外勤组，请先在人员档期安排。</p>
              </fieldset>
              <button
                v-if="selectedIds.length"
                type="button"
                class="text-button"
                :disabled="saving || conflict"
                @click="selectedIds = []"
              >
                清空本次选择 / 取消计划
              </button>
              <fieldset
                v-if="mode === 'online'"
                :disabled="saving || conflict || peopleLoading || !!peopleError"
                class="people-options"
              >
                <section v-for="group in peopleGroups" :key="group.role">
                  <h4>
                    {{ group.label }} <span>{{ group.people.length }}</span>
                  </h4>
                  <label
                    v-for="person in group.people"
                    :key="person.id"
                    class="person-option"
                    :class="{ selected: selectedIds.includes(person.id) }"
                    ><input
                      type="radio"
                      name="video-inspector"
                      :checked="selectedIds.includes(person.id)"
                      :value="person.id"
                      :disabled="!personCanSchedule(person, mode)"
                      @change="selectedIds = [person.id]"
                    /><span
                      ><b>{{ person.display_name }}</b
                      ><small
                        >{{ person.username }} · {{ availabilityLabel(person, mode) }}</small
                      ></span
                    ><em v-if="selectedIds.includes(person.id)">已选</em></label
                  >
                </section>
                <p v-if="!peopleGroups.some((group) => group.people.length)" class="no-people">
                  没有匹配的启用督导组账号。
                </p>
              </fieldset>
              <p v-if="unavailableSelected.length" class="dialog-error">
                所选人员当前不可派工：{{
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
              <span>保存后同步个人巡检待办</span
              ><button type="button" class="secondary-button" :disabled="saving" @click="closeCell">
                关闭</button
              ><button
                v-if="stageableSelection"
                type="button"
                class="secondary-button"
                :disabled="saving || changed"
                @click="stageCurrentSelection"
              >
                加入今日调度待选区
              </button>
              <button
                v-if="stageableSelection"
                type="button"
                class="secondary-button"
                :disabled="saving || changed"
                @click="copyArrangement"
              >
                复制此安排</button
              ><button
                v-if="conflict && currentCell.status !== 'completed'"
                type="button"
                class="primary-button"
                :disabled="loading"
                @click="reloadSelection"
              >
                {{ bulkEdits.length ? '关闭并重新选择' : '载入最新排班' }}</button
              ><button
                v-else-if="scheduleCellEditable(currentCell, canEdit)"
                type="button"
                class="primary-button"
                :disabled="
                  saving ||
                  loading ||
                  !changed ||
                  !!unavailableSelected.length ||
                  (selectedIds.length > 0 && (peopleLoading || !!peopleError || !plannedDate))
                "
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
import {
  computed,
  nextTick,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  ref,
  useId,
  watch,
} from 'vue'
import { createAdaptivePolling } from '@/utils/adaptivePolling'
import { coverageQuery, currentCoveragePeriod } from '@/utils/schedulingCoverage'
import {
  cellKey,
  personCanSchedule,
  availabilityLabel,
  scheduleSelfRole,
} from '@/utils/staffScheduling'
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
const multiSelect = ref(false),
  selectedCells = ref([]),
  bulkEdits = ref([]),
  clipboard = ref(null)
const plannedDate = ref(''),
  fieldGroups = ref([]),
  availablePeople = ref([]),
  peopleLoading = ref(false),
  peopleError = ref('')
let peopleController,
  peopleSerial = 0
const dateOptions = computed(() =>
  (board.value?.workdays || []).filter((day) => day.day >= board.value.today),
)
let controller,
  disposed = false,
  active = false,
  lastSyncedAt = 0,
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
const currentCell = computed(() =>
  bulkEdits.value.length
    ? { status: 'assigned', assignees: [], revision: 0 }
    : board.value?.rows.find((row) => row.station_id === selection.value?.row.station_id)?.cells[
        selection.value?.column.key
      ],
)
const peopleGroups = computed(() =>
  [
    { role: 'supervisor_manager', label: '督导组管理人员' },
    { role: 'supervisor', label: '督导组组员' },
  ].map((group) => ({
    ...group,
    people: availablePeople.value.filter(
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
  peopleLoading.value || peopleError.value
    ? []
    : selectedIds.value
        .map(
          (id) =>
            availablePeople.value.find((p) => p.id === id) ||
            board.value?.inspectors.find((p) => p.id === id) || { id, display_name: '原账号' },
        )
        .filter((p) => !personCanSchedule(p, props.mode)),
)
const changed = computed(() => {
  const selected = JSON.stringify([...selectedIds.value].sort((a, b) => a - b))
  if (bulkEdits.value.length)
    return bulkEdits.value.some((edit) => {
      const cell = board.value?.rows.find((row) => row.station_id === edit.station_id)?.cells[
        edit.column_key
      ]
      return (
        JSON.stringify((cell?.assignees || []).map((p) => p.id).sort((a, b) => a - b)) !==
          selected ||
        (selectedIds.value.length > 0 && cell?.scheduled_date !== plannedDate.value)
      )
    })
  return (
    selected !== JSON.stringify([...(selection.value?.originalIds || [])].sort((a, b) => a - b)) ||
    (selectedIds.value.length > 0 && plannedDate.value !== selection.value?.originalDate)
  )
})
function toggleMulti() {
  multiSelect.value = !multiSelect.value
  selectedCells.value = []
}
function editableRowKeys(row) {
  return board.value.columns
    .filter((c) => scheduleCellEditable(row.cells[c.key], canEdit.value))
    .map((c) => cellKey(row, c))
}
function rowSelected(row) {
  const keys = editableRowKeys(row)
  return keys.length > 0 && keys.every((key) => selectedCells.value.includes(key))
}
function selectKeys(keys) {
  if (keys.every((key) => selectedCells.value.includes(key)))
    selectedCells.value = selectedCells.value.filter((v) => !keys.includes(v))
  else selectedCells.value = [...new Set([...selectedCells.value, ...keys])]
}
function selectRow(row) {
  selectKeys(editableRowKeys(row))
}
const sameIds = (a, b) =>
  JSON.stringify([...a].sort((x, y) => x - y)) === JSON.stringify([...b].sort((x, y) => x - y))
const shelfOpen = ref(false),
  shelf = ref([]),
  pickedShelf = ref(null),
  dragged = ref(null),
  shelfSaving = ref(false)
const stageableSelection = computed(() => {
  if (!canEdit.value || !selection.value) return false
  if (bulkEdits.value.length && new Set(bulkEdits.value.map((e) => e.station_id)).size !== 1)
    return false
  return !!planPayload(selection.value.row)
})
const hasTodayPlans = computed(() =>
  (board.value?.rows || []).some((row) =>
    Object.values(row.cells).some(
      (cell) => cell.status === 'assigned' && cell.scheduled_date === board.value.today,
    ),
  ),
)
function targetCells(row) {
  const columns = board.value.columns.filter((c) =>
    scheduleCellEditable(row.cells[c.key], canEdit.value),
  )
  return columns.map((c) => ({
    station_id: row.station_id,
    column_key: c.key,
    revision: row.cells[c.key].revision,
  }))
}
function planPayload(row) {
  const cells = targetCells(row)
  const first = cells.map((c) => row.cells[c.column_key]).find((c) => c.status === 'assigned')
  if (!first) return null
  if (
    cells.some(
      (c) =>
        row.cells[c.column_key].assignees.length &&
        row.cells[c.column_key].scheduled_date !== board.value.today,
    )
  )
    return null
  return {
    kind: 'plan',
    cells,
    name: first.plan_team?.name || first.assignees.map((p) => p.display_name).join('、'),
  }
}
function openShelf() {
  shelfOpen.value = true
}
async function stageAssignment(row) {
  const item = planPayload(row)
  if (item) await runDispatch('park', { cells: item.cells })
}
async function stageCurrentSelection() {
  if (!selection.value) return
  const { row } = selection.value
  await closeCell(true)
  await stageAssignment(row)
}
function startAssignmentDrag(event, row) {
  const item = canEdit.value && !loading.value && !shelfSaving.value && planPayload(row)
  if (!item) {
    event.preventDefault()
    return
  }
  dragged.value = item
  shelfOpen.value = true
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/x-inspection-dispatch', JSON.stringify(item))
  event.dataTransfer.setData('text/plain', item.name)
}
function startShelfDrag(event, item) {
  if (shelfSaving.value || loading.value) {
    event.preventDefault()
    return
  }
  dragged.value = { ...item, kind: 'shelf' }
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/x-inspection-dispatch', JSON.stringify(dragged.value))
  event.dataTransfer.setData('text/plain', item.name)
}
function dragPayload(event) {
  if (dragged.value) return dragged.value
  try {
    return JSON.parse(event?.dataTransfer?.getData('application/x-inspection-dispatch') || 'null')
  } catch {
    return null
  }
}
async function stageDragged(event) {
  const item = dragPayload(event)
  if (item?.kind === 'plan') await runDispatch('park', { cells: item.cells })
}
async function removeShelf(key) {
  const item = shelf.value.find((s) => s.key === key)
  if (!item || !window.confirm('移除这条待选安排？不会恢复原站点派工，调度历史仍会保留。')) return
  if (item) await runDispatch('discard', { shelf_id: item.id, revision: item.revision })
}
async function dropOn(row, event) {
  const item = dragPayload(event) || shelf.value.find((s) => s.key === pickedShelf.value)
  if (!item) return
  if (item.kind === 'plan') {
    notice.value = '请先将今日计划拖入今日调度待选区，再选择目标站点。'
    return
  }
  const cells = targetCells(row)
  if (cells.length)
    await runDispatch('place', { shelf_id: item.id, revision: item.revision, cells })
}
async function clearToday() {
  await runDispatch('clear_today', { board_token: board.value.board_token })
}
async function runDispatch(action, payload) {
  if (!canEdit.value || loading.value || shelfSaving.value || saving.value) return
  serial++
  controller?.abort()
  polling.pause()
  shelfSaving.value = true
  try {
    const { data } = await axios.post(
      '/api/inspection-schedule/dispatch',
      { ...coverageQuery(draft.value), action, ...payload },
      { timeout: 120000 },
    )
    if (disposed) return
    board.value = data.board
    shelf.value = data.board.shelf || []
    selectedCells.value = []
    pickedShelf.value = null
    error.value = ''
    notice.value = data.message
    lastSyncedAt = Date.now()
    updatedTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    if (action === 'park' || action === 'clear_today') shelfOpen.value = true
    window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
  } catch (err) {
    if (disposed) return
    notice.value = err.response?.data?.error || '无法确认改派结果，请核对最新表格后重试。'
    await retryBoard()
  } finally {
    shelfSaving.value = false
    dragged.value = null
    polling.start()
  }
}
async function openBulk(paste = false) {
  const cells = []
  for (const row of rows.value)
    for (const column of board.value.columns) {
      if (
        selectedCells.value.includes(cellKey(row, column)) &&
        scheduleCellEditable(row.cells[column.key], canEdit.value)
      )
        cells.push({
          station_id: row.station_id,
          column_key: column.key,
          revision: row.cells[column.key].revision,
        })
    }
  if (!cells.length) return
  trigger = document.activeElement
  bulkEdits.value = cells
  selection.value = {
    row: board.value.rows.find((row) => row.station_id === cells[0].station_id),
    column: board.value.columns.find((c) => c.key === cells[0].column_key),
    originalIds: [],
  }
  selectedIds.value = paste ? [...clipboard.value.ids] : []
  plannedDate.value =
    paste && dateOptions.value.some((day) => day.day === clipboard.value.day)
      ? clipboard.value.day
      : dateOptions.value[0]?.day || ''
  saveError.value = ''
  conflict.value = false
  peopleKeyword.value = ''
  await nextTick()
  dialog.value.showModal()
  loadPeople()
}
async function copyArrangement() {
  clipboard.value = {
    ids: [...selectedIds.value],
    day: plannedDate.value,
  }
  await closeCell(true)
  multiSelect.value = true
  selectedCells.value = []
  notice.value = '已复制检查人和日期。请选择目标站点行，再点击“粘贴安排”；保存前会再次核对档期。'
}
async function loadPeople() {
  const ticket = ++peopleSerial
  peopleController?.abort()
  availablePeople.value = []
  fieldGroups.value = []
  peopleError.value = ''
  if (
    !selection.value ||
    !plannedDate.value ||
    !canEdit.value ||
    currentCell.value?.status === 'completed'
  ) {
    peopleLoading.value = false
    return
  }
  peopleController = new AbortController()
  peopleLoading.value = true
  try {
    const { data } = await axios.get('/api/inspection-schedule/available-people', {
      params: { day: plannedDate.value },
      signal: peopleController.signal,
      timeout: 15000,
    })
    if (ticket === peopleSerial && !disposed) {
      availablePeople.value = data.people
      fieldGroups.value = (data.groups || []).filter((g) => g.mode === 'offline')
    }
  } catch (err) {
    if (ticket === peopleSerial && !disposed && err.code !== 'ERR_CANCELED')
      peopleError.value = err.response?.data?.error || '档期核对失败，请重新选择日期重试。'
  } finally {
    if (ticket === peopleSerial) peopleLoading.value = false
  }
}
const clearFilters = () => {
  keyword.value = ''
  region.value = ''
  state.value = ''
}

async function loadBoard() {
  if (disposed || !active || blocked.value || !online.value) return
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
    shelf.value = response.data.shelf || []
    if (!shelf.value.some((item) => item.key === pickedShelf.value)) pickedShelf.value = null
    if (!board.value.can_edit) {
      multiSelect.value = false
      selectedCells.value = []
    }
    if (selection.value && !currentCell.value) {
      closeCell(true)
      notice.value = '原站点已不在当前可见计划名单内，已关闭编辑，请核对站点档案。'
    }
    error.value = ''
    lastSyncedAt = Date.now()
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
  selection.value.originalDate = currentCell.value.scheduled_date
  plannedDate.value = dateOptions.value.some((day) => day.day === currentCell.value.scheduled_date)
    ? currentCell.value.scheduled_date
    : dateOptions.value[0]?.day || ''
  saveError.value = ''
  conflict.value = false
}
async function openCell(row, column) {
  if (pickedShelf.value) {
    await dropOn(row)
    return
  }
  if (
    loading.value ||
    shelfSaving.value ||
    !online.value ||
    error.value ||
    blocked.value ||
    row.cells[column.key].status === 'unavailable'
  )
    return
  trigger = document.activeElement
  bulkEdits.value = []
  selection.value = { row, column }
  peopleKeyword.value = ''
  copySelection()
  if (scheduleCellEditable(row.cells[column.key], canEdit.value)) {
    bulkEdits.value = board.value.columns
      .filter((c) => scheduleCellEditable(row.cells[c.key], canEdit.value))
      .map((c) => ({
        station_id: row.station_id,
        column_key: c.key,
        revision: row.cells[c.key].revision,
      }))
  }
  loadPeople()
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
  peopleSerial++
  peopleController?.abort()
  peopleLoading.value = false
  selection.value = null
  bulkEdits.value = []
  polling.start()
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
  if (bulkEdits.value.length) {
    await closeCell(true)
    await retryBoard()
    selectedCells.value = []
    notice.value = '已载入最新排班，请重新选择需要批量调整的单元格。'
    return
  }
  try {
    if (await loadBoard()) {
      copySelection()
      loadPeople()
    }
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
    conflict.value ||
    (selectedIds.value.length &&
      (peopleLoading.value ||
        peopleError.value ||
        !plannedDate.value ||
        unavailableSelected.value.length))
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
        scheduled_date: plannedDate.value,
        ...(bulkEdits.value.length ? { cells: bulkEdits.value } : {}),
      },
      { timeout: 60000 },
    )
    if (disposed) return
    notice.value = '排班已保存，已同步检查人的巡检待办。'
    selectedCells.value = []
    window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
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
  canRun: () =>
    active &&
    !disposed &&
    !document.hidden &&
    online.value &&
    !blocked.value &&
    !saving.value &&
    !shelfSaving.value &&
    !dialog.value?.open,
})
function visibilityChanged() {
  online.value = navigator.onLine
  if (!active || document.hidden || !online.value) polling.pause()
  else polling.start({ immediate: true })
}
watch(
  () => JSON.stringify(coverageQuery(draft.value)),
  () => {
    serial++
    controller?.abort()
    board.value = null
    selectedCells.value = []
    clipboard.value = null
    shelf.value = []
    pickedShelf.value = null
    dragged.value = null
    error.value = ''
    notice.value = ''
    loading.value = online.value
    clearTimeout(switchTimer)
    switchTimer = setTimeout(() => {
      loadBoard().catch(() => {})
    }, 180)
  },
)
watch([keyword, region, state], () => {
  selectedCells.value = []
})
onMounted(() => {
  document.addEventListener('visibilitychange', visibilityChanged)
  window.addEventListener('online', visibilityChanged)
  window.addEventListener('offline', visibilityChanged)
})
onActivated(() => {
  active = true
  online.value = navigator.onLine
  if (!shelfSaving.value && (!board.value || error.value || Date.now() - lastSyncedAt >= 60000)) {
    loadBoard().catch(() => {})
  }
  polling.start()
})
onDeactivated(() => {
  active = false
  serial++
  controller?.abort()
  peopleSerial++
  peopleController?.abort()
  clearTimeout(switchTimer)
  loading.value = false
  polling.pause()
  closeCell(true)
})
onBeforeUnmount(() => {
  disposed = true
  serial++
  controller?.abort()
  peopleSerial++
  peopleController?.abort()
  clearTimeout(switchTimer)
  polling.dispose()
  dialog.value?.close()
  document.removeEventListener('visibilitychange', visibilityChanged)
  window.removeEventListener('online', visibilityChanged)
  window.removeEventListener('offline', visibilityChanged)
})
</script>

<style scoped>
.matrix-cell.is-self .cell-button {
  outline: 2px solid #12858a;
  outline-offset: -3px;
}
.self-badge {
  display: inline-block;
  align-self: center;
  max-width: 100%;
  border-radius: 5px;
  padding: 2px 5px;
  background: #c9f2eb;
  color: #075e63;
  font-size: 10px;
  line-height: 1.5;
}
.assigned .cell-button[draggable='true'] {
  cursor: grab;
}
.original-plan {
  color: #80632d;
  border-top: 1px dashed #dfc88d;
  padding-top: 4px;
}
.dispatch-shelf {
  position: fixed;
  right: 20px;
  bottom: 18px;
  width: min(310px, calc(100vw - 28px));
  max-height: 55dvh;
  overflow: auto;
  z-index: 105;
  border: 1px solid #a8bbd2;
  border-radius: 15px;
  padding: 15px;
  background: #f8fbff;
  box-shadow: 0 14px 50px #15334c30;
}
.dispatch-shelf header {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 10px;
  color: #173d63;
}
.dispatch-shelf header small {
  display: block;
  margin-top: 5px;
  color: #617e9d;
  font-size: 11px;
}
.dispatch-shelf p {
  font-size: 11px;
  color: #667f99;
  line-height: 1.7;
}
.dispatch-shelf button {
  border: 1px solid #c5d4e4;
  border-radius: 6px;
  color: #416381;
  background: white;
  cursor: pointer;
}
.shelf-item {
  position: relative;
  padding: 12px 30px 12px 12px;
  margin: 8px 0;
  border: 1px solid #c3d4e4;
  border-radius: 9px;
  background: white;
  cursor: grab;
  color: #264e74;
  font-size: 12px;
}
.shelf-item.picked {
  border-color: #2978b2;
  box-shadow: 0 0 0 2px #2978b22a;
}
.shelf-item small {
  display: block;
  margin-top: 5px;
  font-size: 10px;
  color: #6d849b;
}
.shelf-item button {
  position: absolute;
  right: 7px;
  top: 9px;
}
.field-team-options {
  display: grid;
  gap: 9px;
  margin: 10px 0;
  border: 0;
  padding: 0;
}
.team-choice {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid #dbc79d;
  border-radius: 10px;
  background: #fffaf0;
  cursor: pointer;
}
.team-choice.selected {
  border-color: #bb8426;
  background: #fff0ce;
}
.team-choice small {
  display: block;
  color: #8c7142;
  margin-top: 5px;
  line-height: 1.7;
}
.schedule-panel {
  --mode-ink: #8a5015;
  --mode-fill: #ffedc9;
  --mode-border: #dca54d;
  background: #fff;
  border: 1px solid #cbd9e7;
  border-radius: 20px;
  min-width: 0;
  scroll-margin-top: calc(
    var(--schedule-mobile-topbar, 0px) + var(--schedule-switcher-height, 76px) + 12px
  );
  box-shadow: 0 12px 30px #18324c08;
  color: #203a54;
}
.schedule-panel.online {
  --mode-ink: #2056a3;
  --mode-fill: #deebff;
  --mode-border: #77a3e1;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  padding: 22px 24px;
  border-bottom: 1px solid #e7edf4;
  border-radius: 20px 20px 0 0;
  background: linear-gradient(110deg, #f0f5fa, #fff);
  border-top: 3px solid var(--mode-border);
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
  background: #ffedc9;
  color: #8a5015;
  font-weight: 800;
}
.mode-icon.online {
  background: #deebff;
  color: #2056a3;
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
.board-stats > span {
  padding: 7px 12px;
  border-radius: 7px;
  background: #eef3f8;
  border-left: 3px solid #899cb1;
}
.board-stats > span:first-child {
  background: #fff1b8;
  border-color: #d2a322;
}
.board-stats > span:nth-child(2) {
  background: var(--mode-fill);
  border-color: var(--mode-border);
}
.board-stats > span:nth-child(2) b {
  color: var(--mode-ink);
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
.bulk-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 24px;
  background: #f2f7fd;
  border-top: 1px solid #e0e9f4;
  font-size: 12px;
  color: #6c829c;
}
.bulk-toolbar .primary-button,
.bulk-toolbar .secondary-button {
  min-height: 34px;
  font-size: 12px;
  padding: 6px 12px;
}
.station-choice {
  display: flex;
  align-items: center;
  gap: 6px;
}
.station-choice input {
  margin: 0;
  accent-color: #2866b5;
  flex-shrink: 0;
}
.cell-button.selected {
  box-shadow: inset 0 0 0 2px #2866b5;
  background: #dcecff;
}
.matrix-content {
  border-block: 1px solid #dce5f0;
}
.schedule-matrix {
  border-collapse: separate;
  border-spacing: 0;
  width: 100%;
  table-layout: fixed;
  overflow-wrap: anywhere;
}
.index-col {
  width: 44px;
}
.region-col {
  width: 78px;
}
.station-col {
  width: 130px;
}
.check-col {
  width: auto;
}
.schedule-matrix th,
.schedule-matrix td {
  border-bottom: 1px solid #e1e8f0;
  border-right: 1px solid #e1e8f0;
  height: 56px;
  padding: 0;
  text-align: center;
  font-size: 12px;
  font-weight: 450;
  background: #fff;
}
.schedule-matrix thead th {
  position: sticky;
  top: calc(var(--schedule-sticky-top, 0px) + var(--schedule-switcher-height, 76px));
  z-index: 3;
  height: 48px;
  padding: 8px;
  background: #173c59;
  color: #fff;
  font-weight: 750;
  box-shadow: 0 2px #1c6680;
  border-color: #31526c;
}
.schedule-matrix thead small {
  display: block;
  margin-top: 4px;
  font-size: 10px;
  color: #c8d9e7;
  font-weight: 400;
}
.schedule-matrix .fixed-index,
.schedule-matrix .fixed-region,
.schedule-matrix .fixed-station {
  background: #fcfdff;
}
.schedule-matrix .fixed-index {
  color: #7a8b9e;
  font-variant-numeric: tabular-nums;
}
.schedule-matrix .fixed-region {
  padding: 8px;
  color: #687f98;
}
.schedule-matrix .fixed-station {
  padding: 8px 12px;
  text-align: left;
  font-weight: 650;
}
.schedule-matrix thead .fixed-index,
.schedule-matrix thead .fixed-region,
.schedule-matrix thead .fixed-station {
  z-index: 5;
  background: #14334d;
  color: #d5e3ee;
}
.schedule-matrix .region-start > * {
  border-top: 2px solid #becfe1;
}
.station-row:hover > .fixed-index,
.station-row:hover > .fixed-region,
.station-row:hover > .fixed-station {
  background: #edf4fc;
}
.mobile-column-label {
  display: none;
}
.cell-button {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 3px;
  width: 100%;
  min-height: 55px;
  padding: 8px 5px;
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
  background: #ffeb99;
}
.completed .cell-button {
  color: #7d5a15;
}
.completed .cell-button small {
  color: #825f18;
}
.schedule-matrix .assigned {
  background: var(--mode-fill);
  box-shadow: inset 3px 0 var(--mode-border);
}
.assigned .cell-names {
  color: var(--mode-ink);
  font-weight: 750;
}
.assigned .cell-button small {
  color: var(--mode-ink);
}
.schedule-matrix .unassigned {
  background: #f7f9fc;
}
.completed .mobile-column-label,
.assigned .mobile-column-label {
  color: inherit;
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
.person-option:has(input:disabled) {
  background: #f7f8fa;
  color: #8c9aaa;
  cursor: not-allowed;
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
select:focus-visible {
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
@container (max-width: 760px) {
  .bulk-toolbar {
    padding: 12px 16px;
  }
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
  .matrix-content {
    padding: 12px;
    background: #f4f7fb;
  }
  .schedule-matrix,
  .schedule-matrix tbody {
    display: block;
  }
  .schedule-matrix colgroup {
    display: none;
  }
  .schedule-matrix thead {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
  .schedule-matrix .station-row {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 1px;
    border: 1px solid #d7e1ee;
    border-radius: 12px;
    overflow: clip;
    background: #e1e8f0;
    margin-bottom: 12px;
  }
  .schedule-matrix .station-row:last-child {
    margin-bottom: 0;
  }
  .schedule-matrix .station-row > * {
    height: auto;
    border: 0;
    min-width: 0;
  }
  .schedule-matrix .region-start {
    border-top: 3px solid #a8bfdc;
  }
  .schedule-matrix .fixed-index {
    grid-column: span 1;
    padding: 12px 4px;
  }
  .schedule-matrix .fixed-region {
    grid-column: span 2;
    padding: 12px 4px;
  }
  .schedule-matrix .fixed-station {
    grid-column: span 3;
    padding: 12px 8px;
  }
  .schedule-matrix .matrix-cell {
    grid-column: span 3;
  }
  .mobile-column-label {
    display: block;
    color: #71849a;
    font-size: 10px;
    font-weight: 650;
    margin-bottom: 3px;
  }
  .cell-button {
    min-height: 82px;
    padding: 10px 8px;
  }
  .schedule-matrix .empty-cell {
    display: block;
  }
  .panel-footer {
    padding: 12px 16px;
  }
  h3 {
    font-size: 18px;
  }
}
@media (max-width: 760px) {
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
}
</style>
