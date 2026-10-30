<template>
  <section class="evidence-panel" aria-label="问题分类与代表证据">
    <div v-if="!category?.issues.length" class="evidence-empty">当前范围暂无该类别的问题。</div>
    <template v-else>
      <div class="evidence-status">
        <div>
          <strong>{{ ready ? '问题分类已就绪' : '尚未完成问题分类' }}</strong>
          <p>
            {{
              monthly
                ? '月度重点取数量最多的前三个子类，每类一张代表照片。'
                : `本节最多 ${slots} 张照片，按子类频次轮流选取，类内按代表顺序使用。`
            }}
          </p>
          <p v-if="!category.analysis?.representatives_ready && ready">
            已有分类保留展示；代表问题尚未就绪，请明确发起 AI 挑选或人工选择。
          </p>
        </div>
        <button :disabled="!canGenerate || busy || groupingDirty" @click="emit('generate')">
          {{
            busy
              ? '正在处理…'
              : !ready
                ? 'AI分类并挑选代表问题'
                : !category.analysis?.representatives_ready
                  ? 'AI挑选代表问题'
                  : 'AI补齐分类与代表问题'
          }}
        </button>
      </div>
      <p v-if="!canGenerate" class="evidence-note">
        当前账号可查看和人工调整；调用 AI 需要“生成AI报告”权限。
      </p>
      <p v-if="groupingDirty" class="evidence-note" role="status">
        分类或描述有未保存修改，请先在底部保存配置，再重新打开并让 AI 挑选代表问题。
      </p>
      <div class="evidence-picks" aria-label="当前PPT选用问题">
        <strong>当前 PPT 选用</strong>
        <span v-for="pick in pptPicks" :key="pick.issue_id"
          >#{{ pick.issue_id }} · {{ pick.name }}</span
        >
        <span v-if="!pptPicks.length">尚无可用代表照片</span>
        <p>预览当前配置，人工调整需在底部保存并重新生成报告后生效。读取、打开和保存均不调用 AI。</p>
      </div>
      <div v-if="groups.length" class="evidence-layout">
        <nav aria-label="问题表现子类" class="evidence-nav">
          <strong>问题表现子类</strong>
          <button
            v-for="(group, index) in groups"
            :key="group.name"
            :class="{ selected: selectedGroup === group.name }"
            :aria-pressed="selectedGroup === group.name"
            @click="selectGroup(group.name)"
          >
            <span
              >{{ group.name
              }}<small v-if="monthly && group.count">{{
                index < 3 ? '月度重点展示' : '未进入前三子类'
              }}</small></span
            ><b>{{ group.count }}</b>
          </button>
          <label
            >新增子类<input
              v-model="newGroupName"
              maxlength="50"
              :disabled="busy"
              placeholder="输入分类名称"
              @keyup.enter="addGroup"
          /></label>
          <button :disabled="busy || !newGroupName.trim()" @click="addGroup">添加子类</button>
        </nav>
        <section class="evidence-content">
          <header>
            <h3>
              {{ selectedGroup }} <small>{{ groupIssues.length }} 项</small>
            </h3>
            <span class="evidence-badge">{{ summaryManual ? '人工描述' : '默认描述' }}</span>
          </header>
          <label class="evidence-summary"
            >分类共性描述<textarea
              :value="override.summaries[selectedGroup] || ''"
              :disabled="busy"
              maxlength="160"
              rows="3"
              @input="emit('summary', selectedGroup, $event.target.value)"
            ></textarea>
          </label>
          <section class="representative-order" aria-label="代表问题顺序">
            <header>
              <strong>代表问题优先顺序</strong
              ><span class="evidence-badge" :class="{ manual: representativesManual }">{{
                representativesManual ? '人工选择' : '默认选择'
              }}</span>
            </header>
            <button :disabled="busy || !representativesManual" @click="resetRepresentatives">
              恢复 AI 推荐
            </button>
            <p>
              {{
                monthly
                  ? `每类最多列出 ${slots} 项优先顺序，首项用于 PPT；仅前三子类各展示一张照片，其余为后续候选。`
                  : `每类最多优先指定 ${slots} 项，按顺序选用；其余图位沿用已保存的默认顺序补齐。`
              }}
            </p>
            <p>清空优先选择会恢复默认推荐，不会排除该类所有问题。下列顺序包含默认补位。</p>
            <ol v-if="representatives.length">
              <li
                v-for="(id, index) in representatives"
                :key="id"
                :class="{ 'ppt-pick': isPptPick(id) }"
              >
                <b class="representative-position">{{ String(index + 1).padStart(2, '0') }}</b>
                <strong>#{{ id }}</strong
                ><span
                  >{{ chosenRepresentatives.includes(id) ? '优先顺序' : '默认补位' }} ·
                  {{ isPptPick(id) ? '当前 PPT 选用' : '后续候选' }}</span
                >
                <button
                  :disabled="busy || index === 0"
                  :aria-label="`将问题${id}上移`"
                  @click="moveRepresentative(index, -1)"
                >
                  上移
                </button>
                <button
                  :disabled="busy || index === representatives.length - 1"
                  :aria-label="`将问题${id}下移`"
                  @click="moveRepresentative(index, 1)"
                >
                  下移
                </button>
                <button
                  :disabled="busy || !chosenRepresentatives.includes(id)"
                  :aria-label="`移除代表问题${id}`"
                  @click="toggleRepresentative(id, false)"
                >
                  移出优先序
                </button>
              </li>
            </ol>
            <p v-else>尚未选择代表问题，可在下方人工勾选。</p>
            <p>
              已保存代表 ID（{{ representativeSource === 'manual' ? '人工优先' : 'AI 默认' }}）：{{
                defaultRepresentatives.length
                  ? defaultRepresentatives.map((id) => `#${id}`).join('、')
                  : '尚未挑选'
              }}
            </p>
          </section>
          <input
            v-model="keyword"
            type="search"
            aria-label="搜索子类内问题"
            placeholder="搜索问题ID、站点或描述"
          />
          <article v-for="issue in visibleIssues" :key="issue.issue_id" class="evidence-issue">
            <button
              v-if="issue.issue_photo"
              class="evidence-photo"
              :aria-label="`放大问题${issue.issue_id}的照片`"
              @click="emit('photo', issue)"
            >
              <img
                :src="resolveImage(issue.issue_photo)"
                :alt="`问题 ${issue.issue_id}`"
                loading="lazy"
              />
            </button>
            <span v-else class="evidence-no-photo">暂无照片</span>
            <div class="evidence-copy">
              <header>
                <strong>#{{ issue.issue_id }} · {{ issue.station_name }}</strong
                ><span v-if="isPptPick(issue.issue_id)" class="evidence-badge">当前 PPT 选用</span>
              </header>
              <p>{{ issue.description }}</p>
              <div class="evidence-requirement">
                <strong>规范要求</strong
                ><span class="evidence-badge">{{
                  requirementStatus(issue.requirement_status)
                }}</span>
                <p>{{ issue.requirement || '尚未维护规范要求，请在规范要求模块中补充。' }}</p>
              </div>
              <label
                >问题表现分类
                <span class="evidence-badge">{{
                  manual.assignments?.[issue.issue_id] ? '人工分类' : '默认分类'
                }}</span
                ><select
                  :value="override.assignments[issue.issue_id]"
                  :disabled="busy"
                  @change="emit('assignment', issue.issue_id, $event.target.value)"
                >
                  <option v-for="group in groups" :key="group.name" :value="group.name">
                    {{ group.name }}
                  </option>
                </select></label
              >
              <label class="evidence-select"
                ><input
                  type="checkbox"
                  :name="`representative-${category.key}-${selectedGroup}`"
                  :checked="chosenRepresentatives.includes(Number(issue.issue_id))"
                  :disabled="
                    busy ||
                    !issue.issue_photo ||
                    (chosenRepresentatives.length >= slots &&
                      !chosenRepresentatives.includes(Number(issue.issue_id)))
                  "
                  @change="toggleRepresentative(issue.issue_id, $event.target.checked)"
                />{{ issue.issue_photo ? '优先选为代表问题' : '无照片，不用于 PPT 代表图' }}</label
              >
            </div>
          </article>
          <p v-if="!visibleIssues.length" class="evidence-empty">此子类下暂无符合条件的问题。</p>
        </section>
      </div>
      <p v-else class="evidence-empty">尚无已保存的问题子类，请使用上方按钮完成分类。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  safetyAnalysisReady,
  safetySubgroups,
  safetySelectedGroup,
  safetySlotLimit,
  safetyRepresentativeIds,
  safetyRepresentativeOrder,
  safetyPptPicks,
  safetyIssueSearch,
} from '@/utils/safetyReportConfig'
const props = defineProps({
  category: Object,
  override: {
    type: Object,
    default: () => ({ assignments: {}, summaries: {}, representatives: {} }),
  },
  manual: { type: Object, default: () => ({}) },
  monthly: Boolean,
  canGenerate: Boolean,
  groupingDirty: Boolean,
  busy: Boolean,
  resolveImage: { type: Function, default: (path) => path },
})
const emit = defineEmits([
  'generate',
  'photo',
  'assignment',
  'summary',
  'representatives',
  'add-group',
])
const selectedGroup = ref(''),
  keyword = ref(''),
  newGroupName = ref('')
const ready = computed(() => safetyAnalysisReady(props.category))
const slots = computed(() => safetySlotLimit(props.category))
const groups = computed(() => safetySubgroups(props.category, props.override))
const groupIssues = computed(() =>
  (props.category?.issues || []).filter(
    (issue) => props.override.assignments[issue.issue_id] === selectedGroup.value,
  ),
)
const visibleIssues = computed(() => safetyIssueSearch(groupIssues.value, keyword.value))
const representatives = computed(() =>
  safetyRepresentativeOrder(
    props.category,
    props.override,
    selectedGroup.value,
    slots.value,
    props.manual,
  ),
)
const defaultRepresentatives = computed(
  () =>
    props.category?.analysis?.groups?.find((group) => group.name === selectedGroup.value)
      ?.representative_issue_ids || [],
)
const pptPicks = computed(() =>
  safetyPptPicks(props.category, props.override, props.monthly, props.manual),
)
const representativeSource = computed(
  () =>
    props.category?.analysis?.groups?.find((group) => group.name === selectedGroup.value)
      ?.representative_source || 'ai',
)
const representativesManual = computed(
  () => (props.manual.representatives?.[selectedGroup.value]?.length || 0) > 0,
)
const chosenRepresentatives = computed(() =>
  props.category?.analysis?.representatives_ready || representativesManual.value
    ? safetyRepresentativeIds(props.category, props.override, selectedGroup.value, slots.value)
    : [],
)
const summaryManual = computed(() =>
  Object.hasOwn(props.manual.summaries || {}, selectedGroup.value),
)
watch(
  () => props.category?.key,
  () => {
    selectedGroup.value = ''
    keyword.value = ''
    newGroupName.value = ''
  },
  { flush: 'sync' },
)
watch(
  groups,
  (value) => {
    const next = safetySelectedGroup(value, selectedGroup.value)
    if (next !== selectedGroup.value) selectGroup(next)
  },
  { immediate: true },
)
function selectGroup(name) {
  selectedGroup.value = name
  keyword.value = ''
}
function addGroup() {
  const name = newGroupName.value.trim()
  if (!name || props.busy) return
  emit('add-group', name)
  newGroupName.value = ''
}
const isPptPick = (id) => pptPicks.value.some((pick) => pick.issue_id === Number(id))
function toggleRepresentative(id, checked) {
  if (props.busy) return
  const value = Number(id)
  const list = checked
    ? [...new Set([...chosenRepresentatives.value, value])].slice(0, slots.value)
    : chosenRepresentatives.value.filter((item) => item !== value)
  emit('representatives', selectedGroup.value, list)
}
function resetRepresentatives() {
  if (!props.busy) emit('representatives', selectedGroup.value, [])
}
function moveRepresentative(index, delta) {
  if (props.busy) return
  const list = [...representatives.value],
    next = index + delta
  if (next < 0 || next >= list.length) return
  ;[list[index], list[next]] = [list[next], list[index]]
  emit('representatives', selectedGroup.value, list)
}
const requirementStatus = (status) =>
  ({ ready: '已就绪', manual: '人工维护', stale: '规范已更新，待核对', missing: '待补充' })[
    status
  ] || '待补充'
</script>

<style scoped>
.evidence-panel {
  --ink: #24485f;
  --line: #c8dbe5;
  color: var(--ink);
  font-size: 15px;
  line-height: 1.65;
}
.evidence-panel p {
  margin: 8px 0;
  overflow-wrap: anywhere;
  white-space: pre-line;
}
.evidence-panel button,
.evidence-panel input,
.evidence-panel select,
.evidence-panel textarea {
  font: inherit;
  color: inherit;
}
.evidence-panel button {
  border: 1px solid #acc9d6;
  background: #fff;
  border-radius: 8px;
  padding: 9px 13px;
  cursor: pointer;
}
.evidence-panel button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.evidence-panel :focus-visible {
  outline: 3px solid #74b1d0;
  outline-offset: 2px;
}
.evidence-status,
.evidence-picks {
  border: 1px solid var(--line);
  background: #f0f7fa;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}
.evidence-status {
  display: flex;
  gap: 20px;
  align-items: center;
  justify-content: space-between;
}
.evidence-status > button {
  flex-shrink: 0;
  background: #17637e;
  color: white;
}
.evidence-note {
  color: #647889;
}
.evidence-picks > span {
  display: inline-block;
  margin: 4px 6px;
  padding: 4px 8px;
  border-radius: 6px;
  background: #dceef0;
}
.evidence-picks p,
.representative-order p {
  font-size: 14px;
  color: #506f80;
}
.evidence-layout {
  display: grid;
  grid-template-columns: 225px minmax(0, 1fr);
  gap: 22px;
}
.evidence-nav {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--line);
  background: #f4f8fa;
  border-radius: 12px;
  align-self: start;
}
.evidence-nav > button {
  display: flex;
  justify-content: space-between;
  text-align: left;
  gap: 8px;
  overflow-wrap: anywhere;
}
.evidence-nav button.selected {
  background: #175c78;
  color: white;
}
.evidence-nav small {
  display: block;
  font-size: 13px;
  font-weight: 400;
}
.evidence-content {
  min-width: 0;
}
.evidence-content header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
}
.evidence-content h3 {
  font-size: 21px;
  margin: 0;
}
.evidence-content h3 small {
  font-size: 14px;
  font-weight: 400;
}
.evidence-badge {
  display: inline-block;
  border-radius: 5px;
  background: #e1f0ed;
  color: #24675e;
  padding: 2px 8px;
  font-size: 13px;
  font-weight: 500;
}
.evidence-badge.manual {
  background: #fff0db;
  color: #815815;
}
.evidence-panel label {
  display: block;
  margin: 12px 0;
}
.evidence-panel input:not([type='checkbox']):not([type='radio']),
.evidence-panel textarea,
.evidence-panel select {
  display: block;
  box-sizing: border-box;
  width: 100%;
  border: 1px solid #afc8d6;
  background: white;
  border-radius: 8px;
  padding: 10px;
  margin-top: 7px;
}
.evidence-panel textarea {
  resize: vertical;
  min-height: 90px;
}
.representative-order {
  padding: 16px;
  margin: 16px 0;
  border: 1px solid var(--line);
  border-radius: 10px;
}
.representative-order ol {
  padding: 0;
  list-style-position: inside;
}
.representative-order li {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #e2ebf0;
}
.representative-order li > span {
  flex: 1;
  font-size: 14px;
}
.representative-position {
  display: grid;
  place-items: center;
  flex: 0 0 30px;
  height: 30px;
  border-radius: 7px;
  background: #edf3f7;
  color: #536e80;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.ppt-pick .representative-position {
  background: #dceef0;
  color: #17637e;
}
.representative-order li button {
  padding: 6px 10px;
  font-size: 14px;
}
.evidence-issue {
  display: grid;
  grid-template-columns: 135px minmax(0, 1fr);
  gap: 18px;
  padding: 22px 0;
  border-bottom: 1px solid var(--line);
}
.evidence-panel .evidence-photo {
  padding: 0;
  border: 0;
  background: none;
  align-self: start;
}
.evidence-photo img {
  display: block;
  width: 100%;
  height: 125px;
  object-fit: contain;
  border-radius: 8px;
  background: #edf3f6;
}
.evidence-no-photo {
  display: grid;
  place-items: center;
  height: 100px;
  background: #edf3f6;
  border-radius: 8px;
  color: #658091;
  font-size: 14px;
}
.evidence-requirement {
  padding: 12px;
  background: #f3f7fa;
  border-left: 3px solid #80aab7;
  border-radius: 6px;
  margin: 12px 0;
}
.evidence-requirement > span {
  margin-left: 8px;
}
.evidence-select {
  display: flex !important;
  align-items: center;
  gap: 9px;
}
.evidence-select input {
  width: 18px;
  height: 18px;
  accent-color: #17637e;
}
.evidence-empty {
  text-align: center;
  color: #5d7889;
  padding: 30px 16px;
}
@media (max-width: 800px) {
  .evidence-layout {
    grid-template-columns: 1fr;
  }
  .evidence-status {
    align-items: stretch;
    flex-direction: column;
    gap: 8px;
  }
  .evidence-nav {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .evidence-nav > strong,
  .evidence-nav > label {
    grid-column: 1 / -1;
  }
}
@media (max-width: 500px) {
  .evidence-issue {
    grid-template-columns: 1fr;
  }
  .evidence-photo {
    width: 100%;
    max-width: 260px;
  }
  .evidence-photo img {
    height: 160px;
  }
  .evidence-nav {
    grid-template-columns: 1fr;
  }
}
</style>
