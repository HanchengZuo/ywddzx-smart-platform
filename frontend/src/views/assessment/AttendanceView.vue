<template>
  <div class="attendance-page">
    <section class="attendance-hero">
      <div>
        <div class="page-kicker">考核系统</div>
        <h2>人员出勤</h2>
        <p>按巡检记录中的检查人统计出勤天数，并将视频检查与现场检查分开计算。</p>
      </div>
      <div class="hero-badge">
        <span>{{ selectedMonthLabel }}</span>
        <strong>{{ selectedModeLabel }}</strong>
      </div>
    </section>

    <section class="filter-card">
      <div class="filter-main">
        <input v-model="filters.month" class="month-picker" type="month" aria-label="选择统计月份"
          @change="fetchAttendance" />

        <div class="mode-switch" aria-label="检查方式">
          <button v-for="option in modeOptions" :key="option.value" type="button"
            :class="{ active: filters.mode === option.value }" @click="setMode(option.value)">
            <strong>{{ option.label }}</strong>
            <span>{{ option.desc }}</span>
          </button>
        </div>
      </div>
    </section>

    <div v-if="error" class="message-card error">{{ error }}</div>

    <section class="overview-grid">
      <article v-for="card in overviewCards" :key="card.label" class="overview-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.desc }}</small>
      </article>
    </section>

    <div v-if="loading" class="state-card">
      <div class="state-orb loading"></div>
      <h3>正在统计出勤数据</h3>
      <p>系统正在读取巡检记录、检查表模式和检查人信息。</p>
    </div>

    <template v-else>
      <section v-for="mode in visibleModes" :key="mode.mode" class="mode-lane" :class="mode.mode">
        <div class="mode-lane-header">
          <div>
            <span>{{ mode.short_label }}</span>
            <h3>{{ mode.label }}</h3>
            <p>{{ mode.description }}</p>
          </div>
          <div class="mode-summary">
            <div>
              <strong>{{ mode.summary.attendance_person_days }}</strong>
              <span>人次出勤天数</span>
            </div>
            <div>
              <strong>{{ mode.summary.group_count }}</strong>
              <span>小组出勤</span>
            </div>
          </div>
        </div>

        <div class="lane-content">
          <article class="panel-card people-panel">
            <div class="panel-title">
              <div>
                <h4>督导员出勤明细</h4>
                <p>同一检查人在同一天出现一次，即计为 1 天出勤。</p>
              </div>
              <span>{{ mode.people.length }} 人</span>
            </div>

            <div v-if="mode.people.length" class="people-table-wrap">
              <table class="people-table">
                <thead>
                  <tr>
                    <th>检查人</th>
                    <th>出勤天数</th>
                    <th>巡检记录</th>
                    <th>巡检问题</th>
                    <th>审核通过</th>
                    <th>去过站点</th>
                    <th>参与检查表</th>
                    <th>出勤日期</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="person in mode.people" :key="`${mode.mode}-${person.inspector_id}`">
                    <td>
                      <div class="person-cell">
                        <strong>{{ person.inspector_name }}</strong>
                        <span>{{ person.username }}<template v-if="person.phone"> ｜ {{ person.phone }}</template></span>
                      </div>
                    </td>
                    <td><span class="number-pill">{{ person.attendance_days }}</span></td>
                    <td>{{ person.inspection_count }}</td>
                    <td><span class="number-pill issue">{{ person.issue_count || 0 }}</span></td>
                    <td><span class="number-pill approved">{{ person.approved_issue_count || 0 }}</span></td>
                    <td>
                      <div class="chip-list">
                        <button v-for="station in person.stations" :key="station.id" class="info-chip station-chip"
                          type="button" :class="{ focused: isFocusedStationChip(mode, person, station) }"
                          :aria-pressed="isFocusedStationChip(mode, person, station)"
                          @click="focusStationAttendance(mode, person, station)">
                          {{ station.name }}
                        </button>
                      </div>
                    </td>
                    <td>
                      <div class="chip-list">
                        <span v-for="checklist in person.checklists" :key="checklist.id" class="info-chip light"
                          :class="{ focused: isFocusedChecklistChip(mode, person, checklist) }">
                          {{ checklist.name }}
                        </span>
                      </div>
                    </td>
                    <td>
                      <div class="date-stack">
                        <span v-for="date in person.attendance_dates" :key="date">{{ date }}</span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-else class="empty-panel">
              <div class="state-orb"></div>
              <h4>本月暂无{{ mode.label }}出勤数据</h4>
              <p>可以切换月份或检查方式查看其他统计结果。</p>
            </div>
          </article>

          <article class="panel-card group-panel">
            <div class="panel-title">
              <div>
                <h4>小组出勤</h4>
                <p>同一站点同一天的同类检查，自动视为同一个小组。</p>
              </div>
              <span>{{ mode.groups.length }} 组</span>
            </div>

            <div v-if="mode.groups.length" class="group-list">
              <div v-for="group in mode.groups" :key="`${mode.mode}-${group.date}-${group.station_id}`"
                :ref="(el) => setGroupCardRef(mode, group, el)" class="group-card"
                :class="{ focused: isFocusedGroup(mode, group) }">
                <div class="group-card-head">
                  <div>
                    <strong>{{ group.station_name }}</strong>
                    <span>{{ group.station_region || '未设置片区' }} ｜ {{ group.date }}</span>
                  </div>
                  <em>{{ group.inspector_count }} 人</em>
                </div>

                <div class="group-meta">
                  <div>
                    <span>检查人</span>
                    <div class="chip-list">
                      <strong v-for="inspector in group.inspectors" :key="inspector.id" class="people-chip">
                        {{ inspector.name }}
                      </strong>
                    </div>
                  </div>
                  <div>
                    <span>检查表</span>
                    <div class="chip-list">
                      <span v-for="checklist in group.checklists" :key="checklist.id" class="info-chip light">
                        {{ checklist.name }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="empty-panel compact">
              <h4>暂无小组出勤</h4>
              <p>当前条件下还没有可归集的小组记录。</p>
            </div>
          </article>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, nextTick, onMounted, reactive, ref } from 'vue'

const getDefaultMonth = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

const modeOptions = [
  { value: 'all', label: '全部', desc: '视频与现场分开展示' },
  { value: 'online', label: '视频检查', desc: '只看线上检查表' },
  { value: 'offline', label: '现场检查', desc: '只看线下检查表' }
]

const filters = reactive({
  month: getDefaultMonth(),
  mode: 'all'
})

const loading = ref(false)
const error = ref('')
const focusedAttendance = ref({
  mode: '',
  inspectorId: '',
  stationId: ''
})
const groupCardRefs = new Map()
const attendanceData = ref({
  month: filters.month,
  mode: filters.mode,
  modes: []
})

const selectedMonthLabel = computed(() => {
  const [year, month] = String(filters.month || '').split('-')
  return year && month ? `${year}年${Number(month)}月` : '当前月份'
})

const selectedModeLabel = computed(() => {
  return modeOptions.find((item) => item.value === filters.mode)?.label || '全部'
})

const visibleModes = computed(() => attendanceData.value.modes || [])

const totalSummary = computed(() => {
  return visibleModes.value.reduce(
    (result, mode) => {
      result.inspectorCount += Number(mode.summary?.inspector_count || 0)
      result.attendancePersonDays += Number(mode.summary?.attendance_person_days || 0)
      result.groupCount += Number(mode.summary?.group_count || 0)
      result.inspectionCount += Number(mode.summary?.inspection_count || 0)
      result.stationCount += Number(mode.summary?.station_count || 0)
      return result
    },
    {
      inspectorCount: 0,
      attendancePersonDays: 0,
      groupCount: 0,
      inspectionCount: 0,
      stationCount: 0
    }
  )
})

const overviewCards = computed(() => [
  {
    label: '参与检查人',
    value: totalSummary.value.inspectorCount,
    desc: '视频和现场分别统计后汇总'
  },
  {
    label: '人次出勤天数',
    value: totalSummary.value.attendancePersonDays,
    desc: '检查人按日期去重后的出勤天数'
  },
  {
    label: '小组出勤',
    value: totalSummary.value.groupCount,
    desc: '同站同日同方式自动归为一组'
  },
  {
    label: '巡检记录',
    value: totalSummary.value.inspectionCount,
    desc: '纳入本次统计的检查表记录'
  }
])

const normalizeId = (value) => String(value ?? '')

const getGroupKey = (mode, group) => `${mode.mode}-${group.date}-${normalizeId(group.station_id)}`

const setGroupCardRef = (mode, group, el) => {
  const key = getGroupKey(mode, group)
  if (el) {
    groupCardRefs.set(key, el)
    return
  }
  groupCardRefs.delete(key)
}

const groupIncludesInspector = (group, inspectorId) => {
  const targetId = normalizeId(inspectorId)
  return (group.inspectors || []).some((inspector) => normalizeId(inspector.id) === targetId)
}

const getRelatedGroups = (mode, person, station) => {
  const stationId = normalizeId(station?.id)
  const inspectorId = normalizeId(person?.inspector_id)
  return (mode.groups || []).filter((group) => (
    normalizeId(group.station_id) === stationId && groupIncludesInspector(group, inspectorId)
  ))
}

const isFocusedStationChip = (mode, person, station) => (
  focusedAttendance.value.mode === mode.mode &&
  focusedAttendance.value.inspectorId === normalizeId(person?.inspector_id) &&
  focusedAttendance.value.stationId === normalizeId(station?.id)
)

const isFocusedGroup = (mode, group) => (
  focusedAttendance.value.mode === mode.mode &&
  focusedAttendance.value.stationId === normalizeId(group?.station_id) &&
  groupIncludesInspector(group, focusedAttendance.value.inspectorId)
)

const isFocusedChecklistChip = (mode, person, checklist) => {
  if (
    focusedAttendance.value.mode !== mode.mode ||
    focusedAttendance.value.inspectorId !== normalizeId(person?.inspector_id)
  ) {
    return false
  }
  const checklistId = normalizeId(checklist?.id)
  return (mode.groups || []).some((group) => (
    isFocusedGroup(mode, group) &&
    (group.checklists || []).some((item) => normalizeId(item.id) === checklistId)
  ))
}

const focusStationAttendance = async (mode, person, station) => {
  focusedAttendance.value = {
    mode: mode.mode,
    inspectorId: normalizeId(person?.inspector_id),
    stationId: normalizeId(station?.id)
  }

  await nextTick()
  const firstGroup = getRelatedGroups(mode, person, station)[0]
  if (!firstGroup) return

  const target = groupCardRefs.get(getGroupKey(mode, firstGroup))
  target?.scrollIntoView?.({
    behavior: 'smooth',
    block: 'center',
    inline: 'nearest'
  })
}

const fetchAttendance = async () => {
  error.value = ''
  loading.value = true
  try {
    const response = await axios.get('/api/assessment/attendance', {
      params: {
        month: filters.month,
        mode: filters.mode,
        _ts: Date.now()
      }
    })
    attendanceData.value = response.data
    focusedAttendance.value = { mode: '', inspectorId: '', stationId: '' }
  } catch (err) {
    error.value = err?.response?.data?.error || '人员出勤统计读取失败。'
  } finally {
    loading.value = false
  }
}

const setMode = (mode) => {
  if (filters.mode === mode) return
  filters.mode = mode
  fetchAttendance()
}

onMounted(fetchAttendance)
</script>

<style scoped>
.attendance-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.attendance-hero,
.filter-card,
.overview-card,
.mode-lane,
.panel-card,
.state-card,
.message-card {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dbe4ee;
  border-radius: 24px;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.07);
}

.attendance-hero {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 28px;
  background:
    radial-gradient(circle at 92% 10%, rgba(34, 197, 94, 0.16), transparent 32%),
    linear-gradient(135deg, #f8fafc 0%, #eef6ff 100%);
}

.attendance-hero::after {
  content: "";
  position: absolute;
  right: -64px;
  bottom: -88px;
  width: 260px;
  height: 260px;
  border-radius: 999px;
  border: 36px solid rgba(37, 99, 235, 0.08);
}

.page-kicker {
  position: relative;
  z-index: 1;
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 14px;
}

.attendance-hero h2 {
  position: relative;
  z-index: 1;
  margin: 0;
  color: #0f172a;
  font-size: 34px;
  font-weight: 900;
}

.attendance-hero p {
  position: relative;
  z-index: 1;
  max-width: 720px;
  margin: 10px 0 0;
  color: #475569;
  line-height: 1.8;
}

.hero-badge {
  position: relative;
  z-index: 1;
  min-width: 150px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid #dbe4ee;
  text-align: right;
}

.hero-badge span,
.hero-badge strong {
  display: block;
}

.hero-badge span {
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.hero-badge strong {
  margin-top: 6px;
  color: #0f172a;
  font-size: 20px;
  font-weight: 900;
}

.filter-card {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 18px;
  padding: 18px;
}

.filter-main {
  display: flex;
  align-items: stretch;
  gap: 16px;
  flex: 1;
}

.month-picker {
  align-self: stretch;
  min-width: 190px;
  border-radius: 14px;
  border: 1px solid #cbd5e1;
  padding: 0 14px;
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
  background: #fff;
}

.mode-switch {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  flex: 1;
  align-items: stretch;
}

.mode-switch button {
  border: 1px solid #dbe4ee;
  border-radius: 16px;
  padding: 12px 14px;
  background: #f8fafc;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;
  min-height: 64px;
}

.mode-switch button strong,
.mode-switch button span {
  display: block;
}

.mode-switch button strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 900;
}

.mode-switch button span {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.mode-switch button.active {
  background: #0f172a;
  border-color: #0f172a;
  box-shadow: 0 14px 26px rgba(15, 23, 42, 0.18);
}

.mode-switch button.active strong,
.mode-switch button.active span {
  color: #fff;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.overview-card {
  padding: 18px;
}

.overview-card span,
.overview-card small {
  display: block;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.overview-card strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 32px;
  font-weight: 900;
}

.overview-card small {
  margin-top: 8px;
  line-height: 1.6;
  font-weight: 600;
}

.mode-lane {
  overflow: hidden;
}

.mode-lane.online {
  border-top: 5px solid #2563eb;
}

.mode-lane.offline {
  border-top: 5px solid #16a34a;
}

.mode-lane-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.mode-lane-header h3 {
  margin: 6px 0 0;
  color: #0f172a;
  font-size: 24px;
  font-weight: 900;
}

.mode-lane-header p {
  margin: 8px 0 0;
  color: #64748b;
  line-height: 1.7;
}

.mode-lane-header > div > span {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 12px;
  font-weight: 900;
}

.offline .mode-lane-header > div > span {
  background: #dcfce7;
  color: #15803d;
}

.mode-summary {
  display: flex;
  gap: 10px;
}

.mode-summary div {
  min-width: 120px;
  padding: 12px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
  text-align: center;
}

.mode-summary strong,
.mode-summary span {
  display: block;
}

.mode-summary strong {
  color: #0f172a;
  font-size: 24px;
  font-weight: 900;
}

.mode-summary span {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.lane-content {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.75fr);
  gap: 16px;
  padding: 18px;
}

.panel-card {
  padding: 18px;
  box-shadow: none;
}

.panel-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.panel-title h4 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.panel-title p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.panel-title > span {
  flex-shrink: 0;
  padding: 6px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.people-table-wrap {
  overflow-x: auto;
}

.people-table {
  width: 100%;
  min-width: 1120px;
  border-collapse: separate;
  border-spacing: 0 8px;
}

.people-table th {
  padding: 0 12px 6px;
  color: #64748b;
  font-size: 12px;
  text-align: left;
  white-space: nowrap;
}

.people-table td {
  padding: 14px 12px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
  color: #334155;
  font-size: 13px;
  vertical-align: middle;
}

.people-table td:first-child {
  border-left: 1px solid #e2e8f0;
  border-radius: 16px 0 0 16px;
}

.people-table td:last-child {
  border-right: 1px solid #e2e8f0;
  border-radius: 0 16px 16px 0;
}

.person-cell strong,
.person-cell span {
  display: block;
}

.person-cell strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 900;
}

.person-cell span {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.number-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  height: 32px;
  border-radius: 999px;
  background: #0f172a;
  color: #fff;
  font-weight: 900;
}

.number-pill.issue {
  background: #1d4ed8;
}

.number-pill.approved {
  background: #15803d;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.info-chip,
.people-chip {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 9px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-size: 12px;
  font-weight: 800;
}

.station-chip {
  border: none;
  cursor: pointer;
  transition: transform 0.16s ease, box-shadow 0.16s ease, background 0.16s ease, color 0.16s ease;
}

.station-chip:hover,
.station-chip.focused {
  transform: translateY(-1px);
  background: #0f172a;
  color: #fff;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.18);
}

.info-chip.light {
  background: #eef2ff;
  color: #3730a3;
}

.info-chip.light.focused {
  background: #fef3c7;
  color: #92400e;
  box-shadow: inset 0 0 0 1px #f59e0b;
}

.people-chip {
  background: #dcfce7;
  color: #166534;
}

.date-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #475569;
  white-space: nowrap;
}

.group-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 620px;
  overflow: auto;
  padding-right: 4px;
}

.group-card {
  padding: 15px;
  border-radius: 18px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease, background 0.18s ease;
}

.group-card.focused {
  background: linear-gradient(135deg, #fffbeb 0%, #f8fafc 100%);
  border-color: #f59e0b;
  box-shadow: 0 16px 30px rgba(245, 158, 11, 0.18);
  transform: translateY(-2px);
}

.group-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.group-card-head strong,
.group-card-head span {
  display: block;
}

.group-card-head strong {
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.group-card-head span {
  margin-top: 5px;
  color: #64748b;
  font-size: 12px;
}

.group-card-head em {
  flex-shrink: 0;
  font-style: normal;
  color: #0f172a;
  font-size: 12px;
  font-weight: 900;
  padding: 5px 8px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #dbe4ee;
}

.group-meta {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-meta > div > span {
  display: block;
  margin-bottom: 7px;
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.state-card,
.empty-panel,
.message-card {
  padding: 28px;
  text-align: center;
}

.message-card.error {
  color: #b91c1c;
  background: #fef2f2;
  border-color: #fecaca;
  font-weight: 800;
}

.state-orb {
  width: 46px;
  height: 46px;
  margin: 0 auto 14px;
  border-radius: 999px;
  background: radial-gradient(circle, #2563eb 0 34%, #dbeafe 35% 100%);
}

.state-orb.loading {
  animation: pulse 1.2s ease-in-out infinite;
}

.state-card h3,
.empty-panel h4 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.state-card p,
.empty-panel p {
  margin: 8px 0 0;
  color: #64748b;
  line-height: 1.8;
}

.empty-panel.compact {
  padding: 20px;
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }

  50% {
    transform: scale(0.88);
    opacity: 0.65;
  }
}

@media (max-width: 1180px) {
  .lane-content {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 860px) {
  .attendance-hero,
  .filter-card,
  .filter-main,
  .mode-lane-header {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-badge {
    text-align: left;
  }

  .mode-switch,
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .mode-summary {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .attendance-page {
    gap: 14px;
  }

  .attendance-hero,
  .filter-card,
  .mode-lane-header,
  .lane-content,
  .panel-card {
    padding: 16px;
  }

  .attendance-hero h2 {
    font-size: 28px;
  }

  .mode-summary {
    grid-template-columns: 1fr;
  }

  .people-table {
    min-width: 860px;
  }
}
</style>
