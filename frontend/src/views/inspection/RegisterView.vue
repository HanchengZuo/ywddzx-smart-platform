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
          <div class="form-item form-item-full">
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
        </div>

        <template v-if="showIssueFields">
          <div class="section-title issue-section-title">问题信息</div>

          <div class="form-grid">
            <div class="form-item form-item-full">
              <label>规范选择</label>
              <div class="search-select" ref="standardSelectRef">
                <input v-model="standardSearch" type="text" placeholder="搜索并选择规范" @focus="openStandardDropdown"
                  @input="handleStandardInput" />
                <div v-if="standardDropdownVisible" class="search-select-dropdown search-select-dropdown-wide">
                  <div v-for="standard in filteredStandards" :key="standard.standard_id" class="search-select-option"
                    @click="selectStandard(standard)">
                    <div class="option-main">
                      {{ standard.standard_id }}｜{{ standard.check_content || standard.check_item ||
                        standard.project_name || '未命名规范' }}
                    </div>
                    <div class="option-sub standard-detail-preview">{{
                      normalizeStandardDetailForRegister(standard.standard_detail_text) }}</div>
                  </div>
                  <div v-if="filteredStandards.length === 0" class="search-select-empty">无匹配规范</div>
                </div>
              </div>
            </div>

            <div class="form-item form-item-full">
              <label>规范ID</label>
              <input :value="selectedStandard?.standard_id || ''" type="text" readonly />
            </div>

            <div class="form-item form-item-full">
              <label>规范详情</label>
              <textarea :value="normalizeStandardDetailForRegister(selectedStandard?.standard_detail_text || '')"
                rows="8" readonly></textarea>
            </div>

            <div class="form-item form-item-full">
              <label>实际问题描述</label>
              <textarea v-model="form.description" rows="4" placeholder="请填写现场实际问题描述"></textarea>
            </div>

            <div class="form-item form-item-full">
              <label>上传问题照片</label>
              <div class="upload-card">
                <input id="issue-photo-upload" class="upload-input" type="file" accept="image/*"
                  @change="handleFileChange" />
                <input id="issue-photo-camera" class="upload-input" type="file" accept="image/*" capture="environment"
                  @change="handleFileChange" />

                <label for="issue-photo-upload" class="upload-dropzone">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">选择或更换问题照片</div>
                  <div class="upload-desc">
                    支持上传现场问题照片，建议使用清晰、完整、能准确反映问题的图片。
                  </div>
                  <div class="upload-trigger-group">
                    <label for="issue-photo-camera" class="upload-trigger upload-trigger-secondary">拍照上传</label>
                    <label for="issue-photo-upload" class="upload-trigger">相册选择</label>
                  </div>
                </label>

                <div v-if="imagePreviewUrl" class="image-preview-panel">
                  <img :src="imagePreviewUrl" alt="问题照片预览" class="image-preview-thumb" />
                  <div class="image-preview-meta">
                    <div class="image-preview-title">已选择问题照片</div>
                    <div class="image-preview-name">{{ imageFile?.name || '已上传图片' }}</div>
                    <div class="image-preview-actions">
                      <label for="issue-photo-camera" class="btn btn-light image-action-btn">重新拍照</label>
                      <label for="issue-photo-upload" class="btn btn-light image-action-btn">相册重选</label>
                      <button class="btn btn-secondary image-action-btn" type="button" @click="clearImage">移除图片</button>
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
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import {
  compressImageFile,
  validateImageType
} from '@/utils/imageUpload'

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
const stationDropdownVisible = ref(false)
const standardDropdownVisible = ref(false)
const tableDropdownVisible = ref(false)
const stationSearch = ref('')
const standardSearch = ref('')
const tableSearch = ref('')
const imageFile = ref(null)
const imagePreviewUrl = ref('')
const submitMessage = ref('')
const submitMessageType = ref('info')
let submitMessageTimer = null
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
const inspectionTables = ref([])

const form = ref({
  stationId: '',
  hasIssue: 'yes',
  inspectionTableId: '',
  standardId: '',
  description: ''
})

const filteredInspectionTables = computed(() => {
  const keyword = tableSearch.value.trim().toLowerCase()
  return inspectionTables.value.filter((item) => {
    const text = `${item.table_name || ''} ${item.description || ''}`.toLowerCase()
    return !keyword || text.includes(keyword)
  })
})

const selectedStandard = computed(() => {
  return standards.value.find((item) => String(item.standard_id) === String(form.value.standardId)) || null
})

const normalizedHasIssue = computed(() => {
  return String(form.value.hasIssue || 'yes').trim().toLowerCase()
})

const showIssueFields = computed(() => {
  const hasIssueYes = String(form.value.hasIssue || 'yes').trim().toLowerCase() === 'yes'
  const hasStation = Boolean(String(form.value.stationId || '').trim())
  const hasInspectionTable = Boolean(String(form.value.inspectionTableId || '').trim())
  return hasIssueYes && hasStation && hasInspectionTable
})

const normalizeStandardDetailForRegister = (value) => {
  const topLevelLabels = new Set([
    '序号',
    '业务流程',
    '检查项目',
    '检查内容',
    '规范要求',
    '检查方法',
    '问题编号',
    '常见问题',
    '检查路径',
    '是否禁止项',
    '项目',
    '检查类别',
    '检查评比标准',
    '检查方式'
  ])

  const lines = String(value || '')
    .replace(/\\n/g, '\n')
    .split('\n')
    .map((line) => String(line || '').trim())
    .filter(Boolean)

  const result = []

  lines.forEach((line) => {
    const separatorIndex = line.indexOf('：')
    const possibleLabel = separatorIndex > -1 ? line.slice(0, separatorIndex).trim() : ''

    if (separatorIndex > -1 && topLevelLabels.has(possibleLabel)) {
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

const filteredStations = computed(() => {
  const keyword = stationSearch.value.trim().toLowerCase()
  return stations.value.filter((item) => {
    const text = `${item.station_name || ''} ${item.region || ''}`.toLowerCase()
    return !keyword || text.includes(keyword)
  })
})

const filteredStandards = computed(() => {
  const keyword = standardSearch.value.trim().toLowerCase()
  return standards.value.filter((item) => {
    const text = `${item.standard_id || ''} ${item.standard_detail_text || ''} ${item.check_content || ''} ${item.check_item || ''} ${item.project_name || ''}`.toLowerCase()
    return !keyword || text.includes(keyword)
  })
})

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

const fetchStandards = async () => {
  if (!form.value.inspectionTableId) {
    standards.value = []
    return
  }
  const response = await axios.get('/api/inspection-table-standards', {
    params: {
      table_id: form.value.inspectionTableId
    }
  })
  standards.value = response.data || []
}

const openStationDropdown = () => {
  stationDropdownVisible.value = true
}

const openTableDropdown = () => {
  tableDropdownVisible.value = true
}

const openStandardDropdown = () => {
  standardDropdownVisible.value = true
}

const handleStationInput = () => {
  form.value.stationId = ''
  stationDropdownVisible.value = true
}

const handleTableInput = () => {
  form.value.inspectionTableId = ''
  tableDropdownVisible.value = true
  form.value.standardId = ''
  standardSearch.value = ''
  standards.value = []
}

const handleStandardInput = () => {
  form.value.standardId = ''
  standardDropdownVisible.value = true
}

watch(
  [normalizedHasIssue, () => form.value.inspectionTableId],
  async ([hasIssueValue, inspectionTableId]) => {
    if (hasIssueValue === 'no') {
      form.value.standardId = ''
      form.value.description = ''
      standardSearch.value = ''
      standardDropdownVisible.value = false
      clearImage()
      return
    }

    if (hasIssueValue === 'yes' && inspectionTableId) {
      await fetchStandards()
    }
  }
)

const selectStation = (station) => {
  stationSearch.value = station.station_name
  form.value.stationId = station.id
  stationDropdownVisible.value = false
}

const selectInspectionTable = async (table) => {
  tableSearch.value = table.table_name
  form.value.inspectionTableId = String(table.id)
  tableDropdownVisible.value = false
  form.value.standardId = ''
  standardSearch.value = ''

  if (normalizedHasIssue.value === 'yes') {
    await fetchStandards()
  } else {
    standards.value = []
  }
}

const selectStandard = (standard) => {
  standardSearch.value = `${standard.standard_id}｜${standard.check_content || standard.check_item || standard.project_name || '未命名规范'}`
  form.value.standardId = standard.standard_id
  standardDropdownVisible.value = false
}

const handleFileChange = async (event) => {
  const file = event.target.files?.[0]

  if (!file) {
    clearImage()
    return
  }

  if (!validateImageType(file)) {
    showSubmitToast('仅支持上传 JPG、JPEG、PNG、WEBP、HEIC、HEIF 格式图片。', 'error')
    event.target.value = ''
    clearImage()
    return
  }

  try {
    const compressedFile = await compressImageFile(file)
    imageFile.value = compressedFile

    if (imagePreviewUrl.value) {
      URL.revokeObjectURL(imagePreviewUrl.value)
    }
    imagePreviewUrl.value = URL.createObjectURL(compressedFile)

    if (submitMessageType.value !== 'success' && submitMessageTimer) {
      clearTimeout(submitMessageTimer)
      submitMessageTimer = null
      submitMessage.value = ''
      submitMessageType.value = 'info'
    }
  } catch (error) {
    showSubmitToast(error?.message || '图片处理失败，请更换图片后重试。', 'error')
    event.target.value = ''
    clearImage()
  }
}

const clearImage = () => {
  imageFile.value = null
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
  }
  imagePreviewUrl.value = ''
  const uploadInput = document.getElementById('issue-photo-upload')
  if (uploadInput) {
    uploadInput.value = ''
  }
  const cameraInput = document.getElementById('issue-photo-camera')
  if (cameraInput) {
    cameraInput.value = ''
  }
}

const resetForm = (preserveMessage = false) => {
  form.value = {
    stationId: '',
    hasIssue: 'yes',
    inspectionTableId: '',
    standardId: '',
    description: ''
  }
  standards.value = []
  stationSearch.value = ''
  tableSearch.value = ''
  standardSearch.value = ''
  stationDropdownVisible.value = false
  tableDropdownVisible.value = false
  standardDropdownVisible.value = false
  if (!preserveMessage) {
    submitMessage.value = ''
    submitMessageType.value = 'info'
  }
  clearImage()
  createdTime.value = formatCurrentTime()
}

const handleSubmit = async () => {
  const hasIssueValue = normalizedHasIssue.value

  if (!form.value.stationId) {
    showSubmitToast('请选择站点名称。', 'error')
    return
  }

  if (!form.value.inspectionTableId) {
    showSubmitToast('请选择检查表。', 'error')
    return
  }

  if (hasIssueValue === 'yes' && !form.value.standardId) {
    showSubmitToast('请选择规范。', 'error')
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
    formData.append('inspection_table_id', String(form.value.inspectionTableId))
    formData.append('has_issue', hasIssueValue)

    if (hasIssueValue === 'yes') {
      formData.append('standard_id', String(form.value.standardId))
      formData.append('description', form.value.description)
      formData.append('photo', imageFile.value)
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
  if (tableSelectRef.value && !tableSelectRef.value.contains(event.target)) {
    tableDropdownVisible.value = false
  }
  if (standardSelectRef.value && !standardSelectRef.value.contains(event.target)) {
    standardDropdownVisible.value = false
  }
}


watch(
  () => form.value.inspectionTableId,
  () => {
    if (submitMessageType.value !== 'success') {
      submitMessage.value = ''
      submitMessageType.value = 'info'
    }
  }
)

onMounted(async () => {
  createdTime.value = formatCurrentTime()
  document.addEventListener('click', handleClickOutside)
  try {
    await Promise.all([fetchStations(), fetchInspectionTables()])
  } catch (error) {
    showSubmitToast('初始化站点或检查表数据失败，请检查后端服务。', 'error')
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  if (submitMessageTimer) {
    clearTimeout(submitMessageTimer)
    submitMessageTimer = null
  }
  if (imagePreviewUrl.value) {
    URL.revokeObjectURL(imagePreviewUrl.value)
  }
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

.form-item input[readonly],
.form-item textarea[readonly] {
  background: #f8fafc;
  color: #475569;
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

.standard-detail-preview {
  white-space: pre-line;
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
}

.upload-dropzone:hover {
  border-color: #93c5fd;
  background: linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%);
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

.upload-desc {
  max-width: 560px;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
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

.image-preview-thumb {
  width: 148px;
  height: 108px;
  object-fit: cover;
  border-radius: 14px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  flex-shrink: 0;
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
  z-index: 1200;
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
    padding: 16px;
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
    gap: 14px;
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
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .issue-toggle-btn {
    height: 46px;
    font-size: 15px;
  }

  .search-select-dropdown {
    max-height: 240px;
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
    padding: 20px 14px;
  }

  .upload-title {
    font-size: 15px;
  }

  .upload-desc {
    font-size: 12px;
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

  .image-preview-thumb {
    width: 100%;
    max-width: none;
    height: auto;
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
