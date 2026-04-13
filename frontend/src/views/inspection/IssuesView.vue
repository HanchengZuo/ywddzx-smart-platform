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
              <span class="mobile-card-category">{{ item.inspection_table_name || '暂无' }}</span>
              <span :class="statusClass(item.status)">{{ item.status }}</span>
            </div>
            <div class="mobile-card-code">规范ID：{{ item.standard_id || '暂无' }}</div>
            <div class="mobile-card-meta">{{ item.month }}｜{{ item.time }}</div>
          </div>

          <div class="mobile-card-body">
            <div class="mobile-card-row"><span>站点</span><strong>{{ item.station }}</strong></div>
            <div class="mobile-card-row"><span>所属地</span><strong>{{ item.region }}</strong></div>
            <div class="mobile-card-row"><span>站点负责人</span><strong>{{ item.station_manager }}</strong></div>
            <div class="mobile-card-row"><span>检查人员</span><strong>{{ item.inspector }}</strong></div>
            <div class="mobile-card-row"><span>检查表</span><strong>{{ item.inspection_table_name || '暂无' }}</strong></div>
            <div class="mobile-card-row"><span>规范ID</span><strong>{{ item.standard_id || '暂无' }}</strong></div>

            <div class="mobile-card-row mobile-card-row-top">
              <span>规范详情</span>
              <div class="mobile-card-standard-box">
                <div class="mobile-card-standard-preview multiline-clamp">{{ formatMultiline(item.standard_detail_text)
                  }}</div>
                <button class="text-link-btn" type="button" @click="openStandardDetail(item)">查看详情</button>
              </div>
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

            <button v-if="item.rectification_photo" class="mobile-image-btn" type="button"
              @click="preview(resolveImage(item.rectification_photo), '站点反馈整改照片')">
              <img :src="resolveImage(item.rectification_photo)" class="mobile-thumb" alt="站点反馈整改照片" />
              <span>整改照片</span>
            </button>
            <button v-if="item.review_photo" class="mobile-image-btn" type="button"
              @click="preview(resolveImage(item.review_photo), '督导组复核照片')">
              <img :src="resolveImage(item.review_photo)" class="mobile-thumb" alt="督导组复核照片" />
              <span>复核照片</span>
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
          <div class="search-select" ref="regionSelectRef">
            <input v-model="filters.region" placeholder="搜索或选择站点所属地" @focus="openFilterDropdown('region')"
              @input="openFilterDropdown('region')" />
            <div v-if="dropdownVisible.region" class="search-select-dropdown">
              <div v-for="option in filteredRegionOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('region', option)">
                <div class="option-main">{{ option }}</div>
              </div>
              <div v-if="filteredRegionOptions.length === 0" class="search-select-empty">无匹配站点所属地</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
          <label>站点名称</label>
          <div class="search-select" ref="stationSelectRef">
            <input v-model="filters.station" placeholder="搜索或选择站点名称" @focus="openFilterDropdown('station')"
              @input="openFilterDropdown('station')" />
            <div v-if="dropdownVisible.station" class="search-select-dropdown">
              <div v-for="option in filteredStationOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('station', option)">
                <div class="option-main">{{ option }}</div>
              </div>
              <div v-if="filteredStationOptions.length === 0" class="search-select-empty">无匹配站点名称</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
          <label>站点负责人</label>
          <div class="search-select" ref="stationManagerSelectRef">
            <input v-model="filters.stationManager" placeholder="搜索或选择站点负责人"
              @focus="openFilterDropdown('stationManager')" @input="openFilterDropdown('stationManager')" />
            <div v-if="dropdownVisible.stationManager" class="search-select-dropdown">
              <div v-for="option in filteredStationManagerOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('stationManager', option)">
                <div class="option-main">{{ option }}</div>
              </div>
              <div v-if="filteredStationManagerOptions.length === 0" class="search-select-empty">无匹配站点负责人</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
          <label>检查人员</label>
          <div class="search-select" ref="inspectorSelectRef">
            <input v-model="filters.inspector" placeholder="搜索或选择检查人员" @focus="openFilterDropdown('inspector')"
              @input="openFilterDropdown('inspector')" />
            <div v-if="dropdownVisible.inspector" class="search-select-dropdown">
              <div v-for="option in filteredInspectorOptions" :key="option" class="search-select-option"
                @click="selectFilterOption('inspector', option)">
                <div class="option-main">{{ option }}</div>
              </div>
              <div v-if="filteredInspectorOptions.length === 0" class="search-select-empty">无匹配检查人员</div>
            </div>
          </div>
        </div>

        <div class="filter-item">
          <label>检查表</label>
          <div class="search-select" ref="inspectionTableSelectRef">
            <input v-model="filters.inspectionTableName" placeholder="搜索或选择检查表"
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
          <label>规范ID</label>
          <input v-model="filters.standardId" placeholder="搜索规范ID" />
        </div>
        <div class="filter-item">
          <label>规范详情</label>
          <input v-model="filters.standardDetail" placeholder="搜索规范详情关键词" />
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
                <th class="nowrap">检查表</th>
                <th class="nowrap">规范ID</th>
                <th>规范详情</th>
                <th>问题描述</th>
                <th class="nowrap">问题照片</th>
                <th class="nowrap">站经理整改结果</th>
                <th class="nowrap">站点反馈整改说明</th>
                <th class="nowrap">站点反馈整改照片</th>
                <th class="nowrap">督导组复核结果</th>
                <th class="nowrap">督导组复核说明</th>
                <th class="nowrap">督导组复核照片</th>
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
                <td class="nowrap">{{ item.inspection_table_name || '暂无' }}</td>
                <td class="nowrap">{{ item.standard_id || '暂无' }}</td>
                <td class="standard-detail-cell">
                  <div class="standard-detail-box">
                    <div class="standard-detail-preview multiline-clamp">{{ formatMultiline(item.standard_detail_text)
                      }}</div>
                    <button class="text-link-btn" type="button" @click="openStandardDetail(item)">查看详情</button>
                  </div>
                </td>
                <td class="long-text">{{ item.description }}</td>
                <td class="nowrap">
                  <button class="image-btn" type="button" @click="preview(resolveImage(item.issue_photo), '问题照片')">
                    <img :src="resolveImage(item.issue_photo)" class="thumb" alt="问题照片" />
                  </button>
                </td>
                <td class="nowrap">{{ item.rectification_result || '暂无' }}</td>
                <td class="nowrap">{{ item.rectification_note || '暂无' }}</td>
                <td class="nowrap">
                  <button v-if="item.rectification_photo" class="image-btn" type="button"
                    @click="preview(resolveImage(item.rectification_photo), '站点反馈整改照片')">
                    <img :src="resolveImage(item.rectification_photo)" class="thumb" alt="站点反馈整改照片" />
                  </button>
                  <span v-else>暂无</span>
                </td>
                <td class="nowrap">{{ item.review_result || '暂无' }}</td>
                <td class="nowrap">{{ item.review_note || '暂无' }}</td>
                <td class="nowrap">
                  <button v-if="item.review_photo" class="image-btn" type="button"
                    @click="preview(resolveImage(item.review_photo), '督导组复核照片')">
                    <img :src="resolveImage(item.review_photo)" class="thumb" alt="督导组复核照片" />
                  </button>
                  <span v-else>暂无</span>
                </td>
                <td class="nowrap-col status-col">
                  <span :class="statusClass(item.status)">{{ item.status }}</span>
                </td>
              </tr>
              <tr v-if="!loading && paginatedData.length === 0">
                <td colspan="20" class="empty-row">当前没有符合条件的问题记录。</td>
              </tr>
              <tr v-if="loading">
                <td colspan="20" class="empty-row">正在加载问题列表...</td>
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
    <div v-if="standardDetailState.visible" class="image-modal" @click.self="closeStandardDetail">
      <div class="image-modal-content standard-detail-modal">
        <div class="image-modal-header">
          <span>{{ standardDetailState.title }}</span>
          <button class="close-btn" type="button" @click="closeStandardDetail">×</button>
        </div>
        <div class="standard-detail-modal-body">
          <div class="standard-detail-grid">
            <div v-for="entry in standardDetailEntries" :key="`${standardDetailState.title}-${entry.label}`"
              class="standard-detail-card">
              <div class="standard-detail-card-label">{{ entry.label }}</div>
              <div class="standard-detail-card-value multiline-cell">{{ entry.value }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'

const filters = ref({
  month: '',
  date: '',
  region: '',
  station: '',
  stationManager: '',
  inspector: '',
  inspectionTableName: '',
  standardId: '',
  standardDetail: '',
  rectificationResult: '',
  reviewResult: '',
  status: ''
})

const list = ref([])
const loading = ref(false)
const regionSelectRef = ref(null)
const stationSelectRef = ref(null)
const stationManagerSelectRef = ref(null)
const inspectorSelectRef = ref(null)
const inspectionTableSelectRef = ref(null)

const dropdownVisible = ref({
  region: false,
  station: false,
  stationManager: false,
  inspector: false,
  inspectionTableName: false
})

const page = ref(1)
const pageSize = ref(20)

const normalizedKeyword = (value) => String(value || '').toLowerCase()
const formatMultiline = (value) => String(value || '').replace(/\\n/g, '\n')
const uniqueSortedOptions = (values) => {
  return [...new Set(values.map((item) => String(item || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

const filterOptionByKeyword = (options, keyword) => {
  const normalized = normalizedKeyword(keyword)
  return options.filter((item) => !normalized || normalizedKeyword(item).includes(normalized))
}

const filteredData = computed(() => {
  return list.value.filter((item) => {
    const matchedMonth = !filters.value.month || item.month === filters.value.month
    const matchedDate = !filters.value.date || String(item.time || '').startsWith(filters.value.date)
    const matchedRegion = !filters.value.region || normalizedKeyword(item.region).includes(normalizedKeyword(filters.value.region))
    const matchedStation = !filters.value.station || normalizedKeyword(item.station).includes(normalizedKeyword(filters.value.station))
    const matchedStationManager = !filters.value.stationManager || normalizedKeyword(item.station_manager).includes(normalizedKeyword(filters.value.stationManager))
    const matchedInspector = !filters.value.inspector || normalizedKeyword(item.inspector).includes(normalizedKeyword(filters.value.inspector))
    const matchedInspectionTableName = !filters.value.inspectionTableName || normalizedKeyword(item.inspection_table_name).includes(normalizedKeyword(filters.value.inspectionTableName))
    const matchedStandardId = !filters.value.standardId || normalizedKeyword(item.standard_id || item.code).includes(normalizedKeyword(filters.value.standardId))
    const matchedStandardDetail = !filters.value.standardDetail || normalizedKeyword(item.standard_detail_text).includes(normalizedKeyword(filters.value.standardDetail))
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
      matchedInspectionTableName &&
      matchedStandardId &&
      matchedStandardDetail &&
      matchedRectificationResult &&
      matchedReviewResult &&
      matchedStatus
    )
  })
})

const regionOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.region)))
const stationOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.station)))
const stationManagerOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.station_manager)))
const inspectorOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.inspector)))
const inspectionTableOptions = computed(() => uniqueSortedOptions(list.value.map((item) => item.inspection_table_name)))

const filteredRegionOptions = computed(() => filterOptionByKeyword(regionOptions.value, filters.value.region))
const filteredStationOptions = computed(() => filterOptionByKeyword(stationOptions.value, filters.value.station))
const filteredStationManagerOptions = computed(() => filterOptionByKeyword(stationManagerOptions.value, filters.value.stationManager))
const filteredInspectorOptions = computed(() => filterOptionByKeyword(inspectorOptions.value, filters.value.inspector))
const filteredInspectionTableOptions = computed(() => filterOptionByKeyword(inspectionTableOptions.value, filters.value.inspectionTableName))

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
    const userId = localStorage.getItem('user_id') || ''
    const response = await axios.get('/api/issues', {
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
    month: '',
    date: '',
    region: '',
    station: '',
    stationManager: '',
    inspector: '',
    inspectionTableName: '',
    standardId: '',
    standardDetail: '',
    rectificationResult: '',
    reviewResult: '',
    status: ''
  }
  closeAllDropdowns()
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

const standardDetailState = ref({
  visible: false,
  title: '',
  content: ''
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

const openStandardDetail = (item) => {
  standardDetailState.value = {
    visible: true,
    title: `规范详情｜${item.inspection_table_name || '未命名检查表'}｜${item.standard_id || '暂无'}`,
    content: item.standard_detail_text || '暂无规范详情'
  }
}

const closeStandardDetail = () => {
  standardDetailState.value = {
    visible: false,
    title: '',
    content: ''
  }
}

const standardDetailEntries = computed(() => {
  const content = formatMultiline(standardDetailState.value.content || '').trim()
  if (!content) return []

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
    '检查方式',
    '规范ID'
  ])

  const entries = []

  content
    .split('\n')
    .map((line) => String(line || '').trim())
    .filter(Boolean)
    .forEach((line, index) => {
      const separatorIndex = line.indexOf('：')
      const possibleLabel = separatorIndex > -1 ? line.slice(0, separatorIndex).trim() : ''

      if (separatorIndex > -1 && topLevelLabels.has(possibleLabel)) {
        entries.push({
          label: possibleLabel,
          value: formatMultiline(line.slice(separatorIndex + 1).trim()) || '暂无'
        })
        return
      }

      if (entries.length > 0) {
        const lastEntry = entries[entries.length - 1]
        lastEntry.value = `${lastEntry.value}\n${formatMultiline(line)}`.trim()
        return
      }

      entries.push({
        label: `详情 ${index + 1}`,
        value: formatMultiline(line)
      })
    })

  return entries
})

const openFilterDropdown = (key) => {
  dropdownVisible.value[key] = true
}

const selectFilterOption = (key, value) => {
  filters.value[key] = value
  dropdownVisible.value[key] = false
}

const closeAllDropdowns = () => {
  dropdownVisible.value = {
    region: false,
    station: false,
    stationManager: false,
    inspector: false,
    inspectionTableName: false
  }
}

const handleClickOutside = (event) => {
  if (regionSelectRef.value && !regionSelectRef.value.contains(event.target)) {
    dropdownVisible.value.region = false
  }
  if (stationSelectRef.value && !stationSelectRef.value.contains(event.target)) {
    dropdownVisible.value.station = false
  }
  if (stationManagerSelectRef.value && !stationManagerSelectRef.value.contains(event.target)) {
    dropdownVisible.value.stationManager = false
  }
  if (inspectorSelectRef.value && !inspectorSelectRef.value.contains(event.target)) {
    dropdownVisible.value.inspector = false
  }
  if (inspectionTableSelectRef.value && !inspectionTableSelectRef.value.contains(event.target)) {
    dropdownVisible.value.inspectionTableName = false
  }
}

const statusClass = (status) => {
  if (status === '待整改') return 'status-tag danger'
  if (status === '待复核') return 'status-tag warning'
  if (status === '已闭环') return 'status-tag success'
  return 'status-tag'
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  fetchIssues()
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

.filter-item-wide {
  grid-column: span 2;
}

.search-select {
  position: relative;
}

.search-select input {
  width: 100%;
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

.filter-item label {
  font-size: 14px;
  font-weight: 700;
  color: #374151;
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

.mobile-card-standard-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.mobile-card-standard-preview {
  width: 100%;
  text-align: left;
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

.standard-detail-cell {
  min-width: 300px;
}

.standard-detail-box {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.standard-detail-preview {
  width: 100%;
}

.multiline-clamp {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.text-link-btn {
  border: none;
  background: transparent;
  padding: 0;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
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

.standard-detail-modal {
  width: min(880px, 100%);
}

.standard-detail-modal-body {
  padding: 20px;
  max-height: 70vh;
  overflow: auto;
  line-height: 1.9;
  color: #334155;
  background: #f8fafc;
}

.standard-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(240px, 1fr));
  gap: 14px;
}

.standard-detail-card {
  padding: 16px 18px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #e7edf4;
}

.standard-detail-card-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  margin-bottom: 8px;
}

.standard-detail-card-value {
  font-size: 14px;
  line-height: 1.9;
  color: #334155;
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

  .filter-item-wide {
    grid-column: span 1;
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

  .standard-detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>