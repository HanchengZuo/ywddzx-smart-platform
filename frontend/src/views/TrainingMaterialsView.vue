<template>
  <div class="page-shell training-materials-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">培训系统</div>
        <h2>培训材料库</h2>
        <p class="page-desc">集中维护督导组培训 PDF 与视频材料，上传人、文件大小和最后更新日期由系统自动记录。</p>
      </div>
      <div class="header-actions">
        <div class="header-badges">
          <span class="status-pill info">材料 {{ materials.length }}</span>
          <span class="status-pill neutral">PDF {{ pdfCount }}</span>
          <span class="status-pill neutral">视频 {{ videoCount }}</span>
        </div>
        <button v-if="canUpload" class="btn btn-primary" type="button" @click="openCreateDialog">
          上传材料
        </button>
      </div>
    </div>

    <div v-if="pageError" class="message-card error">{{ pageError }}</div>
    <div v-if="actionMessage" :class="['message-card', actionMessageType]">{{ actionMessage }}</div>

    <div class="content-grid">
      <section class="list-card card-surface">
        <div class="section-head">
          <div>
            <div class="section-kicker">材料目录</div>
            <h3>全部培训材料</h3>
          </div>
        </div>

        <div class="material-list">
          <article v-for="item in materials" :key="item.id" class="material-card"
            :class="{ active: activeMaterial?.id === item.id }" @click="selectMaterial(item)">
            <div class="material-card-main">
              <div>
                <div class="file-type-label">{{ fileTypeLabel(item.file_type) }}</div>
                <h4>{{ item.title }}</h4>
              </div>
              <span :class="['status-pill', item.file_type === 'video' ? 'video' : 'pdf']">
                {{ item.file_type === 'video' ? '视频' : 'PDF' }}
              </span>
            </div>

            <div class="material-card-actions">
              <button class="btn btn-secondary btn-compact" type="button" @click.stop="selectMaterial(item)">
                查看预览
              </button>
              <button v-if="item.can_edit" class="btn btn-secondary btn-compact" type="button"
                @click.stop="openEditDialog(item)">
                编辑/上传新版
              </button>
              <button v-if="item.can_delete" class="btn btn-danger btn-compact" type="button"
                :disabled="deletingId === item.id" @click.stop="deleteMaterial(item)">
                {{ deletingId === item.id ? '删除中...' : '删除' }}
              </button>
            </div>
          </article>

          <div v-if="!loading && materials.length === 0" class="empty-block">
            暂无培训材料。督导组账号可以点击“上传材料”创建第一份材料。
          </div>
          <div v-if="loading" class="empty-block">正在加载培训材料库...</div>
        </div>
      </section>

      <section class="preview-card card-surface">
        <template v-if="activeMaterial">
          <div class="preview-header">
            <div>
              <div class="section-kicker">材料预览</div>
              <h3>{{ activeMaterial.title }}</h3>
              <p>{{ activeMaterial.original_filename || '暂无原始文件名' }}</p>
            </div>
            <div class="preview-actions">
              <a class="btn btn-secondary" :href="activeMaterial.file_url" target="_blank" rel="noopener">
                新窗口打开
              </a>
            </div>
          </div>

          <div class="preview-meta-grid">
            <div class="meta-item">
              <span>上传人</span>
              <strong>{{ activeMaterial.uploaded_by_real_name || activeMaterial.uploaded_by_username || '-' }}</strong>
            </div>
            <div class="meta-item">
              <span>最后更新日期</span>
              <strong>{{ activeMaterial.updated_at || '-' }}</strong>
            </div>
            <div class="meta-item">
              <span>文件大小</span>
              <strong>{{ formatFileSize(activeMaterial.file_size) }}</strong>
            </div>
          </div>

          <div v-if="activeMaterial.file_type === 'pdf'" class="preview-shell">
            <iframe :src="activeMaterial.file_url" title="培训材料 PDF 预览"></iframe>
          </div>
          <div v-else class="preview-shell video-shell">
            <video :src="activeMaterial.file_url" controls preload="metadata"></video>
          </div>
        </template>

        <div v-else class="empty-preview">
          <div class="empty-icon">材</div>
          <div class="empty-title">暂无培训材料</div>
          <p>上传 PDF 或视频后，可以在这里直接预览和打开。</p>
        </div>
      </section>
    </div>

    <div v-if="dialog.visible" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog-card card-surface">
        <div class="dialog-header">
          <div>
            <div class="section-kicker">{{ dialog.mode === 'create' ? '新增材料' : '编辑材料' }}</div>
            <h3>{{ dialog.mode === 'create' ? '上传培训材料' : '更新培训材料' }}</h3>
          </div>
          <button class="btn btn-secondary" type="button" @click="closeDialog">关闭</button>
        </div>

        <div class="dialog-body">
          <label class="form-field">
            <span>材料标题</span>
            <input v-model.trim="dialog.title" type="text" maxlength="120" placeholder="选择文件后会自动带出文件名"
              @input="dialog.error = ''" />
          </label>

          <label class="file-picker">
            <input type="file" accept="application/pdf,video/mp4,video/webm,video/quicktime,.pdf,.mp4,.webm,.mov,.m4v"
              @change="handleDialogFileChange" />
            <div class="file-picker-content">
              <strong>{{ dialog.file ? dialog.file.name : dialog.mode === 'create' ? '选择 PDF 或视频文件' : '选择文件上传新版' }}</strong>
              <span>{{ dialog.file ? formatFileSize(dialog.file.size) : '支持 PDF、MP4、MOV、M4V、WEBM。PDF 最大 50MB，视频最大 500MB。' }}</span>
            </div>
          </label>

          <div v-if="dialog.mode === 'edit'" class="dialog-hint">
            不选择新文件时仅更新标题；选择文件后会替换为新版，并自动更新文件大小和最后更新日期。
          </div>

          <div v-if="dialog.error" class="dialog-message error">{{ dialog.error }}</div>
        </div>

        <div class="dialog-actions">
          <button class="btn btn-secondary" type="button" @click="closeDialog">取消</button>
          <button class="btn btn-primary" type="button" :disabled="saving" @click="submitMaterial">
            {{ saving ? '保存中...' : dialog.mode === 'create' ? '上传材料' : '保存更新' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const currentUserId = ref(localStorage.getItem('user_id') || '')
const currentRole = ref(localStorage.getItem('user_role') || '')
const loading = ref(false)
const saving = ref(false)
const deletingId = ref(null)
const canUpload = ref(currentRole.value === 'supervisor')
const materials = ref([])
const activeMaterialId = ref('')
const pageError = ref('')
const actionMessage = ref('')
const actionMessageType = ref('info')
let actionMessageTimer = null

const dialog = reactive({
  visible: false,
  mode: 'create',
  id: null,
  title: '',
  file: null,
  error: ''
})

const pdfCount = computed(() => materials.value.filter((item) => item.file_type === 'pdf').length)
const videoCount = computed(() => materials.value.filter((item) => item.file_type === 'video').length)

const activeMaterial = computed(() => {
  return materials.value.find((item) => String(item.id) === String(activeMaterialId.value)) ||
    materials.value[0] ||
    null
})

const fileTypeLabel = (type) => type === 'video' ? '视频材料' : 'PDF 材料'

const getTitleFromFileName = (fileName) => {
  return String(fileName || '')
    .replace(/\.[^.]+$/, '')
    .trim()
    .slice(0, 120)
}

const formatFileSize = (size) => {
  const bytes = Number(size || 0)
  if (!bytes) return '-'
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

const setActionMessage = (message, type = 'info') => {
  if (actionMessageTimer) {
    window.clearTimeout(actionMessageTimer)
    actionMessageTimer = null
  }

  actionMessage.value = message
  actionMessageType.value = type
  if (!message) return

  actionMessageTimer = window.setTimeout(() => {
    actionMessage.value = ''
    actionMessageTimer = null
  }, 2600)
}

const selectMaterial = (item) => {
  activeMaterialId.value = String(item.id)
}

const validateFile = (file) => {
  if (!file) return ''
  const name = file.name.toLowerCase()
  const isPdf = name.endsWith('.pdf')
  const isVideo = ['.mp4', '.webm', '.mov', '.m4v'].some((ext) => name.endsWith(ext))
  if (!isPdf && !isVideo) return '只能上传 PDF 或视频文件。'
  if (isPdf && file.size > 50 * 1024 * 1024) return 'PDF 文件不能超过 50MB。'
  if (isVideo && file.size > 500 * 1024 * 1024) return '视频文件不能超过 500MB。'
  return ''
}

const fetchMaterials = async () => {
  if (!currentUserId.value) {
    pageError.value = '缺少当前用户信息，请重新登录。'
    return
  }

  try {
    loading.value = true
    pageError.value = ''
    const response = await axios.get('/api/training-materials', {
      params: {
        user_id: currentUserId.value,
        _ts: Date.now()
      }
    })
    materials.value = response.data?.items || []
    canUpload.value = Boolean(response.data?.can_upload)

    if (!materials.value.some((item) => String(item.id) === String(activeMaterialId.value))) {
      activeMaterialId.value = materials.value[0]?.id ? String(materials.value[0].id) : ''
    }
  } catch (error) {
    pageError.value = error?.response?.data?.error || '培训材料库加载失败，请稍后重试。'
    setActionMessage(pageError.value, 'error')
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  dialog.visible = true
  dialog.mode = 'create'
  dialog.id = null
  dialog.title = ''
  dialog.file = null
  dialog.error = ''
  setActionMessage('')
}

const openEditDialog = (item) => {
  dialog.visible = true
  dialog.mode = 'edit'
  dialog.id = item.id
  dialog.title = item.title || ''
  dialog.file = null
  dialog.error = ''
  setActionMessage('')
}

const resetDialogState = () => {
  dialog.visible = false
  dialog.id = null
  dialog.title = ''
  dialog.file = null
  dialog.error = ''
}

const closeDialog = () => {
  if (saving.value) return
  resetDialogState()
}

const handleDialogFileChange = (event) => {
  const input = event.target
  const file = input.files?.[0] || null
  input.value = ''
  dialog.error = ''
  if (!file) {
    dialog.file = null
    return
  }

  const message = validateFile(file)
  if (message) {
    dialog.error = message
    dialog.file = null
    return
  }
  dialog.file = file
  if (!dialog.title.trim()) {
    dialog.title = getTitleFromFileName(file.name)
  }
}

const submitMaterial = async () => {
  dialog.error = ''

  if (!dialog.title.trim()) {
    dialog.error = '请填写材料标题。'
    return
  }

  if (dialog.mode === 'create' && !dialog.file) {
    dialog.error = '请选择需要上传的 PDF 或视频文件。'
    return
  }

  try {
    saving.value = true
    pageError.value = ''
    const formData = new FormData()
    formData.append('user_id', currentUserId.value)
    formData.append('title', dialog.title.trim())
    if (dialog.file) {
      formData.append('file', dialog.file)
    }

    const response = dialog.mode === 'create'
      ? await axios.post('/api/training-materials', formData)
      : await axios.put(`/api/training-materials/${dialog.id}`, formData)

    const successMessage = response.data?.message || '培训材料已保存。'
    const nextActiveId = response.data?.id || dialog.id
    resetDialogState()
    setActionMessage(successMessage, 'success')
    await fetchMaterials()
    if (nextActiveId) {
      activeMaterialId.value = String(nextActiveId)
    }
  } catch (error) {
    const message = error?.response?.data?.error || '培训材料保存失败，请稍后重试。'
    dialog.error = message
  } finally {
    saving.value = false
  }
}

const deleteMaterial = async (item) => {
  if (!item?.id) return
  const confirmed = window.confirm(`确定删除培训材料【${item.title || '未命名材料'}】吗？`)
  if (!confirmed) return

  try {
    deletingId.value = item.id
    pageError.value = ''
    const response = await axios.delete(`/api/training-materials/${item.id}`, {
      data: {
        user_id: currentUserId.value
      }
    })
    setActionMessage(response.data?.message || '培训材料已删除。', 'success')
    await fetchMaterials()
  } catch (error) {
    const message = error?.response?.data?.error || '删除失败，请稍后重试。'
    pageError.value = message
    setActionMessage(message, 'error')
  } finally {
    deletingId.value = null
  }
}

onMounted(fetchMaterials)

onBeforeUnmount(() => {
  if (actionMessageTimer) {
    window.clearTimeout(actionMessageTimer)
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
  border-radius: 24px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
}

.page-header {
  padding: 26px 28px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.page-kicker,
.section-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 12px;
}

.page-header h2,
.preview-header h3,
.section-head h3,
.dialog-header h3 {
  margin: 0;
  color: #0f172a;
}

.page-header h2 {
  font-size: 34px;
}

.page-desc,
.preview-header p,
.material-card p,
.empty-preview p,
.dialog-hint {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.dialog-message {
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.7;
}

.dialog-message.error {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #dc2626;
}

.header-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}

.header-badges {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.status-pill.info {
  background: #eff6ff;
  color: #1d4ed8;
}

.status-pill.neutral {
  background: #f1f5f9;
  color: #475569;
}

.status-pill.pdf {
  background: #eef4ff;
  color: #1d4ed8;
}

.status-pill.video {
  background: #fff7ed;
  color: #c2410c;
}

.message-card {
  padding: 13px 16px;
  border-radius: 16px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 14px;
  font-weight: 700;
}

.message-card.success {
  border-color: #bbf7d0;
  background: #ecfdf5;
  color: #15803d;
}

.message-card.error {
  border-color: #fecaca;
  background: #fef2f2;
  color: #dc2626;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(320px, 430px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.list-card,
.preview-card {
  padding: 20px;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.section-head h3 {
  font-size: 20px;
}

.material-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 760px;
  overflow: auto;
  padding-right: 4px;
}

.material-card {
  border: 1px solid #e5edf5;
  background: #fff;
  border-radius: 18px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.material-card:hover,
.material-card.active {
  border-color: #93c5fd;
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.08);
}

.material-card-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.file-type-label {
  color: #2563eb;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.04em;
}

.material-card h4 {
  margin: 6px 0 0;
  color: #0f172a;
  font-size: 16px;
  line-height: 1.45;
}

.card-meta-grid,
.preview-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.card-meta-grid {
  grid-template-columns: 1fr;
}

.card-meta-grid div,
.meta-item {
  padding: 11px 12px;
  border-radius: 14px;
  border: 1px solid #e7edf4;
  background: #f8fafc;
  min-width: 0;
}

.card-meta-grid span,
.meta-item span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 5px;
}

.card-meta-grid strong,
.meta-item strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.material-card-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.preview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.preview-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.preview-shell {
  margin-top: 16px;
  height: min(74vh, 760px);
  min-height: 520px;
  border: 1px solid #dbe4ee;
  border-radius: 20px;
  overflow: hidden;
  background: #f8fafc;
}

.preview-shell iframe,
.preview-shell video {
  width: 100%;
  height: 100%;
  border: 0;
  background: #fff;
}

.video-shell {
  background: #0f172a;
}

.video-shell video {
  object-fit: contain;
  background: #0f172a;
}

.empty-block,
.empty-preview {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
  line-height: 1.8;
}

.empty-preview {
  min-height: 520px;
  border: 1px dashed #cbd5e1;
  border-radius: 20px;
  background: #f8fafc;
  margin-top: 16px;
  padding: 24px;
}

.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 20px;
  font-weight: 900;
  margin-bottom: 14px;
}

.empty-title {
  color: #0f172a;
  font-size: 20px;
  font-weight: 900;
}

.btn {
  min-height: 42px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s ease;
}

.btn-compact {
  min-height: 38px;
  padding: 0 12px;
  font-size: 13px;
}

.btn-primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.btn-danger {
  border-color: #fecaca;
  background: #fff;
  color: #dc2626;
}

.btn-secondary:hover:not(:disabled) {
  background: #f8fafc;
}

.btn-danger:hover:not(:disabled) {
  background: #fef2f2;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.46);
}

.dialog-card {
  width: min(620px, 100%);
  padding: 22px;
}

.dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 16px;
  margin-bottom: 18px;
  border-bottom: 1px solid #e2e8f0;
}

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-field span {
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.form-field input {
  width: 100%;
  height: 46px;
  border: 1px solid #d7e0ea;
  border-radius: 14px;
  padding: 0 14px;
  color: #0f172a;
  font-size: 14px;
}

.file-picker {
  display: block;
  cursor: pointer;
}

.file-picker input {
  display: none;
}

.file-picker-content {
  padding: 18px;
  border: 1px dashed #93c5fd;
  border-radius: 18px;
  background: #eff6ff;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-picker-content strong {
  color: #0f172a;
  font-size: 15px;
}

.file-picker-content span {
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.dialog-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 1200px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

  .material-list {
    max-height: none;
  }
}

@media (max-width: 768px) {
  .page-header,
  .preview-header,
  .dialog-header,
  .dialog-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .page-header,
  .list-card,
  .preview-card {
    padding: 18px;
    border-radius: 22px;
  }

  .page-header h2 {
    font-size: 29px;
  }

  .header-actions {
    align-items: stretch;
    width: 100%;
  }

  .header-badges,
  .preview-actions {
    justify-content: flex-start;
  }

  .header-actions .btn,
  .preview-actions .btn,
  .dialog-actions .btn {
    width: 100%;
  }

  .card-meta-grid,
  .preview-meta-grid,
  .material-card-actions {
    grid-template-columns: 1fr;
  }

  .material-card-main {
    flex-direction: column;
  }

  .preview-shell {
    height: 68vh;
    min-height: 420px;
    border-radius: 18px;
  }

  .empty-preview {
    min-height: 360px;
  }

  .dialog-overlay {
    align-items: flex-end;
    padding: 0;
  }

  .dialog-card {
    width: 100%;
    max-height: 92vh;
    overflow-y: auto;
    padding: 18px;
    border-radius: 24px 24px 0 0;
  }
}
</style>
