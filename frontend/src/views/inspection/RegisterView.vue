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
              <input
                v-model="stationSearch"
                type="text"
                placeholder="搜索并选择站点名称"
                @focus="openStationDropdown"
                @input="handleStationInput"
              />
              <div v-if="stationDropdownVisible" class="search-select-dropdown">
                <div
                  v-for="station in filteredStations"
                  :key="station.id"
                  class="search-select-option"
                  @click="selectStation(station)"
                >
                  <div class="option-main">{{ station.station_name }}</div>
                  <div class="option-sub">{{ station.region || '未设置所属地' }}</div>
                </div>
                <div v-if="filteredStations.length === 0" class="search-select-empty">无匹配站点</div>
              </div>
            </div>
          </div>
          <div class="form-item form-item-full">
            <label>巡检大类</label>
            <div class="search-select" ref="categorySelectRef">
              <input
                v-model="categorySearch"
                type="text"
                placeholder="搜索并选择巡检大类"
                @focus="openCategoryDropdown"
                @input="handleCategoryInput"
              />
              <div v-if="categoryDropdownVisible" class="search-select-dropdown">
                <div
                  v-for="category in filteredCategories"
                  :key="category.id"
                  class="search-select-option"
                  @click="selectCategory(category)"
                >
                  <div class="option-main">{{ category.name }}</div>
                </div>
                <div v-if="filteredCategories.length === 0" class="search-select-empty">无匹配巡检大类</div>
              </div>
            </div>
          </div>

          <div class="form-item form-item-full">
            <label>是否发现问题</label>
            <select v-model="form.hasIssue">
              <option value="">请选择</option>
              <option value="no">未发现问题</option>
              <option value="yes">发现问题</option>
            </select>
          </div>
        </div>

        <template v-if="showIssueFields">
          <div class="section-title issue-section-title">问题信息</div>

          <div class="form-grid">
            <div class="form-item form-item-full">
              <label>规范引用</label>
              <div class="search-select" ref="standardSelectRef">
                <input
                  v-model="standardSearch"
                  type="text"
                  placeholder="搜索并选择规范引用"
                  @focus="openStandardDropdown"
                  @input="handleStandardInput"
                />
                <div v-if="standardDropdownVisible" class="search-select-dropdown search-select-dropdown-wide">
                  <div
                    v-for="standard in filteredStandards"
                    :key="standard.id"
                    class="search-select-option"
                    @click="selectStandard(standard)"
                  >
                    <div class="option-main">
                      {{ standard.code }}｜{{ standard.business_process }}｜{{ standard.check_item }}
                    </div>
                    <div class="option-sub">{{ standard.check_content }}</div>
                  </div>
                  <div v-if="filteredStandards.length === 0" class="search-select-empty">无匹配规范</div>
                </div>
              </div>
            </div>

            <div class="form-item">
              <label>规范编号</label>
              <input :value="selectedStandard?.code || ''" type="text" readonly />
            </div>

            <div class="form-item">
              <label>业务流程</label>
              <input :value="selectedStandard?.business_process || ''" type="text" readonly />
            </div>

            <div class="form-item">
              <label>检查项目</label>
              <input :value="selectedStandard?.check_item || ''" type="text" readonly />
            </div>

            <div class="form-item">
              <label>检查内容</label>
              <input :value="selectedStandard?.check_content || ''" type="text" readonly />
            </div>

            <div class="form-item form-item-full">
              <label>规范要求</label>
              <textarea :value="selectedStandard?.requirement || ''" rows="4" readonly></textarea>
            </div>

            <div class="form-item form-item-full">
              <label>检查方法</label>
              <textarea :value="selectedStandard?.check_method || ''" rows="4" readonly></textarea>
            </div>

            <div class="form-item form-item-full">
              <label>实际问题描述</label>
              <textarea v-model="form.description" rows="4" placeholder="请填写现场实际问题描述"></textarea>
            </div>

            <div class="form-item form-item-full">
              <label>上传问题照片</label>
              <div class="upload-card">
                <input
                  id="issue-photo-upload"
                  class="upload-input"
                  type="file"
                  accept="image/*"
                  @change="handleFileChange"
                />

                <label for="issue-photo-upload" class="upload-dropzone">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">选择或更换问题照片</div>
                  <div class="upload-desc">
                    支持上传现场问题照片，建议使用清晰、完整、能准确反映问题的图片。
                  </div>
                  <div class="upload-trigger">选择文件</div>
                </label>

                <div v-if="imagePreviewUrl" class="image-preview-panel">
                  <img :src="imagePreviewUrl" alt="问题照片预览" class="image-preview-thumb" />
                  <div class="image-preview-meta">
                    <div class="image-preview-title">已选择问题照片</div>
                    <div class="image-preview-name">{{ imageFile?.name || '已上传图片' }}</div>
                    <div class="image-preview-actions">
                      <label for="issue-photo-upload" class="btn btn-light image-action-btn">重新选择</label>
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

        <div v-if="submitMessage" class="submit-message" :class="submitMessageType">{{ submitMessage }}</div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'

const currentRole = localStorage.getItem('user_role') || ''
const hasPermission = currentRole === 'supervisor'
const stationSelectRef = ref(null)
const standardSelectRef = ref(null)
const categorySelectRef = ref(null)
const stationDropdownVisible = ref(false)
const standardDropdownVisible = ref(false)
const categoryDropdownVisible = ref(false)
const stationSearch = ref('')
const standardSearch = ref('')
const categorySearch = ref('')
const imageFile = ref(null)
const imagePreviewUrl = ref('')
const submitMessage = ref('')
const submitMessageType = ref('info')
const createdTime = ref('')
const submitting = ref(false)
const MAX_UPLOAD_BYTES = 500 * 1024
const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
const stations = ref([])
const standards = ref([])
const categories = ref([])

const form = ref({
  stationId: '',
  categoryId: '',
  hasIssue: '',
  standardId: '',
  description: ''
})
const filteredCategories = computed(() => {
  const keyword = categorySearch.value.trim().toLowerCase()
  return categories.value.filter((item) => {
    const text = `${item.name || ''}`.toLowerCase()
    return !keyword || text.includes(keyword)
  })
})

const selectedStandard = computed(() => {
  return standards.value.find((item) => String(item.id) === String(form.value.standardId)) || null
})

const showIssueFields = computed(() => form.value.hasIssue === 'yes')

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
    const text = `${item.code} ${item.business_process} ${item.check_item} ${item.check_content}`.toLowerCase()
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

const loadImageFromFile = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = () => reject(new Error('图片读取失败。'))
      img.src = reader.result
    }
    reader.onerror = () => reject(new Error('图片读取失败。'))
    reader.readAsDataURL(file)
  })
}

const canvasToBlob = (canvas, quality = 0.82) => {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('图片压缩失败。'))
        return
      }
      resolve(blob)
    }, 'image/jpeg', quality)
  })
}

const compressImageFile = async (file) => {
  const img = await loadImageFromFile(file)
  const maxWidth = 1600
  let targetWidth = img.width
  let targetHeight = img.height

  if (img.width > maxWidth) {
    const ratio = maxWidth / img.width
    targetWidth = maxWidth
    targetHeight = Math.max(1, Math.round(img.height * ratio))
  }

  let canvas = document.createElement('canvas')
  canvas.width = targetWidth
  canvas.height = targetHeight
  let ctx = canvas.getContext('2d')
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, targetWidth, targetHeight)
  ctx.drawImage(img, 0, 0, targetWidth, targetHeight)

  let quality = 0.82
  let blob = await canvasToBlob(canvas, quality)

  while (blob.size > MAX_UPLOAD_BYTES && quality > 0.46) {
    quality -= 0.08
    blob = await canvasToBlob(canvas, quality)
  }

  while (blob.size > MAX_UPLOAD_BYTES && canvas.width > 960) {
    const nextWidth = Math.max(960, Math.round(canvas.width * 0.9))
    const nextHeight = Math.max(1, Math.round(canvas.height * 0.9))
    const nextCanvas = document.createElement('canvas')
    nextCanvas.width = nextWidth
    nextCanvas.height = nextHeight
    const nextCtx = nextCanvas.getContext('2d')
    nextCtx.fillStyle = '#ffffff'
    nextCtx.fillRect(0, 0, nextWidth, nextHeight)
    nextCtx.drawImage(canvas, 0, 0, nextWidth, nextHeight)
    canvas = nextCanvas
    ctx = nextCtx
    blob = await canvasToBlob(canvas, 0.7)
  }

  return new File([blob], `${(file.name || 'upload').replace(/\.[^.]+$/, '') || 'upload'}.jpg`, {
    type: 'image/jpeg'
  })
}

const fetchStations = async () => {
  const response = await axios.get('/api/stations')
  stations.value = response.data || []
}

const fetchCategories = async () => {
  const response = await axios.get('/api/inspection-categories')
  categories.value = response.data || []
}

const fetchStandards = async () => {
  const response = await axios.get('/api/inspection-standards')
  standards.value = response.data || []
}

const openStationDropdown = () => {
  stationDropdownVisible.value = true
}

const openCategoryDropdown = () => {
  categoryDropdownVisible.value = true
}

const openStandardDropdown = () => {
  standardDropdownVisible.value = true
}

const handleStationInput = () => {
  form.value.stationId = ''
  stationDropdownVisible.value = true
}

const handleCategoryInput = () => {
  form.value.categoryId = ''
  categoryDropdownVisible.value = true
}

const handleStandardInput = () => {
  form.value.standardId = ''
  standardDropdownVisible.value = true
}

const selectStation = (station) => {
  stationSearch.value = station.station_name
  form.value.stationId = station.id
  stationDropdownVisible.value = false
}

const selectCategory = (category) => {
  categorySearch.value = category.name
  form.value.categoryId = category.id
  categoryDropdownVisible.value = false
}

const selectStandard = (standard) => {
  standardSearch.value = `${standard.code}｜${standard.business_process}｜${standard.check_item}｜${standard.check_content}`
  form.value.standardId = standard.id
  standardDropdownVisible.value = false
}

const handleFileChange = async (event) => {
  const file = event.target.files?.[0]

  if (!file) {
    clearImage()
    return
  }

  if (file.type && !ACCEPTED_IMAGE_TYPES.includes(file.type)) {
    submitMessageType.value = 'error'
    submitMessage.value = '仅支持上传 JPG、JPEG、PNG、WEBP、HEIC、HEIF 格式图片。'
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

    if (submitMessageType.value !== 'success') {
      submitMessage.value = ''
      submitMessageType.value = 'info'
    }
  } catch (error) {
    submitMessageType.value = 'error'
    submitMessage.value = error?.message || '图片处理失败，请更换图片后重试。'
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
  const input = document.getElementById('issue-photo-upload')
  if (input) {
    input.value = ''
  }
}

const resetForm = (preserveMessage = false) => {
  form.value = {
    stationId: '',
    categoryId: '',
    hasIssue: '',
    standardId: '',
    description: ''
  }
  stationSearch.value = ''
  categorySearch.value = ''
  standardSearch.value = ''
  stationDropdownVisible.value = false
  categoryDropdownVisible.value = false
  standardDropdownVisible.value = false
  if (!preserveMessage) {
    submitMessage.value = ''
    submitMessageType.value = 'info'
  }
  clearImage()
  createdTime.value = formatCurrentTime()
}

const handleSubmit = async () => {
  if (!form.value.stationId) {
    submitMessageType.value = 'error'
    submitMessage.value = '请选择站点名称。'
    return
  }
  if (!form.value.categoryId) {
    submitMessageType.value = 'error'
    submitMessage.value = '请选择巡检大类。'
    return
  }

  if (!form.value.hasIssue) {
    submitMessageType.value = 'error'
    submitMessage.value = '请选择是否发现问题。'
    return
  }

  if (form.value.hasIssue === 'yes') {
    if (!form.value.standardId) {
      submitMessageType.value = 'error'
      submitMessage.value = '请选择规范引用。'
      return
    }
    if (!form.value.description.trim()) {
      submitMessageType.value = 'error'
      submitMessage.value = '请填写实际问题描述。'
      return
    }
    if (!imageFile.value) {
      submitMessageType.value = 'error'
      submitMessage.value = '请上传问题照片。'
      return
    }
  }

  const inspectorId = localStorage.getItem('user_id') || ''
  if (!inspectorId) {
    submitMessageType.value = 'error'
    submitMessage.value = '当前登录信息缺失，请重新登录。'
    return
  }

  try {
    submitting.value = true
    submitMessage.value = ''

    const formData = new FormData()
    formData.append('inspector_id', inspectorId)
    formData.append('station_id', String(form.value.stationId))
    formData.append('category_id', String(form.value.categoryId))
    formData.append('has_issue', form.value.hasIssue)

    if (form.value.hasIssue === 'yes') {
      formData.append('standard_id', String(form.value.standardId))
      formData.append('description', form.value.description)
      formData.append('photo', imageFile.value)
    }

    const response = await axios.post('/api/inspection-register', formData)
    submitMessageType.value = 'success'
    resetForm(true)
    submitMessage.value = response.data.message || '提交成功。'
  } catch (error) {
    submitMessageType.value = 'error'
    submitMessage.value = error?.response?.data?.error || '提交失败，请稍后重试。'
  } finally {
    submitting.value = false
  }
}

const handleClickOutside = (event) => {
  if (stationSelectRef.value && !stationSelectRef.value.contains(event.target)) {
    stationDropdownVisible.value = false
  }
  if (categorySelectRef.value && !categorySelectRef.value.contains(event.target)) {
    categoryDropdownVisible.value = false
  }
  if (standardSelectRef.value && !standardSelectRef.value.contains(event.target)) {
    standardDropdownVisible.value = false
  }
}

watch(
  () => form.value.hasIssue,
  (value) => {
    if (value !== 'yes') {
      form.value.standardId = ''
      form.value.description = ''
      standardSearch.value = ''
      standardDropdownVisible.value = false
      clearImage()
    }
  }
)

watch(
  () => form.value.categoryId,
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
    await Promise.all([fetchStations(), fetchCategories(), fetchStandards()])
  } catch (error) {
    submitMessage.value = '初始化站点或规范数据失败，请检查后端服务。'
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
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
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
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

.submit-message {
  font-size: 14px;
  color: #2563eb;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  padding: 12px 14px;
}

.submit-message.success {
  color: #166534;
  background: #ecfdf5;
  border-color: #bbf7d0;
}

.submit-message.error {
  color: #b91c1c;
  background: #fef2f2;
  border-color: #fecaca;
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
    position: sticky;
    bottom: 0;
    padding-top: 8px;
    background: rgba(255, 255, 255, 0.96);
  }

  .btn {
    width: 100%;
    min-height: 46px;
  }

  .submit-message {
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