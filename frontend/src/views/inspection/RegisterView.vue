<template>
  <div class="page-shell register-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>巡检登记</h2>
      </div>
    </div>

    <div class="form-card card-surface">
      <div v-if="!hasPermission" class="permission-card">
        <div class="permission-icon">!</div>
        <div class="permission-title">无权限访问</div>
        <div class="permission-desc">当前账号无权进行巡检登记，请使用督导组账号登录后操作。</div>
      </div>

      <form v-else class="register-form" @submit.prevent="handleSubmit">
        <div class="section-title">基础信息</div>

        <div class="form-grid">
          <div class="form-item form-item-full">
            <label>创建时间</label>
            <input :value="createdTime" type="text" readonly />
          </div>

          <div class="form-item form-item-full">
            <label>站点名称</label>
            <div class="search-select" ref="stationSelectRef">
              <input v-model="stationSearch" type="text" placeholder="搜索并选择站点名称" @focus="openStationDropdown"
                @input="handleStationInput" />
              <div v-if="stationDropdownVisible" class="search-select-dropdown">
                <div v-for="station in filteredStations" :key="station.id" class="search-select-option"
                  @click="selectStation(station)">
                  <div class="option-main">{{ station.station_name }}</div>
                  <div class="option-sub">{{ station.region || '未设置所属地' }}</div>
                </div>
                <div v-if="filteredStations.length === 0" class="search-select-empty">无匹配站点</div>
              </div>
            </div>
          </div>
          <div class="form-item form-item-full">
            <label>是否发现问题</label>
            <div class="issue-toggle-group" role="radiogroup" aria-label="是否发现问题">
              <button type="button" class="issue-toggle-btn" :class="{ active: normalizedHasIssue === 'yes' }"
                @click="form.hasIssue = 'yes'">
                发现问题
              </button>
              <button type="button" class="issue-toggle-btn" :class="{ active: normalizedHasIssue === 'no' }"
                @click="form.hasIssue = 'no'">
                未发现问题
              </button>
            </div>
          </div>
          <div v-if="normalizedHasIssue === 'yes'" class="form-item form-item-full">
            <label>规范引用方式</label>
            <div class="reference-mode-panel" role="radiogroup" aria-label="规范引用方式">
              <button type="button" class="reference-mode-btn" :class="{ active: referenceMode === 'manual' }"
                @click="setReferenceMode('manual')">
                <strong>人工引用规范</strong>
                <span>手动输入{{ standardSourceMode === 'internal' ? '内部规范ID' : '外部规范ID' }}，按现有流程选择规范。</span>
              </button>
              <button type="button" class="reference-mode-btn reference-mode-btn-ai"
                :class="{ active: referenceMode === 'ai' }" @click="setReferenceMode('ai')">
                <strong>AI引用规范</strong>
                <span>先填写问题描述，由AI从{{ standardSourceModeLabel }}推荐候选规范。</span>
              </button>
            </div>
          </div>

          <div v-if="normalizedHasIssue === 'yes' && referenceMode === 'manual'" class="form-item form-item-full">
            <label>搜索并选择规范ID</label>
            <div class="search-select" ref="standardSelectRef">
              <input v-model="standardSearch" type="text" placeholder="输入规范ID搜索" @focus="openStandardDropdown"
                @input="handleStandardInput" />
              <div v-if="standardDropdownVisible" class="search-select-dropdown search-select-dropdown-wide">
                <div v-for="standard in filteredStandards" :key="getStandardIdentity(standard)"
                  class="search-select-option" @click="selectStandard(standard)">
                  <div class="option-main">
                    {{ standard.standard_id }}｜{{ getStandardTitle(standard) }}
                  </div>
                  <div class="option-sub option-table-name">{{ standard.inspection_table_name || '未关联外部检查表' }}</div>
                  <div class="option-sub standard-detail-preview">{{ getRegisterStandardPreview(standard) }}</div>
                </div>
                <div v-if="filteredStandards.length === 0" class="search-select-empty">无匹配规范</div>
              </div>
            </div>
          </div>

          <div v-if="normalizedHasIssue === 'yes' && referenceMode === 'ai'" class="form-item form-item-full">
            <label>AI引用规范</label>
            <div class="ai-reference-card">
              <div class="ai-reference-header">
                <div>
                  <div class="ai-reference-kicker">DEEPSEEK ASSISTED MATCH</div>
                  <h3>根据实际问题描述推荐规范</h3>
                  <p>AI会读取当前{{ standardSourceModeLabel }}资料并给出候选项，最终仍由你确认引用哪一条规范。</p>
                </div>
              </div>

              <div class="ai-description-field">
                <label>实际问题描述</label>
                <textarea v-model="form.description" rows="5" placeholder="请先描述现场发现的问题，例如设备位置、异常现象、现场影响等。"></textarea>
              </div>

              <div class="ai-reference-actions">
                <button class="btn btn-primary" type="button" :disabled="aiMatching || !form.description.trim()"
                  @click="runAiStandardMatch">
                  {{ aiMatching ? 'AI匹配中...' : 'AI匹配规范' }}
                </button>
                <button class="btn btn-secondary" type="button" :disabled="aiMatching"
                  @click="setReferenceMode('manual')">
                  改用人工引用
                </button>
              </div>

              <div v-if="aiMatching" class="ai-matching-panel">
                <div class="ai-matching-title">正在匹配巡检规范库</div>
                <div class="ai-matching-desc">系统正在分析问题描述和规范条目，请稍候。</div>
                <div class="ai-progress-bar"><span></span></div>
              </div>

              <div v-else-if="aiReferenceMessage" class="ai-reference-message" :class="aiReferenceMessageType">
                {{ aiReferenceMessage }}
              </div>

              <div v-if="aiRecommendations.length" class="ai-recommendation-list">
                <button v-for="candidate in aiRecommendations" :key="getStandardIdentity(candidate)" type="button"
                  class="ai-recommendation-card"
                  :class="{ selected: String(candidate.standard_id) === String(form.standardId) }"
                  @click="selectRecommendedStandard(candidate)">
                  <div class="ai-recommendation-top">
                    <span class="ai-recommendation-code">{{ candidate.standard_id }}</span>
                    <span class="ai-confidence" :class="`level-${candidate.confidence || '中'}`">
                      {{ candidate.confidence || '中' }}相关
                    </span>
                  </div>
                  <div class="ai-recommendation-title">{{ getStandardTitle(candidate) }}</div>
                  <div class="ai-recommendation-table">{{ candidate.inspection_table_name || '未命名检查表' }}</div>
                  <div class="ai-recommendation-reason">{{ candidate.reason || 'AI认为该规范与问题描述相关。' }}</div>
                </button>
              </div>

              <div v-if="aiNoRelated" class="ai-no-related">
                <strong>未找到明确相关规范</strong>
                <span>可以补充更具体的问题描述后重新匹配，也可以切换到人工引用规范。</span>
              </div>
            </div>
          </div>

          <div v-if="normalizedHasIssue !== 'yes'" class="form-item form-item-full">
            <label>检查表</label>
            <div class="search-select" ref="tableSelectRef">
              <input v-model="tableSearch" type="text" placeholder="搜索并选择检查表" @focus="openTableDropdown"
                @input="handleTableInput" />
              <div v-if="tableDropdownVisible" class="search-select-dropdown">
                <div v-for="table in filteredInspectionTables" :key="table.id" class="search-select-option"
                  @click="selectInspectionTable(table)">
                  <div class="option-main">{{ table.table_name }}</div>
                  <div class="option-sub">{{ table.description || '未设置说明' }}</div>
                </div>
                <div v-if="filteredInspectionTables.length === 0" class="search-select-empty">无匹配检查表</div>
              </div>
            </div>
          </div>

          <template v-if="normalizedHasIssue === 'yes' && selectedStandard">
            <div class="form-item form-item-full selected-standard-field selected-standard-first"
              ref="selectedStandardStartRef">
              <label>{{ selectedStandard.internal_standard_id ? '内部规范ID' : '外部规范ID' }}</label>
              <input :value="selectedStandard.standard_id || ''" type="text" readonly />
            </div>

            <div class="form-item form-item-full selected-standard-field">
              <label>{{ selectedStandard.internal_standard_id ? '关联检查表' : '检查表名称' }}</label>
              <input :value="selectedStandard.inspection_table_name || ''" type="text" readonly />
            </div>

            <div class="form-item form-item-full selected-standard-field selected-standard-detail">
              <label>规范详情</label>
              <textarea :value="normalizeStandardDetailForRegister(selectedStandard.standard_detail_text || '')"
                rows="8" readonly></textarea>
            </div>
          </template>
        </div>

        <template v-if="showIssueFields">
          <div class="section-title issue-section-title">{{ referenceMode === 'ai' ? '问题照片' : '问题信息' }}</div>

          <div class="form-grid">
            <div v-if="referenceMode === 'manual'" class="form-item form-item-full">
              <label>实际问题描述</label>
              <textarea v-model="form.description" rows="4" placeholder="请填写现场实际问题描述"></textarea>
            </div>

            <div ref="issuePhotoUploadSectionRef" class="form-item form-item-full upload-follow-anchor">
              <label>上传问题照片</label>
              <div class="upload-card">
                <input id="issue-photo-upload" class="upload-input" type="file" accept="image/*" multiple
                  @change="handleFileChange" />
                <input id="issue-photo-camera" class="upload-input" type="file" accept="image/*" capture="environment"
                  @change="handleFileChange" />

                <div class="upload-dropzone" :class="{ 'drag-active': isPhotoDragActive }" role="button" tabindex="0"
                  @click="openIssuePhotoPicker" @keydown.enter.prevent="openIssuePhotoPicker"
                  @keydown.space.prevent="openIssuePhotoPicker" @dragenter.prevent="handlePhotoDragEnter"
                  @dragover.prevent="handlePhotoDragOver" @dragleave.prevent="handlePhotoDragLeave"
                  @drop.prevent="handlePhotoDrop" @paste="handlePhotoPaste">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">
                    <span class="desktop-upload-title">选择或拖拽问题照片</span>
                    <span class="mobile-upload-title">选择或添加问题照片</span>
                  </div>
                  <div class="upload-desc">
                    最多上传3张，系统会自动拼接成一张照片提交；你也可以进入图片编辑调整裁剪和画圈标注。
                    <span class="desktop-drop-hint">桌面端可拖拽多张图片，也可复制图片后在此处粘贴上传。</span>
                  </div>
                  <div class="upload-trigger-group">
                    <label for="issue-photo-camera" class="upload-trigger upload-trigger-secondary" @click.stop>拍照添加</label>
                    <label for="issue-photo-upload" class="upload-trigger" @click.stop>相册选择</label>
                  </div>
                </div>

                <div v-if="imagePreviewUrl" class="image-preview-panel">
                  <button class="image-preview-thumb-btn" type="button" @click="openIssuePhotoPreview">
                    <img :src="imagePreviewUrl" alt="问题照片预览" class="image-preview-thumb" />
                  </button>
                  <div class="image-preview-meta">
                    <div class="image-preview-title">最终提交照片</div>
                    <div class="image-preview-name">
                      {{ sourcePhotos.length > 1 ? `已由 ${sourcePhotos.length} 张照片拼接生成` : imageFile?.name || '已上传图片' }}
                    </div>
                    <div v-if="sourcePhotos.length" class="source-photo-strip">
                      <span v-for="photo in sourcePhotos" :key="photo.id" class="source-photo-chip">
                        <img :src="photo.url" :alt="photo.name" />
                        <button type="button" @click="removeSourcePhoto(photo.id)">×</button>
                      </span>
                    </div>
                    <div class="image-preview-actions">
                      <button v-if="sourcePhotos.length" class="btn btn-secondary image-action-btn" type="button"
                        @click="openPhotoEditor">图片编辑</button>
                      <label for="issue-photo-camera" class="btn btn-light image-action-btn">继续拍照</label>
                      <label for="issue-photo-upload" class="btn btn-light image-action-btn">继续添加</label>
                      <button class="btn btn-secondary image-action-btn" type="button" @click="clearImage">清空图片</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <div class="form-actions">
          <button class="btn btn-primary" type="submit" :disabled="submitting">
            {{ submitting ? '提交中...' : '提交登记' }}
          </button>
          <button class="btn btn-secondary" type="button" @click="resetForm" :disabled="submitting">重置</button>
        </div>

        <transition name="toast-fade">
          <div v-if="submitMessage" class="submit-toast" :class="submitMessageType">{{ submitMessage }}</div>
        </transition>
      </form>
    </div>

    <div v-if="issuePhotoPreviewVisible" class="issue-photo-preview-overlay" @click.self="closeIssuePhotoPreview">
      <div class="issue-photo-preview-dialog" @wheel.prevent="handleIssuePhotoPreviewWheel" @dblclick="resetIssuePhotoPreviewScale">
        <img :src="imagePreviewUrl" :style="issuePhotoPreviewImageStyle" alt="问题照片大图预览" />
      </div>
    </div>

    <div v-if="photoEditor.visible" class="photo-editor-overlay">
      <div class="photo-editor-dialog">
        <div class="photo-editor-head">
          <div>
            <span>问题照片编辑</span>
            <h3>拼接、调换、裁剪和标注</h3>
          </div>
          <button class="photo-editor-close" type="button" @click="closePhotoEditor">×</button>
        </div>

        <div class="photo-editor-body">
          <aside class="photo-editor-side">
            <div class="editor-tool-group">
              <button type="button" :class="{ active: photoEditor.tool === 'crop' }" @click="photoEditor.tool = 'crop'">
                裁剪调整
              </button>
              <button type="button" :class="{ active: photoEditor.tool === 'swap' }" @click="photoEditor.tool = 'swap'">
                调换位置
              </button>
              <button type="button" :class="{ active: photoEditor.tool === 'circle' }" @click="photoEditor.tool = 'circle'">
                画圈标注
              </button>
            </div>

            <div class="editor-tip">
              <template v-if="photoEditor.tool === 'crop'">
                选择下方图片后，在画布中拖动可调整裁剪位置，也可用缩放条放大图片。
              </template>
              <template v-else-if="photoEditor.tool === 'swap'">
                在画布中按住一张照片拖到另一个框，两张照片会调换位置。
              </template>
              <template v-else>
                在画布上按住并拖动即可画圈，适合标出问题位置。
              </template>
            </div>

            <div class="editor-source-list">
              <button v-for="photo in sourcePhotos" :key="photo.id" type="button"
                :class="{ active: photoEditor.selectedPhotoId === photo.id }" @click="selectEditorPhoto(photo.id)">
                <img :src="photo.url" :alt="photo.name" />
                <span>{{ photo.name }}</span>
              </button>
            </div>

            <label v-if="photoEditor.tool === 'crop' && selectedEditorItem" class="editor-range">
              <span>图片缩放 {{ Math.round(selectedEditorItem.scale * 100) }}%</span>
              <input v-model.number="selectedEditorItem.scale" type="range" min="1" max="3" step="0.05"
                @input="handleEditorScaleChange" />
            </label>

            <div class="editor-actions-stack">
              <button class="btn btn-light" type="button" @click="resetPhotoComposition">自动重新拼接</button>
              <button class="btn btn-light" type="button" :disabled="!photoComposition.circles.length"
                @click="undoEditorCircle">撤销画圈</button>
            </div>
          </aside>

          <main class="photo-editor-canvas-wrap">
            <canvas ref="photoEditorCanvasRef" class="photo-editor-canvas" @pointerdown="handleEditorPointerDown"
              @pointermove="handleEditorPointerMove" @pointerup="handleEditorPointerUp"
              @pointercancel="handleEditorPointerUp" @pointerleave="handleEditorPointerLeave"></canvas>
          </main>
        </div>

        <div class="photo-editor-foot">
          <button class="btn btn-secondary" type="button" @click="closePhotoEditor">取消</button>
          <button class="btn btn-primary" type="button" :disabled="photoEditor.saving" @click="savePhotoEditor">
            {{ photoEditor.saving ? '生成中...' : '保存拼接照片' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { pinyin } from 'pinyin-pro'
import {
  clearFileInputsById,
  getImageFilesFromClipboardEvent,
  getImageFilesFromDataTransfer,
  getImageFilesFromFileList,
  hasImageInDataTransfer,
  isDesktopImageDropEnabled,
  loadImageFromFile,
  prepareImageFile,
  prepareImagePreview,
  revokeObjectUrl,
  scrollImageUploadIntoView
} from '@/utils/imageUpload'
import {
  clampCompositionItemOffset,
  createAutoIssuePhotoComposition,
  exportIssuePhotoCompositionFile,
  renderIssuePhotoComposition
} from '@/utils/imageComposer'
import {
  createLocalDraftManager,
  draftAssetToFile,
  fileToDraftAsset
} from '@/utils/localDraft'

const currentRole = localStorage.getItem('user_role') || ''
let localPermissions = {}
try {
  localPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  localPermissions = {}
}
const hasPermission = currentRole === 'root' || Boolean(localPermissions.submit_inspections)
const stationSelectRef = ref(null)
const standardSelectRef = ref(null)
const tableSelectRef = ref(null)
const selectedStandardStartRef = ref(null)
const stationDropdownVisible = ref(false)
const standardDropdownVisible = ref(false)
const tableDropdownVisible = ref(false)
const stationSearch = ref('')
const standardSearch = ref('')
const tableSearch = ref('')
const standardSourceMode = ref('internal')
const referenceMode = ref('manual')
const aiMatching = ref(false)
const aiRecommendations = ref([])
const aiReferenceMessage = ref('')
const aiReferenceMessageType = ref('info')
const aiNoRelated = ref(false)
const aiSelectedStandard = ref(null)
const imageFile = ref(null)
const imagePreviewUrl = ref('')
const imageDraftAsset = ref(null)
const sourcePhotos = ref([])
const photoComposition = ref({ width: 1200, height: 800, items: [], circles: [] })
const photoEditorCanvasRef = ref(null)
const photoEditor = ref({
  visible: false,
  tool: 'crop',
  selectedPhotoId: '',
  swapTargetPhotoId: '',
  saving: false,
  pointer: null,
  draftCircle: null
})
const issuePhotoPreviewVisible = ref(false)
const issuePhotoPreviewScale = ref(1)
const issuePhotoUploadSectionRef = ref(null)
const isPhotoDragActive = ref(false)
const submitMessage = ref('')
const submitMessageType = ref('info')
let submitMessageTimer = null
let photoDragDepth = 0
const showSubmitToast = (message, type = 'info') => {
  if (submitMessageTimer) {
    clearTimeout(submitMessageTimer)
    submitMessageTimer = null
  }

  submitMessageType.value = type
  submitMessage.value = message

  submitMessageTimer = setTimeout(() => {
    submitMessage.value = ''
    submitMessageTimer = null
  }, 2200)
}
const createdTime = ref('')
const submitting = ref(false)
const stations = ref([])
const standards = ref([])
const standardFields = ref([])
const inspectionTables = ref([])
const STANDARD_SEARCH_RESULT_LIMIT = 80
const LAST_REGISTER_STATION_KEY = 'inspection_register_last_station'
const REGISTER_DRAFT_SCOPE = 'inspection-register'
let registerDraftManager = null
let registerDraftReady = false

const form = ref({
  stationId: '',
  hasIssue: 'yes',
  inspectionTableId: '',
  standardId: '',
  description: ''
})

const buildRegisterDraftData = () => ({
  form: { ...form.value },
  stationSearch: stationSearch.value,
  standardSearch: standardSearch.value,
  tableSearch: tableSearch.value,
  referenceMode: referenceMode.value,
  standardSourceMode: standardSourceMode.value,
  image: imageDraftAsset.value
})

const buildRegisterDraftFallbackData = (data) => ({
  ...data,
  image: null
})

const isRegisterDraftEmpty = (data) => {
  const draftForm = data?.form || {}
  return !String(draftForm.description || '').trim() &&
    !String(draftForm.standardId || '').trim() &&
    !String(draftForm.inspectionTableId || '').trim() &&
    !String(data?.standardSearch || '').trim() &&
    !String(data?.tableSearch || '').trim() &&
    !data?.image
}

registerDraftManager = createLocalDraftManager(REGISTER_DRAFT_SCOPE, {
  collect: buildRegisterDraftData,
  collectFallback: buildRegisterDraftFallbackData,
  isEmpty: isRegisterDraftEmpty,
  onFallback: () => showSubmitToast('草稿文字已自动保存，图片较大需重新选择。', 'info')
})

const handleRegisterBeforeUnload = () => {
  registerDraftManager?.flush()
}

const normalizeSearchToken = (value) => {
  return String(value || '')
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, '')
}

const toPinyinText = (value, options = {}) => {
  const text = String(value || '').trim()
  if (!text) return ''
  try {
    return pinyin(text, {
      toneType: 'none',
      nonZh: 'consecutive',
      ...options
    })
  } catch (error) {
    return ''
  }
}

const buildSearchVariants = (value) => {
  const source = String(value || '').trim()
  if (!source) return []

  const fullPinyin = toPinyinText(source)
  const firstLetters = toPinyinText(source, { pattern: 'first' })

  return [
    source,
    fullPinyin,
    firstLetters
  ].map(normalizeSearchToken).filter(Boolean)
}

const matchesSmartSearch = (values, keyword) => {
  const needle = normalizeSearchToken(keyword)
  if (!needle) return true

  return values.some((value) => {
    const variants = buildSearchVariants(value)
    return variants.some((variant) => variant.includes(needle))
  })
}

const STANDARD_SEARCH_EXCLUDED_KEYS = new Set([
  'id',
  'inspection_table_id',
  'created_at',
  'updated_at',
  'standard_detail_text'
])

const getStandardSearchValues = (item = {}) => {
  if (item?.internal_standard_id) {
    const fieldValues = Object.values(item.field_values || {})
    const tagValues = (item.tags || []).flatMap((tag) => [tag.group_name, tag.tag_name])
    const linkedValues = (item.linked_externals || []).flatMap((link) => [
      link.external_standard_id,
      link.inspection_table_name,
      link.standard_detail_text
    ])
    return [
      item.internal_standard_id,
      item.standard_id,
      item.content,
      item.standard_detail_text,
      item.inspection_table_name,
      ...fieldValues,
      ...tagValues,
      ...linkedValues
    ].filter((value) => value !== null && value !== undefined)
  }

  return Object.entries(item)
    .filter(([key, value]) => !STANDARD_SEARCH_EXCLUDED_KEYS.has(key) && value !== null && value !== undefined)
    .map(([, value]) => value)
}

const normalizeExactNumericText = (value) => {
  return String(value ?? '').normalize('NFKC').trim()
}

const isNumericStandardKeyword = (value) => {
  return /^\d+$/.test(normalizeExactNumericText(value))
}

const standardSequenceFieldKeys = computed(() => {
  return standardFields.value
    .filter((field) => String(field?.field_label || '').trim().includes('序号'))
    .map((field) => field.field_key)
    .filter(Boolean)
})

const matchesNumericStandardSearch = (item, keyword) => {
  const needle = normalizeExactNumericText(keyword)
  if (!needle) return true
  if (normalizeExactNumericText(item?.standard_id) === needle) return true
  if (normalizeExactNumericText(item?.internal_standard_id) === needle) return true
  if (normalizeExactNumericText(item?.external_standard_id) === needle) return true
  if ((item?.linked_externals || []).some((link) => normalizeExactNumericText(link.external_standard_id) === needle)) return true
  const sequenceDetailMatched = normalizeStandardDetailForRegister(item?.standard_detail_text || '')
    .split('\n')
    .some((line) => {
      const separatorIndex = line.indexOf('：')
      if (separatorIndex < 0) return false
      const label = line.slice(0, separatorIndex).trim()
      const value = line.slice(separatorIndex + 1).trim()
      return label.includes('序号') && normalizeExactNumericText(value) === needle
    })
  if (sequenceDetailMatched) return true
  return standardSequenceFieldKeys.value.some((fieldKey) => {
    return normalizeExactNumericText(item?.[fieldKey] ?? item?.field_values?.[fieldKey]) === needle
  })
}

const selectedStandard = computed(() => {
  const standard = standards.value.find((item) => String(item.standard_id) === String(form.value.standardId))
  if (standard) return standard
  if (String(aiSelectedStandard.value?.standard_id || '') === String(form.value.standardId || '')) {
    return aiSelectedStandard.value
  }
  return null
})

const normalizedHasIssue = computed(() => {
  return String(form.value.hasIssue || 'yes').trim().toLowerCase()
})

const standardSourceModeLabel = computed(() => standardSourceMode.value === 'external' ? '外部规范库' : '内部规范库')

const showIssueFields = computed(() => {
  const hasIssueYes = String(form.value.hasIssue || 'yes').trim().toLowerCase() === 'yes'
  const hasStation = Boolean(String(form.value.stationId || '').trim())
  const hasStandard = Boolean(String(form.value.standardId || '').trim())
  return hasIssueYes && hasStation && hasStandard
})

const issuePhotoPreviewImageStyle = computed(() => ({
  transform: `scale(${issuePhotoPreviewScale.value})`
}))

const normalizeStandardDetailForRegister = (value) => {
  const lines = String(value || '')
    .replace(/\\n/g, '\n')
    .split('\n')
    .map((line) => String(line || '').trim())
    .filter(Boolean)

  const result = []

  lines.forEach((line) => {
    const separatorIndex = line.indexOf('：')
    const possibleLabel = separatorIndex > -1 ? line.slice(0, separatorIndex).trim() : ''

    if (separatorIndex > -1 && possibleLabel) {
      result.push(line)
      return
    }

    if (result.length === 0) {
      result.push(line)
      return
    }

    result[result.length - 1] = `${result[result.length - 1]} ${line}`.replace(/\s+/g, ' ').trim()
  })

  return result.join('\n')
}

const getRegisterStandardPreview = (standard) => {
  const hasRegisterDisplayText = Object.prototype.hasOwnProperty.call(standard || {}, 'register_display_text')
  const text = hasRegisterDisplayText ? standard?.register_display_text : standard?.standard_detail_text
  return normalizeStandardDetailForRegister(
    text || '未设置登记展示字段'
  )
}

const filteredStations = computed(() => {
  return stations.value.filter((item) => {
    return matchesSmartSearch([item.station_name, item.region, item.station_usernames], stationSearch.value)
  })
})

const filteredInspectionTables = computed(() => {
  return inspectionTables.value.filter((item) => {
    return matchesSmartSearch([item.table_name, item.description], tableSearch.value)
  })
})

const filteredStandards = computed(() => {
  if (isNumericStandardKeyword(standardSearch.value)) {
    return standards.value.filter((item) => {
      return matchesNumericStandardSearch(item, standardSearch.value)
    }).slice(0, STANDARD_SEARCH_RESULT_LIMIT)
  }

  return standards.value.filter((item) => {
    return matchesSmartSearch(getStandardSearchValues(item), standardSearch.value)
  }).slice(0, STANDARD_SEARCH_RESULT_LIMIT)
})

const getStandardFallbackTitle = (item) => {
  const firstLine = String(item?.standard_detail_text || item?.content || '')
    .replace(/\\n/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .find(Boolean)
  if (!firstLine) return ''
  const separatorIndex = firstLine.indexOf('：')
  return separatorIndex > -1 ? firstLine.slice(separatorIndex + 1).trim() : firstLine
}

const getStandardTitle = (item) => {
  if (item?.internal_standard_id) {
    const firstValue = standardFields.value
      .map((field) => String(item?.field_values?.[field.field_key] || '').trim())
      .find(Boolean)
    return firstValue || getStandardFallbackTitle(item) || '未命名内部规范'
  }
  return item.check_content || item.check_item || item.project_name || getStandardFallbackTitle(item) || '未命名规范'
}

const getStandardIdentity = (item) => {
  if (item?.internal_standard_id) return `internal:${item.internal_standard_id}`
  return `${item?.inspection_table_id || 'unknown'}:${item?.standard_id || ''}`
}

const buildInternalStandardDetailText = (item, fields = standardFields.value) => {
  if (!fields.length) return item?.content || ''
  const lines = fields.map((field) => {
    const value = String(item?.field_values?.[field.field_key] || '').trim() || '-'
    return `${field.field_label}：${value}`
  })
  return lines.filter(Boolean).join('\n') || item?.content || ''
}

const formatCurrentTime = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  const seconds = String(now.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}


const fetchStations = async () => {
  const response = await axios.get('/api/stations')
  stations.value = response.data || []
}

const fetchInspectionTables = async () => {
  const response = await axios.get('/api/inspection-tables')
  inspectionTables.value = response.data || []
}

const fetchStandardSourceMode = async () => {
  const response = await axios.get('/api/inspection-standard-usage-mode', {
    params: { _ts: Date.now() }
  })
  standardSourceMode.value = response.data?.usage_mode?.mode === 'external' ? 'external' : 'internal'
}

const fetchStandards = async () => {
  if (standardSourceMode.value === 'external') {
    const response = await axios.get('/api/external-standards', {
      params: { _ts: Date.now() }
    })
    standardFields.value = []
    standards.value = (response.data?.items || []).map((item) => ({
      ...item,
      standard_id: String(item.standard_id || item.external_standard_id || ''),
      external_standard_id: item.external_standard_id || item.standard_id,
      inspection_table_id: String(item.inspection_table_id || ''),
      inspection_table_name: item.inspection_table_name || '未命名检查表',
      standard_detail_text: item.standard_detail_text || '',
      register_display_text: item.register_display_text || ''
    }))
    return
  }

  const response = await axios.get('/api/inspection-internal-standards', {
    params: { _ts: Date.now() }
  })
  const fields = response.data?.fields || []
  standardFields.value = fields
  standards.value = (response.data?.items || []).map((item) => {
    const linkedExternals = item.linked_externals || []
    const linkedTableNames = [...new Set(
      linkedExternals
        .map((link) => String(link.inspection_table_name || '').trim())
        .filter(Boolean)
    )]
    const detailText = buildInternalStandardDetailText(item, fields)
    return {
      ...item,
      standard_id: item.internal_standard_id,
      internal_standard_id: item.internal_standard_id,
      standard_detail_text: detailText,
      register_display_text: item.register_display_text || detailText,
      inspection_table_id: '',
      inspection_table_name: linkedTableNames.length
        ? `${linkedTableNames.join('、')}（共挂载${linkedExternals.length}条外部规范）`
        : '未挂载外部检查表',
      linked_externals: linkedExternals
    }
  })
}

const openStationDropdown = () => {
  if (form.value.stationId || stationSearch.value) {
    form.value.stationId = ''
    stationSearch.value = ''
  }
  stationDropdownVisible.value = true
}

const openStandardDropdown = () => {
  if (form.value.standardId || standardSearch.value) {
    form.value.inspectionTableId = ''
    form.value.standardId = ''
    standardSearch.value = ''
    aiSelectedStandard.value = null
    clearAiReferenceState()
  }
  standardDropdownVisible.value = true
}

const openTableDropdown = () => {
  tableDropdownVisible.value = true
}

const handleStationInput = () => {
  form.value.stationId = ''
  stationDropdownVisible.value = true
}

const handleStandardInput = () => {
  form.value.inspectionTableId = ''
  form.value.standardId = ''
  aiSelectedStandard.value = null
  standardDropdownVisible.value = true
}

const handleTableInput = () => {
  form.value.inspectionTableId = ''
  tableDropdownVisible.value = true
}

const clearAiReferenceState = () => {
  aiRecommendations.value = []
  aiReferenceMessage.value = ''
  aiReferenceMessageType.value = 'info'
  aiNoRelated.value = false
}

const clearSelectedStandard = () => {
  form.value.inspectionTableId = ''
  form.value.standardId = ''
  standardSearch.value = ''
  standardDropdownVisible.value = false
  aiSelectedStandard.value = null
}

const setReferenceMode = (mode) => {
  const nextMode = mode === 'ai' ? 'ai' : 'manual'
  if (referenceMode.value === nextMode) return
  referenceMode.value = nextMode
  clearSelectedStandard()
  clearAiReferenceState()
}

watch(
  normalizedHasIssue,
  (hasIssueValue) => {
    clearSelectedStandard()
    clearAiReferenceState()
    if (hasIssueValue === 'no') {
      referenceMode.value = 'manual'
      form.value.description = ''
      clearImage()
      return
    }

    tableSearch.value = ''
    tableDropdownVisible.value = false
  }
)

const selectStation = (station) => {
  stationSearch.value = station.station_name
  form.value.stationId = station.id
  stationDropdownVisible.value = false
  localStorage.setItem(
    LAST_REGISTER_STATION_KEY,
    JSON.stringify({
      id: station.id,
      station_name: station.station_name
    })
  )
}

const findScrollableParent = (element) => {
  let parent = element?.parentElement || null
  while (parent && parent !== document.body) {
    const style = window.getComputedStyle(parent)
    const overflowY = style.overflowY
    const canScroll = parent.scrollHeight > parent.clientHeight
    if (canScroll && ['auto', 'scroll', 'overlay'].includes(overflowY)) {
      return parent
    }
    parent = parent.parentElement
  }
  return window
}

const scrollToSelectedStandard = async () => {
  await nextTick()
  const target = selectedStandardStartRef.value
  if (!target || typeof window === 'undefined') return

  const isMobile = window.matchMedia?.('(max-width: 900px)').matches
  const topOffset = isMobile ? 8 : 24
  const scrollParent = findScrollableParent(target)
  requestAnimationFrame(() => {
    if (scrollParent === window) {
      const targetTop = target.getBoundingClientRect().top + window.scrollY - topOffset
      window.scrollTo({
        top: Math.max(targetTop, 0),
        behavior: 'smooth'
      })
      return
    }

    const parentRect = scrollParent.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    const targetTop = scrollParent.scrollTop + targetRect.top - parentRect.top - topOffset
    scrollParent.scrollTo({
      top: Math.max(targetTop, 0),
      behavior: 'smooth'
    })
  })
}

const selectStandard = async (standard) => {
  standardSearch.value = `${standard.standard_id}｜${getStandardTitle(standard)}`
  form.value.standardId = standard.internal_standard_id || standard.standard_id
  form.value.inspectionTableId = standard.internal_standard_id ? '' : String(standard.inspection_table_id || '')
  aiSelectedStandard.value = { ...standard }
  standardDropdownVisible.value = false
  await scrollToSelectedStandard()
}

const selectRecommendedStandard = async (candidate) => {
  const standard = standards.value.find((item) => {
    return String(item.standard_id) === String(candidate.standard_id)
  }) || candidate
  await selectStandard({
    ...standard,
    confidence: candidate.confidence,
    reason: candidate.reason
  })
  aiReferenceMessage.value = `已引用规范 ${candidate.standard_id}，请继续上传问题照片后提交。`
  aiReferenceMessageType.value = 'success'
}

const selectInspectionTable = (table) => {
  tableSearch.value = table.table_name
  form.value.inspectionTableId = String(table.id)
  tableDropdownVisible.value = false
}

const runAiStandardMatch = async () => {
  const description = String(form.value.description || '').trim()
  if (description.length < 4) {
    aiReferenceMessage.value = '请先填写更具体的实际问题描述。'
    aiReferenceMessageType.value = 'error'
    return
  }

  clearSelectedStandard()
  clearAiReferenceState()

  try {
    aiMatching.value = true
    const response = await axios.post('/api/inspection-standards/ai-recommend', {
      description,
      standard_source_mode: standardSourceMode.value
    })
    aiRecommendations.value = response.data?.items || []
    aiNoRelated.value = Boolean(response.data?.no_related)

    if (aiNoRelated.value) {
      aiReferenceMessage.value = response.data?.summary || 'AI未找到明确相关规范。'
      aiReferenceMessageType.value = response.data?.ai_generated ? 'warning' : 'error'
      return
    }

    aiReferenceMessage.value = response.data?.ai_generated
      ? `AI已生成${standardSourceModeLabel.value}候选规范，请选择最符合现场问题的一条。`
      : `${response.data?.message || 'AI暂不可用，已使用本地规则匹配。'}请人工确认候选规范。`
    aiReferenceMessageType.value = response.data?.ai_generated ? 'success' : 'warning'
  } catch (error) {
    aiRecommendations.value = []
    aiNoRelated.value = true
    aiReferenceMessage.value = error?.response?.data?.error || 'AI匹配失败，请稍后重试或改用人工引用。'
    aiReferenceMessageType.value = 'error'
  } finally {
    aiMatching.value = false
  }
}

const applyRememberedStation = () => {
  const raw = localStorage.getItem(LAST_REGISTER_STATION_KEY)
  if (!raw) return

  try {
    const remembered = JSON.parse(raw)
    const station = stations.value.find((item) => {
      return String(item.id) === String(remembered?.id || '')
    })
    if (!station) {
      localStorage.removeItem(LAST_REGISTER_STATION_KEY)
      return
    }

    form.value.stationId = station.id
    stationSearch.value = station.station_name
  } catch (error) {
    localStorage.removeItem(LAST_REGISTER_STATION_KEY)
  }
}

const restoreRegisterDraft = async () => {
  const draft = registerDraftManager?.load()?.data
  if (!draft || isRegisterDraftEmpty(draft)) return false

  await registerDraftManager.pause(async () => {
    const draftForm = draft.form || {}
    form.value = {
      stationId: draftForm.stationId || '',
      hasIssue: draftForm.hasIssue === 'no' ? 'no' : 'yes',
      inspectionTableId: String(draftForm.inspectionTableId || ''),
      standardId: String(draftForm.standardId || ''),
      description: draftForm.description || ''
    }
    stationSearch.value = draft.stationSearch || stations.value.find((item) => {
      return String(item.id) === String(form.value.stationId)
    })?.station_name || ''
    tableSearch.value = draft.tableSearch || inspectionTables.value.find((item) => {
      return String(item.id) === String(form.value.inspectionTableId)
    })?.table_name || ''
    referenceMode.value = draft.referenceMode === 'ai' ? 'ai' : 'manual'
    standardSearch.value = draft.standardSearch || ''

    if (form.value.hasIssue === 'yes' && draft.standardSourceMode && draft.standardSourceMode !== standardSourceMode.value) {
      clearSelectedStandard()
    } else if (form.value.standardId) {
      const standard = standards.value.find((item) => String(item.standard_id) === String(form.value.standardId))
      if (standard) {
        aiSelectedStandard.value = { ...standard }
        standardSearch.value = draft.standardSearch || `${standard.standard_id}｜${getStandardTitle(standard)}`
      }
    }

    if (draft.image?.data_url) {
      try {
        const restoredFile = await draftAssetToFile(draft.image)
        if (restoredFile) {
          imageFile.value = restoredFile
          imageDraftAsset.value = draft.image
          revokeObjectUrl(imagePreviewUrl.value)
          imagePreviewUrl.value = URL.createObjectURL(restoredFile)
        }
      } catch (error) {
        imageDraftAsset.value = null
        showSubmitToast('已恢复文字草稿，图片需要重新选择。', 'info')
      }
    }
  })

  showSubmitToast('已恢复上次未提交的巡检登记草稿。', 'success')
  return true
}

const selectedEditorItem = computed(() => {
  return (photoComposition.value.items || []).find((item) => item.photoId === photoEditor.value.selectedPhotoId) || null
})

const getPhotoById = (photoId) => sourcePhotos.value.find((photo) => photo.id === photoId)

const revokeSourcePhotos = () => {
  sourcePhotos.value.forEach((photo) => revokeObjectUrl(photo.url))
  sourcePhotos.value = []
}

const setFinalIssuePhotoFile = async (file, options = {}) => {
  const prepared = await prepareImagePreview(file)
  imageFile.value = prepared.file
  revokeObjectUrl(imagePreviewUrl.value)
  imagePreviewUrl.value = prepared.previewUrl
  try {
    imageDraftAsset.value = await fileToDraftAsset(prepared.file)
  } catch {
    imageDraftAsset.value = null
    if (!options.silentDraftWarning) {
      showSubmitToast('图片已选择，草稿只会保存文字内容。', 'info')
    }
  }
  registerDraftManager?.scheduleSave()
}

const redrawPhotoEditor = () => {
  renderIssuePhotoComposition(photoEditorCanvasRef.value, sourcePhotos.value, photoComposition.value, {
    selectedPhotoId: photoEditor.value.tool === 'crop' ? photoEditor.value.selectedPhotoId : '',
    swapSourcePhotoId: photoEditor.value.pointer?.type === 'swap' ? photoEditor.value.pointer.sourcePhotoId : '',
    swapTargetPhotoId: photoEditor.value.tool === 'swap' ? photoEditor.value.swapTargetPhotoId : '',
    draftCircle: photoEditor.value.draftCircle
  })
}

const generateCompositePhoto = async (options = {}) => {
  if (!sourcePhotos.value.length) return false
  const outputFile = await exportIssuePhotoCompositionFile(
    sourcePhotos.value,
    photoComposition.value,
    `inspection-issue-${Date.now()}.jpg`
  )
  await setFinalIssuePhotoFile(outputFile, { silentDraftWarning: true })
  if (!options.keepEditorCanvas) {
    await nextTick()
  }
  return true
}

const resetPhotoComposition = async () => {
  photoComposition.value = createAutoIssuePhotoComposition(sourcePhotos.value)
  photoEditor.value.selectedPhotoId = sourcePhotos.value[0]?.id || ''
  photoEditor.value.swapTargetPhotoId = ''
  photoEditor.value.draftCircle = null
  await nextTick()
  redrawPhotoEditor()
  await generateCompositePhoto({ keepEditorCanvas: true })
}

const handleFileChange = async (event) => {
  const files = getImageFilesFromFileList(event.target.files || [])
  if (!files.length) return
  await processSelectedImages(files)
  clearFileInputsById(['issue-photo-upload', 'issue-photo-camera'])
}

const processSelectedImages = async (files = []) => {
  const incomingFiles = Array.from(files || []).filter(Boolean)
  if (!incomingFiles.length) return false

  const remainingCount = Math.max(0, 3 - sourcePhotos.value.length)
  if (remainingCount <= 0) {
    showSubmitToast('问题照片最多只能添加3张。', 'error')
    return false
  }

  const filesToProcess = incomingFiles.slice(0, remainingCount)
  const addedPhotos = []
  try {
    for (const file of filesToProcess) {
      const preparedFile = await prepareImageFile(file)
      const img = await loadImageFromFile(preparedFile)
      addedPhotos.push({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        file: preparedFile,
        url: URL.createObjectURL(preparedFile),
        img,
        name: preparedFile.name || file.name || '问题照片'
      })
    }

    sourcePhotos.value = [...sourcePhotos.value, ...addedPhotos].slice(0, 3)
    photoComposition.value = createAutoIssuePhotoComposition(sourcePhotos.value)
    photoEditor.value.selectedPhotoId = sourcePhotos.value[0]?.id || ''
    photoEditor.value.swapTargetPhotoId = ''
    await generateCompositePhoto()

    if (incomingFiles.length > remainingCount) {
      showSubmitToast('最多添加3张问题照片，已自动忽略超出的图片。', 'info')
    } else if (sourcePhotos.value.length > 1) {
      showSubmitToast('已自动拼接问题照片，可点击图片编辑继续调整。', 'success')
    }

    if (submitMessageType.value !== 'success' && submitMessageTimer) {
      clearTimeout(submitMessageTimer)
      submitMessageTimer = null
      submitMessage.value = ''
      submitMessageType.value = 'info'
    }
    return true
  } catch (error) {
    addedPhotos.forEach((photo) => revokeObjectUrl(photo.url))
    showSubmitToast(error?.message || '图片处理失败，请更换图片后重试。', 'error')
    return false
  }
}

const scrollToIssuePhotoUpload = async () => {
  await nextTick()
  scrollImageUploadIntoView(issuePhotoUploadSectionRef.value)
}

const openIssuePhotoPicker = () => {
  document.getElementById('issue-photo-upload')?.click()
}

const openIssuePhotoPreview = () => {
  if (!imagePreviewUrl.value) return
  issuePhotoPreviewScale.value = 1
  issuePhotoPreviewVisible.value = true
}

const closeIssuePhotoPreview = () => {
  issuePhotoPreviewVisible.value = false
  issuePhotoPreviewScale.value = 1
}

const resetIssuePhotoPreviewScale = () => {
  issuePhotoPreviewScale.value = 1
}

const handleIssuePhotoPreviewWheel = (event) => {
  const delta = event.deltaY > 0 ? -0.12 : 0.12
  const nextScale = issuePhotoPreviewScale.value + delta
  issuePhotoPreviewScale.value = Math.min(4, Math.max(0.5, Number(nextScale.toFixed(2))))
}

const handlePhotoDragEnter = (event) => {
  if (!isDesktopImageDropEnabled() || !hasImageInDataTransfer(event.dataTransfer)) return
  photoDragDepth += 1
  isPhotoDragActive.value = true
}

const handlePhotoDragOver = (event) => {
  if (!isDesktopImageDropEnabled() || !hasImageInDataTransfer(event.dataTransfer)) return
  event.dataTransfer.dropEffect = 'copy'
  isPhotoDragActive.value = true
}

const handlePhotoDragLeave = () => {
  if (!isDesktopImageDropEnabled()) return
  photoDragDepth = Math.max(photoDragDepth - 1, 0)
  if (photoDragDepth === 0) {
    isPhotoDragActive.value = false
  }
}

const handlePhotoDrop = async (event) => {
  if (!isDesktopImageDropEnabled()) return
  photoDragDepth = 0
  isPhotoDragActive.value = false
  const files = getImageFilesFromDataTransfer(event.dataTransfer)
  if (!files.length) {
    showSubmitToast('请拖入图片文件。', 'error')
    return
  }
  await processSelectedImages(files)
}

const handlePhotoPaste = async (event) => {
  const files = getImageFilesFromClipboardEvent(event)
  if (!files.length) {
    showSubmitToast('剪贴板里没有可上传的图片。', 'error')
    return
  }
  event.preventDefault()
  photoDragDepth = 0
  isPhotoDragActive.value = false
  const uploaded = await processSelectedImages(files)
  if (uploaded) {
    await scrollToIssuePhotoUpload()
  }
}

const handleWindowPhotoPaste = async (event) => {
  if (event.defaultPrevented || normalizedHasIssue.value !== 'yes') return
  const files = getImageFilesFromClipboardEvent(event)
  if (!files.length) return
  event.preventDefault()
  photoDragDepth = 0
  isPhotoDragActive.value = false
  const uploaded = await processSelectedImages(files)
  if (uploaded) {
    await scrollToIssuePhotoUpload()
  }
}

const removeSourcePhoto = async (photoId) => {
  const target = getPhotoById(photoId)
  if (target) revokeObjectUrl(target.url)
  sourcePhotos.value = sourcePhotos.value.filter((photo) => photo.id !== photoId)
  if (!sourcePhotos.value.length) {
    clearImage()
    return
  }
  await resetPhotoComposition()
}

const selectEditorPhoto = (photoId) => {
  photoEditor.value.selectedPhotoId = photoId
  photoEditor.value.tool = 'crop'
  nextTick(redrawPhotoEditor)
}

const openPhotoEditor = async () => {
  if (!sourcePhotos.value.length) return
  photoEditor.value.visible = true
  photoEditor.value.tool = 'crop'
  photoEditor.value.selectedPhotoId = photoEditor.value.selectedPhotoId || sourcePhotos.value[0]?.id || ''
  photoEditor.value.swapTargetPhotoId = ''
  photoEditor.value.pointer = null
  photoEditor.value.draftCircle = null
  await nextTick()
  redrawPhotoEditor()
}

const closePhotoEditor = (force = false) => {
  if (photoEditor.value.saving && !force) return
  photoEditor.value.visible = false
  photoEditor.value.pointer = null
  photoEditor.value.draftCircle = null
  photoEditor.value.swapTargetPhotoId = ''
}

const getCanvasPoint = (event) => {
  const canvas = photoEditorCanvasRef.value
  const rect = canvas?.getBoundingClientRect()
  if (!canvas || !rect) return null
  return {
    x: (event.clientX - rect.left) * (canvas.width / rect.width),
    y: (event.clientY - rect.top) * (canvas.height / rect.height)
  }
}

const findCompositionItemAtPoint = (point) => {
  if (!point) return null
  return [...(photoComposition.value.items || [])].reverse().find((item) => (
    point.x >= item.x &&
    point.x <= item.x + item.w &&
    point.y >= item.y &&
    point.y <= item.y + item.h
  )) || null
}

const handleEditorPointerDown = (event) => {
  const point = getCanvasPoint(event)
  if (!point) return
  photoEditorCanvasRef.value?.setPointerCapture?.(event.pointerId)

  if (photoEditor.value.tool === 'circle') {
    photoEditor.value.pointer = { type: 'circle', startX: point.x, startY: point.y }
    photoEditor.value.draftCircle = { x: point.x, y: point.y, r: 1, color: '#ef4444', lineWidth: 8 }
    redrawPhotoEditor()
    return
  }

  const item = findCompositionItemAtPoint(point)
  if (!item) return
  photoEditor.value.selectedPhotoId = item.photoId

  if (photoEditor.value.tool === 'swap') {
    photoEditor.value.swapTargetPhotoId = item.photoId
    photoEditor.value.pointer = {
      type: 'swap',
      sourcePhotoId: item.photoId
    }
    redrawPhotoEditor()
    return
  }

  photoEditor.value.pointer = {
    type: 'crop',
    startX: point.x,
    startY: point.y,
    itemPhotoId: item.photoId,
    startOffsetX: item.offsetX || 0,
    startOffsetY: item.offsetY || 0
  }
  redrawPhotoEditor()
}

const handleEditorPointerMove = (event) => {
  const pointer = photoEditor.value.pointer
  if (!pointer) return
  const point = getCanvasPoint(event)
  if (!point) return

  if (pointer.type === 'circle') {
    const dx = point.x - pointer.startX
    const dy = point.y - pointer.startY
    photoEditor.value.draftCircle = {
      x: pointer.startX,
      y: pointer.startY,
      r: Math.max(1, Math.sqrt(dx * dx + dy * dy)),
      color: '#ef4444',
      lineWidth: 8
    }
    redrawPhotoEditor()
    return
  }

  if (pointer.type === 'swap') {
    const targetItem = findCompositionItemAtPoint(point)
    photoEditor.value.swapTargetPhotoId = targetItem?.photoId || ''
    redrawPhotoEditor()
    return
  }

  const item = (photoComposition.value.items || []).find((entry) => entry.photoId === pointer.itemPhotoId)
  const photo = getPhotoById(pointer.itemPhotoId)
  if (!item || !photo) return
  item.offsetX = pointer.startOffsetX + point.x - pointer.startX
  item.offsetY = pointer.startOffsetY + point.y - pointer.startY
  clampCompositionItemOffset(item, photo)
  redrawPhotoEditor()
}

const handleEditorPointerUp = async () => {
  const pointer = photoEditor.value.pointer
  if (!pointer) return

  if (pointer.type === 'circle' && photoEditor.value.draftCircle?.r > 8) {
    photoComposition.value.circles = [
      ...(photoComposition.value.circles || []),
      { ...photoEditor.value.draftCircle }
    ]
  }

  if (pointer.type === 'swap') {
    const sourceItem = (photoComposition.value.items || []).find((entry) => entry.photoId === pointer.sourcePhotoId)
    const targetItem = (photoComposition.value.items || []).find((entry) => entry.photoId === photoEditor.value.swapTargetPhotoId)
    if (sourceItem && targetItem && sourceItem !== targetItem) {
      const sourcePhotoId = sourceItem.photoId
      sourceItem.photoId = targetItem.photoId
      targetItem.photoId = sourcePhotoId
      ;[sourceItem, targetItem].forEach((item) => {
        item.scale = 1
        item.offsetX = 0
        item.offsetY = 0
      })
      photoEditor.value.selectedPhotoId = sourcePhotoId
    }
  }

  photoEditor.value.pointer = null
  photoEditor.value.draftCircle = null
  photoEditor.value.swapTargetPhotoId = ''
  redrawPhotoEditor()
  await generateCompositePhoto({ keepEditorCanvas: true })
}

const handleEditorPointerLeave = (event) => {
  if (!photoEditor.value.pointer) return
  if (event.buttons === 0) {
    handleEditorPointerUp()
  }
}

const handleEditorScaleChange = async () => {
  const item = selectedEditorItem.value
  const photo = getPhotoById(item?.photoId)
  if (item && photo) {
    clampCompositionItemOffset(item, photo)
  }
  redrawPhotoEditor()
  await generateCompositePhoto({ keepEditorCanvas: true })
}

const undoEditorCircle = async () => {
  photoComposition.value.circles = (photoComposition.value.circles || []).slice(0, -1)
  redrawPhotoEditor()
  await generateCompositePhoto({ keepEditorCanvas: true })
}

const savePhotoEditor = async () => {
  try {
    photoEditor.value.saving = true
    await generateCompositePhoto({ keepEditorCanvas: true })
    photoEditor.value.saving = false
    closePhotoEditor(true)
    showSubmitToast('拼接照片已更新。', 'success')
  } catch (error) {
    showSubmitToast(error?.message || '拼接照片生成失败，请稍后重试。', 'error')
  } finally {
    photoEditor.value.saving = false
  }
}

const clearImage = () => {
  closeIssuePhotoPreview()
  closePhotoEditor()
  imageFile.value = null
  imageDraftAsset.value = null
  revokeSourcePhotos()
  revokeObjectUrl(imagePreviewUrl.value)
  imagePreviewUrl.value = ''
  photoComposition.value = { width: 1200, height: 800, items: [], circles: [] }
  isPhotoDragActive.value = false
  photoDragDepth = 0
  clearFileInputsById(['issue-photo-upload', 'issue-photo-camera'])
  registerDraftManager?.scheduleSave()
}

const resetForm = (preserveMessage = false) => {
  form.value = {
    stationId: '',
    hasIssue: 'yes',
    inspectionTableId: '',
    standardId: '',
    description: ''
  }
  stationSearch.value = ''
  standardSearch.value = ''
  tableSearch.value = ''
  referenceMode.value = 'manual'
  stationDropdownVisible.value = false
  standardDropdownVisible.value = false
  tableDropdownVisible.value = false
  clearAiReferenceState()
  aiSelectedStandard.value = null
  if (!preserveMessage) {
    submitMessage.value = ''
    submitMessageType.value = 'info'
  }
  clearImage()
  applyRememberedStation()
  createdTime.value = formatCurrentTime()
  registerDraftManager?.clear()
}

const handleSubmit = async () => {
  const hasIssueValue = normalizedHasIssue.value

  if (!form.value.stationId) {
    showSubmitToast('请选择站点名称。', 'error')
    return
  }

  const currentStandard = selectedStandard.value

  if (hasIssueValue === 'yes' && !form.value.standardId) {
    showSubmitToast(referenceMode.value === 'ai'
      ? '请先通过AI匹配并确认一条规范，或改用人工引用规范。'
      : '请先搜索并选择规范ID，系统会自动带出检查表。', 'error')
    return
  }

  if (hasIssueValue === 'yes' && !currentStandard?.internal_standard_id && !form.value.inspectionTableId) {
    showSubmitToast('所选规范缺少检查表信息，请重新选择规范。', 'error')
    return
  }

  if (hasIssueValue === 'no' && !form.value.inspectionTableId) {
    showSubmitToast('请选择检查表。', 'error')
    return
  }

  if (hasIssueValue === 'yes' && !form.value.description.trim()) {
    showSubmitToast('请填写实际问题描述。', 'error')
    return
  }

  if (hasIssueValue === 'yes' && !imageFile.value) {
    showSubmitToast('请上传问题照片。', 'error')
    return
  }

  const inspectorId = localStorage.getItem('user_id') || ''
  if (!inspectorId) {
    showSubmitToast('当前登录信息缺失，请重新登录。', 'error')
    return
  }

  try {
    submitting.value = true
    if (submitMessageTimer) {
      clearTimeout(submitMessageTimer)
      submitMessageTimer = null
    }
    submitMessage.value = ''

    const formData = new FormData()
    formData.append('inspector_id', inspectorId)
    formData.append('station_id', String(form.value.stationId))
    formData.append('has_issue', hasIssueValue)

    if (hasIssueValue === 'yes') {
      if (currentStandard?.internal_standard_id) {
        formData.append('internal_standard_id', String(currentStandard.internal_standard_id))
      } else {
        formData.append('inspection_table_id', String(form.value.inspectionTableId))
        formData.append('standard_id', String(form.value.standardId))
      }
      formData.append('description', form.value.description)
      formData.append('photo', imageFile.value)
    } else {
      formData.append('inspection_table_id', String(form.value.inspectionTableId))
    }

    const response = await axios.post('/api/inspection-register', formData)
    resetForm(true)
    showSubmitToast(response.data.message || '提交成功。', 'success')
  } catch (error) {
    showSubmitToast(error?.response?.data?.error || '提交失败，请稍后重试。', 'error')
  } finally {
    submitting.value = false
  }
}

const handleClickOutside = (event) => {
  if (stationSelectRef.value && !stationSelectRef.value.contains(event.target)) {
    stationDropdownVisible.value = false
  }
  if (standardSelectRef.value && !standardSelectRef.value.contains(event.target)) {
    standardDropdownVisible.value = false
  }
  if (tableSelectRef.value && !tableSelectRef.value.contains(event.target)) {
    tableDropdownVisible.value = false
  }
}


watch(
  [() => form.value.standardId, () => form.value.inspectionTableId],
  () => {
    if (submitMessageType.value !== 'success') {
      submitMessage.value = ''
      submitMessageType.value = 'info'
    }
  }
)

watch(
  () => form.value.description,
  () => {
    if (referenceMode.value !== 'ai') return
    if (!aiRecommendations.value.length && !aiNoRelated.value && !form.value.standardId) return
    clearSelectedStandard()
    clearAiReferenceState()
  }
)

watch(
  [form, stationSearch, standardSearch, tableSearch, referenceMode, imageDraftAsset],
  () => {
    if (!registerDraftReady) return
    registerDraftManager?.scheduleSave()
  },
  { deep: true }
)

onMounted(async () => {
  createdTime.value = formatCurrentTime()
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('paste', handleWindowPhotoPaste)
  window.addEventListener('beforeunload', handleRegisterBeforeUnload)
  try {
    await Promise.all([fetchStations(), fetchInspectionTables(), fetchStandardSourceMode()])
    applyRememberedStation()
    await fetchStandards()
    await restoreRegisterDraft()
    registerDraftReady = true
  } catch (error) {
    showSubmitToast('初始化站点或规范数据失败，请检查后端服务。', 'error')
    registerDraftReady = true
  }
})

onBeforeUnmount(() => {
  registerDraftManager?.flush()
  registerDraftManager?.destroy()
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('paste', handleWindowPhotoPaste)
  window.removeEventListener('beforeunload', handleRegisterBeforeUnload)
  if (submitMessageTimer) {
    clearTimeout(submitMessageTimer)
    submitMessageTimer = null
  }
  closeIssuePhotoPreview()
  closePhotoEditor()
  revokeSourcePhotos()
  revokeObjectUrl(imagePreviewUrl.value)
})
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-surface {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dbe4ee;
  border-radius: 22px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
}

.page-header {
  padding: 24px 28px;
}

.page-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 14px;
}

.page-header h2 {
  margin: 0;
  font-size: 34px;
  color: #0f172a;
}

.form-card {
  padding: 24px;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(260px, 1fr));
  gap: 18px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-item-full {
  grid-column: 1 / -1;
}

.form-item label {
  font-size: 14px;
  font-weight: 700;
  color: #374151;
}

.form-item input,
.form-item select,
.form-item textarea {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 0 14px;
  font-size: 14px;
  color: #111827;
  background: #fff;
}

.form-item input,
.form-item select {
  height: 44px;
}

.form-item textarea {
  min-height: 112px;
  padding: 12px 14px;
  resize: vertical;
  line-height: 1.7;
}

.issue-toggle-group {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.issue-toggle-btn {
  height: 44px;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  background: #fff;
  color: #374151;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.18s ease;
}

.issue-toggle-btn:hover {
  background: #f8fafc;
}

.issue-toggle-btn.active {
  background: #eff6ff;
  border-color: #93c5fd;
  color: #1d4ed8;
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.08);
}

.reference-mode-panel {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.reference-mode-btn {
  min-height: 84px;
  padding: 14px 16px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  color: #334155;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;
}

.reference-mode-btn strong,
.reference-mode-btn span {
  display: block;
}

.reference-mode-btn strong {
  font-size: 15px;
  color: #0f172a;
  margin-bottom: 6px;
}

.reference-mode-btn span {
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}

.reference-mode-btn:hover {
  border-color: #bfdbfe;
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
}

.reference-mode-btn.active {
  border-color: #2563eb;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.14), transparent 38%),
    linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.12), 0 14px 28px rgba(37, 99, 235, 0.12);
}

.reference-mode-btn-ai.active {
  border-color: #0f766e;
  background:
    radial-gradient(circle at top right, rgba(20, 184, 166, 0.14), transparent 38%),
    linear-gradient(180deg, #f0fdfa 0%, #ffffff 100%);
  box-shadow: inset 0 0 0 1px rgba(20, 184, 166, 0.12), 0 14px 28px rgba(15, 118, 110, 0.12);
}

.ai-reference-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  border: 1px solid #cdece6;
  border-radius: 22px;
  background:
    radial-gradient(circle at top right, rgba(20, 184, 166, 0.12), transparent 36%),
    linear-gradient(180deg, #f8fffd 0%, #ffffff 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.86);
}

.ai-reference-header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.ai-reference-kicker {
  width: fit-content;
  padding: 5px 10px;
  border-radius: 999px;
  background: #ccfbf1;
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
  margin-bottom: 10px;
}

.ai-reference-header h3 {
  margin: 0 0 8px;
  color: #0f172a;
  font-size: 20px;
}

.ai-reference-header p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.8;
}

.ai-description-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-description-field label {
  color: #0f766e;
}

.ai-reference-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.ai-matching-panel {
  padding: 14px;
  border: 1px solid #bfdbfe;
  border-radius: 18px;
  background: rgba(239, 246, 255, 0.84);
}

.ai-matching-title {
  color: #1d4ed8;
  font-size: 14px;
  font-weight: 900;
  margin-bottom: 4px;
}

.ai-matching-desc {
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
  margin-bottom: 12px;
}

.ai-progress-bar {
  position: relative;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #dbeafe;
}

.ai-progress-bar span {
  position: absolute;
  inset: 0;
  width: 42%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #14b8a6);
  animation: ai-progress-slide 1.18s ease-in-out infinite;
}

.ai-reference-message {
  padding: 11px 13px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.7;
  font-weight: 700;
}

.ai-reference-message.success {
  color: #166534;
  background: #ecfdf5;
  border: 1px solid #bbf7d0;
}

.ai-reference-message.warning {
  color: #92400e;
  background: #fffbeb;
  border: 1px solid #fde68a;
}

.ai-reference-message.error {
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.ai-recommendation-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.ai-recommendation-card {
  padding: 14px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #ffffff;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;
}

.ai-recommendation-card:hover {
  border-color: #5eead4;
  transform: translateY(-1px);
  box-shadow: 0 12px 26px rgba(15, 118, 110, 0.12);
}

.ai-recommendation-card.selected {
  border-color: #0f766e;
  background: #f0fdfa;
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.14);
}

.ai-recommendation-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.ai-recommendation-code {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 3px 9px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 12px;
  font-weight: 900;
}

.ai-confidence {
  flex: 0 0 auto;
  padding: 3px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}

.ai-confidence.level-高 {
  background: #dcfce7;
  color: #166534;
}

.ai-confidence.level-中 {
  background: #fef3c7;
  color: #92400e;
}

.ai-confidence.level-低 {
  background: #fee2e2;
  color: #991b1b;
}

.ai-recommendation-title {
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
  line-height: 1.6;
  margin-bottom: 4px;
}

.ai-recommendation-table {
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
  margin-bottom: 8px;
}

.ai-recommendation-reason {
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.ai-no-related {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px;
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  background: #f8fafc;
}

.ai-no-related strong {
  color: #0f172a;
}

.ai-no-related span {
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.form-item input[readonly],
.form-item textarea[readonly] {
  background: #f8fafc;
  color: #475569;
}

.selected-standard-field {
  box-sizing: border-box;
  position: relative;
  padding: 14px;
  border: 1px solid rgba(147, 197, 253, 0.46);
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.08), transparent 34%),
    linear-gradient(180deg, #f8fbff 0%, #f8fafc 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82);
}

.selected-standard-field *,
.selected-standard-field *::before,
.selected-standard-field *::after {
  box-sizing: border-box;
}

.selected-standard-first {
  scroll-margin-top: 18px;
}

.selected-standard-first::before {
  content: '已选择规范';
  width: fit-content;
  padding: 4px 9px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
}

.selected-standard-field label {
  color: #1e3a8a;
}

.selected-standard-field input,
.selected-standard-field textarea {
  border-color: rgba(191, 219, 254, 0.96);
  background: rgba(255, 255, 255, 0.9);
}

.selected-standard-detail textarea {
  min-height: 152px;
  resize: none;
}

.search-select {
  position: relative;
}

.search-select-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  max-height: 220px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.12);
  z-index: 20;
  padding: 8px;
}

.search-select-dropdown-wide {
  max-height: 260px;
}

.search-select-option {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  line-height: 1.5;
}

.search-select-option:hover {
  background: #eff6ff;
}

.search-select-empty {
  padding: 12px;
  color: #6b7280;
  font-size: 14px;
}

.option-table-name {
  color: #2563eb;
  font-weight: 700;
}

.standard-detail-preview {
  white-space: pre-line;
  line-height: 1.65;
}

.upload-follow-anchor {
  scroll-margin-top: 96px;
}

.upload-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.upload-input {
  display: none;
}

.upload-dropzone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 10px;
  min-height: 168px;
  padding: 24px 20px;
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fbff 0%, #f8fafc 100%);
  cursor: pointer;
  transition: all 0.18s ease;
  overflow: hidden;
}

.upload-dropzone:hover {
  border-color: #93c5fd;
  background: linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%);
}

.upload-dropzone.drag-active {
  border-color: #2563eb;
  background:
    radial-gradient(circle at 50% 20%, rgba(37, 99, 235, 0.16), transparent 36%),
    linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%);
  box-shadow: inset 0 0 0 2px rgba(37, 99, 235, 0.14), 0 18px 36px rgba(37, 99, 235, 0.12);
  transform: translateY(-1px);
}

.upload-icon {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 24px;
  font-weight: 800;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.upload-title {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

.mobile-upload-title {
  display: none;
}

.upload-desc {
  max-width: 560px;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.desktop-drop-hint {
  display: block;
  margin-top: 4px;
  color: #2563eb;
  font-weight: 700;
}

.upload-trigger-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}

.upload-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 96px;
  height: 38px;
  padding: 0 16px;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.upload-trigger-secondary {
  background: #eef4ff;
  color: #1d4ed8;
  border: 1px solid #bfd3ff;
}

.upload-trigger:hover {
  filter: brightness(0.98);
}

.upload-trigger-secondary:hover {
  background: #e0edff;
  border-color: #93c5fd;
}

.image-preview-panel {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #fff;
  flex-wrap: wrap;
}

.image-preview-thumb-btn {
  position: relative;
  display: block;
  flex-shrink: 0;
  width: 148px;
  height: 108px;
  padding: 0;
  border: none;
  border-radius: 14px;
  overflow: hidden;
  background: #f8fafc;
  cursor: zoom-in;
}

.image-preview-thumb {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: inherit;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  transition: transform 0.2s ease;
}

.image-preview-thumb-btn:hover .image-preview-thumb {
  transform: scale(1.04);
}

.image-preview-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 220px;
  flex: 1;
}

.image-preview-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
}

.image-preview-name {
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
  word-break: break-all;
}

.source-photo-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  padding: 2px 0 4px;
  overflow-x: auto;
}

.source-photo-chip {
  position: relative;
  flex: 0 0 auto;
  width: 72px;
  height: 54px;
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: #f8fafc;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}

.source-photo-chip img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: inherit;
}

.source-photo-chip button {
  position: absolute;
  top: -7px;
  right: -7px;
  width: 22px;
  height: 22px;
  border: 2px solid #fff;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 14px;
  font-weight: 900;
  line-height: 1;
  cursor: pointer;
  box-shadow: 0 8px 14px rgba(239, 68, 68, 0.28);
}

.image-preview-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.image-action-btn {
  min-width: 96px;
  justify-content: center;
  text-decoration: none;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.issue-photo-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.76);
}

.issue-photo-preview-dialog {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: min(980px, 96vw);
  max-height: 92vh;
  overflow: visible;
  cursor: zoom-in;
}

.issue-photo-preview-dialog img {
  display: block;
  max-width: 100%;
  max-height: 92vh;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 24px 54px rgba(15, 23, 42, 0.32);
  transform-origin: center center;
  transition: transform 0.12s ease-out;
  will-change: transform;
}

.photo-editor-overlay {
  position: fixed;
  inset: 0;
  z-index: 4300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at 20% 10%, rgba(96, 165, 250, 0.22), transparent 28%),
    rgba(15, 23, 42, 0.78);
  backdrop-filter: blur(10px);
}

.photo-editor-dialog {
  width: min(1280px, calc(100vw - 24px));
  height: min(96vh, 980px);
  max-height: calc(100vh - 24px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 34px 80px rgba(15, 23, 42, 0.36);
}

.photo-editor-head,
.photo-editor-foot {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 22px;
  border-bottom: 1px solid #e2e8f0;
  background: linear-gradient(135deg, #f8fbff 0%, #ffffff 55%, #f1f5f9 100%);
}

.photo-editor-head span {
  display: inline-flex;
  margin-bottom: 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.photo-editor-head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 22px;
  font-weight: 900;
}

.photo-editor-close {
  width: 38px;
  height: 38px;
  border: 1px solid #dbe4ee;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  font-size: 24px;
  font-weight: 800;
  line-height: 1;
  cursor: pointer;
}

.photo-editor-close:hover {
  color: #0f172a;
  background: #f8fafc;
}

.photo-editor-body {
  min-height: 0;
  flex: 1;
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 0;
  overflow: hidden;
}

.photo-editor-side {
  min-height: 0;
  padding: 18px;
  overflow-y: auto;
  border-right: 1px solid #e2e8f0;
  background: #f8fafc;
}

.editor-tool-group {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.editor-tool-group button,
.editor-source-list button {
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  font-weight: 800;
}

.editor-tool-group button {
  min-height: 42px;
  padding: 0 10px;
  font-size: 13px;
  line-height: 1;
  white-space: nowrap;
}

.editor-tool-group button.active,
.editor-source-list button.active {
  color: #1d4ed8;
  border-color: #93c5fd;
  background: #eff6ff;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.12);
}

.editor-tip {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  background: #eff6ff;
  color: #1e40af;
  font-size: 13px;
  line-height: 1.75;
}

.editor-source-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.editor-source-list button {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-height: 58px;
  padding: 8px;
  text-align: left;
}

.editor-source-list img {
  width: 58px;
  height: 42px;
  object-fit: cover;
  border-radius: 10px;
  background: #e2e8f0;
}

.editor-source-list span {
  min-width: 0;
  overflow: hidden;
  color: inherit;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.editor-range {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
  padding: 13px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.editor-range input {
  width: 100%;
  accent-color: #2563eb;
}

.editor-actions-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.photo-editor-canvas-wrap {
  min-width: 0;
  min-height: 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 20px 22px 26px;
  overflow: hidden;
  background:
    linear-gradient(45deg, rgba(203, 213, 225, 0.24) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(203, 213, 225, 0.24) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(203, 213, 225, 0.24) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(203, 213, 225, 0.24) 75%),
    #eef2f7;
  background-position: 0 0, 0 14px, 14px -14px, -14px 0;
  background-size: 28px 28px;
}

.photo-editor-canvas {
  display: block;
  width: auto;
  max-width: 100%;
  max-height: 100%;
  height: auto;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.2);
  cursor: grab;
  touch-action: none;
}

.photo-editor-canvas:active {
  cursor: grabbing;
}

.photo-editor-foot {
  justify-content: flex-end;
  border-top: 1px solid #e2e8f0;
  border-bottom: 0;
}

.btn {
  height: 42px;
  padding: 0 18px;
  border-radius: 10px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.btn-primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-secondary:hover:not(:disabled),
.btn-light:hover:not(:disabled) {
  background: #f8fafc;
}

.submit-toast {
  position: fixed;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: min(calc(100vw - 32px), 420px);
  z-index: 5000;
  font-size: 14px;
  line-height: 1.7;
  color: #2563eb;
  background: rgba(239, 246, 255, 0.98);
  border: 1px solid #bfdbfe;
  border-radius: 14px;
  padding: 12px 14px;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(8px);
  text-align: center;
}

.submit-toast.success {
  color: #166534;
  background: rgba(236, 253, 245, 0.98);
  border-color: #bbf7d0;
}

.submit-toast.error {
  color: #b91c1c;
  background: rgba(254, 242, 242, 0.98);
  border-color: #fecaca;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, calc(-50% + 12px));
}

@keyframes ai-progress-slide {
  0% {
    transform: translateX(-110%);
  }

  50% {
    transform: translateX(80%);
  }

  100% {
    transform: translateX(250%);
  }
}

@media (max-width: 900px) {
  .page-shell {
    gap: 14px;
  }

  .page-header {
    padding: 18px 16px;
  }

  .page-header h2 {
    font-size: 28px;
  }

  .page-kicker {
    margin-bottom: 10px;
  }

  .form-card {
    padding: 14px;
    border-radius: 18px;
  }

  .register-form {
    gap: 16px;
  }

  .section-title,
  .issue-section-title {
    font-size: 16px;
  }

  .form-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .form-item label {
    font-size: 13px;
  }

  .form-item input,
  .form-item select {
    height: 46px;
    padding: 0 12px;
    font-size: 15px;
  }

  .form-item textarea {
    min-height: 108px;
    padding: 12px;
    font-size: 15px;
  }

  .issue-toggle-group {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .issue-toggle-btn {
    height: 46px;
    font-size: 15px;
  }

  .reference-mode-panel,
  .ai-recommendation-list {
    grid-template-columns: 1fr;
  }

  .reference-mode-btn {
    min-height: auto;
    padding: 13px 14px;
  }

  .ai-reference-card {
    padding: 14px;
    border-radius: 18px;
  }

  .ai-reference-header h3 {
    font-size: 18px;
  }

  .ai-reference-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .search-select-dropdown {
    max-height: min(56vh, 320px);
    border-radius: 16px;
    padding: 6px;
  }

  .search-select-option {
    padding: 11px 10px;
  }

  .selected-standard-field {
    padding: 12px;
    border-radius: 16px;
  }

  .selected-standard-first {
    scroll-margin-top: 12px;
  }

  .selected-standard-detail textarea {
    min-height: 168px;
    max-height: 42vh;
  }

  .option-main {
    font-size: 14px;
    line-height: 1.6;
  }

  .option-sub {
    font-size: 12px;
    line-height: 1.7;
  }

  .upload-dropzone {
    min-height: 148px;
    padding: 18px 14px;
  }

  .upload-title {
    font-size: 15px;
  }

  .desktop-upload-title {
    display: none;
  }

  .mobile-upload-title {
    display: inline;
  }

  .upload-desc {
    font-size: 12px;
  }

  .desktop-drop-hint {
    display: none;
  }

  .upload-trigger-group {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }

  .upload-trigger {
    width: 100%;
  }

  .image-preview-panel {
    align-items: flex-start;
    padding: 12px;
  }

  .image-preview-thumb-btn {
    width: 100%;
    height: auto;
    aspect-ratio: 4 / 3;
  }

  .image-preview-thumb {
    width: 100%;
    max-width: none;
    height: 100%;
    aspect-ratio: 4 / 3;
  }

  .image-preview-meta {
    min-width: 0;
    width: 100%;
  }

  .image-preview-actions {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }

  .image-action-btn {
    width: 100%;
  }

  .source-photo-strip {
    padding-bottom: 8px;
  }

  .source-photo-chip {
    width: 66px;
    height: 50px;
  }

  .photo-editor-overlay {
    align-items: stretch;
    padding: 0;
  }

  .photo-editor-dialog {
    width: 100vw;
    height: 100dvh;
    max-height: none;
    border-radius: 0;
  }

  .photo-editor-head,
  .photo-editor-foot {
    padding: 14px;
  }

  .photo-editor-head h3 {
    font-size: 18px;
  }

  .photo-editor-close {
    width: 36px;
    height: 36px;
  }

  .photo-editor-body {
    display: flex;
    flex-direction: column;
    grid-template-columns: 1fr;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }

  .photo-editor-side {
    flex: 0 0 auto;
    padding: 14px;
    border-right: 0;
    border-bottom: 1px solid #e2e8f0;
    overflow: visible;
  }

  .editor-tip {
    margin-top: 10px;
    padding: 10px;
    font-size: 12px;
  }

  .editor-source-list {
    flex-direction: row;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .editor-source-list button {
    grid-template-columns: 52px 88px;
    flex: 0 0 auto;
    width: 154px;
  }

  .editor-source-list img {
    width: 52px;
    height: 40px;
  }

  .editor-tool-group button {
    min-height: 40px;
    font-size: 12px;
    padding: 0 8px;
  }

  .editor-actions-stack {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .photo-editor-canvas-wrap {
    flex: 0 0 auto;
    min-height: 0;
    padding: 12px 12px 18px;
    align-items: flex-start;
    justify-content: center;
    overflow: visible;
  }

  .photo-editor-canvas {
    width: min(100%, 720px);
    max-height: none;
    border-radius: 14px;
  }

  .photo-editor-foot {
    flex: 0 0 auto;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .form-actions {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    position: static;
    padding-top: 0;
    background: transparent;
  }

  .btn {
    width: 100%;
    min-height: 46px;
  }

  .submit-toast {
    width: min(calc(100vw - 24px), 420px);
    top: 50%;
    font-size: 13px;
    line-height: 1.7;
  }

  .permission-card {
    min-height: 220px;
    padding: 24px 16px;
  }
}

.permission-card {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 32px 20px;
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: #f8fafc;
}

.permission-icon {
  width: 56px;
  height: 56px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 28px;
  font-weight: 800;
  margin-bottom: 14px;
}

.permission-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 8px;
}

.permission-desc {
  font-size: 14px;
  line-height: 1.8;
  color: #64748b;
  max-width: 420px;
}
</style>
