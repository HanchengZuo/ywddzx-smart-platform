<template>
  <div class="page-shell issues-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>巡检问题列表</h2>
      </div>
    </div>

    <div class="mobile-issue-list">
      <div v-if="loading" class="mobile-empty card-surface">正在加载问题列表...</div>

      <div v-else-if="paginatedData.length === 0" class="mobile-empty card-surface">
        当前没有符合条件的问题记录。
      </div>

      <div v-else class="mobile-issue-cards">
        <div v-for="item in paginatedData" :key="item.id" class="mobile-issue-card card-surface">
          <div class="mobile-card-head">
            <div class="mobile-card-title-row">
              <span class="mobile-card-category">{{ item.category_name || '暂无' }}</span>
              <span :class="statusClass(item.status)">{{ item.status }}</span>
            </div>
            <div class="mobile-card-code">问题编号：{{ item.code }}</div>
            <div class="mobile-card-meta">{{ item.month }}｜{{ item.time }}</div>
          </div>

          <div class="mobile-card-body">
            <div class="mobile-card-row"><span>站点</span><strong>{{ item.station }}</strong></div>
            <div class="mobile-card-row"><span>所属地</span><strong>{{ item.region }}</strong></div>
            <div class="mobile-card-row"><span>站点负责人</span><strong>{{ item.station_manager }}</strong></div>
            <div class="mobile-card-row"><span>检查人员</span><strong>{{ item.inspector }}</strong></div>
            <div class="mobile-card-row"><span>业务流程</span><strong>{{ item.business_process }}</strong></div>
            <div class="mobile-card-row"><span>检查项目</span><strong>{{ item.check_item }}</strong></div>

            <div class="mobile-card-row mobile-card-row-top">
              <span>规范要求</span>
              <div class="mobile-card-text multiline-cell">{{ formatMultiline(item.requirement) }}</div>
            </div>
            <div class="mobile-card-row mobile-card-row-top">
              <span>检查方法</span>
              <div class="mobile-card-text multiline-cell">{{ formatMultiline(item.check_method) }}</div>
            </div>
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
              <img :src="resolveImage(item.rectification_photo)" class="mobile-thumb" alt="站点反馈整改照片" />
              <span>整改照片</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="filter-card card-surface">
      <div class="filter-grid">
        <div class="filter-item">
          <label>检查月度</label>
          <input v-model="filters.month" type="month" />
        </div>
        <div class="filter-item">
          <label>检查时间（按天）</label>
          <input v-model="filters.date" type="date" />
        </div>
        <div class="filter-item">
          <label>站点所属地</label>
          <input v-model="filters.region" placeholder="搜索站点所属地" />
        </div>
        <div class="filter-item">
          <label>站点名称</label>
          <input v-model="filters.station" placeholder="搜索站点名称" />
        </div>
        <div class="filter-item">
          <label>站点负责人</label>
          <input v-model="filters.stationManager" placeholder="搜索站点负责人" />
        </div>
        <div class="filter-item">
          <label>检查人员</label>
          <input v-model="filters.inspector" placeholder="搜索检查人员" />
        </div>
        <div class="filter-item">
          <label>巡检大类</label>
          <input v-model="filters.categoryName" placeholder="搜索巡检大类" />
        </div>
        <div class="filter-item">
          <label>问题编号</label>
          <input v-model="filters.code" placeholder="搜索问题编号" />
        </div>
        <div class="filter-item">
          <label>业务流程</label>
          <input v-model="filters.businessProcess" placeholder="搜索业务流程" />
        </div>
        <div class="filter-item">
          <label>检查项目</label>
          <input v-model="filters.checkItem" placeholder="搜索检查项目" />
        </div>
        <div class="filter-item">
          <label>站经理整改结果</label>
          <select v-model="filters.rectificationResult">
            <option value="">全部</option>
            <option value="未整改">未整改</option>
            <option value="已整改">已整改</option>
            <option value="站级无法完成整改">站级无法完成整改</option>
          </select>
        </div>
        <div class="filter-item">
          <label>督导组复核结果</label>
          <select v-model="filters.reviewResult">
            <option value="">全部</option>
            <option value="未整改">未整改</option>
            <option value="已整改">已整改</option>
            <option value="站级无法完成整改">站级无法完成整改</option>
          </select>
        </div>
        <div class="filter-item">
          <label>问题状态</label>
          <select v-model="filters.status">
            <option value="">全部</option>
            <option value="待整改">待整改</option>
            <option value="待复核">待复核</option>
            <option value="已闭环">已闭环</option>
          </select>
        </div>
      </div>

      <div class="filter-actions">
        <button class="btn btn-secondary" @click="resetFilters">重置筛选</button>
        <button class="btn btn-secondary" @click="fetchIssues" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
      </div>
    </div>

    <div class="table-card card-surface">
      <div class="table-scroll-wrap">
        <div class="table-scroll">
          <table class="issues-table">
            <thead>
              <tr>
                <th class="nowrap">检查月度</th>
                <th class="nowrap">检查时间</th>
                <th class="nowrap">站点所属地</th>
                <th class="nowrap">站点名称</th>
                <th class="nowrap">站点负责人</th>
                <th class="nowrap">站点负责人手机号</th>
                <th class="nowrap">检查人员</th>
                <th class="nowrap">检查人员手机号</th>
                <th class="nowrap">巡检大类</th>
                <th class="nowrap">问题编号</th>
                <th class="nowrap">业务流程</th>
                <th class="nowrap">检查项目</th>
                <th>规范要求</th>
                <th>检查方法</th>
                <th>问题描述</th>
                <th class="nowrap">问题照片</th>
                <th class="nowrap">站经理整改结果</th>
                <th class="nowrap">站点反馈整改说明</th>
                <th class="nowrap">站点反馈整改照片</th>
                <th class="nowrap">督导组复核结果</th>
                <th class="nowrap">督导组复核说明</th>
                <th class="nowrap-col status-col">问题状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in paginatedData" :key="item.id">
                <td class="nowrap">{{ item.month }}</td>
                <td class="nowrap">{{ item.time }}</td>
                <td class="nowrap">{{ item.region }}</td>
                <td class="nowrap">{{ item.station }}</td>
                <td class="nowrap">{{ item.station_manager }}</td>
                <td class="nowrap">{{ item.station_manager_phone }}</td>
                <td class="nowrap">{{ item.inspector }}</td>
                <td class="nowrap">{{ item.inspector_phone }}</td>
                <td class="nowrap">{{ item.category_name || '暂无' }}</td>
                <td class="nowrap">{{ item.code }}</td>
                <td class="nowrap">{{ item.business_process }}</td>
                <td class="nowrap">{{ item.check_item }}</td>
                <td class="long-text multiline-cell">{{ formatMultiline(item.requirement) }}</td>
                <td class="long-text multiline-cell">{{ formatMultiline(item.check_method) }}</td>
                <td class="long-text">{{ item.description }}</td>
                <td class="nowrap">
                  <button class="image-btn" type="button" @click="preview(resolveImage(item.issue_photo), '问题照片')">
                    <img :src="resolveImage(item.issue_photo)" class="thumb" alt="问题照片" />
                  </button>
                </td>
                <td class="nowrap">{{ item.rectification_result || '暂无' }}</td>
                <td class="nowrap">{{ item.rectification_note || '暂无' }}</td>
                <td class="nowrap">
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
                <td class="nowrap">{{ item.review_result || '暂无' }}</td>
                <td class="nowrap">{{ item.review_note || '暂无' }}</td>
                <td class="nowrap-col status-col">
                  <span :class="statusClass(item.status)">{{ item.status }}</span>
                </td>
              </tr>
              <tr v-if="!loading && paginatedData.length === 0">
                <td colspan="22" class="empty-row">当前没有符合条件的问题记录。</td>
                <td colspan="22" class="empty-row">正在加载问题列表...</td>
              </tr>
              <tr v-if="loading">
                <td colspan="21" class="empty-row">正在加载问题列表...</td>
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

const filters = ref({
  month: '',
  date: '',
  region: '',
  station: '',
  stationManager: '',
  inspector: '',
  code: '',
  businessProcess: '',
  categoryName: '',
  checkItem: '',
  rectificationResult: '',
  reviewResult: '',
  status: ''
})

const list = ref([])
const loading = ref(false)

const page = ref(1)
const pageSize = ref(20)

const normalizedKeyword = (value) => String(value || '').toLowerCase()
const formatMultiline = (value) => String(value || '').replace(/\\n/g, '\n')

const filteredData = computed(() => {
  return list.value.filter((item) => {
    const matchedMonth = !filters.value.month || item.month === filters.value.month
    const matchedDate = !filters.value.date || String(item.time || '').startsWith(filters.value.date)
    const matchedRegion = !filters.value.region || normalizedKeyword(item.region).includes(normalizedKeyword(filters.value.region))
    const matchedStation = !filters.value.station || normalizedKeyword(item.station).includes(normalizedKeyword(filters.value.station))
    const matchedStationManager = !filters.value.stationManager || normalizedKeyword(item.station_manager).includes(normalizedKeyword(filters.value.stationManager))
    const matchedInspector = !filters.value.inspector || normalizedKeyword(item.inspector).includes(normalizedKeyword(filters.value.inspector))
    const matchedCode = !filters.value.code || normalizedKeyword(item.code).includes(normalizedKeyword(filters.value.code))
    const matchedBusinessProcess = !filters.value.businessProcess || normalizedKeyword(item.business_process).includes(normalizedKeyword(filters.value.businessProcess))
    const matchedCategoryName = !filters.value.categoryName || normalizedKeyword(item.category_name).includes(normalizedKeyword(filters.value.categoryName))
    const matchedCheckItem = !filters.value.checkItem || normalizedKeyword(item.check_item).includes(normalizedKeyword(filters.value.checkItem))
    const matchedRectificationResult = !filters.value.rectificationResult || item.rectification_result === filters.value.rectificationResult
    const matchedReviewResult = !filters.value.reviewResult || item.review_result === filters.value.reviewResult
    const matchedStatus = !filters.value.status || item.status === filters.value.status

    return (
      matchedMonth &&
      matchedDate &&
      matchedRegion &&
      matchedStation &&
      matchedStationManager &&
      matchedInspector &&
      matchedCode &&
      matchedBusinessProcess &&
      matchedCategoryName &&
      matchedCheckItem &&
      matchedRectificationResult &&
      matchedReviewResult &&
      matchedStatus
    )
  })
})

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

const fetchIssues = async () => {
  try {
    loading.value = true
    const response = await axios.get('/api/issues')
    list.value = response.data || []
  } catch (error) {
    list.value = []
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.value = {
    month: '',
    date: '',
    region: '',
    station: '',
    stationManager: '',
    inspector: '',
    code: '',
    businessProcess: '',
    categoryName: '',
    checkItem: '',
    rectificationResult: '',
    reviewResult: '',
    status: ''
  }
}

const nextPage = () => {
  if (page.value < totalPage.value) {
    page.value += 1
  }
}

const prevPage = () => {
  if (page.value > 1) {
    page.value -= 1
  }
}

const previewState = ref({
  visible: false,
  url: '',
  title: ''
})

const resolveImage = (path) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  const normalizedPath = String(path).startsWith('/') ? path.slice(1) : path
  return `/storage/${normalizedPath}`
}

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

const statusClass = (status) => {
  if (status === '待整改') return 'status-tag danger'
  if (status === '待复核') return 'status-tag warning'
  if (status === '已闭环') return 'status-tag success'
  return 'status-tag'
}

onMounted(() => {
  fetchIssues()
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


.filter-card,
.table-card {
  padding: 20px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(220px, 1fr));
  gap: 16px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-item label {
  font-size: 14px;
  font-weight: 700;
  color: #374151;
}

.filter-item input,
.filter-item select {
  height: 42px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 14px;
}

.filter-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
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
    color: #334155;
    font-weight: 700;
  }

  .mobile-card-meta {
    font-size: 12px;
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

  .mobile-empty {
    padding: 28px 16px;
    text-align: center;
    color: #64748b;
    font-size: 14px;
  }

.btn-secondary:hover {
  background: #f9fafb;
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
  min-width: 2940px;
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

.status-col {
  min-width: 110px;
}

.nowrap {
  white-space: nowrap;
}

.long-text {
  min-width: 260px;
  white-space: normal;
  line-height: 1.7;
}
.multiline-cell {
  white-space: pre-line;
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

.image-modal {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
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

.close-btn {
  border: none;
  background: transparent;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
}

.image-modal-full {
  display: block;
  width: 100%;
  max-height: 78vh;
  object-fit: contain;
  background: #f8fafc;
}

@media (max-width: 1200px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
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

  .filter-card,
  .table-card {
    padding: 16px;
  }

  .filter-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .filter-item label {
    font-size: 13px;
  }

  .filter-item input,
  .filter-item select {
    height: 46px;
    font-size: 15px;
    padding: 0 12px;
  }

  .filter-actions,
  .pagination-controls {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-actions {
    gap: 10px;
  }

  .pagination-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .table-card {
    display: none;
  }

  .mobile-issue-list {
    display: block;
  }

  .mobile-card-images {
    grid-template-columns: 1fr 1fr;
  }

  .btn {
    width: 100%;
    min-height: 46px;
  }

  .image-modal {
    padding: 12px;
  }
}
</style>