<template>
  <div class="page-shell records-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>巡检记录</h2>
      </div>
    </div>

    <div class="filter-card card-surface">
      <div class="filter-grid">
        <div class="filter-item">
          <label>巡检日期</label>
          <input v-model="filters.date" type="date" />
        </div>
        <div class="filter-item">
          <label>站点</label>
          <input v-model="filters.station" type="text" placeholder="搜索站点名称" />
        </div>
        <div class="filter-item">
          <label>巡检大类</label>
          <input v-model="filters.categories" type="text" placeholder="搜索巡检大类" />
        </div>
        <div class="filter-item">
          <label>结果</label>
          <select v-model="filters.result">
            <option value="">全部</option>
            <option value="正常">正常</option>
            <option value="异常">异常</option>
          </select>
        </div>
      </div>

      <div class="filter-actions">
        <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
        <button class="btn btn-secondary" type="button" @click="fetchInspections" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
      </div>
    </div>

    <div class="mobile-record-list">
      <div v-if="loading" class="mobile-empty card-surface">正在加载巡检记录...</div>

      <div v-else-if="paginatedData.length === 0" class="mobile-empty card-surface">
        当前没有巡检记录。
      </div>

      <div v-else class="mobile-record-cards">
        <div v-for="item in paginatedData" :key="item.id" class="mobile-record-card card-surface">
          <div class="mobile-card-head">
            <div class="mobile-card-title-row">
              <div class="mobile-card-station">{{ item.station }}</div>
              <span :class="statusClass(item.result)">{{ item.result }}</span>
            </div>
            <div class="mobile-card-date">巡检日期：{{ item.date }}</div>
          </div>

          <div class="mobile-card-body">
            <div class="mobile-card-row mobile-card-row-top">
              <span>巡检大类</span>
              <div class="mobile-card-text">{{ item.categories || '暂无' }}</div>
            </div>
            <div class="mobile-card-row">
              <span>发现问题数</span>
              <strong>{{ item.issue_count }}</strong>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="table-card card-surface">
      <div class="table-scroll-wrap">
        <div class="table-scroll">
          <table class="records-table">
            <thead>
              <tr>
                <th>巡检日期</th>
                <th>站点</th>
                <th>巡检大类</th>
                <th>结果</th>
                <th>发现问题数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in paginatedData" :key="item.id">
                <td>{{ item.date }}</td>
                <td>{{ item.station }}</td>
                <td class="long-text">{{ item.categories || '暂无' }}</td>
                <td>
                  <span :class="statusClass(item.result)">{{ item.result }}</span>
                </td>
                <td>{{ item.issue_count }}</td>
              </tr>
              <tr v-if="!loading && paginatedData.length === 0">
                <td colspan="5" class="empty-row">当前没有巡检记录。</td>
              </tr>
              <tr v-if="loading">
                <td colspan="5" class="empty-row">正在加载巡检记录...</td>
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
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import axios from 'axios'

const filters = ref({
  date: '',
  station: '',
  categories: '',
  result: ''
})

const list = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)

const filteredData = computed(() => {
  return list.value.filter((item) => {
    const matchedDate = !filters.value.date || item.date === filters.value.date
    const matchedStation =
      !filters.value.station || String(item.station || '').toLowerCase().includes(filters.value.station.trim().toLowerCase())
    const matchedCategories =
      !filters.value.categories || String(item.categories || '').toLowerCase().includes(filters.value.categories.trim().toLowerCase())
    const matchedResult = !filters.value.result || item.result === filters.value.result

    return matchedDate && matchedStation && matchedCategories && matchedResult
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

const fetchInspections = async () => {
  try {
    loading.value = true
    const response = await axios.get('/api/inspections')
    list.value = response.data || []
  } catch (error) {
    list.value = []
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.value = {
    date: '',
    station: '',
    categories: '',
    result: ''
  }
}

const prevPage = () => {
  if (page.value > 1) {
    page.value -= 1
  }
}

const nextPage = () => {
  if (page.value < totalPage.value) {
    page.value += 1
  }
}

const statusClass = (value) => {
  if (value === '正常') return 'status-tag success'
  if (value === '异常') return 'status-tag danger'
  return 'status-tag'
}

onMounted(() => {
  fetchInspections()
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
  gap: 12px;
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
.mobile-record-list {
  display: none;
}

.mobile-record-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-record-card {
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

.mobile-card-station {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

.mobile-card-date {
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

.mobile-empty {
  padding: 28px 16px;
  text-align: center;
  color: #64748b;
  font-size: 14px;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.btn-secondary:hover:not(:disabled) {
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

.records-table {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
}

.records-table th,
.records-table td {
  border: 1px solid #e5e7eb;
  padding: 12px 14px;
  text-align: left;
  vertical-align: top;
  font-size: 14px;
  color: #111827;
}

.records-table th {
  background: #f8fafc;
  font-weight: 700;
  white-space: nowrap;
}

.long-text {
  min-width: 220px;
  white-space: normal;
  line-height: 1.7;
}

.empty-row {
  text-align: center;
  color: #6b7280;
  padding: 40px 0 !important;
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

.status-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.status-tag.success {
  background: #f0fdf4;
  color: #16a34a;
}

.status-tag.danger {
  background: #fef2f2;
  color: #dc2626;
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
  .filter-item select,
  .pagination-controls select {
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

  .mobile-record-list {
    display: block;
  }

  .btn {
    width: 100%;
    min-height: 46px;
  }
}
</style>