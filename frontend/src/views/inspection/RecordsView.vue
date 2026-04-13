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
          <div class="search-select" ref="stationSelectRef">
            <input v-model="filters.station" type="text" placeholder="搜索或选择站点名称" @focus="openFilterDropdown('station')"
              @input="openFilterDropdown('station')" />
            <div v-if="dropdownVisible.station" class="search-select-dropdown">
              <div v-for="option in filteredStationOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('station', option)">
                <div class="option-main">{{ option }}</div>
              </div>
              <div v-if="filteredStationOptions.length === 0" class="search-select-empty">无匹配站点</div>
            </div>
          </div>
        </div>
        <div class="filter-item">
          <label>检查表</label>
          <div class="search-select" ref="inspectionTableSelectRef">
            <input v-model="filters.inspectionTableName" type="text" placeholder="搜索或选择检查表"
              @focus="openFilterDropdown('inspectionTableName')" @input="openFilterDropdown('inspectionTableName')" />
            <div v-if="dropdownVisible.inspectionTableName" class="search-select-dropdown">
              <div v-for="option in filteredInspectionTableOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('inspectionTableName', option)">
                <div class="option-main">{{ option }}</div>
              </div>
              <div v-if="filteredInspectionTableOptions.length === 0" class="search-select-empty">无匹配检查表</div>
            </div>
          </div>
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

      <div v-else-if="paginatedBatches.length === 0" class="mobile-empty card-surface">
        当前没有巡检记录。
      </div>

      <div v-else class="mobile-record-cards">
        <div v-for="batch in paginatedBatches" :key="batch.batchKey" class="mobile-record-card card-surface">
          <div class="mobile-card-head">
            <div class="mobile-card-title-row">
              <div class="mobile-card-station">{{ batch.station }}</div>
              <span :class="statusClass(batch.batchResult)">{{ batch.batchResult }}</span>
            </div>
            <div class="mobile-card-date">巡检日期：{{ batch.date }}</div>
          </div>

          <div class="mobile-card-body">
            <div class="mobile-card-row">
              <span>本批次检查表数</span>
              <strong>{{ batch.rowspan }}</strong>
            </div>
            <div class="mobile-card-row">
              <span>本批次问题总数</span>
              <strong>{{ batch.batchIssueCount }}</strong>
            </div>
          </div>

          <div class="mobile-batch-list">
            <div v-for="record in batch.records" :key="record.id" class="mobile-batch-item">
              <div class="mobile-batch-item-head">
                <div class="mobile-batch-table-name">{{ record.inspection_table_name || '暂无' }}</div>
                <span :class="statusClass(record.result)">{{ record.result }}</span>
              </div>
              <div class="mobile-batch-item-meta">发现问题数：{{ record.issue_count }}</div>
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
                <th>检查表</th>
                <th>结果</th>
                <th>发现问题数</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="batch in paginatedBatches" :key="batch.batchKey">
                <tr v-for="(record, index) in batch.records" :key="record.id">
                  <td v-if="index === 0" :rowspan="batch.rowspan" class="batch-merged-cell batch-main-cell">{{
                    batch.date }}</td>
                  <td v-if="index === 0" :rowspan="batch.rowspan" class="batch-merged-cell batch-main-cell">{{
                    batch.station }}</td>
                  <td class="long-text">{{ record.inspection_table_name || '暂无' }}</td>
                  <td>
                    <span :class="statusClass(record.result)">{{ record.result }}</span>
                  </td>
                  <td>{{ record.issue_count }}</td>
                </tr>
              </template>
              <tr v-if="!loading && paginatedBatches.length === 0">
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
        <div class="pagination-summary">共 {{ groupedBatches.length }} 个巡检批次</div>
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
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'

const filters = ref({
  date: '',
  station: '',
  inspectionTableName: '',
  result: ''
})

const stationSelectRef = ref(null)
const inspectionTableSelectRef = ref(null)

const dropdownVisible = ref({
  station: false,
  inspectionTableName: false
})

const list = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)

const normalizedKeyword = (value) => String(value || '').trim().toLowerCase()

const uniqueSortedOptions = (values) => {
  return [...new Set(values.map((item) => String(item || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

const filterOptionByKeyword = (options, keyword) => {
  const normalized = normalizedKeyword(keyword)
  return options.filter((item) => !normalized || normalizedKeyword(item).includes(normalized))
}

const filteredData = computed(() => {
  return list.value.filter((item) => {
    const matchedDate = !filters.value.date || item.date === filters.value.date
    const matchedStation = !filters.value.station || normalizedKeyword(item.station).includes(normalizedKeyword(filters.value.station))
    const matchedInspectionTableName = !filters.value.inspectionTableName || normalizedKeyword(item.inspection_table_name).includes(normalizedKeyword(filters.value.inspectionTableName))
    const matchedResult = !filters.value.result || item.result === filters.value.result

    return matchedDate && matchedStation && matchedInspectionTableName && matchedResult
  })
})

const stationOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.station)))
const inspectionTableOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.inspection_table_name)))

const filteredStationOptions = computed(() => filterOptionByKeyword(stationOptions.value, filters.value.station))
const filteredInspectionTableOptions = computed(() => filterOptionByKeyword(inspectionTableOptions.value, filters.value.inspectionTableName))

const groupedBatches = computed(() => {
  const batchMap = new Map()

  filteredData.value.forEach((item) => {
    const batchKey = `${item.date || ''}__${item.station || ''}`
    if (!batchMap.has(batchKey)) {
      batchMap.set(batchKey, {
        batchKey,
        date: item.date,
        station: item.station,
        records: [],
        batchIssueCount: 0,
        batchResult: '正常',
        rowspan: 0
      })
    }

    const batch = batchMap.get(batchKey)
    batch.records.push(item)
    batch.batchIssueCount += Number(item.issue_count || 0)
    if (item.result === '异常') {
      batch.batchResult = '异常'
    }
  })

  return Array.from(batchMap.values()).map((batch) => {
    batch.rowspan = batch.records.length
    return batch
  })
})

const totalPage = computed(() => Math.max(1, Math.ceil(groupedBatches.value.length / pageSize.value)))

const paginatedBatches = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return groupedBatches.value.slice(start, start + pageSize.value)
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
    const userId = localStorage.getItem('user_id') || ''
    const response = await axios.get('/api/inspections', {
      params: {
        user_id: userId
      }
    })
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
    inspectionTableName: '',
    result: ''
  }
  closeAllDropdowns()
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

const openFilterDropdown = (key) => {
  dropdownVisible.value[key] = true
}

const selectFilterOption = (key, value) => {
  filters.value[key] = value
  dropdownVisible.value[key] = false
}

const closeAllDropdowns = () => {
  dropdownVisible.value = {
    station: false,
    inspectionTableName: false
  }
}

const handleClickOutside = (event) => {
  if (stationSelectRef.value && !stationSelectRef.value.contains(event.target)) {
    dropdownVisible.value.station = false
  }
  if (inspectionTableSelectRef.value && !inspectionTableSelectRef.value.contains(event.target)) {
    dropdownVisible.value.inspectionTableName = false
  }
}

const statusClass = (value) => {
  if (value === '正常') return 'status-tag success'
  if (value === '异常') return 'status-tag danger'
  return 'status-tag'
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  fetchInspections()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
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

.search-select {
  position: relative;
}

.search-select input {
  width: 100%;
  box-sizing: border-box;
}

.search-select-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  max-height: 240px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.12);
  z-index: 200;
}

.search-select-option {
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid #eef2f7;
}

.search-select-option:last-child {
  border-bottom: none;
}

.search-select-option:hover {
  background: #f8fafc;
}

.search-select-empty {
  padding: 12px;
  color: #64748b;
  font-size: 13px;
}

.option-main {
  font-size: 14px;
  color: #0f172a;
}

.filter-item input,
.filter-item select {
  width: 100%;
  height: 42px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 14px;
  box-sizing: border-box;
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

.mobile-batch-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px dashed #dbe4ee;
}

.mobile-batch-item {
  padding: 12px 14px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #e7edf4;
}

.mobile-batch-item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.mobile-batch-table-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.6;
}

.mobile-batch-item-meta {
  font-size: 13px;
  color: #64748b;
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

.batch-merged-cell {
  background: #fcfdff;
}

.batch-main-cell {
  font-weight: 700;
  color: #0f172a;
  vertical-align: middle;
  text-align: center;
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