<template>
  <div class="page-shell standards-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>巡检规范库</h2>
      </div>
    </div>

    <div class="filter-card card-surface">
      <div class="filter-grid">
        <div class="filter-item filter-item-keyword">
          <label>关键词搜索</label>
          <input
            v-model.trim="filters.keyword"
            type="text"
            placeholder="可搜索编号、业务流程、检查项目、检查内容、规范要求、检查方法"
          />
        </div>

        <div class="filter-item">
          <label>规范编号</label>
          <input v-model.trim="filters.code" type="text" placeholder="搜索规范编号" />
        </div>

        <div class="filter-item">
          <label>业务流程</label>
          <input v-model.trim="filters.businessProcess" type="text" placeholder="搜索业务流程" />
        </div>

        <div class="filter-item">
          <label>检查项目</label>
          <input v-model.trim="filters.checkItem" type="text" placeholder="搜索检查项目" />
        </div>
      </div>

      <div class="filter-actions">
        <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
        <button class="btn btn-secondary" type="button" @click="fetchStandards" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
      </div>
    </div>

    <div class="content-grid">
      <div class="list-card card-surface">
        <div class="list-toolbar">
          <div class="list-count">共 {{ filteredList.length }} 条规范</div>
        </div>

        <div class="list-wrap">
          <button
            v-for="item in filteredList"
            :key="item.id"
            class="standard-item"
            :class="{ active: activeStandard && activeStandard.id === item.id }"
            type="button"
            @click="selectStandard(item)"
          >
            <div class="standard-item-top">
              <span class="standard-code">{{ item.code }}</span>
              <span class="standard-process">{{ item.business_process }}</span>
            </div>
            <div class="standard-check-item">{{ item.check_item }}</div>
            <div class="standard-check-content">{{ item.check_content }}</div>
          </button>

          <div v-if="!loading && filteredList.length === 0" class="empty-block">
            未查询到符合条件的规范。
          </div>

          <div v-if="loading" class="empty-block">
            正在加载规范数据...
          </div>
        </div>
      </div>

      <div class="detail-card card-surface">
        <template v-if="activeStandard">
          <div class="detail-header">
            <div>
              <div class="detail-kicker">规范详情</div>
              <h3>{{ activeStandard.code }}｜{{ activeStandard.check_item }}</h3>
            </div>
            <div class="detail-actions">
              <button class="btn btn-secondary" type="button" @click="copyCode">复制编号</button>
              <button class="btn btn-primary" type="button" @click="copyStandard">复制整条规范</button>
            </div>
          </div>

          <div class="detail-meta-grid">
            <div class="meta-item">
              <div class="meta-label">规范编号</div>
              <div class="meta-value">{{ activeStandard.code }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">业务流程</div>
              <div class="meta-value">{{ activeStandard.business_process }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">检查项目</div>
              <div class="meta-value">{{ activeStandard.check_item }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">检查内容</div>
              <div class="meta-value">{{ activeStandard.check_content }}</div>
            </div>
          </div>

          <div class="detail-block">
            <div class="detail-block-title">规范要求</div>
            <div class="detail-block-content multiline-content">{{ formatMultiline(activeStandard.requirement) || '暂无' }}</div>
          </div>

          <div class="detail-block">
            <div class="detail-block-title">检查方法</div>
            <div class="detail-block-content multiline-content">{{ formatMultiline(activeStandard.check_method) || '暂无' }}</div>
          </div>

          <div v-if="copyMessage" class="copy-message">{{ copyMessage }}</div>
        </template>

        <div v-else class="empty-detail">
          <div class="empty-detail-icon">书</div>
          <div class="empty-detail-title">请选择一条巡检规范</div>
          <div class="empty-detail-desc">左侧可按关键词、编号、业务流程、检查项目进行查询，点击后查看完整规范内容。</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import axios from 'axios'

const loading = ref(false)
const standards = ref([])
const activeStandard = ref(null)
const copyMessage = ref('')

const filters = ref({
  keyword: '',
  code: '',
  businessProcess: '',
  checkItem: ''
})

const normalize = (value) => String(value || '').toLowerCase()
const formatMultiline = (value) => String(value || '').replace(/\\n/g, '\n')

const filteredList = computed(() => {
  return standards.value.filter((item) => {
    const keywordSource = [
      item.code,
      item.business_process,
      item.check_item,
      item.check_content,
      item.requirement,
      item.check_method
    ].join(' ')

    const matchedKeyword = !filters.value.keyword || normalize(keywordSource).includes(normalize(filters.value.keyword))
    const matchedCode = !filters.value.code || normalize(item.code).includes(normalize(filters.value.code))
    const matchedBusinessProcess =
      !filters.value.businessProcess || normalize(item.business_process).includes(normalize(filters.value.businessProcess))
    const matchedCheckItem = !filters.value.checkItem || normalize(item.check_item).includes(normalize(filters.value.checkItem))

    return matchedKeyword && matchedCode && matchedBusinessProcess && matchedCheckItem
  })
})

watch(
  filteredList,
  (list) => {
    if (!list.length) {
      activeStandard.value = null
      return
    }

    const stillExists = list.find((item) => activeStandard.value && item.id === activeStandard.value.id)
    if (!stillExists) {
      activeStandard.value = list[0]
    }
  },
  { immediate: true }
)

const fetchStandards = async () => {
  try {
    loading.value = true
    copyMessage.value = ''
    const response = await axios.get('/api/inspection-standards')
    standards.value = response.data || []
  } catch (error) {
    standards.value = []
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.value = {
    keyword: '',
    code: '',
    businessProcess: '',
    checkItem: ''
  }
}

const selectStandard = (item) => {
  activeStandard.value = item
  copyMessage.value = ''
}

const copyCode = async () => {
  if (!activeStandard.value) return
  try {
    await navigator.clipboard.writeText(String(activeStandard.value.code || ''))
    copyMessage.value = '规范编号已复制。'
  } catch (error) {
    copyMessage.value = '复制失败，请手动复制。'
  }
}

const copyStandard = async () => {
  if (!activeStandard.value) return
  const text = [
    `编号：${activeStandard.value.code || ''}`,
    `业务流程：${activeStandard.value.business_process || ''}`,
    `检查项目：${activeStandard.value.check_item || ''}`,
    `检查内容：${activeStandard.value.check_content || ''}`,
    `规范要求：${formatMultiline(activeStandard.value.requirement) || ''}`,
    `检查方法：${formatMultiline(activeStandard.value.check_method) || ''}`
  ].join('\n')

  try {
    await navigator.clipboard.writeText(text)
    copyMessage.value = '整条规范已复制。'
  } catch (error) {
    copyMessage.value = '复制失败，请手动复制。'
  }
}

onMounted(() => {
  fetchStandards()
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

.filter-card {
  padding: 22px;
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

.filter-item-keyword {
  grid-column: span 2;
}

.filter-item label {
  font-size: 14px;
  font-weight: 700;
  color: #334155;
}

.filter-item input {
  height: 46px;
  border: 1px solid #d7e0ea;
  border-radius: 14px;
  padding: 0 14px;
  font-size: 14px;
  color: #0f172a;
  transition: all 0.18s ease;
}

.filter-item input:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.4);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.08);
}

.filter-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(340px, 420px) minmax(0, 1fr);
  gap: 20px;
  min-height: 620px;
}

.list-card,
.detail-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  min-height: 620px;
}

.list-toolbar {
  margin-bottom: 14px;
}

.list-count {
  font-size: 14px;
  color: #64748b;
  font-weight: 700;
}

.list-wrap {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.standard-item {
  width: 100%;
  text-align: left;
  border: 1px solid #e5edf5;
  background: #fff;
  border-radius: 16px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.standard-item:hover {
  background: #f8fbff;
  border-color: #bfdbfe;
}

.standard-item.active {
  background: #eff6ff;
  border-color: #93c5fd;
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.08);
}

.standard-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.standard-code {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
}

.standard-process {
  font-size: 12px;
  color: #64748b;
  font-weight: 700;
}

.standard-check-item {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 6px;
}

.standard-check-content {
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
}

.detail-card {
  overflow: auto;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.detail-kicker {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 8px;
}

.detail-header h3 {
  margin: 0;
  font-size: 26px;
  color: #0f172a;
  line-height: 1.4;
}

.detail-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.detail-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.meta-item {
  padding: 14px 16px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e7edf4;
}

.meta-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 8px;
}

.meta-value {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.6;
}

.detail-block {
  margin-bottom: 18px;
}

.detail-block-title {
  font-size: 15px;
  font-weight: 800;
  color: #334155;
  margin-bottom: 10px;
}

.detail-block-content {
  padding: 16px 18px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e7edf4;
  color: #334155;
  line-height: 1.9;
  white-space: pre-wrap;
}
.multiline-content {
  white-space: pre-line;
}

.copy-message {
  margin-top: 8px;
  font-size: 14px;
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 14px;
  padding: 12px 14px;
}

.empty-block,
.empty-detail {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
  line-height: 1.8;
}

.empty-detail-icon {
  width: 60px;
  height: 60px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 26px;
  font-weight: 800;
  margin-bottom: 14px;
}

.empty-detail-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 8px;
}

.empty-detail-desc {
  max-width: 440px;
  font-size: 14px;
}

.btn {
  height: 42px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  cursor: pointer;
  transition: all 0.18s ease;
}

.btn-primary {
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
  border-color: #2563eb;
  color: #fff;
  box-shadow: 0 12px 22px rgba(37, 99, 235, 0.16);
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%);
}

.btn-secondary:hover:not(:disabled) {
  background: #f8fafc;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@media (max-width: 1200px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }

  .filter-item-keyword {
    grid-column: span 2;
  }

  .content-grid {
    grid-template-columns: 1fr;
  }

  .list-card,
  .detail-card {
    min-height: auto;
  }
}

@media (max-width: 768px) {
  .filter-grid,
  .detail-meta-grid {
    grid-template-columns: 1fr;
  }

  .filter-item-keyword {
    grid-column: span 1;
  }

  .page-header h2 {
    font-size: 30px;
  }

  .detail-header h3 {
    font-size: 22px;
  }
}
</style>