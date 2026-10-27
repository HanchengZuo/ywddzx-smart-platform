<template>
  <button type="button" class="team-trigger" @click="open">
    {{ canEdit ? '一键安排巡检' : '查看巡检分组' }}
  </button>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="team-dialog"
      aria-labelledby="daily-team-title"
      @cancel.prevent="close"
      @click="backdrop"
    >
      <header>
        <div>
          <small>DAILY INSPECTION TEAMS</small>
          <h3 id="daily-team-title">
            巡检安排 <span>{{ activeDay || '选择日期' }}</span>
          </h3>
        </div>
        <button type="button" :disabled="saving" aria-label="关闭巡检安排" @click="close">
          ×
        </button>
      </header>
      <TransientNotice
        :message="warningToast"
        :sequence="warningSequence"
        @dismiss="warningToast = ''"
      />
      <div class="team-body">
        <PlanningDateSelection :model-value="selectedDates" :options="dateOptions" :disabled="loading || saving" @update:model-value="selectDates" />
        <nav v-if="selectedDates.length > 1" class="planning-day-tabs" aria-label="逐日配置巡检方案">
          <button v-for="date in selectedDates" :key="date" type="button" :class="{ active: activeDay === date }" :disabled="loading || saving" @click="activateDay(date)">
            {{ date }}<small>{{ sessionFor(date)?.preview ? '待采用草案' : sessionFor(date)?.context?.updated_at ? '已保存安排' : '待确定分工' }}</small>
          </button>
        </nav>
        <details class="planning-help"><summary>安排规则与实绩保护</summary><p class="method">
          仅当天未设置的档期默认有空；未来日期必须全部确认有空/没空，已设置的没空及原因保持不变；仅安排有空且账号匹配的人员。上海时间
          17:00
          前的当日记录不影响档期展示；但外勤组任一成员在派工后登记了对应站点、检查表的巡检记录，该组立即锁定。未开工的外勤组可以调整组员，采用后同步站点排班与个人待办。已有派工的带队人、视频人员仍须先撤下派工才能更换分工。每组只能有一位管理人员，且至少1人持准驾证，优先配2人。
        </p></details>
        <p v-if="loading" role="status" class="empty">正在核对所选日期档期与已有安排…</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <template v-if="context">
          <p v-if="context.unconfirmed?.length" class="warning" role="status">
            所选日期档期已确认 {{ context.confirmed_count }}/{{ context.total_count }} 人。请先为
            {{ context.unconfirmed.join('、') }} 选择有空或没空，全部确认后才能一键安排。
          </p>
          <p v-if="!context.working" class="warning">该日不是已发布的工作日，不能新安排巡检。</p>
          <p v-if="!context.people.length" class="warning">该日没有有空且账号匹配的人员，请取消选择该日期，或先调整人员档期。</p>
          <details
            v-if="editable && context.working"
            class="manager-step"
            :open="!(preview?.groups || context.groups).length"
          >
            <summary class="step-heading">
              <b>01</b>
              <div>
                <strong>确定管理人员分工</strong
                ><small
                  >该日有空的 {{ managers.length }} 位管理人员 ·
                  {{ students.length }} 位大学生</small
                >
              </div>
            </summary>
            <div v-for="person in managers" :key="person.id" class="manager-row">
              <div>
                <strong
                  >{{ person.display_name }}
                  <em v-if="person.has_driving_permit" class="permit-tag">准驾证</em></strong
                ><small v-if="lockedMode(person)"
                  >已有{{
                    lockedMode(person) === 'offline' ? '现场' : '视频'
                  }}站点安排或实绩，不可冲突</small
                >
              </div>
              <select
                v-model="managerModes[person.id]"
                :disabled="loading || saving || personLocked(person)"
                :aria-label="person.display_name + '所选日期巡检方式'"
                @change="invalidate"
              >
                <option value="">请选择分工</option>
                <option value="offline" :disabled="lockedMode(person) === 'online'">
                  现场巡检 · 带队
                </option>
                <option value="online" :disabled="lockedMode(person) === 'offline'">
                  视频巡检 · 内勤
                </option>
              </select>
            </div>
            <p v-if="!managers.length" class="warning">
              该日没有有空的管理人员，大学生只能安排视频巡检，不会形成无带队人的外勤组。
            </p>
            <p class="method">
              准驾证安全要求优先：现场组至少1人持证，条件允许时优先配2人，再尽量均分现场、视频人数及各组人数。已有站点安排或实绩优先保留，因此受约束时可能无法完全均分。请先在用户数据管理维护准驾证属性，未配置视为无证。
            </p>
            <button
              type="button"
              class="primary"
              :disabled="!batchReady || loading || saving"
              @click="createPreview"
            >
              智能生成巡检方案（{{ selectedDates.length }}天）
            </button>
            <p v-if="hasDispatchedMembers" class="method">
              已派站的外勤组和视频人员将原样保留，仅重新生成其他有空人员的方案。
            </p>
          </details>
          <section class="result-step">
            <div class="step-heading">
              <b>02</b>
              <div>
                <strong>{{ preview ? '待采用的所选日期巡检方案' : '当前生效的所选日期巡检安排' }}</strong
                ><small>{{
                  preview
                    ? '仅为草案 · 调整不自动生效，采用后覆盖所选日期安排'
                    : context.updated_at
                      ? context.updated_by_name + ' · ' + context.updated_at + ' 保存'
                      : '所选日期尚未安排分组'
                }}</small>
              </div>
            </div>
            <p v-if="success" class="applied-notice" role="status">{{ success }}</p>
            <section
              v-if="unassignedPeople.length"
              class="unassigned-personnel"
              aria-label="待编组人员"
            >
              <header>
                <div>
                  <strong
                    >有空待编组 <span>{{ unassignedPeople.length }} 人</span></strong
                  >
                  <p>
                    来自所选日期档期中有空、尚未编组且没有站点派工的人员。{{
                      editable ? '可拖动或点击姓名加入下方分组。' : '当前为只读查看。'
                    }}
                  </p>
                </div>
              </header>
              <div class="member-tags">
                <button
                  v-for="person in unassignedPeople"
                  :key="person.id"
                  type="button"
                  :draggable="editable && !loading && !saving"
                  :disabled="!editable || loading || saving"
                  :aria-label="person.display_name + '，待编组，点击或拖动加入分组'"
                  :class="{ selected: selectedStudent === person.id }"
                  :aria-pressed="selectedStudent === person.id"
                  @dragstart="startStudentDrag($event, person)"
                  @dragend="draggingStudent = null"
                  @click="selectedStudent = selectedStudent === person.id ? null : person.id"
                >
                  {{ person.display_name }}<small>{{ person.position }}</small
                  ><small v-if="person.has_driving_permit" class="permit-tag">准驾</small>
                </button>
              </div>
            </section>
            <div v-if="displayGroups.length" class="team-groups">
              <article
                v-for="group in displayGroups"
                :key="group.name"
                :class="[group.mode, { 'drop-active': draggingStudent || selectedStudent }]"
                @dragover.prevent
                @drop.prevent="dropStudent(group, $event)"
              >
                <header>
                  <strong>{{ group.name }}</strong
                  ><span>{{ group.members.length }} 人</span>
                </header>
                <small v-if="groupLocked(group)" class="dispatch-lock"
                  >派工后已有本站巡检记录 · 人员锁定</small
                >
                <small
                  v-else-if="group.mode === 'offline' && group.has_dispatch"
                  class="dispatch-lock editable-dispatch"
                  >{{
                    editable ? '已派站、未开工 · 可调整组员' : '已派站、未开工 · 组员未锁定'
                  }}</small
                >
                <p
                  v-if="group.mode === 'offline'"
                  class="driver-status"
                  :class="{ unsafe: !driverCount(group), preferred: driverCount(group) >= 2 }"
                >
                  {{
                    driverCount(group)
                      ? driverCount(group) +
                        ' 人拥有准驾证' +
                        (driverCount(group) >= 2 ? ' · 优选配置' : ' · 已满足最低要求')
                      : '缺少持准驾证人员 · 不可确认或派现场任务'
                  }}
                </p>
                <div class="member-tags">
                  <button
                    v-for="person in group.members"
                    :key="person.id"
                    type="button"
                    :draggable="editable && !loading && !saving && !personLocked(person)"
                    :disabled="!editable || loading || saving || personLocked(person)"
                    :aria-label="person.display_name + '，点击或拖动调整分组'"
                    :class="{
                      leader: person.id === group.leader_id,
                      selected: selectedStudent === person.id,
                    }"
                    :aria-pressed="selectedStudent === person.id"
                    @dragstart="startStudentDrag($event, person)"
                    @dragend="draggingStudent = null"
                    @click="selectedStudent = selectedStudent === person.id ? null : person.id"
                  >
                    {{ person.display_name }}<small v-if="person.id === group.leader_id">带队</small
                    ><small v-if="person.has_driving_permit" class="permit-tag">准驾</small
                    ><small v-if="personLocked(person)">{{
                      groupLocked(group) ? '实绩锁定' : '派工绑定'
                    }}</small>
                  </button>
                </div>
                <button
                  v-if="selectedStudent && canMoveTo(group)"
                  type="button"
                  class="move-here"
                  :disabled="saving || groupLocked(group)"
                  @click="dropStudent(group)"
                >
                  移至{{ group.name }}
                </button>
              </article>
            </div>
            <div v-if="editable && videoManagers.length" class="restore-leaders">
              <span>有空的内勤或待编组管理人员可独立带队：</span>
              <button
                v-for="person in videoManagers"
                :key="person.id"
                type="button"
                :disabled="loading || saving || personLocked(person)"
                @click="restoreLeader(person)"
              >
                {{ person.display_name }} · 设为外勤带队
              </button>
            </div>
            <p v-if="editable && displayGroups.length" class="method move-help" role="status">
              {{
                saving
                  ? '正在采用方案…'
                  : '拖动姓名可调整草案，手机或键盘可先点姓名，再点目标组“移至”。管理人员只能移至内勤或独立带队，离开外勤时原组大学生自动转内勤。所有调整须点击“采用方案并覆盖所选日期安排”才生效。'
              }}
              <button v-if="selectedStudent" type="button" @click="selectedStudent = null">
                取消选择
              </button>
            </p>
            <p v-else-if="!displayGroups.length" class="empty">
              {{
                editable
                  ? '完成所选各日管理人员分工后，点击“智能生成巡检方案”。'
                  : '所选日期暂未保存巡检分组。'
              }}
            </p>
            <p
              v-if="
                preview?.source === 'generated' && !displayGroups.some((g) => g.mode === 'offline')
              "
              class="warning"
            >
              没有现场带队管理人员，本次大学生全部安排视频巡检。
            </p>
            <p v-if="unsafeGroups.length" class="error" role="alert">
              {{
                unsafeGroups.map((g) => g.name).join('、')
              }}尚无持准驾证成员。请调整预览；已保存分组请先维护人员准驾证资料或调整成员，不能派现场任务。
            </p>
          </section>
          <details v-if="context.excluded.length" class="excluded">
            <summary>未参与安排的人员（{{ context.excluded.length }}）</summary>
            <span v-for="person in context.excluded" :key="person.name"
              >{{ person.name }} · {{ person.reason }}</span
            >
          </details>
        </template>
      </div>
      <footer>
        <span>{{
          preview
            ? '草案未采用 · 当前安排不会自动变化'
            : '当前展示为已保存安排，可生成新方案或直接调整'
        }}</span>
        <button v-if="preview" type="button" :disabled="saving || loading" @click="discardDraft">
          放弃草案
        </button>
        <button type="button" :disabled="saving" @click="close">关闭</button
        ><button
          v-if="editable"
          type="button"
          class="primary"
          :disabled="!batchAdoptable || loading || saving"
          @click="confirm"
        >
          {{ saving ? '整批采用中…' : '采用已调整方案（' + batchDraftCount + '天）' }}
        </button>
      </footer>
    </dialog>
  </Teleport>
</template>
<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, ref } from 'vue'
import { fieldDriverCount, currentTeamDraft, movePreviewMember } from '@/utils/dailyTeamPreview'
import TransientNotice from '@/components/TransientNotice.vue'
import PlanningDateSelection from '@/components/PlanningDateSelection.vue'
import { dateSelection, preferredPlanningDay, planSession, personnelApplyPlan } from '@/utils/datedPlans'
const props = defineProps({ canEdit: { type: Boolean, default: false } })
const emit = defineEmits(['saved', 'opened', 'closed'])
const dialog = ref(null),
  context = ref(null),
  preview = ref(null),
  managerModes = ref({}),
  loading = ref(false),
  saving = ref(false),
  error = ref(''),
  success = ref('')
const dateOptions = ref([]), selectedDates = ref([]), activeDay = ref(''), sessions = ref({})
const sessionFor = day => planSession(day, activeDay.value, { context: context.value, preview: preview.value, managerModes: managerModes.value }, sessions.value)
const dayReady = session => session?.context?.working && session.context.unconfirmed?.length === 0 && session.context.people.length > 0 &&
  session.context.people.filter(p => p.position === '管理人员').every(p => session.managerModes[p.id])
const batchReady = computed(() => selectedDates.value.length > 0 && selectedDates.value.every(day => dayReady(sessionFor(day))))
const batchDraftCount = computed(() => selectedDates.value.filter(day => sessionFor(day)?.preview).length)
const batchAdoptable = computed(() => batchDraftCount.value > 0 && selectedDates.value.every(day => {
  const session = sessionFor(day)
  return !session?.preview || (session.context.working && session.preview.groups.every(group => group.mode !== 'offline' || fieldDriverCount(group, session.context.people) > 0))
}))
const editable = computed(() => props.canEdit && context.value?.can_edit)
const warningToast = ref(''),
  warningSequence = ref(0)
function warn(message) {
  warningToast.value = message
  warningSequence.value++
}
const lockGroups = computed(() => preview.value?.groups || context.value?.groups || [])
const hasDispatchedMembers = computed(() =>
  lockGroups.value.some((g) => g.members.some((p) => p.dispatch_locked || p.field_dispatched)),
)
const personLocked = (p) =>
  lockGroups.value.some((g) => g.members.some((m) => m.id === p.id && m.dispatch_locked))
const groupLocked = (g) =>
  g.mode === 'offline' &&
  lockGroups.value.some(
    (saved) => saved.mode === 'offline' && saved.leader_id === g.leader_id && saved.dispatch_locked,
  )
const managers = computed(() =>
  (context.value?.people || []).filter((p) => p.position === '管理人员'),
)
const students = computed(() =>
  (context.value?.people || []).filter((p) => p.position === '大学生'),
)
const displayGroups = computed(() => {
  const groups = preview.value?.groups || context.value?.groups || []
  return editable.value &&
    (groups.length || unassignedPeople.value.length) &&
    !groups.some((g) => g.mode === 'online')
    ? [...groups, { name: '内勤视频组', mode: 'online', leader_id: null, members: [] }]
    : groups
})
const unassignedPeople = computed(
  () => preview.value?.unassigned_people || context.value?.unassigned_people || [],
)
const videoManagers = computed(() =>
  [
    ...displayGroups.value.filter((g) => g.mode === 'online').flatMap((g) => g.members),
    ...unassignedPeople.value,
  ].filter((p) => p.position === '管理人员'),
)
const driverCount = (group) => fieldDriverCount(group, context.value?.people)
const unsafeGroups = computed(() =>
  displayGroups.value.filter((group) => group.mode === 'offline' && !driverCount(group)),
)
const draggingStudent = ref(null),
  selectedStudent = ref(null)
function startStudentDrag(event, person) {
  if (!editable.value || loading.value || saving.value || personLocked(person)) {
    event.preventDefault()
    return
  }
  draggingStudent.value = person.id
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/x-inspection-student', String(person.id))
  event.dataTransfer.setData('text/plain', person.display_name)
}
async function dropStudent(group, event) {
  const studentId =
    draggingStudent.value ||
    Number(event?.dataTransfer?.getData('application/x-inspection-student')) ||
    selectedStudent.value
  if (
    !Number.isInteger(studentId) ||
    studentId < 1 ||
    !editable.value ||
    loading.value ||
    saving.value
  )
    return
  const source = displayGroups.value.find((g) => g.members.some((p) => p.id === studentId))
  const person =
    source?.members.find((p) => p.id === studentId) ||
    unassignedPeople.value.find((p) => p.id === studentId)
  if (!person) return
  if (personLocked(person) || groupLocked(group)) {
    warn(
      person.lock_reason ||
        group.lock_reason ||
        '相关外勤组已有派工后的巡检实绩，或人员已有视频派工，暂不能调整。',
    )
    draggingStudent.value = selectedStudent.value = null
    return
  }
  if (source?.name === group.name) {
    draggingStudent.value = selectedStudent.value = null
    return
  }
  try {
    preview.value = movePreviewMember(
      preview.value || currentTeamDraft(context.value),
      context.value.people,
      studentId,
      group.leader_id,
    )
    success.value = ''
    error.value = ''
  } catch (err) {
    warn(err.message)
  } finally {
    draggingStudent.value = selectedStudent.value = null
  }
}
function canMoveTo(group) {
  const person = [...displayGroups.value.flatMap((g) => g.members), ...unassignedPeople.value].find(
    (p) => p.id === selectedStudent.value,
  )
  return person?.position !== '管理人员' || group.mode === 'online' || group.leader_id === person.id
}
function restoreLeader(person) {
  selectedStudent.value = person.id
  dropStudent({ mode: 'offline', leader_id: person.id, name: `外勤${person.display_name}组` })
}
function discardDraft() {
  invalidate()
  success.value = ''
  load()
}
let controller,
  serial = 0,
  disposed = false
function lockedMode(person) {
  const modes = [
    ...new Set([
      ...(person.station_modes || []),
      ...(person.actual_modes || []).map((m) => m.mode),
    ]),
  ]
  return modes.length === 1 ? modes[0] : ''
}
function invalidate() {
  preview.value = null
  draggingStudent.value = selectedStudent.value = null
  error.value = ''
  success.value = ''
}
function saveActive() {
  if (activeDay.value && context.value) sessions.value[activeDay.value] = sessionFor(activeDay.value)
}
function initialSession(data) {
  const members = data.groups.flatMap(group => group.members)
  return { context: data, preview: null, managerModes: Object.fromEntries(data.people.filter(p => p.position === '管理人员')
    .map(p => [p.id, lockedMode(p) || members.find(member => member.id === p.id)?.mode || ''])) }
}
function activateDay(date, persist = true) {
  if (persist) saveActive()
  activeDay.value = date
  const session = sessions.value[date]
  context.value = session?.context || null
  preview.value = session?.preview || null
  managerModes.value = session?.managerModes || {}
  selectedStudent.value = draggingStudent.value = null
}
async function selectDates(values) {
  saveActive()
  selectedDates.value = dateSelection(values, dateOptions.value)
  const next = selectedDates.value.includes(activeDay.value) ? activeDay.value : selectedDates.value[0] || ''
  const missing = selectedDates.value.filter(day => !sessions.value[day])
  activateDay(next, false)
  const ticket = ++serial
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  try {
    if (missing.length) {
      const { data } = await axios.get('/api/staff-availability/today-inspection', {
        params: { dates: JSON.stringify(missing) }, signal: controller.signal, timeout: 30000,
      })
      if (disposed || ticket !== serial) return
      for (const result of data.results) sessions.value[result.day] = initialSession(result)
    }
    activateDay(next, false)
    error.value = ''
  } catch (err) {
    if (!disposed && ticket === serial && err.code !== 'ERR_CANCELED') error.value = err.response?.data?.error || '所选日期档期读取失败，请重新选择。'
  } finally { if (ticket === serial) loading.value = false }
}
async function open() {
  warningToast.value = ''; success.value = ''; error.value = ''
  selectedStudent.value = draggingStudent.value = null
  context.value = preview.value = null
  sessions.value = {}; selectedDates.value = []; activeDay.value = ''; dateOptions.value = []
  dialog.value.showModal(); emit('opened')
  const ticket = ++serial
  controller?.abort(); controller = new AbortController(); loading.value = true
  try {
    const { data } = await axios.get('/api/staff-availability/inspection-dates', { signal: controller.signal, timeout: 15000 })
    if (disposed || ticket !== serial) return
    dateOptions.value = data.dates
    const first = preferredPlanningDay(data.dates)
    await selectDates(first ? [first] : [])
  } catch (err) {
    if (!disposed && ticket === serial && err.code !== 'ERR_CANCELED') error.value = err.response?.data?.error || '可安排日期读取失败，请重新打开。'
  } finally { if (ticket === serial) loading.value = false }
}
async function load() {
  if (!activeDay.value) return
  delete sessions.value[activeDay.value]
  context.value = preview.value = null
  await selectDates(selectedDates.value)
}
async function createPreview() {
  if (!editable.value || !batchReady.value || loading.value || saving.value) return
  saveActive()
  const ticket = ++serial
  controller?.abort(); controller = new AbortController(); loading.value = true
  error.value = ''; success.value = ''
  try {
    const { data } = await axios.post('/api/staff-availability/today-inspection', {
      action: 'preview', plans: selectedDates.value.map(day => {
        const session = sessions.value[day]
        return { day, revision: session.context.revision, manager_modes: session.managerModes }
      }),
    }, { signal: controller.signal, timeout: 90000 })
    if (disposed || ticket !== serial) return
    for (const result of data.results) {
      const session = sessions.value[result.day]
      session.context.people = result.people; session.context.excluded = result.excluded; session.preview = result
    }
    activateDay(activeDay.value, false)
  } catch (err) {
    if (!disposed && ticket === serial && err.code !== 'ERR_CANCELED') error.value = err.response?.data?.error || '批量方案生成失败，未保存任何安排。'
  } finally { if (ticket === serial) loading.value = false }
}
async function submit() {
  if (!editable.value || saving.value || loading.value || !batchAdoptable.value) return
  saveActive()
  const plans = selectedDates.value.map(day => personnelApplyPlan(sessions.value[day])).filter(Boolean)
  saving.value = true; error.value = ''
  try {
    const { data } = await axios.post('/api/staff-availability/today-inspection', { action: 'apply', plans }, { timeout: 120000 })
    if (disposed) return
    for (const result of data.results) sessions.value[result.day] = initialSession(result)
    activateDay(activeDay.value, false)
    success.value = '已采用 ' + data.results.length + ' 天巡检安排，各日分组、站点任务和调度待选区已同步。'
    emit('saved', { ...context.value, results: data.results })
    window.dispatchEvent(new Event('inspection-schedule-changed'))
    window.dispatchEvent(new Event('inspection-sign-pending-refresh'))
  } catch (err) {
    if (!disposed) warn(err.response?.data?.error || '批量保存未能确认，请重新读取后核对；不会部分采用。')
  } finally { saving.value = false }
}
function confirm() { submit() }
function close() {
  if (saving.value) return
  serial++
  controller?.abort()
  loading.value = false
  dialog.value?.close()
  emit('closed')
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
onBeforeUnmount(() => {
  disposed = true
  serial++
  controller?.abort()
  dialog.value?.close()
})
</script>
<style scoped>
.planning-help { margin:0 0 16px; padding:10px 12px; border:1px solid #cadbe5; border-radius:8px; background:#f7fafc; }
.planning-help summary { cursor:pointer; font-weight:600; font-size:13px; color:#375f77; }
.planning-day-tabs { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }
.planning-day-tabs button { display:grid; gap:5px; padding:10px 14px; border:1px solid #b8ccd9; border-radius:10px; background:#f6f9fc; color:#365b75; cursor:pointer; }
.planning-day-tabs button.active { color:white; background:#206b83; border-color:#206b83; }
.planning-day-tabs small { font-size:11px; opacity:.85; }
.dispatch-lock {
  display: block;
  margin: -4px 0 12px;
  color: #7e4b18;
  font-weight: 700;
  font-size: 11px;
}
.permit-tag {
  display: inline-block;
  font-size: 11px;
  font-style: normal;
  color: #17634b;
  background: #e5f5ed;
  border-radius: 4px;
  padding: 2px 5px;
}
.driver-status {
  margin: 0 0 12px;
  padding: 7px 9px;
  background: #fff3df;
  color: #805019;
  border-radius: 6px;
  font-size: 12px;
}
.driver-status.preferred {
  background: #e5f5ed;
  color: #17634b;
}
.driver-status.unsafe {
  background: #fff0ed;
  color: #9c352a;
}
.team-trigger,
.primary {
  background: #1e6786;
  color: #fff;
  border-color: #1e6786;
}
.team-trigger {
  border: 1px solid #a5d2df;
  background: #f2c35c;
  color: #173c59;
  font-weight: 750;
  white-space: nowrap;
}
button {
  font: inherit;
  font-size: 12px;
  border: 1px solid #cbd9e7;
  border-radius: 8px;
  padding: 10px 14px;
  color: #365775;
  background: #fff;
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button:focus-visible,
select:focus-visible {
  outline: 2px solid #368db4;
  outline-offset: 2px;
}
.team-dialog {
  width: min(1000px, calc(100vw - 24px));
  max-height: calc(100dvh - 28px);
  padding: 0;
  margin: auto;
  border: 1px solid #cbd9e7;
  border-radius: 18px;
  box-shadow: 0 24px 80px #0d263b55;
  color: #1c3b55;
}
.team-dialog[open] {
  display: flex;
  flex-direction: column;
}
.team-dialog::backdrop {
  background: #102b4866;
  backdrop-filter: blur(4px);
}
.team-dialog > header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 22px;
  background: #163c58;
  color: #fff;
  border-bottom: 3px solid #e7ae42;
  flex-shrink: 0;
}
header small {
  color: #acd0df;
  font-size: 10px;
  letter-spacing: 1px;
}
h3 {
  font-size: 22px;
  margin: 8px 0 0;
}
h3 span {
  font-size: 13px;
  color: #bcd7e4;
  margin-left: 8px;
}
header > button {
  background: #ffffff12;
  color: #d7e9f1;
  border-color: #ffffff33;
}
.team-body {
  padding: 22px;
  overflow-y: auto;
  min-height: 0;
}
.method {
  font-size: 12px;
  line-height: 1.85;
  color: #617b92;
  margin: 0 0 16px;
}
.step-heading {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 18px 0 12px;
}
.step-heading > b {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #e3eef5;
  color: #25637f;
  font-size: 12px;
}
.step-heading strong {
  font-size: 14px;
}
.step-heading small {
  display: block;
  font-size: 10px;
  color: #73889c;
  margin-top: 4px;
}
.manager-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid #dce6ef;
  border-radius: 8px;
  margin-bottom: 8px;
}
.manager-row strong {
  font-size: 13px;
}
.manager-row small {
  display: block;
  font-size: 10px;
  color: #987237;
  margin-top: 4px;
}
select {
  font: inherit;
  font-size: 12px;
  background: #fff;
  border: 1px solid #c4d4e3;
  color: #365775;
  border-radius: 7px;
  padding: 8px;
  max-width: 55%;
}
.manager-step {
  border-bottom: 1px solid #dae5ee;
  padding-bottom: 18px;
}
.team-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.unassigned-personnel {
  margin: 0 0 16px;
  padding: 15px;
  border: 1px dashed #92b9c9;
  border-left: 4px solid #2d7c8a;
  border-radius: 10px;
  background: #f0f8fa;
}
.unassigned-personnel strong {
  color: #215668;
  font-size: 14px;
}
.unassigned-personnel strong span {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 500;
}
.unassigned-personnel p {
  margin: 7px 0 13px;
  color: #56798a;
  font-size: 12px;
  line-height: 1.7;
}
.dispatch-lock.editable-dispatch {
  color: #226f5b;
  background: #e8f4ec;
  border-color: #a7cfc0;
}
.team-groups article {
  border: 1px solid #e6c98c;
  border-top: 3px solid #d39d3b;
  border-radius: 10px;
  background: #fff7e4;
  padding: 14px;
}
.team-groups article.online {
  border-color: #a6c4ec;
  background: #edf4ff;
  border-top-color: #3175d1;
}
.team-groups article header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  color: #895013;
  margin-bottom: 12px;
}
.team-groups article.online header {
  color: #2056a3;
}
.team-groups article strong {
  font-size: 14px;
}
.team-groups article header span {
  font-size: 11px;
}
.member-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.member-tags > button {
  border: 1px solid #d7dfe8;
  border-radius: 5px;
  background: #fff;
  padding: 5px 8px;
  font-size: 11px;
  color: #465f75;
}
.member-tags .leader {
  border-color: #d6af5d;
  color: #895013;
  font-weight: 750;
}
.member-tags > button.selected {
  outline: 2px solid #2375a7;
  outline-offset: 2px;
  box-shadow: 0 0 0 4px #d8edf6;
}
.member-tags > button:not(:disabled) {
  cursor: grab;
  border: 1px solid #bdd4e8;
}
.member-tags > button:disabled {
  opacity: 1;
  cursor: default;
}
.drop-active {
  outline: 2px dashed #8bb4d0;
  outline-offset: -4px;
}
.move-here {
  margin-top: 12px;
  background: #e5f1ff;
  color: #205c91;
}
.move-help {
  margin-top: 12px;
}
.applied-notice {
  padding: 12px 16px;
  border: 1px solid #a8cdbb;
  border-left: 4px solid #278364;
  border-radius: 8px;
  background: #edf8f1;
  color: #17583f;
  font-size: 13px;
}
.restore-leaders {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
  padding: 12px;
  border: 1px dashed #9ebcd6;
  border-radius: 8px;
  font-size: 12px;
}
.member-tags small {
  margin-left: 5px;
  font-size: 9px;
  color: #aa741b;
}
.excluded {
  margin-top: 16px;
  font-size: 11px;
  color: #7b8fa2;
}
.excluded summary {
  cursor: pointer;
}
.excluded span {
  display: inline-block;
  margin: 10px 12px 0 0;
}
.empty {
  color: #7b8fa2;
  padding: 20px 0;
  font-size: 12px;
}
.warning,
.error {
  padding: 10px 12px;
  border-radius: 7px;
  font-size: 12px;
  line-height: 1.8;
}
.warning {
  background: #fff3d9;
  color: #976529;
}
.error {
  background: #ffedf0;
  color: #b23442;
}
footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px 22px;
  border-top: 1px solid #dce5ee;
  flex-shrink: 0;
  background: #f7faff;
}
footer > span {
  flex: 1;
  align-self: center;
  min-width: 180px;
  color: #526d84;
  font-size: 12px;
  line-height: 1.6;
}
@media (max-width: 600px) {
  .team-dialog {
    width: calc(100vw - 16px);
    max-height: calc(100dvh - 20px);
  }
  .team-body,
  .team-dialog > header,
  footer {
    padding: 16px;
  }
  .team-groups {
    grid-template-columns: 1fr;
  }
  h3 {
    font-size: 19px;
  }
  h3 span {
    display: block;
    margin: 5px 0 0;
  }
  .manager-row {
    align-items: flex-start;
  }
  footer > span {
    flex-basis: 100%;
  }
  footer > .primary {
    flex: 1;
  }
}
</style>
