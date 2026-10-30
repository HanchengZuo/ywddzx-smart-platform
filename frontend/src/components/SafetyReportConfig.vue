<template>
  <section class="safety-config" aria-label="安全报告专属配置">
    <p v-if="error" class="safety-error" role="alert">
      {{ error }} <button @click="load">重新读取</button>
    </p>
    <div v-if="loading" role="status">正在核对现场、视频问题与已保存配置…</div>
    <template v-else-if="data">
      <article class="safety-source">
        <div>
          <small class="safety-step-label">01 · 数据范围</small>
          <h3>本次报告数据来源</h3>
          <p>仅采用审核通过问题；受检站点包含已确认完成的零问题巡检。现场与视频分别统计。</p>
        </div>
        <button :disabled="busy" @click="open('source')">设置来源</button>
        <dl>
          <div v-for="item in metrics" :key="item.key">
            <dt>{{ item.label }}</dt>
            <dd>
              {{ data.summary[item.key] }}<small>{{ item.unit }}</small>
            </dd>
          </div>
        </dl>
      </article>
      <div class="safety-panels" aria-label="报告专属配置工具">
        <article class="safety-tool safety-tool-typical">
          <small class="safety-step-label">02 · 典型选题</small>
          <h3>现场与视频典型问题</h3>
          <p>
            现场选一个代表问题；视频默认采用最高频风险类别，可切换类别并指定该类别的 PPT 展示照片。
          </p>
          <button :disabled="busy" @click="open('typical')">查看与调整典型问题</button>
        </article>
        <SafetyRequirementsPanel
          :can-generate="canGenerate"
          :busy="busy || saving || analyzing || !!active"
          @saved="requirementsSaved"
        />
        <article class="safety-tool safety-tool-focus">
          <small class="safety-step-label">04 · 月度重点</small>
          <h3>月度重点与问题再分类</h3>
          <p>
            当前重点：{{
              data.focus_category || '暂无现场问题'
            }}。先选择检查主题，再查看或生成该主题的问题表现分类。
          </p>
          <button :disabled="busy" @click="open('analysis')">查看与调整分析</button>
        </article>
        <article class="safety-tool safety-tool-evidence">
          <small class="safety-step-label">05 · 固定章节证据</small>
          <h3>现场与视频分类证据</h3>
          <p>分别维护现场五类与视频四类固定章节，查看问题子类、规范要求和代表照片顺序。</p>
          <button :disabled="busy" @click="open('evidence')">查看与调整固定章节</button>
        </article>
      </div>
      <div class="safety-saved" role="status">
        <span class="safety-saved-mark" aria-hidden="true"></span>
        <span>{{ savedLabel }}</span>
      </div>
    </template>
    <Teleport to="body">
      <div v-if="active" class="safety-overlay" @click.self="close" @keydown.esc.stop="close">
        <section
          ref="dialog"
          class="safety-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="safety-dialog-title"
          tabindex="-1"
          @keydown.tab="trapFocus"
        >
          <header>
            <div>
              <small>安全质量检查报告 · 全局共享配置</small>
              <h2 id="safety-dialog-title">{{ titles[active] }}</h2>
            </div>
            <button
              class="safety-close"
              :disabled="saving || analyzing"
              aria-label="关闭"
              @click="close"
            >
              ×
            </button>
          </header>
          <div class="safety-dialog-body">
            <p v-if="dialogError" class="safety-error" role="alert">{{ dialogError }}</p>
            <template v-if="active === 'source'">
              <label class="safety-check"
                ><input
                  type="checkbox"
                  :checked="draft.station_ids === null"
                  @change="setAll($event.target.checked)"
                />使用当前范围全部受检站点</label
              >
              <p>自定义范围下，未勾选的站点不参与本份报告。累计整改统计也采用相同站点范围。</p>
              <input
                v-model="keyword"
                type="search"
                placeholder="搜索片区、站点名称"
                aria-label="搜索来源站点"
              />
              <div class="safety-stations">
                <label
                  v-for="station in visibleStations"
                  :key="station.station_id"
                  class="safety-check"
                  ><input
                    type="checkbox"
                    :checked="
                      draft.station_ids === null || draft.station_ids.includes(station.station_id)
                    "
                    @change="toggleStation(station.station_id, $event.target.checked)"
                  /><span
                    ><b>{{ station.station_name }}</b
                    ><small
                      >{{ station.unit_name }} · 现场 {{ station.onsite_count }} 项 / 视频
                      {{ station.video_count }} 项</small
                    ></span
                  ></label
                >
              </div>
            </template>
            <template v-else-if="active === 'typical'">
              <div class="safety-choice-layout">
                <nav class="safety-mode-nav" aria-label="典型问题检查方式">
                  <small>检查方式</small>
                  <button
                    v-for="mode in modes"
                    :key="mode.key"
                    :class="{ selected: typicalMode === mode.key }"
                    @click="selectTypicalMode(mode.key)"
                  >
                    <span
                      ><b>{{ mode.label }}检查</b
                      ><small>{{ modeIssues(mode.key).length }} 条候选问题</small></span
                    >
                    <span class="mode-count">{{ modeIssues(mode.key).length }}</span>
                  </button>
                  <p>
                    {{
                      typicalMode === 'onsite'
                        ? '现场：选择一个代表问题及照片。'
                        : '视频：先选风险类别，再从该类别的问题中选择一张 PPT 展示照片。'
                    }}
                  </p>
                  <div class="safety-mode-note">保存只记录选择；重新生成后应用到报告。</div>
                </nav>
                <section v-if="typicalMode === 'onsite'" class="safety-choice-content">
                  <div class="safety-list-heading">
                    <div>
                      <small>典型案例选择</small>
                      <h3>{{ typicalMode === 'onsite' ? '现场' : '视频' }}问题库</h3>
                    </div>
                    <button @click="setTypical(typicalMode, '')">使用自动推荐</button>
                  </div>
                  <div class="safety-current-choice">
                    <span>当前选用</span>
                    <strong v-if="typical(typicalMode)"
                      >#{{ typical(typicalMode).issue_id }} ·
                      {{ typical(typicalMode).station_name }}</strong
                    >
                    <strong v-else>生成报告时自动推荐，也可在下方人工选择</strong>
                    <small>{{ typicalSelection(typicalMode) ? '人工选择' : '自动推荐' }}</small>
                  </div>
                  <input
                    v-model="issueKeyword"
                    type="search"
                    placeholder="搜索问题ID、站点或问题描述"
                    aria-label="搜索典型问题"
                  />
                  <p class="safety-list-count">
                    {{ typicalCandidates.length }} 条问题 · 点击照片可放大
                  </p>
                  <ul class="safety-candidate-list">
                    <li
                      v-for="issue in typicalCandidates"
                      :key="issue.issue_id"
                      :class="[
                        'safety-candidate',
                        { chosen: typical(typicalMode)?.issue_id === issue.issue_id },
                      ]"
                    >
                      <input
                        :id="'safety-typical-' + issue.issue_id"
                        type="radio"
                        :name="'safety-typical-' + typicalMode"
                        :checked="typical(typicalMode)?.issue_id === issue.issue_id"
                        @change="setTypical(typicalMode, issue.issue_id)"
                      />
                      <label
                        :for="'safety-typical-' + issue.issue_id"
                        class="safety-candidate-copy"
                      >
                        <span
                          ><b>#{{ issue.issue_id }}</b
                          ><strong>{{ issue.station_name }}</strong
                          ><em v-if="typical(typicalMode)?.issue_id === issue.issue_id"
                            >已选用</em
                          ></span
                        >
                        <p>{{ issue.description }}</p>
                        <small>{{ issue.topic }}</small>
                      </label>
                      <button
                        v-if="issue.issue_photo"
                        class="safety-photo safety-list-photo"
                        :aria-label="'放大问题' + issue.issue_id + '的照片'"
                        @click="emit('photo', issue)"
                      >
                        <img
                          :src="resolveImage(issue.issue_photo)"
                          :alt="'问题 ' + issue.issue_id"
                          loading="lazy"
                        />
                      </button>
                      <span v-else class="safety-missing-photo">暂无照片</span>
                    </li>
                  </ul>
                  <div v-if="!typicalCandidates.length" class="safety-no-items">
                    没有符合条件的问题，请调整关键词。
                  </div>
                </section>
                <section v-else class="safety-choice-content">
                  <div class="safety-list-heading">
                    <div>
                      <small>以风险控制缺陷归类，不按相似措辞重复拆类</small>
                      <h3>视频高频问题类别</h3>
                    </div>
                    <button
                      v-if="videoReady"
                      :disabled="analyzing"
                      @click="chooseVideoCategory('')"
                    >
                      跟随最高频类别
                    </button>
                  </div>
                  <div v-if="!videoCategory?.issues.length" class="safety-analysis-empty">
                    <h3>当前范围暂无视频问题</h3>
                  </div>
                  <div v-else-if="!videoReady" class="safety-analysis-empty">
                    <span class="safety-pending-mark">AI</span>
                    <h3>尚未完成视频风险归类</h3>
                    <p>
                      将同义的隔离、围栏和消防防护缺失合并统计。读取历史不调用
                      AI；首次使用新版分类或问题变化后，请先完成归类。
                    </p>
                    <p v-if="videoCategory.analysis?.classified_count">
                      已读取 {{ videoCategory.analysis.classified_count }}/{{
                        videoCategory.issues.length
                      }}
                      条历史分类。
                    </p>
                    <button
                      class="safety-primary"
                      :disabled="!canGenerate || analyzing || busy"
                      @click="analyzeVideo"
                    >
                      {{ analyzing ? '正在归类，请稍候…' : '调用 AI 归类视频问题' }}
                    </button>
                    <small v-if="!canGenerate"
                      >需要“生成AI报告”权限才能发起归类，查看和保存选择不调用 AI。</small
                    >
                  </div>
                  <template v-else>
                    <div class="safety-current-choice">
                      <span>报告选用</span><strong>{{ selectedVideoGroup?.name }}</strong
                      ><small
                        >{{ selectedVideoGroup?.count }}项 · {{ selectedVideoGroup?.percentage }}% ·
                        {{ videoHasManualSelection ? '人工选择' : '自动最高频' }}</small
                      >
                    </div>
                    <div
                      class="safety-video-groups"
                      role="radiogroup"
                      aria-label="视频典型问题类别"
                    >
                      <label
                        v-for="group in videoGroups"
                        :key="group.name"
                        :class="[
                          'safety-video-group',
                          { chosen: selectedVideoGroup?.name === group.name },
                        ]"
                      >
                        <input
                          type="radio"
                          name="safety-video-category"
                          :value="group.name"
                          :checked="selectedVideoGroup?.name === group.name"
                          @change="chooseVideoCategory(group.name)"
                        />
                        <span
                          ><b>{{ group.name }}</b
                          ><small>{{ group.count }}项 · {{ group.percentage }}%</small></span
                        >
                      </label>
                    </div>
                    <div class="safety-video-evidence-heading">
                      <h4>
                        该类别关联问题 <span>{{ selectedVideoGroup?.count }}项</span>
                      </h4>
                      <p>{{ selectedVideoGroup?.summary }}</p>
                    </div>
                    <div class="safety-current-choice" aria-live="polite">
                      <span>PPT 展示照片</span>
                      <strong v-if="typical('video')"
                        >#{{ typical('video').issue_id }} ·
                        {{ typical('video').station_name }}</strong
                      >
                      <strong v-else>该类别暂无可用照片，请选择其他类别</strong>
                      <small>{{ typicalSelection('video') ? '人工选择' : '自动推荐' }}</small>
                      <button
                        :disabled="!typicalSelection('video')"
                        @click="setTypical('video', '')"
                      >
                        恢复自动选图
                      </button>
                    </div>
                    <p class="safety-list-count">
                      选择一条有照片的问题用于
                      PPT。文字仍汇总所选类别，保存并重新生成后应用照片选择。
                    </p>
                    <input
                      v-model="issueKeyword"
                      type="search"
                      placeholder="在该类别中搜索问题ID、站点或描述"
                      aria-label="搜索视频类别内问题"
                    />
                    <p class="safety-list-count">
                      {{ videoCandidates.length }} 条问题 · 仅展示所选类别 · 点击照片可放大
                    </p>
                    <ul class="safety-candidate-list">
                      <li
                        v-for="issue in videoCandidates"
                        :key="issue.issue_id"
                        :class="[
                          'safety-candidate',
                          { chosen: typical('video')?.issue_id === issue.issue_id },
                        ]"
                      >
                        <input
                          :id="'safety-video-photo-' + issue.issue_id"
                          type="radio"
                          name="safety-video-photo"
                          :checked="typical('video')?.issue_id === issue.issue_id"
                          :disabled="!issue.issue_photo"
                          @change="setTypical('video', issue.issue_id)"
                        />
                        <label
                          :for="'safety-video-photo-' + issue.issue_id"
                          class="safety-candidate-copy"
                        >
                          <span
                            ><b>#{{ issue.issue_id }}</b
                            ><strong>{{ issue.station_name }}</strong
                            ><em v-if="typical('video')?.issue_id === issue.issue_id"
                              >PPT 选用</em
                            ></span
                          >
                          <p>{{ issue.description }}</p>
                          <small>{{ issue.category_name }}</small>
                        </label>
                        <button
                          v-if="issue.issue_photo"
                          class="safety-photo safety-list-photo"
                          :aria-label="'放大问题' + issue.issue_id + '的照片'"
                          @click="emit('photo', issue)"
                        >
                          <img
                            :src="resolveImage(issue.issue_photo)"
                            :alt="'问题 ' + issue.issue_id"
                            loading="lazy"
                          /></button
                        ><span v-else class="safety-missing-photo">暂无照片</span>
                      </li>
                    </ul>
                    <div v-if="!videoCandidates.length" class="safety-no-items">
                      没有符合条件的问题，请调整关键词。
                    </div>
                  </template>
                </section>
              </div>
            </template>
            <template v-else>
              <div v-if="active === 'evidence'" class="safety-focus">
                <div class="safety-scope-modes" role="group" aria-label="固定章节检查方式">
                  <button
                    v-for="mode in modes"
                    :key="mode.key"
                    :class="{ selected: evidenceMode === mode.key }"
                    :aria-pressed="evidenceMode === mode.key"
                    :disabled="analyzing || saving"
                    @click="selectEvidenceMode(mode.key)"
                  >
                    {{ mode.label }}检查
                  </button>
                </div>
                <label
                  >固定报告类别<select
                    :value="categoryKey"
                    :disabled="analyzing || saving"
                    @change="selectEvidenceCategory($event.target.value)"
                  >
                    <option
                      v-for="category in fixedCategories"
                      :key="category.key"
                      :value="category.key"
                    >
                      {{ category.name }}（{{ category.issues.length }}项 ·
                      {{ safetySlotLimit(category) }}张）
                    </option>
                  </select></label
                >
                <p>
                  先选择现场或视频，再进入固定类别。设备设施及其他隐患最多六张，其余章节最多三张。
                </p>
              </div>
              <div v-else class="safety-focus">
                <div class="safety-focus-select">
                  <label
                    >检查主题<select
                      :value="focusName"
                      :disabled="analyzing"
                      @change="setFocus($event.target.value)"
                    >
                      <option v-if="!focusName" value="" disabled>当前范围暂无现场问题</option>
                      <option
                        v-for="item in data.focus_categories"
                        :key="item.name"
                        :value="item.name"
                        :disabled="!item.count"
                      >
                        {{ item.label || item.name }}（{{ item.count }}项）
                      </option>
                    </select></label
                  >
                  <button :disabled="analyzing || !focusName" @click="setFocus('')">
                    恢复最高频主题
                  </button>
                </div>
                <p>
                  选择现场检查表的检查主题，再查看该主题下的问题表现分类。首次或数据变化后需完成 AI
                  再分类，之后可调整分类及描述。
                </p>
              </div>
              <div v-if="focusReading" class="safety-analysis-empty" role="status">
                <h3>正在读取已保存的主题分析</h3>
                <p>只读取历史结果，不调用 AI。</p>
              </div>
              <div v-else-if="focusError" class="safety-analysis-empty" role="alert">
                <h3>主题分析暂未读取成功</h3>
                <p>{{ focusError }}</p>
                <button @click="loadCategory(currentCategory, true)">重新读取</button>
              </div>
              <SafetyEvidencePanel
                v-else-if="currentCategory"
                :category="currentCategory"
                :override="currentOverride"
                :manual="currentManual"
                :monthly="active === 'analysis'"
                :can-generate="canGenerate"
                :grouping-dirty="groupingDirty"
                :busy="analyzing || saving || busy"
                :resolve-image="resolveImage"
                @generate="analyze"
                @photo="emit('photo', $event)"
                @assignment="setAssignment"
                @summary="setSummary"
                @representatives="setRepresentatives"
                @add-group="addGroup"
              />
              <p v-else class="safety-no-items">当前范围暂无可选类别。</p>
            </template>
          </div>
          <footer>
            <div>
              <small
                >保存配置不会调用
                AI。人工选择保存后，需重新生成报告才能应用；所有用户共享最新配置。</small
              ><small>{{ savedLabel }}</small>
            </div>
            <button :disabled="saving || analyzing" @click="close">取消</button
            ><button
              class="safety-primary"
              :disabled="
                saving ||
                analyzing ||
                busy ||
                focusReading ||
                (['analysis', 'evidence'].includes(active) && !!focusError)
              "
              @click="save"
            >
              {{ saving ? '正在保存…' : '保存配置' }}
            </button>
          </footer>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import SafetyRequirementsPanel from './SafetyRequirementsPanel.vue'
import SafetyEvidencePanel from './SafetyEvidencePanel.vue'
import {
  manualClassificationChanges,
  safetyFocusCategory,
  safetyFocusName,
  safetyAnalysisReady,
  safetyClassificationDraft,
  safetyFixedCategories,
  safetySlotLimit,
  safetyGroupingEdited,
  safetyMoveIssue,
  safetyIssueSearch,
  videoTypicalGroups,
  videoTypicalSelection,
  videoTypicalIssue,
} from '@/utils/safetyReportConfig'
const props = defineProps({
  month: String,
  dateFrom: String,
  dateTo: String,
  generatedAt: String,
  resolveImage: Function,
  canGenerate: Boolean,
  busy: Boolean,
})
const emit = defineEmits(['change', 'saved', 'photo'])
const data = ref(null),
  draft = ref({}),
  loading = ref(false),
  saving = ref(false),
  analyzing = ref(false)
const analysisBaseline = ref({})
const typicalMode = ref('onsite'),
  issueKeyword = ref(''),
  evidenceMode = ref('onsite')
const focusReading = ref(false),
  focusError = ref('')
const error = ref(''),
  dialogError = ref(''),
  active = ref(''),
  categoryKey = ref(''),
  keyword = ref(''),
  categories = ref([]),
  dialog = ref(null)
const titles = {
  source: '本次报告数据来源',
  typical: '典型问题与代表案例',
  analysis: '月度重点与问题再分类',
  evidence: '现场与视频固定章节证据',
}
const modes = [
  { key: 'onsite', label: '现场' },
  { key: 'video', label: '视频' },
]
const metrics = [
  { key: 'region_count', label: '涉及单位', unit: '个' },
  { key: 'station_count', label: '受检站点', unit: '座' },
  { key: 'issue_count', label: '问题总数', unit: '项' },
  { key: 'onsite_count', label: '现场问题', unit: '项' },
  { key: 'video_count', label: '视频问题', unit: '项' },
]
const clone = (value) => JSON.parse(JSON.stringify(value))
const params = () => ({ month: props.month, date_from: props.dateFrom, date_to: props.dateTo })
let sequence = 0,
  timer,
  controller,
  previousFocus
let focusSequence = 0,
  focusController,
  focusLoaded = new Set()
const savedLabel = computed(() =>
  data.value?.meta?.updated_by_name
    ? `最近保存：${data.value.meta.updated_by_name} · ${data.value.meta.updated_at}`
    : '尚未保存人工配置，默认使用全部数据和 AI 自动分析。',
)
const visibleStations = computed(() =>
  (data.value?.stations || []).filter((s) =>
    `${s.station_name} ${s.unit_name}`.includes(keyword.value.trim()),
  ),
)
const currentCategory = computed(() => categories.value.find((c) => c.key === categoryKey.value))
const currentOverride = computed(() => draft.value.classifications[categoryKey.value])
const manualChanges = computed(() =>
  manualClassificationChanges(
    draft.value.classifications,
    analysisBaseline.value,
    data.value?.settings.classifications,
  ),
)
const currentManual = computed(() => manualChanges.value[categoryKey.value] || {})
const groupingDirty = computed(() =>
  safetyGroupingEdited(currentOverride.value, analysisBaseline.value[categoryKey.value]),
)
const fixedCategories = computed(() => safetyFixedCategories(categories.value, evidenceMode.value))
const focusName = computed(() =>
  safetyFocusName(draft.value.focus_category, data.value?.focus_categories),
)
const typicalCandidates = computed(() =>
  safetyIssueSearch(modeIssues(typicalMode.value), issueKeyword.value),
)
const videoCategory = computed(() => categories.value.find((c) => c.key === 'video:__typical__'))
const videoReady = computed(() => safetyAnalysisReady(videoCategory.value))
const videoGroups = computed(() => videoTypicalGroups(videoCategory.value))
const selectedVideoGroup = computed(() =>
  videoTypicalSelection(draft.value.typical_video_category, videoGroups.value),
)
const videoHasManualSelection = computed(() =>
  videoGroups.value.some((g) => g.name === draft.value.typical_video_category),
)
const videoCandidates = computed(() => {
  const ids = new Set(selectedVideoGroup.value?.issue_ids || [])
  return safetyIssueSearch(
    modeIssues('video').filter((i) => ids.has(i.issue_id)),
    issueKeyword.value,
  )
})
const modeIssues = (mode) => (data.value?.issues || []).filter((i) => i.mode === mode)
function typical(mode) {
  const list = modeIssues(mode),
    manual = draft.value.typical_issue_ids[mode]
  if (mode === 'video') return videoTypicalIssue(list, selectedVideoGroup.value, manual)
  const chosen = list.find((i) => i.issue_id === manual)
  if (chosen) return chosen
  const groups =
    categories.value.find((c) => c.key === `${mode}:__typical__`)?.analysis?.groups || []
  for (const group of groups) {
    const issue = list.find((i) => group.issue_ids.includes(i.issue_id) && i.issue_photo)
    if (issue) return issue
  }
  return null
}
function typicalSelection(mode) {
  const id = draft.value.typical_issue_ids[mode]
  if (mode === 'video') return typical(mode)?.issue_id === id ? id : ''
  return modeIssues(mode).some((issue) => issue.issue_id === id) ? id : ''
}
function setTypical(mode, value) {
  if (value) draft.value.typical_issue_ids[mode] = Number(value)
  else delete draft.value.typical_issue_ids[mode]
}
function selectTypicalMode(mode) {
  typicalMode.value = mode
  issueKeyword.value = ''
}
function chooseVideoCategory(name) {
  draft.value.typical_video_category = name
  delete draft.value.typical_issue_ids.video
  issueKeyword.value = ''
}
async function analyzeVideo() {
  if (!props.canGenerate || props.busy || analyzing.value || !videoCategory.value?.issues.length)
    return
  const loadSequence = sequence
  analyzing.value = true
  dialogError.value = ''
  try {
    const { data: response } = await axios.post(
      '/api/inspection-reports/safety-analysis',
      {
        ...params(),
        mode: 'video',
        category: '__typical__',
        revision: data.value.meta.revision,
        data_signature: data.value.data_signature,
      },
      { timeout: 300000 },
    )
    if (loadSequence !== sequence || active.value !== 'typical') return
    videoCategory.value.analysis = response.analysis
  } catch (err) {
    if (loadSequence === sequence)
      dialogError.value = err.response?.data?.error || '视频问题归类未完成，请稍后重试。'
  } finally {
    analyzing.value = false
  }
}
function adopt(value) {
  data.value = value
  emit('change', value.settings)
}
async function load(keepVisible = false) {
  const id = ++sequence
  controller?.abort()
  controller = new AbortController()
  focusSequence++
  focusController?.abort()
  focusReading.value = false
  active.value = ''
  loading.value = keepVisible !== true
  if (!props.dateFrom || !props.dateTo || props.dateFrom > props.dateTo) {
    data.value = null
    loading.value = false
    emit('change', null)
    return
  }
  error.value = ''
  emit('change', null)
  try {
    const response = await axios.get('/api/inspection-reports/safety-config', {
      params: params(),
      signal: controller.signal,
    })
    if (id === sequence) adopt(response.data)
  } catch (err) {
    if (id === sequence && !axios.isCancel(err))
      error.value = err.response?.data?.error || '安全报告配置读取失败。'
  } finally {
    if (id === sequence) loading.value = false
  }
}
function ensureCategory(category, manual = data.value.settings.classifications) {
  draft.value.classifications[category.key] = safetyClassificationDraft(
    category,
    manual[category.key],
  )
}
async function requirementsSaved() {
  emit('saved')
  await load(true)
}
async function open(name) {
  draft.value = clone(data.value.settings)
  draft.value.classifications ||= {}
  draft.value.typical_issue_ids ||= {}
  categories.value = clone(data.value.categories)
  for (const category of categories.value) ensureCategory(category)
  analysisBaseline.value = clone(draft.value.classifications)
  categoryKey.value = ''
  typicalMode.value = 'onsite'
  evidenceMode.value = 'onsite'
  issueKeyword.value = ''
  focusLoaded = new Set()
  focusError.value = ''
  keyword.value = ''
  dialogError.value = ''
  active.value = name
  previousFocus = document.activeElement
  await nextTick()
  dialog.value?.focus()
  if (name === 'analysis') loadFocus()
  else if (name === 'evidence') selectEvidenceMode('onsite')
}
function close() {
  if (saving.value || analyzing.value) return
  active.value = ''
  focusSequence++
  focusController?.abort()
  focusReading.value = false
  previousFocus?.focus()
}
function trapFocus(event) {
  const nodes = [
    ...dialog.value.querySelectorAll(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]',
    ),
  ]
  const target = event.shiftKey ? nodes.at(-1) : nodes[0]
  if (document.activeElement === (event.shiftKey ? nodes[0] : nodes.at(-1))) {
    event.preventDefault()
    target?.focus()
  }
}
function setAll(checked) {
  draft.value.station_ids = checked ? null : data.value.stations.map((s) => s.station_id)
}
function toggleStation(id, checked) {
  if (draft.value.station_ids === null)
    draft.value.station_ids = data.value.stations.map((s) => s.station_id)
  draft.value.station_ids = checked
    ? [...new Set([...draft.value.station_ids, id])]
    : draft.value.station_ids.filter((i) => i !== id)
}
function setFocus(value) {
  if (analyzing.value) return
  draft.value.focus_category = value
  issueKeyword.value = ''
  loadFocus()
}
function selectEvidenceMode(mode) {
  if (analyzing.value || saving.value) return
  evidenceMode.value = mode
  const options = fixedCategories.value
  selectEvidenceCategory((options.find((item) => item.issues.length) || options[0])?.key || '')
}
function selectEvidenceCategory(key) {
  if (analyzing.value || saving.value) return
  categoryKey.value = key
  loadCategory(currentCategory.value)
}
function loadFocus() {
  const focus = focusName.value
  const category = focus ? safetyFocusCategory(focus, data.value.issues) : null
  if (category && !categories.value.some((item) => item.key === category.key)) {
    categories.value.push(category)
    ensureCategory(category)
    analysisBaseline.value[category.key] = clone(draft.value.classifications[category.key])
  }
  categoryKey.value = category?.key || ''
  return loadCategory(currentCategory.value)
}
async function loadCategory(category, force = false) {
  const id = ++focusSequence
  focusController?.abort()
  focusReading.value = false
  focusError.value = ''
  if (!category) return
  const key = category.key
  if (focusLoaded.has(key) && !force) return
  focusController = new AbortController()
  focusReading.value = true
  focusError.value = ''
  dialogError.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/safety-analysis', {
      params: { ...params(), mode: category.mode, category: category.category },
      signal: focusController.signal,
    })
    if (
      id !== focusSequence ||
      !['analysis', 'evidence'].includes(active.value) ||
      categoryKey.value !== key
    )
      return
    if (
      response.data.revision !== data.value.meta.revision ||
      response.data.data_signature !== data.value.data_signature
    )
      throw new Error('数据或配置已有更新，请关闭弹窗并重新读取配置，避免覆盖其他用户的保存。')
    const entry = categories.value.find((item) => item.key === key)
    const manual = manualChanges.value
    entry.issues = response.data.issues
    entry.analysis = response.data.analysis
    analysisBaseline.value[key] = safetyClassificationDraft(
      entry,
      data.value.settings.classifications[key],
    )
    ensureCategory(entry, manual)
    focusLoaded.add(key)
  } catch (err) {
    if (id === focusSequence && !axios.isCancel(err))
      focusError.value = err.response?.data?.error || err.message || '主题分析读取失败。'
  } finally {
    if (id === focusSequence) focusReading.value = false
  }
}
function setAssignment(id, name) {
  if (analyzing.value || saving.value || props.busy) return
  const value = name.trim()
  if (value) safetyMoveIssue(currentOverride.value, id, value)
}
function setSummary(name, value) {
  if (!analyzing.value && !saving.value && !props.busy)
    currentOverride.value.summaries[name] = value
}
function setRepresentatives(name, ids) {
  if (!analyzing.value && !saving.value && !props.busy)
    currentOverride.value.representatives[name] = ids
}
function addGroup(name) {
  if (analyzing.value || saving.value || props.busy || !name || !currentOverride.value) return
  currentOverride.value.summaries[name] ||= ''
}
async function analyze() {
  if (
    !props.canGenerate ||
    props.busy ||
    saving.value ||
    groupingDirty.value ||
    analyzing.value ||
    focusReading.value ||
    !currentCategory.value?.issues.length
  )
    return
  analyzing.value = true
  dialogError.value = ''
  const loadSequence = sequence
  try {
    const c = currentCategory.value
    const response = await axios.post(
      '/api/inspection-reports/safety-analysis',
      {
        ...params(),
        mode: c.mode,
        category: c.category,
        revision: data.value.meta.revision,
        data_signature: data.value.data_signature,
      },
      { timeout: 300000 },
    )
    if (
      loadSequence !== sequence ||
      !['analysis', 'evidence'].includes(active.value) ||
      categoryKey.value !== c.key
    )
      return
    const manual = manualChanges.value
    c.analysis = response.data.analysis
    analysisBaseline.value[c.key] = safetyClassificationDraft(
      c,
      data.value.settings.classifications[c.key],
    )
    ensureCategory(c, manual)
    issueKeyword.value = ''
  } catch (err) {
    if (loadSequence === sequence && ['analysis', 'evidence'].includes(active.value))
      dialogError.value = err.response?.data?.error || 'AI 分析未完成，原保存配置不变。请稍后重试。'
  } finally {
    analyzing.value = false
  }
}
async function save() {
  if (
    saving.value ||
    analyzing.value ||
    props.busy ||
    focusReading.value ||
    (['analysis', 'evidence'].includes(active.value) && focusError.value)
  )
    return
  saving.value = true
  const loadSequence = sequence
  dialogError.value = ''
  try {
    // Viewing AI evidence does not turn every generated grouping into a manual override.
    const settings = clone(draft.value)
    settings.classifications = ['analysis', 'evidence'].includes(active.value)
      ? manualClassificationChanges(
          settings.classifications,
          analysisBaseline.value,
          data.value.settings.classifications,
        )
      : data.value.settings.classifications
    const response = await axios.put('/api/inspection-reports/safety-config', {
      ...params(),
      settings,
      revision: data.value.meta.revision,
      data_signature: data.value.data_signature,
    })
    if (loadSequence !== sequence) return
    adopt(response.data)
    active.value = ''
    emit('saved')
    previousFocus?.focus()
  } catch (err) {
    if (loadSequence === sequence)
      dialogError.value = err.response?.data?.error || '配置保存失败，请重试。'
  } finally {
    saving.value = false
  }
}
watch(
  () => [props.month, props.dateFrom, props.dateTo, props.generatedAt],
  () => {
    clearTimeout(timer)
    timer = setTimeout(load, 180)
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  sequence++
  controller?.abort()
  clearTimeout(timer)
  focusSequence++
  focusController?.abort()
})
</script>

<style scoped>
.safety-config {
  color: #294b65;
}
.safety-step-label {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.7px;
}
.safety-source {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 18px;
  padding: 24px;
  border: 1px solid #b9cddc;
  border-left: 4px solid #205977;
  border-radius: 16px;
  background: linear-gradient(110deg, #edf4f8, #fff);
}
.safety-source > div {
  flex: 1;
}
.safety-config h3 {
  margin: 6px 0 10px;
  font-size: 20px;
  color: #173951;
}
.safety-config p {
  font-size: 15px;
  line-height: 1.7;
  margin: 6px 0 16px;
}
.safety-config small {
  color: #527184;
}
.safety-config button,
.safety-dialog button {
  border: 1px solid #b6cddd;
  border-radius: 9px;
  padding: 10px 16px;
  background: #fff;
  color: #225373;
  font-weight: 600;
  cursor: pointer;
}
.safety-config button:disabled,
.safety-dialog button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.safety-source dl {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  width: 100%;
  margin: 0;
  border: 1px solid #cddce8;
  border-radius: 10px;
  padding: 16px 0;
  background: #fff;
}
.safety-source dl > div {
  padding: 0 20px;
  border-right: 1px solid #d7e3eb;
}
.safety-source dl > div:last-child {
  border-right: 0;
}
.safety-source dt {
  font-size: 14px;
  color: #47667b;
}
.safety-source dd {
  margin: 6px 0 0;
  font-size: 27px;
  font-weight: 700;
  color: #176c85;
}
.safety-source dd small {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 400;
}
.safety-panels {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  margin-top: 18px;
  border: 1px solid #b9cddc;
  border-radius: 16px;
  background: #bfd2df;
  overflow: hidden;
}
.safety-panels > .safety-tool {
  border: 0;
  margin: 0;
  border-radius: 0;
  padding: 25px 28px;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
  font-size: 15px;
  line-height: 1.7;
}
.safety-tool .safety-step-label {
  line-height: 1.4;
  padding: 4px 9px;
  border-radius: 5px;
  color: #255c7e;
  background: #e8f1f8;
  margin-bottom: 10px;
}
.safety-tool-focus .safety-step-label {
  background: #eef1f4;
  color: #415f74;
}
.safety-tool-evidence .safety-step-label {
  background: #e5f1ee;
  color: #22675d;
}
.safety-tool > button {
  margin-top: auto;
  min-height: 44px;
  font-size: 15px;
  line-height: 1.5;
  box-sizing: border-box;
  border-color: #9dbbd0;
  box-shadow: 0 2px 5px #17395108;
}
.safety-tool > button:hover:not(:disabled) {
  background: #edf5f9;
  border-color: #4c809e;
}
.safety-tool p {
  max-width: 64ch;
  margin-bottom: 20px;
  color: #496579;
}
.safety-saved {
  display: flex;
  align-items: baseline;
  gap: 9px;
  margin: 16px 0 0;
  padding: 12px 15px;
  border: 1px solid #dce6ed;
  border-radius: 10px;
  background: #f4f8fb;
  color: #496579;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.7;
}
.safety-saved-mark {
  flex: 0 0 6px;
  height: 6px;
  border-radius: 50%;
  background: #4c839a;
}
.safety-overlay {
  position: fixed;
  inset: 0;
  z-index: 4200;
  background: #102a47a8;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #243f55;
}
.safety-dialog {
  width: min(1240px, 96vw);
  max-height: 90vh;
  background: #fff;
  display: flex;
  flex-direction: column;
  border-radius: 18px;
  box-shadow: 0 24px 90px #061d3d66;
  overflow: hidden;
  font-size: 15px;
  line-height: 1.6;
}
.safety-dialog header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 26px;
  background: #f1f7fb;
  border-bottom: 1px solid #c6d8e6;
}
.safety-dialog h2 {
  margin: 6px 0 0;
  font-size: 22px;
}
.safety-dialog small {
  color: #5a7387;
  font-size: 13px;
}
.safety-dialog button {
  font-size: 14px;
}
.safety-dialog .safety-close {
  font-size: 25px;
  padding: 3px 12px;
}
.safety-dialog-body {
  overflow: auto;
  padding: 24px;
  min-height: 160px;
}
.safety-dialog input:not([type='checkbox']):not([type='radio']),
.safety-dialog select,
.safety-dialog textarea {
  width: 100%;
  border: 1px solid #b2c9db;
  border-radius: 8px;
  padding: 10px;
  color: #233e55;
  background: #fff;
  box-sizing: border-box;
  font: inherit;
  margin-top: 7px;
}
.safety-dialog label {
  font-size: 14px;
}
.safety-check {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid #d0dfe9;
  border-radius: 10px;
  background: #f7fafc;
}
.safety-check small {
  display: block;
  margin-top: 4px;
}
.safety-stations {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 18px;
}
.safety-choice-layout {
  display: grid;
  grid-template-columns: 205px minmax(0, 1fr);
  gap: 22px;
}
.safety-mode-nav,
.safety-subgroup-nav {
  align-self: start;
  padding: 14px;
  background: #f2f6fa;
  border: 1px solid #d2e0eb;
  border-radius: 12px;
}
.safety-mode-nav > small,
.safety-subgroup-nav > small {
  display: block;
  margin: 0 0 12px;
  font-size: 12px;
  letter-spacing: 1px;
}
.safety-mode-nav > button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 12px;
  margin-bottom: 10px;
  text-align: left;
}
.safety-mode-nav button small {
  display: block;
  font-size: 13px;
  margin-top: 5px;
  font-weight: 400;
}
.safety-mode-nav button.selected {
  background: #194d6b;
  border-color: #194d6b;
  color: #fff;
}
.safety-mode-nav button.selected small {
  color: #c3e4ed;
}
.mode-count {
  background: #e5f0f6;
  color: #215a77;
  border-radius: 7px;
  padding: 4px 7px;
  font-size: 13px;
}
.safety-mode-nav p,
.safety-edit-hint {
  color: #5a7387;
  font-size: 14px;
  line-height: 1.7;
}
.safety-choice-content,
.safety-analysis-content {
  min-width: 0;
}
.safety-list-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.safety-list-heading h3 {
  margin: 5px 0 14px;
  font-size: 20px;
}
.safety-current-choice {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 12px 14px;
  background: #edf6f7;
  border: 1px solid #bcdce0;
  border-radius: 9px;
  font-size: 14px;
  margin-bottom: 12px;
}
.safety-current-choice > span {
  color: #4f737b;
}
.safety-current-choice > strong {
  flex: 1;
}
.safety-list-count {
  font-size: 14px;
  color: #5a7387;
  margin: 14px 0 8px;
}
.safety-candidate-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.safety-candidate {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) 110px;
  align-items: center;
  gap: 12px;
  border: 1px solid #d1dee8;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 10px;
  background: #fff;
}
.safety-candidate.chosen {
  border-color: #2583a0;
  background: #f0f8fb;
  box-shadow: inset 3px 0 #2583a0;
}
.safety-candidate input[type='radio'] {
  width: 18px;
  height: 18px;
  margin: 0;
  accent-color: #17637e;
  cursor: pointer;
}
.safety-candidate-copy {
  cursor: pointer;
  min-width: 0;
  overflow-wrap: anywhere;
}
.safety-candidate-copy > span {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.safety-candidate-copy b {
  color: #17637e;
}
.safety-candidate-copy em,
.safety-ready-badge {
  font-size: 12px;
  font-style: normal;
  font-weight: 600;
  color: #196d62;
  background: #dff0eb;
  border-radius: 5px;
  padding: 4px 7px;
  white-space: nowrap;
}
.safety-candidate-copy p {
  margin: 8px 0;
  line-height: 1.65;
  white-space: pre-line;
}
.safety-list-photo,
.safety-missing-photo {
  width: 110px;
}
.safety-missing-photo {
  display: grid;
  place-items: center;
  height: 82px;
  font-size: 12px;
  background: #f1f5f8;
  color: #73889a;
  border-radius: 8px;
}
.safety-photo {
  padding: 0 !important;
  border: 0 !important;
  background: transparent !important;
}
.safety-photo img {
  display: block;
  max-width: 100%;
  width: 100%;
  height: 110px;
  object-fit: contain;
  background: #edf2f5;
  border-radius: 7px;
}
.safety-focus {
  padding: 16px;
  background: #eaf4f8;
  border-radius: 10px;
  margin-bottom: 20px;
}
.safety-focus p {
  font-size: 14px;
  line-height: 1.7;
  margin-bottom: 0;
}
.safety-scope-modes {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}
.safety-scope-modes button.selected {
  background: #175c78;
  color: #fff;
  border-color: #175c78;
}
.safety-focus-select {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}
.safety-focus-select label {
  flex: 1;
  font-weight: 600;
}
.safety-focus-select > button {
  flex-shrink: 0;
}
.safety-analysis-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 42px 24px;
  text-align: center;
  border: 1px dashed #b9cddd;
  border-radius: 12px;
  background: #f8fbfd;
}
.safety-analysis-empty h3 {
  font-size: 19px;
  margin: 16px 0 0;
}
.safety-analysis-empty p {
  max-width: 620px;
  color: #526c7e;
  font-size: 14px;
  line-height: 1.8;
}
.safety-analysis-empty > small {
  margin-top: 14px;
}
.safety-pending-mark {
  padding: 12px;
  background: #e1edf5;
  border-radius: 12px;
  color: #246c91;
  font-weight: 700;
}
.safety-analysis-layout {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  gap: 20px;
}
.safety-analysis-layout nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.safety-analysis-layout nav button {
  text-align: left;
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  overflow-wrap: anywhere;
}
.safety-subgroup-nav > button span {
  border-radius: 5px;
  background: #e3edf2;
  color: #335e75;
  padding: 1px 6px;
  align-self: start;
}
.safety-analysis-layout nav button.selected {
  background: #175c78;
  color: #fff;
  border-color: #175c78;
}
.safety-analysis-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.safety-analysis-heading h3 {
  margin: 8px 0 0;
  font-size: 20px;
}
.safety-analysis-heading h3 span {
  font-size: 14px;
  color: #658296;
  margin-left: 6px;
}
.safety-group-summary {
  display: block;
  padding: 12px;
  background: #f2f7fa;
  margin-top: 12px;
  border-radius: 8px;
}
.safety-new-group {
  border-top: 1px solid #d0dfe8;
  margin-top: 10px;
  padding-top: 8px;
}
.safety-new-group button {
  margin-top: 8px;
  width: 100%;
  justify-content: center !important;
}
.safety-no-items {
  padding: 25px 12px;
  text-align: center;
  color: #698092;
  font-size: 14px;
}
.safety-issue {
  display: grid;
  grid-template-columns: 115px 1fr;
  gap: 16px;
  padding: 20px 0;
  border-bottom: 1px solid #d6e2ea;
}
.safety-issue p {
  white-space: pre-line;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.safety-issue label {
  display: block;
  margin: 10px 0;
}
.safety-issue details {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-line;
  color: #526c7e;
}
.safety-dialog footer {
  border-top: 1px solid #ccdce7;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  background: #f8fbfd;
}
.safety-dialog footer div {
  flex: 1;
}
.safety-dialog footer small {
  display: block;
  margin: 3px 0;
  font-size: 13px;
}
.safety-dialog footer small:last-child {
  color: #496579;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.7;
}
.safety-mode-note {
  border-top: 1px solid #d2dfe7;
  margin-top: 16px;
  padding-top: 12px;
  color: #527184;
  font-size: 14px;
}
.safety-video-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 18px 0;
}
.safety-video-group {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px;
  border: 1px solid #c8d8e4;
  border-radius: 10px;
  cursor: pointer;
}
.safety-video-group.chosen {
  background: #eaf5f8;
  border-color: #227f9a;
  box-shadow: inset 3px 0 #227f9a;
}
.safety-video-group input {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  accent-color: #17637e;
  margin: 3px 0 0;
}
.safety-video-group small {
  display: block;
  margin-top: 5px;
}
.safety-video-evidence-heading {
  padding: 14px 16px;
  background: #f3f7fa;
  border-radius: 9px;
  margin: 16px 0 10px;
}
.safety-video-evidence-heading h4 {
  font-size: 16px;
  margin: 0;
}
.safety-video-evidence-heading h4 span {
  color: #17637e;
  margin-left: 8px;
}
.safety-video-evidence-heading p {
  color: #48697e;
  font-size: 14px;
  margin-bottom: 0;
}
.safety-dialog .safety-primary {
  background: #17637e;
  color: #fff;
  border-color: #17637e;
}
.safety-error {
  background: #fff1ef;
  color: #a1332a;
  padding: 12px;
  border-radius: 8px;
}
.safety-config button:hover:not(:disabled),
.safety-dialog button:hover:not(:disabled) {
  box-shadow: 0 2px 7px #163f5f26;
}
.safety-dialog :focus-visible {
  outline: 3px solid #64a6d1;
  outline-offset: 2px;
}
@media (min-width: 701px) and (max-width: 1000px) {
  .safety-panels {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 700px) {
  .safety-overlay {
    padding: 8px;
  }
  .safety-dialog {
    max-height: 96dvh;
    width: 100%;
  }
  .safety-dialog header,
  .safety-dialog-body {
    padding: 16px;
  }
  .safety-panels,
  .safety-choice-layout {
    grid-template-columns: 1fr;
  }
  .safety-source dl {
    grid-template-columns: repeat(3, 1fr);
    gap: 16px 0;
  }
  .safety-source dl > div {
    padding: 0 12px;
  }
  .safety-source dl > div:nth-child(3) {
    border-right: 0;
  }
  .safety-stations {
    grid-template-columns: 1fr;
  }
  .safety-analysis-layout {
    grid-template-columns: 1fr;
  }
  .safety-analysis-layout nav {
    flex-direction: column;
  }
  .safety-analysis-layout nav button {
    width: 100%;
  }
  .safety-analysis-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .safety-issue {
    grid-template-columns: 80px 1fr;
  }
  .safety-issue .safety-missing-photo {
    width: 80px;
  }
  .safety-mode-nav {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .safety-mode-nav > small,
  .safety-mode-nav > p {
    grid-column: 1 / -1;
    margin: 0;
  }
  .safety-mode-note {
    display: none;
  }
  .safety-current-choice {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 6px;
  }
  .safety-video-groups {
    grid-template-columns: 1fr;
  }
  .safety-mode-nav > button {
    margin: 0;
    padding: 12px 8px;
  }
  .safety-mode-nav .mode-count {
    display: none;
  }
  .safety-candidate {
    grid-template-columns: 18px minmax(0, 1fr) 76px;
    gap: 8px;
    padding: 10px;
  }
  .safety-candidate .safety-list-photo,
  .safety-candidate .safety-missing-photo {
    width: 76px;
  }
  .safety-list-heading {
    align-items: flex-start;
    flex-direction: column;
    margin-bottom: 14px;
  }
  .safety-focus-select {
    flex-wrap: wrap;
  }
  .safety-focus-select label {
    flex-basis: 100%;
    min-width: 0;
  }
  .safety-analysis-empty {
    padding: 22px 14px;
  }
  .safety-dialog footer {
    flex-wrap: wrap;
    padding: 12px;
  }
  .safety-dialog footer div {
    flex-basis: 100%;
  }
}
</style>
