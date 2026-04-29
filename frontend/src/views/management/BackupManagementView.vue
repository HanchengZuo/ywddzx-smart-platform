<template>
  <div class="page-shell backup-management-page">
    <div class="page-header card-surface backup-hero">
      <div class="hero-content">
        <div class="page-kicker">管理系统</div>
        <h2>数据备份管理</h2>
        <p class="page-desc">完整备份 PostgreSQL 数据库和 storage 上传文件目录，支持手动下载、导入恢复和自动定时导出。</p>
        <div v-if="hasPermission" class="hero-meta">
          <span>自动备份：{{ frequencyLabel(config.frequency) }}</span>
          <span>保存位置：{{ config.destination_path || '默认目录' }}</span>
        </div>
      </div>
      <div v-if="hasPermission" class="header-actions action-panel">
        <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchBackups">
          {{ loading ? '刷新中...' : '刷新状态' }}
        </button>
        <button class="btn btn-primary main-action" type="button" :disabled="exporting || importing" @click="exportBackup">
          {{ exporting ? '导出中...' : '立即导出完整备份' }}
        </button>
        <button class="btn btn-import" type="button" :disabled="importing || exporting" @click="triggerImport">
          {{ importing ? '导入恢复中...' : '导入备份恢复' }}
        </button>
        <input ref="backupFileInputRef" class="hidden-file-input" type="file" accept="application/zip,.zip"
          :disabled="importing || exporting" @change="importBackup" />
      </div>
    </div>

    <div v-if="!hasPermission" class="card-surface permission-card">
      <div class="permission-icon">!</div>
      <div class="permission-title">无权限访问</div>
      <div class="permission-desc">当前页面仅 root 系统管理员账号可访问和操作。</div>
    </div>

    <template v-else>
      <div v-if="message.text" :class="['message-card', message.type]">{{ message.text }}</div>

      <div class="backup-grid">
        <section class="card-surface config-card">
          <div class="section-head">
            <div>
              <div class="section-kicker">自动备份设置</div>
              <h3>设置备份频率和服务端保存位置</h3>
              <p>保存位置是后端服务器可访问的路径；Docker 部署时建议放在已挂载到宿主机的目录里。</p>
            </div>
          </div>

          <div class="config-form">
            <label class="form-field span-2">
              <span>备份保存位置</span>
              <input v-model.trim="form.destination_path" type="text" placeholder="/app/storage/backups" />
              <small>可填写绝对路径；相对路径会保存到默认备份目录下。</small>
            </label>

            <label class="form-field">
              <span>自动导出频率</span>
              <select v-model="form.frequency">
                <option v-for="option in frequencyOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>

            <div class="form-actions span-2">
              <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchBackups">取消修改</button>
              <button class="btn btn-primary" type="button" :disabled="savingConfig" @click="saveConfig">
                {{ savingConfig ? '保存中...' : '保存备份设置' }}
              </button>
            </div>
          </div>
          <div class="auto-note">
            自动备份只保留一个固定文件：<strong>ywddzx_full_backup_auto.zip</strong>，每次执行都会覆盖上一份自动备份。
          </div>
        </section>

        <section class="card-surface status-card">
          <div class="section-head">
            <div>
              <div class="section-kicker">运行状态</div>
              <h3>备份任务概览</h3>
            </div>
          </div>

          <div class="status-list">
            <div class="status-item">
              <span>当前频率</span>
              <strong>{{ frequencyLabel(config.frequency) }}</strong>
            </div>
            <div class="status-item">
              <span>下次自动备份</span>
              <strong>{{ formatDate(config.next_run_at) }}</strong>
            </div>
            <div class="status-item">
              <span>上次自动备份</span>
              <strong>{{ formatDate(config.last_auto_export_at) }}</strong>
            </div>
            <div class="status-item">
              <span>最近备份文件</span>
              <strong>{{ config.last_backup_path || '-' }}</strong>
            </div>
            <div class="status-item">
              <span>最近备份大小</span>
              <strong>{{ formatSize(config.last_backup_size) }}</strong>
            </div>
            <div class="status-item" :class="{ error: config.last_status === 'error' }">
              <span>最近任务状态</span>
              <strong>{{ config.last_status === 'error' ? (config.last_error || '执行失败') : '正常' }}</strong>
            </div>
          </div>
        </section>
      </div>

      <section class="card-surface warning-card">
        <div class="warning-mark">!</div>
        <div>
          <div class="warning-title">导入恢复会覆盖当前系统数据</div>
          <p>导入完整备份会用备份包中的 PostgreSQL 数据库和 storage 上传文件替换当前数据。建议先点击“立即导出完整备份”留一份当前状态。</p>
        </div>
      </section>

      <section class="card-surface table-card">
        <div class="section-head">
          <div>
            <div class="section-kicker">备份文件</div>
            <h3>最近 {{ latestBackups.length }} 个服务端备份</h3>
          </div>
        </div>

        <div class="table-wrap">
          <table class="backup-table">
            <thead>
              <tr>
                <th>文件名</th>
                <th>类型</th>
                <th>保存路径</th>
                <th>文件大小</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="5" class="empty-cell">正在加载备份状态...</td>
              </tr>
              <tr v-else-if="!latestBackups.length">
                <td colspan="5" class="empty-cell">当前保存位置下暂无完整备份文件。</td>
              </tr>
              <tr v-for="backup in latestBackups" :key="backup.path">
                <td>
                  <div class="table-title">{{ backup.filename }}</div>
                </td>
                <td>
                  <span :class="['backup-type', backup.filename.includes('_auto') ? 'auto' : 'manual']">
                    {{ backup.filename.includes('_auto') ? '自动覆盖' : '手动导出' }}
                  </span>
                </td>
                <td>{{ backup.path }}</td>
                <td>{{ formatSize(backup.size) }}</td>
                <td>{{ formatDate(backup.updated_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import axios from 'axios'
import { onMounted, reactive, ref } from 'vue'

const currentUserId = localStorage.getItem('user_id') || ''
const currentRole = localStorage.getItem('user_role') || ''
const hasPermission = currentRole === 'root'

const loading = ref(false)
const savingConfig = ref(false)
const exporting = ref(false)
const importing = ref(false)
const backupFileInputRef = ref(null)
const frequencyOptions = ref([])
const latestBackups = ref([])
const message = reactive({
  text: '',
  type: 'info'
})

const config = reactive({
  destination_path: '',
  frequency: 'off',
  next_run_at: '',
  last_auto_export_at: '',
  last_backup_path: '',
  last_backup_size: null,
  last_status: 'idle',
  last_error: ''
})

const form = reactive({
  destination_path: '',
  frequency: 'off'
})

const setMessage = (text, type = 'info') => {
  message.text = text
  message.type = type
}

const syncConfig = (nextConfig = {}) => {
  Object.assign(config, {
    destination_path: nextConfig.destination_path || '',
    frequency: nextConfig.frequency || 'off',
    next_run_at: nextConfig.next_run_at || '',
    last_auto_export_at: nextConfig.last_auto_export_at || '',
    last_backup_path: nextConfig.last_backup_path || '',
    last_backup_size: nextConfig.last_backup_size ?? null,
    last_status: nextConfig.last_status || 'idle',
    last_error: nextConfig.last_error || ''
  })
  form.destination_path = config.destination_path
  form.frequency = config.frequency
}

const frequencyLabel = (value) => {
  return frequencyOptions.value.find((item) => item.value === value)?.label || '关闭自动备份'
}

const formatDate = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatSize = (value) => {
  const size = Number(value || 0)
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`
}

const fetchBackups = async () => {
  if (!hasPermission) return
  try {
    loading.value = true
    const response = await axios.get('/api/management/backups', {
      params: {
        user_id: currentUserId,
        _ts: Date.now()
      }
    })
    syncConfig(response.data?.config || {})
    frequencyOptions.value = response.data?.frequency_options || []
    latestBackups.value = response.data?.latest_backups || []
  } catch (error) {
    setMessage(error?.response?.data?.error || '备份状态加载失败。', 'error')
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  if (!form.destination_path) {
    setMessage('请填写备份保存位置。', 'error')
    return
  }

  try {
    savingConfig.value = true
    setMessage('')
    const response = await axios.put('/api/management/backups/config', {
      user_id: currentUserId,
      destination_path: form.destination_path,
      frequency: form.frequency
    })
    syncConfig(response.data?.config || {})
    latestBackups.value = response.data?.latest_backups || []
    setMessage(response.data?.message || '备份设置已保存。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || '备份设置保存失败。', 'error')
  } finally {
    savingConfig.value = false
  }
}

const getDownloadFileName = (disposition) => {
  const value = String(disposition || '')
  const matched = value.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i)
  const filename = decodeURIComponent(matched?.[1] || matched?.[2] || '')
  return filename || `ywddzx_full_backup_${new Date().toISOString().slice(0, 10)}.zip`
}

const readBlobError = async (error, fallback) => {
  const data = error?.response?.data
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      const payload = JSON.parse(text)
      return payload.error || fallback
    } catch {
      return fallback
    }
  }
  return error?.response?.data?.error || fallback
}

const triggerImport = () => {
  if (importing.value || exporting.value) return
  backupFileInputRef.value?.click()
}

const exportBackup = async () => {
  try {
    exporting.value = true
    setMessage('正在生成完整备份，数据和文件较多时需要等待一会儿。', 'info')
    const response = await axios.post(
      '/api/management/backups/export',
      { user_id: currentUserId },
      { responseType: 'blob' }
    )
    const blobUrl = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = getDownloadFileName(response.headers['content-disposition'])
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(blobUrl)
    setMessage('完整备份已生成并开始下载，服务端也已保存在当前备份目录。', 'success')
    await fetchBackups()
  } catch (error) {
    setMessage(await readBlobError(error, '完整备份导出失败。'), 'error')
  } finally {
    exporting.value = false
  }
}

const importBackup = async (event) => {
  const input = event.target
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  if (!file.name.toLowerCase().endsWith('.zip')) {
    setMessage('只能导入 ZIP 格式的完整备份文件。', 'error')
    return
  }

  const confirmed = window.confirm('导入完整备份会覆盖当前 PostgreSQL 数据库和 storage 上传文件目录。建议确认已经导出当前备份后再继续，确定导入吗？')
  if (!confirmed) return

  try {
    importing.value = true
    setMessage('正在导入并恢复完整备份，请不要关闭页面。', 'info')
    const formData = new FormData()
    formData.append('user_id', currentUserId)
    formData.append('file', file)
    const response = await axios.post('/api/management/backups/import', formData)
    setMessage(response.data?.message || '完整备份导入完成。', 'success')
    await fetchBackups()
  } catch (error) {
    setMessage(error?.response?.data?.error || '完整备份导入失败。', 'error')
  } finally {
    importing.value = false
  }
}

onMounted(fetchBackups)
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.card-surface {
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 24px;
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.07);
}

.page-header {
  padding: 28px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 22px;
}

.backup-hero {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at 86% 18%, rgba(20, 184, 166, 0.24), transparent 30%),
    linear-gradient(135deg, #f8fafc 0%, #ecfeff 46%, #ffffff 100%);
}

.backup-hero::before {
  content: "";
  position: absolute;
  inset: auto -70px -120px auto;
  width: 280px;
  height: 280px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.1);
}

.hero-content,
.action-panel {
  position: relative;
  z-index: 1;
}

.hero-content {
  max-width: 720px;
}

.page-kicker,
.section-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 900;
  margin-bottom: 12px;
}

.page-header h2,
.section-head h3 {
  margin: 0;
  color: #0f172a;
}

.page-header h2 {
  font-size: 36px;
  letter-spacing: -0.04em;
}

.page-desc,
.section-head p,
.warning-card p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.hero-meta {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-meta span {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.28);
  color: #0f766e;
  font-size: 12px;
  font-weight: 900;
  overflow-wrap: anywhere;
}

.header-actions,
.form-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.action-panel {
  width: min(360px, 100%);
  padding: 14px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.26);
  box-shadow: 0 18px 30px rgba(15, 23, 42, 0.08);
}

.action-panel .btn {
  flex: 1 1 150px;
}

.hidden-file-input {
  display: none;
}

.btn {
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #d7e0ea;
  border-radius: 13px;
  padding: 0 15px;
  background: #ffffff;
  color: #334155;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.1);
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.btn-primary {
  background: linear-gradient(135deg, #0f766e 0%, #0d9488 100%);
  border-color: transparent;
  color: #ffffff;
}

.btn-secondary {
  background: #ffffff;
  color: #334155;
}

.btn-import {
  background: #fff7ed;
  border-color: #fed7aa;
  color: #9a3412;
}

.main-action {
  flex-basis: 100%;
}

.message-card {
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 800;
}

.message-card.success {
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #bbf7d0;
}

.message-card.error {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
}

.message-card.info {
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
}

.backup-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(380px, 0.8fr);
  gap: 20px;
}

.config-card,
.status-card,
.table-card,
.warning-card,
.permission-card {
  padding: 20px;
}

.config-card {
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(240, 253, 250, 0.9) 100%);
}

.status-card {
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.96) 100%);
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.config-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 14px;
  align-items: end;
}

.span-2 {
  grid-column: span 2;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-field span {
  color: #334155;
  font-size: 13px;
  font-weight: 900;
}

.form-field input,
.form-field select {
  width: 100%;
  height: 42px;
  border: 1px solid #d7e0ea;
  border-radius: 12px;
  padding: 0 12px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
}

.form-field small {
  color: #64748b;
  font-size: 12px;
}

.auto-note {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(240, 253, 250, 0.9);
  border: 1px dashed #5eead4;
  color: #0f766e;
  font-size: 13px;
  line-height: 1.7;
}

.status-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.status-item {
  min-height: 86px;
  padding: 13px 14px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
}

.status-item span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 6px;
}

.status-item strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.status-item:nth-child(4) {
  grid-column: span 2;
}

.status-item.error {
  background: #fef2f2;
  border-color: #fecaca;
}

.status-item.error strong {
  color: #b91c1c;
}

.warning-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  border-color: #fed7aa;
  background: linear-gradient(135deg, #fff7ed 0%, #ffffff 100%);
}

.warning-mark {
  width: 36px;
  height: 36px;
  border-radius: 14px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #fed7aa;
  color: #9a3412;
  font-weight: 900;
}

.warning-title {
  color: #9a3412;
  font-size: 16px;
  font-weight: 900;
}

.table-wrap {
  overflow-x: auto;
}

.backup-table {
  min-width: 1100px;
  width: 100%;
  border-collapse: collapse;
}

.backup-table th,
.backup-table td {
  padding: 13px 12px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  white-space: nowrap;
  vertical-align: middle;
  color: #0f172a;
  font-size: 13px;
}

.backup-table th {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.backup-type {
  display: inline-flex;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 900;
}

.backup-type.auto {
  background: #ecfeff;
  color: #0f766e;
}

.backup-type.manual {
  background: #eff6ff;
  color: #1d4ed8;
}

.table-title {
  font-size: 14px;
  font-weight: 900;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 22px 12px;
}

.permission-card {
  text-align: center;
}

.permission-icon {
  width: 44px;
  height: 44px;
  border-radius: 16px;
  margin: 0 auto 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fee2e2;
  color: #b91c1c;
  font-weight: 900;
}

.permission-title {
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
}

.permission-desc {
  margin-top: 8px;
  color: #64748b;
}

@media (max-width: 1180px) {
  .page-header {
    flex-direction: column;
  }

  .action-panel {
    width: 100%;
  }

  .backup-grid {
    grid-template-columns: 1fr;
  }

  .config-form {
    grid-template-columns: 1fr;
  }

  .span-2 {
    grid-column: span 1;
  }

  .status-list {
    grid-template-columns: 1fr;
  }

  .status-item:nth-child(4) {
    grid-column: span 1;
  }
}
</style>
