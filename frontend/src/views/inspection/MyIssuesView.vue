<template>
  <div class="page-shell my-issues-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>{{ currentRole === 'station_manager' ? '我的待整改问题' : '我的待复核问题' }}</h2>
      </div>
    </div>

    <div class="toolbar-card card-surface">
      <div class="toolbar-grid">
        <div class="toolbar-item">
          <label>当前账号类型</label>
          <input :value="currentRole === 'station_manager' ? '站点账号' : '督导组账号'" type="text" readonly />
        </div>

        <div class="toolbar-item">
          <label>问题状态</label>
          <select v-model="filters.status">
            <option value="">全部</option>
            <option value="待整改">待整改</option>
            <option value="待复核">待复核</option>
            <option value="已闭环">已闭环</option>
          </select>
        </div>

        <div class="toolbar-item">
          <label>站点名称</label>
          <input v-model="filters.station" type="text" placeholder="搜索站点名称" />
        </div>

        <div class="toolbar-item">
          <label>巡检大类</label>
          <input v-model="filters.categoryName" type="text" placeholder="搜索巡检大类" />
        </div>
        <div class="toolbar-item">
          <label>问题编号</label>
          <input v-model="filters.code" type="text" placeholder="搜索问题编号" />
        </div>
      </div>

      <div class="toolbar-actions">
        <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
        <button class="btn btn-secondary" type="button" @click="fetchMyIssues" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
      </div>
    </div>

    <div class="summary-grid">
      <div class="summary-card summary-card-primary card-surface">
        <div class="summary-label">当前待办</div>
        <div class="summary-value">{{ filteredData.length }}</div>
        <div class="summary-desc">{{ currentRole === 'station_manager' ? '待整改问题' : '待复核问题' }}</div>
      </div>

      <div class="summary-card card-surface">
        <div class="summary-label">当前视角</div>
        <div class="summary-value summary-value-small">
          {{ currentRole === 'station_manager' ? '站点账号' : '督导组账号' }}
        </div>
        <div class="summary-desc">
          {{ currentRole === 'station_manager' ? '可填写整改结果与整改说明' : '可提交督导组复核结果与复核说明' }}
        </div>
      </div>
    </div>

    <div class="mobile-issue-list">
      <div v-if="loading" class="mobile-empty card-surface">正在加载数据...</div>

      <div v-else-if="paginatedData.length === 0" class="mobile-empty card-surface">
        {{ currentRole === 'station_manager' ? '当前没有待整改问题。' : '当前没有待复核问题。' }}
      </div>

      <div v-else class="mobile-issue-cards">
        <div v-for="item in paginatedData" :key="item.id" class="mobile-issue-card card-surface">
          <div class="mobile-card-head">
            <div class="mobile-card-title-row">
              <span class="mobile-card-category">{{ item.category_name || '暂无' }}</span>
              <span :class="statusClass(item.status)">{{ item.status }}</span>
            </div>
            <div class="mobile-card-code">问题编号：{{ item.code }}</div>
          </div>

          <div class="mobile-card-body">
            <div class="mobile-card-row"><span>站点</span><strong>{{ item.station }}</strong></div>
            <div class="mobile-card-row"><span>业务流程</span><strong>{{ item.business_process }}</strong></div>
            <div class="mobile-card-row"><span>检查项目</span><strong>{{ item.check_item }}</strong></div>
            <div class="mobile-card-row mobile-card-row-top">
              <span>问题描述</span>
              <div class="mobile-card-text">{{ item.description }}</div>
            </div>
            <div class="mobile-card-row mobile-card-row-top">
              <span>整改说明</span>
              <div class="mobile-card-text">{{ item.rectification_note || '暂无' }}</div>
            </div>
            <div class="mobile-card-row mobile-card-row-top">
              <span>复核说明</span>
              <div class="mobile-card-text">{{ item.review_note || '暂无' }}</div>
            </div>
          </div>

          <div class="mobile-card-images">
            <button class="mobile-image-btn" type="button" @click="preview(resolveImage(item.issue_photo), '问题照片')">
              <img :src="resolveImage(item.issue_photo)" class="mobile-thumb" alt="问题照片" />
              <span>问题照片</span>
            </button>

            <button
              v-if="item.rectification_photo"
              class="mobile-image-btn"
              type="button"
              @click="preview(resolveImage(item.rectification_photo), '站点反馈整改照片')"
            >
              <img :src="resolveImage(item.rectification_photo)" class="mobile-thumb" alt="整改照片" />
              <span>整改照片</span>
            </button>
          </div>

          <div class="mobile-card-actions">
            <button class="btn btn-primary" type="button" @click="openActionDrawer(item)">
              {{ currentRole === 'station_manager' ? '提交整改' : '提交复核' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="table-card card-surface">
      <div class="table-scroll-wrap">
        <div class="table-scroll">
          <table class="issues-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>站点</th>
                <th>巡检大类</th>
                <th>问题编号</th>
                <th>业务流程</th>
                <th>检查项目</th>
                <th>问题描述</th>
                <th>问题照片</th>
                <th>站经理整改结果</th>
                <th>站点反馈整改说明</th>
                <th>站点反馈整改照片</th>
                <th>督导组复核结果</th>
                <th>督导组复核说明</th>
                <th class="nowrap-col">问题状态</th>
                <th class="nowrap-col action-col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in paginatedData" :key="item.id">
                <td>{{ item.id }}</td>
                <td>{{ item.station }}</td>
                <td>{{ item.category_name || '暂无' }}</td>
                <td>{{ item.code }}</td>
                <td>{{ item.business_process }}</td>
                <td>{{ item.check_item }}</td>
                <td class="long-text">{{ item.description }}</td>
                <td>
                  <button class="image-btn" type="button" @click="preview(resolveImage(item.issue_photo), '问题照片')">
                    <img :src="resolveImage(item.issue_photo)" class="thumb" alt="问题照片" />
                  </button>
                </td>
                <td>{{ item.rectification_result || '暂无' }}</td>
                <td class="long-text">{{ item.rectification_note || '暂无' }}</td>
                <td>
                  <button
                    v-if="item.rectification_photo"
                    class="image-btn"
                    type="button"
                    @click="preview(resolveImage(item.rectification_photo), '站点反馈整改照片')"
                  >
                    <img :src="resolveImage(item.rectification_photo)" class="thumb" alt="站点反馈整改照片" />
                  </button>
                  <span v-else>暂无</span>
                </td>
                <td>{{ item.review_result || '暂无' }}</td>
                <td class="long-text">{{ item.review_note || '暂无' }}</td>
                <td class="nowrap-col">
                  <span :class="statusClass(item.status)">{{ item.status }}</span>
                </td>
                <td class="nowrap-col action-col">
                  <button class="btn btn-primary btn-sm" type="button" @click="openActionDrawer(item)">
                    {{ currentRole === 'station_manager' ? '提交整改' : '提交复核' }}
                  </button>
                </td>
              </tr>
              <tr v-if="!loading && paginatedData.length === 0">
                <td colspan="15" class="empty-row">
                  {{ currentRole === 'station_manager' ? '当前没有待整改问题。' : '当前没有待复核问题。' }}
                </td>
              </tr>
              <tr v-if="loading">
                <td colspan="15" class="empty-row">正在加载数据...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="pagination-bar">
        <div class="pagination-summary">共 {{ filteredData.length }} 条</div>
        <div class="pagination-controls">
          <label>每页显示</label>
          <select v-model.number="pageSize">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
          <button class="btn btn-secondary" :disabled="page <= 1" @click="prevPage">上一页</button>
          <span>{{ page }} / {{ totalPage }}</span>
          <button class="btn btn-secondary" :disabled="page >= totalPage" @click="nextPage">下一页</button>
        </div>
      </div>
    </div>

    <div v-if="actionDrawer.visible" class="drawer-mask" @click.self="closeActionDrawer">
      <div class="drawer-panel">
        <div class="drawer-header">
          <div>
            <h3>{{ currentRole === 'station_manager' ? '提交整改' : '提交督导组复核' }}</h3>
            <p>{{ actionDrawer.item?.station }}｜问题编号 {{ actionDrawer.item?.code }}</p>
          </div>
          <button class="drawer-close" type="button" @click="closeActionDrawer">×</button>
        </div>

        <div class="drawer-content" v-if="actionDrawer.item">
          <div class="drawer-info-card">
            <div><strong>问题描述：</strong>{{ actionDrawer.item.description }}</div>
            <div><strong>当前状态：</strong>{{ actionDrawer.item.status }}</div>
          </div>

          <template v-if="currentRole === 'station_manager'">
            <div class="form-item">
              <label>整改结果</label>
              <select v-model="actionForm.rectificationResult">
                <option value="">请选择</option>
                <option value="未整改">未整改</option>
                <option value="已整改">已整改</option>
                <option value="站级无法完成整改">站级无法完成整改</option>
              </select>
            </div>

            <div class="form-item">
              <label>整改说明</label>
              <textarea v-model="actionForm.rectificationNote" rows="4" placeholder="请填写整改说明"></textarea>
            </div>

            <div class="form-item">
              <label>整改照片</label>
              <div class="drawer-upload-card">
                <input
                  id="rectification-photo-upload"
                  class="drawer-upload-input"
                  type="file"
                  accept="image/*"
                  @change="handleRectificationFileChange"
                />

                <label for="rectification-photo-upload" class="drawer-upload-dropzone">
                  <div class="drawer-upload-icon">↑</div>
                  <div class="drawer-upload-title">选择或更换整改照片</div>
                  <div class="drawer-upload-desc">
                    请上传能够清晰反映整改完成情况的现场照片，建议画面完整、重点明确。
                  </div>
                  <div class="drawer-upload-trigger">选择文件</div>
                </label>

                <div v-if="actionForm.rectificationPhotoPreview" class="drawer-image-preview-panel">
                  <img :src="actionForm.rectificationPhotoPreview" alt="整改照片预览" class="drawer-preview-thumb" />
                  <div class="drawer-preview-meta">
                    <div class="drawer-preview-title">已选择整改照片</div>
                    <div class="drawer-preview-name">{{ actionForm.rectificationPhotoFile?.name || '已上传图片' }}</div>
                    <div class="drawer-preview-actions">
                      <label for="rectification-photo-upload" class="btn btn-light btn-sm drawer-preview-btn">重新选择</label>
                      <button class="btn btn-secondary btn-sm drawer-preview-btn" type="button" @click="clearRectificationFile">移除图片</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
          </template>

          <template v-else>
            <div class="form-item">
              <label>督导组复核结果</label>
              <select v-model="actionForm.reviewResult">
                <option value="">请选择</option>
                <option value="未整改">未整改</option>
                <option value="已整改">已整改</option>
                <option value="站级无法完成整改">站级无法完成整改</option>
              </select>
            </div>

            <div class="form-item">
              <label>督导组复核说明</label>
              <textarea v-model="actionForm.reviewNote" rows="4" placeholder="可填写复核说明"></textarea>
            </div>
          </template>

          <div class="drawer-actions">
            <button class="btn btn-primary" type="button" @click="submitAction" :disabled="submittingAction">
              {{ submittingAction ? '提交中...' : (currentRole === 'station_manager' ? '确认提交整改' : '确认提交复核') }}
            </button>
            <button class="btn btn-secondary" type="button" @click="closeActionDrawer" :disabled="submittingAction">取消</button>
          </div>

          <div v-if="actionMessage" class="action-message">{{ actionMessage }}</div>
        </div>
      </div>
    </div>

    <div v-if="previewState.visible" class="image-modal" @click.self="closePreview">
      <div class="image-modal-content">
        <div class="image-modal-header">
          <span>{{ previewState.title }}</span>
          <button class="close-btn" type="button" @click="closePreview">×</button>
        </div>
        <img :src="previewState.url" class="image-modal-full" :alt="previewState.title" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import axios from 'axios'

const currentRole = ref(localStorage.getItem('user_role') || '')
const loading = ref(false)
const submittingAction = ref(false)
const issues = ref([])

const filters = ref({
  status: '',
  station: '',
  code: '',
  categoryName: ''
})

const filteredData = computed(() => {
  return issues.value.filter((item) => {
    const matchedStatus = !filters.value.status || item.status === filters.value.status
    const matchedStation = !filters.value.station || item.station.toLowerCase().includes(filters.value.station.trim().toLowerCase())
    const matchedCode = !filters.value.code || String(item.code).toLowerCase().includes(filters.value.code.trim().toLowerCase())
    const matchedCategoryName = !filters.value.categoryName || String(item.category_name || '').toLowerCase().includes(filters.value.categoryName.trim().toLowerCase())
    return matchedStatus && matchedStation && matchedCode && matchedCategoryName
  })
})

const page = ref(1)
const pageSize = ref(20)

const totalPage = computed(() => Math.max(1, Math.ceil(filteredData.value.length / pageSize.value)))

const paginatedData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredData.value.slice(start, start + pageSize.value)
})

watch([filters, pageSize], () => {
  page.value = 1
}, { deep: true })

watch(totalPage, (value) => {
  if (page.value > value) {
    page.value = value
  }
})

const resetFilters = () => {
  filters.value = {
    status: '',
    station: '',
    code: '',
    categoryName: ''
  }
}

const prevPage = () => {
  if (page.value > 1) page.value -= 1
}

const nextPage = () => {
  if (page.value < totalPage.value) page.value += 1
}

const previewState = ref({
  visible: false,
  url: '',
  title: ''
})

const preview = (url, title) => {
  previewState.value = {
    visible: true,
    url,
    title
  }
}

const closePreview = () => {
  previewState.value = {
    visible: false,
    url: '',
    title: ''
  }
}

const actionDrawer = ref({
  visible: false,
  item: null
})

const actionForm = ref({
  rectificationResult: '',
  rectificationNote: '',
  rectificationPhotoFile: null,
  rectificationPhotoPreview: '',
  reviewResult: '',
  reviewNote: ''
})

const actionMessage = ref('')

const resolveImage = (path) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  const normalizedPath = String(path).startsWith('/') ? path.slice(1) : path
  return `/storage/${normalizedPath}`
}

const fetchMyIssues = async () => {
  const userId = localStorage.getItem('user_id') || ''
  if (!userId) {
    actionMessage.value = '当前登录信息缺失，请重新登录。'
    return
  }

  try {
    loading.value = true
    const response = await axios.get('/api/my-issues', {
      params: { user_id: userId }
    })
    issues.value = response.data || []
  } catch (error) {
    actionMessage.value = error?.response?.data?.error || '获取待办问题失败。'
  } finally {
    loading.value = false
  }
}

const openActionDrawer = (item) => {
  actionDrawer.value = {
    visible: true,
    item
  }
  actionMessage.value = ''
  actionForm.value = {
    rectificationResult: item.rectification_result || '',
    rectificationNote: item.rectification_note || '',
    rectificationPhotoFile: null,
    rectificationPhotoPreview: item.rectification_photo ? resolveImage(item.rectification_photo) : '',
    reviewResult: item.review_result || '',
    reviewNote: item.review_note || ''
  }
}

const closeActionDrawer = () => {
  actionDrawer.value = {
    visible: false,
    item: null
  }
  actionMessage.value = ''
}

const handleRectificationFileChange = (event) => {
  const file = event.target.files?.[0]
  actionForm.value.rectificationPhotoFile = file || null
  if (!file) {
    actionForm.value.rectificationPhotoPreview = ''
    return
  }
  actionForm.value.rectificationPhotoPreview = URL.createObjectURL(file)
}

const clearRectificationFile = () => {
  actionForm.value.rectificationPhotoFile = null
  actionForm.value.rectificationPhotoPreview = ''
}

const submitAction = async () => {
  if (!actionDrawer.value.item) return

  const userId = localStorage.getItem('user_id') || ''
  if (!userId) {
    actionMessage.value = '当前登录信息缺失，请重新登录。'
    return
  }

  try {
    submittingAction.value = true
    actionMessage.value = ''

    if (currentRole.value === 'station_manager') {
      if (!actionForm.value.rectificationResult) {
        actionMessage.value = '请选择整改结果。'
        return
      }
      if (!actionForm.value.rectificationNote.trim()) {
        actionMessage.value = '请填写整改说明。'
        return
      }

      const formData = new FormData()
      formData.append('user_id', userId)
      formData.append('rectification_result', actionForm.value.rectificationResult)
      formData.append('rectification_note', actionForm.value.rectificationNote)
      if (actionForm.value.rectificationPhotoFile) {
        formData.append('rectification_photo', actionForm.value.rectificationPhotoFile)
      }

      const response = await axios.post(
        `/api/issues/${actionDrawer.value.item.id}/rectification`,
        formData
      )
      actionMessage.value = response.data.message || '整改提交成功。'
      await fetchMyIssues()
      closeActionDrawer()
      return
    }

    if (!actionForm.value.reviewResult) {
      actionMessage.value = '请选择督导组复核结果。'
      return
    }

    const formData = new FormData()
    formData.append('user_id', userId)
    formData.append('review_result', actionForm.value.reviewResult)
    formData.append('review_note', actionForm.value.reviewNote)

    const response = await axios.post(
      `/api/issues/${actionDrawer.value.item.id}/review`,
      formData
    )
    actionMessage.value = response.data.message || '复核提交成功。'
    await fetchMyIssues()
    closeActionDrawer()
  } catch (error) {
    actionMessage.value = error?.response?.data?.error || '提交失败，请稍后重试。'
  } finally {
    submittingAction.value = false
  }
}

const statusClass = (status) => {
  if (status === '待整改') return 'status-tag danger'
  if (status === '待复核') return 'status-tag warning'
  if (status === '已闭环') return 'status-tag success'
  return 'status-tag'
}

onMounted(() => {
  fetchMyIssues()
})
</script>

<style scoped>
/* --- Consistent page shell and card styles --- */
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


.toolbar-card,
.table-card {
  padding: 20px;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(220px, 1fr));
  gap: 16px;
}

.toolbar-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toolbar-item label,
.form-item label {
  font-size: 14px;
  font-weight: 700;
  color: #374151;
}

.toolbar-item input,
.toolbar-item select,
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

.toolbar-item input,
.toolbar-item select,
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

.toolbar-actions,
.drawer-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(240px, 1fr));
  gap: 16px;
}

.summary-card {
  padding: 20px;
}

.summary-card-danger {
  border-color: #fecaca;
  background: linear-gradient(180deg, #fff7f7 0%, #fff 100%);
}

.summary-label {
  color: #6b7280;
  font-size: 14px;
  margin-bottom: 10px;
}

.summary-value {
  font-size: 34px;
  font-weight: 800;
  color: #111827;
  line-height: 1;
  margin-bottom: 8px;
}

.summary-value-small {
  font-size: 24px;
}

.summary-desc {
  color: #6b7280;
  font-size: 14px;
  line-height: 1.6;
}

.mobile-issue-list {
  display: none;
}

.mobile-issue-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-issue-card {
  padding: 16px;
}

.mobile-card-head {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}

.mobile-card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mobile-card-category {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
}

.mobile-card-code {
  font-size: 13px;
  color: #64748b;
}

.mobile-card-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mobile-card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mobile-card-row span {
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
}

.mobile-card-row strong {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  text-align: right;
}

.mobile-card-row-top {
  align-items: flex-start;
}

.mobile-card-text {
  flex: 1;
  font-size: 14px;
  line-height: 1.7;
  color: #334155;
  text-align: right;
}

.mobile-card-images {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.mobile-image-btn {
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  background: #fff;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
}

.mobile-image-btn span {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
}

.mobile-thumb {
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
}

.mobile-card-actions {
  margin-top: 14px;
}

.mobile-empty {
  padding: 28px 16px;
  text-align: center;
  color: #64748b;
  font-size: 14px;
}

.table-scroll-wrap {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  overflow: hidden;
}

.table-scroll {
  max-height: 60vh;
  overflow: auto;
}

.issues-table {
  width: 100%;
  min-width: 2360px;
  border-collapse: collapse;
}

.issues-table th,
.issues-table td {
  border: 1px solid #e5e7eb;
  padding: 12px 14px;
  text-align: left;
  vertical-align: top;
  font-size: 14px;
  color: #111827;
}

.issues-table th {
  background: #f8fafc;
  font-weight: 700;
  white-space: nowrap;
}

.nowrap-col {
  white-space: nowrap;
}

.action-col {
  min-width: 110px;
}

.long-text {
  min-width: 240px;
  white-space: normal;
  line-height: 1.7;
}

.thumb {
  width: 88px;
  height: 66px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
}

.image-btn {
  border: none;
  padding: 0;
  background: transparent;
  cursor: zoom-in;
}

.pagination-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.pagination-summary {
  color: #475569;
  font-size: 14px;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.pagination-controls select {
  height: 40px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0 10px;
}

.btn {
  height: 40px;
  padding: 0 16px;
  border-radius: 10px;
  border: 1px solid #d1d5db;
  background: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-sm {
  height: 34px;
  padding: 0 12px;
  font-size: 13px;
}

.btn-primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.btn-primary:hover {
  background: #1d4ed8;
}

.btn-secondary:hover:not(:disabled) {
  background: #f8fafc;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.empty-row {
  text-align: center;
  color: #6b7280;
  padding: 40px 0 !important;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.status-tag.danger {
  background: #fef2f2;
  color: #dc2626;
}

.status-tag.warning {
  background: #fff7ed;
  color: #d97706;
}

.status-tag.success {
  background: #f0fdf4;
  color: #16a34a;
}

.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  justify-content: flex-end;
  z-index: 1000;
}

.drawer-panel {
  width: min(520px, 100%);
  height: 100%;
  background: #fff;
  display: flex;
  flex-direction: column;
  box-shadow: -12px 0 30px rgba(15, 23, 42, 0.16);
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px;
  border-bottom: 1px solid #e5e7eb;
}

.drawer-header h3 {
  margin: 0 0 6px;
  font-size: 24px;
  color: #111827;
}

.drawer-header p {
  margin: 0;
  color: #6b7280;
  font-size: 14px;
}

.drawer-close,
.close-btn {
  border: none;
  background: transparent;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
}

.drawer-content {
  padding: 20px 22px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-info-card {
  padding: 14px 16px;
  background: #f8fafc;
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  color: #334155;
  line-height: 1.8;
}

.drawer-upload-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drawer-upload-input {
  display: none;
}

.drawer-upload-dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
  min-height: 156px;
  padding: 20px 18px;
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fbff 0%, #f8fafc 100%);
  cursor: pointer;
  transition: all 0.18s ease;
}

.drawer-upload-dropzone:hover {
  border-color: #93c5fd;
  background: linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%);
}

.drawer-upload-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 22px;
  font-weight: 800;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
}

.drawer-upload-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
}

.drawer-upload-desc {
  max-width: 420px;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.drawer-upload-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 96px;
  height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.drawer-image-preview-panel {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #fff;
  flex-wrap: wrap;
}

.drawer-preview-thumb {
  width: 136px;
  height: 102px;
  object-fit: cover;
  border-radius: 14px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  flex-shrink: 0;
}

.drawer-preview-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 200px;
  flex: 1;
}

.drawer-preview-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
}

.drawer-preview-name {
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
  word-break: break-all;
}

.drawer-preview-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.drawer-preview-btn {
  min-width: 96px;
  justify-content: center;
  text-decoration: none;
}

.action-message {
  font-size: 14px;
  color: #2563eb;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  padding: 12px 14px;
}

.image-modal {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
  padding: 24px;
}

.image-modal-content {
  width: min(1000px, 100%);
  background: #fff;
  border-radius: 18px;
  overflow: hidden;
}

.image-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 700;
}

.image-modal-full {
  display: block;
  width: 100%;
  max-height: 78vh;
  object-fit: contain;
  background: #f8fafc;
}

@media (max-width: 1200px) {
  .toolbar-grid {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
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

  .toolbar-card,
  .table-card,
  .summary-card {
    padding: 16px;
  }

  .toolbar-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .toolbar-item label,
  .form-item label {
    font-size: 13px;
  }

  .toolbar-item input,
  .toolbar-item select,
  .form-item input,
  .form-item select {
    height: 46px;
    font-size: 15px;
    padding: 0 12px;
  }

  .form-item textarea {
    min-height: 108px;
    padding: 12px;
    font-size: 15px;
  }

  .toolbar-actions,
  .drawer-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .summary-value {
    font-size: 30px;
  }

  .table-card {
    display: none;
  }

  .mobile-issue-list {
    display: block;
  }

  .drawer-panel {
    width: 100%;
    height: 100%;
    border-radius: 0;
  }

  .drawer-header {
    padding: 16px;
  }

  .drawer-header h3 {
    font-size: 20px;
  }

  .drawer-content {
    padding: 16px;
  }

  .drawer-image-preview-panel {
    align-items: flex-start;
  }

  .drawer-preview-thumb {
    width: 100%;
    max-width: 280px;
    height: auto;
    aspect-ratio: 4 / 3;
  }

  .drawer-preview-meta {
    min-width: 0;
    width: 100%;
  }

  .drawer-preview-actions {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
  }

  .drawer-preview-btn,
  .btn {
    width: 100%;
  }

  .image-modal {
    padding: 12px;
  }
}
</style>