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

      <div v-else-if="paginatedInspectionGroups.length === 0" class="mobile-empty card-surface">
        当前没有巡检记录。
      </div>

      <div v-else class="mobile-record-cards">
        <div v-for="batch in paginatedInspectionGroups" :key="batch.batchKey" class="mobile-record-card card-surface">
          <div class="mobile-card-head">
            <div class="mobile-card-title-row">
              <div class="mobile-card-station">{{ batch.station }}</div>
              <span :class="statusClass(batch.batchResult)">{{ batch.batchResult }}</span>
            </div>
            <div class="mobile-card-date">巡检日期：{{ batch.date }}</div>
          </div>

          <div class="mobile-card-body">
            <div class="mobile-card-row">
              <span>当日检查表数</span>
              <strong>{{ batch.rowspan }}</strong>
            </div>
            <div class="mobile-card-row">
              <span>当日问题总数</span>
              <strong>{{ batch.batchIssueCount }}</strong>
            </div>
            <div class="mobile-card-row">
              <span>检查表签名进度</span>
              <strong>{{ batch.signedCount }}/{{ batch.rowspan }}</strong>
            </div>
          </div>

          <div class="mobile-batch-list">
            <div v-for="record in batch.records" :key="record.id" class="mobile-batch-item">
              <div class="mobile-batch-item-head">
                <div class="mobile-batch-table-name">{{ record.inspection_table_name || '暂无' }}</div>
                <span :class="statusClass(record.result)">{{ record.result }}</span>
              </div>
              <div class="mobile-batch-item-meta">发现问题数：{{ record.issue_count }}</div>
              <div class="mobile-batch-item-meta">签名状态：{{ record.sign_status === '已签名确认' ? '已签名确认' : '待签名确认' }}</div>

              <div class="mobile-batch-item-actions">
                <button class="btn btn-secondary batch-action-btn" type="button" @click="openInspectionDetail(record)">
                  查看本表录入问题
                </button>

                <button v-if="isSupervisorLike && record.sign_status !== '已签名确认'"
                  class="btn btn-primary signature-action-btn" type="button" @click="openSignatureDialog(record)">
                  结束本检查表并签名确认
                </button>
              </div>

              <div v-if="record.sign_status === '已签名确认' && record.station_manager_signature_path"
                class="mobile-signature-box">
                <div class="mobile-signature-label">本表已签名</div>
                <img :src="resolveImage(record.station_manager_signature_path)" class="signature-preview-image"
                  alt="站经理签名" />
                <div class="mobile-signature-time">{{ record.station_manager_signed_at || '已完成签名确认' }}</div>
              </div>
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
                <th>本表问题</th>
                <th>本表签字确认</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="batch in paginatedInspectionGroups" :key="batch.batchKey">
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

                  <td class="batch-action-cell">
                    <button class="btn btn-secondary batch-action-btn" type="button"
                      @click="openInspectionDetail(record)">
                      查看本表录入问题
                    </button>
                  </td>

                  <td class="batch-signature-cell">
                    <div v-if="record.sign_status === '已签名确认' && record.station_manager_signature_path"
                      class="signature-preview-box">
                      <div class="signature-status-badge success">已签名确认</div>
                      <img :src="resolveImage(record.station_manager_signature_path)" class="signature-preview-image"
                        alt="站经理签名" />
                      <div class="signature-preview-time">{{ record.station_manager_signed_at || '已完成签名确认' }}</div>
                    </div>

                    <button v-else-if="isSupervisorLike" class="btn btn-primary signature-action-btn"
                      type="button" @click="openSignatureDialog(record)">
                      结束本检查表并签名确认
                    </button>

                    <span v-else class="signature-status-badge pending">待签名确认</span>
                  </td>

                </tr>
              </template>
              <tr v-if="!loading && paginatedInspectionGroups.length === 0">
                <td colspan="7" class="empty-row">当前没有巡检记录。</td>
              </tr>
              <tr v-if="loading">
                <td colspan="7" class="empty-row">正在加载巡检记录...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="pagination-bar">
        <div class="pagination-summary">共 {{ groupedInspectionGroups.length }} 组巡检记录</div>
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

    <div v-if="signatureDialog.visible" class="batch-detail-overlay" @click.self="closeSignatureDialog">
      <div v-if="isMobileView" class="mobile-signature-board card-surface">
        <div v-if="!isLandscapeMobile" class="mobile-signature-orientation-overlay">
          <div class="mobile-signature-orientation-overlay-inner">
            <div class="mobile-signature-orientation-icon">↻</div>
            <div class="mobile-signature-orientation-title">请横屏后签字</div>
            <div class="mobile-signature-orientation-text">为了便于站经理手写签名，请将手机旋转为横屏后继续操作。</div>
            <button class="btn btn-secondary mobile-signature-close" type="button"
              @click="closeSignatureDialog">关闭</button>
          </div>
        </div>

        <template v-else>
          <div class="mobile-signature-layout">
            <div class="mobile-signature-canvas-wrap">
              <canvas ref="signatureCanvasRef" class="signature-canvas mobile-signature-canvas"></canvas>
            </div>

            <div class="mobile-signature-rail">
              <button class="mobile-signature-icon-btn mobile-signature-confirm" type="button"
                :disabled="signatureDialog.submitting" @click="submitInspectionSignature" aria-label="确认签名"
                title="确认签名">
                ✓
              </button>
              <button class="mobile-signature-icon-btn mobile-signature-reset" type="button" @click="clearSignature"
                aria-label="重置签名" title="重置签名">
                ↻
              </button>
              <button class="mobile-signature-icon-btn mobile-signature-close-btn" type="button"
                @click="closeSignatureDialog" aria-label="退出签名" title="退出签名">
                ✕
              </button>
            </div>
          </div>

          <div v-if="signatureDialog.error" class="signature-error mobile-signature-error">{{ signatureDialog.error }}
          </div>
        </template>
      </div>

      <div v-else class="signature-dialog card-surface">
        <div class="signature-dialog-header">
          <div>
            <div class="batch-detail-kicker">检查表签名确认</div>
            <h3>{{ signatureDialog.record?.inspection_table_name || '检查表签名确认' }}</h3>
            <div class="batch-detail-meta">
              <span>巡检日期：{{ signatureDialog.record?.date || '-' }}</span>
              <span>站点：{{ signatureDialog.record?.station || '-' }}</span>
              <span>检查表：{{ signatureDialog.record?.inspection_table_name || '-' }}</span>
            </div>
          </div>
          <button class="btn btn-secondary" type="button" @click="closeSignatureDialog">关闭</button>
        </div>

        <div class="signature-layout">
          <div class="signature-side-card">
            <div class="signature-side-title">确认提示</div>
            <div class="signature-side-desc">请将手机交由站经理签字。提交后，本检查表将完成签名确认，不能继续登记同一天同站点的该检查表问题。</div>
            <div class="signature-side-meta">
              <span>站点：{{ signatureDialog.record?.station || '-' }}</span>
              <span>日期：{{ signatureDialog.record?.date || '-' }}</span>
              <span>检查表：{{ signatureDialog.record?.inspection_table_name || '-' }}</span>
            </div>
          </div>

          <div class="signature-pad-card signature-pad-card-landscape">
            <div class="signature-pad-head signature-pad-head-minimal"></div>
            <div class="signature-pad-wrap signature-pad-wrap-landscape">
              <canvas ref="signatureCanvasRef" class="signature-canvas signature-canvas-landscape"></canvas>
            </div>
            <div class="signature-pad-actions">
              <button class="btn btn-secondary" type="button" @click="clearSignature">清空签名</button>
              <button class="btn btn-primary" type="button" :disabled="signatureDialog.submitting"
                @click="submitInspectionSignature">
                {{ signatureDialog.submitting ? '提交中...' : '提交签名确认' }}
              </button>
            </div>
            <div v-if="signatureDialog.error" class="signature-error">{{ signatureDialog.error }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="batchDetail.visible" class="batch-detail-overlay" @click.self="closeBatchDetail">
      <div class="batch-detail-dialog card-surface">
        <div class="batch-detail-header">
          <div>

            <div class="batch-detail-kicker">检查表录入问题</div>
            <h3>{{ batchDetail.inspection?.inspection_table_name || '检查表详情' }}</h3>
            <div class="batch-detail-meta">
              <span>巡检日期：{{ batchDetail.inspection?.inspection_date || batchDetail.inspection?.date || '-' }}</span>
              <span>站点：{{ batchDetail.inspection?.station_name || batchDetail.inspection?.station || '-' }}</span>
              <span>问题数：{{ batchDetail.issues.length || 0 }}</span>
            </div>

          </div>
          <button class="btn btn-secondary" type="button" @click="closeBatchDetail">关闭</button>
        </div>

        <div v-if="batchDetail.loading" class="batch-detail-empty">正在加载本表问题...</div>
        <div v-else-if="batchDetail.error" class="batch-detail-empty">{{ batchDetail.error }}</div>
        <div v-else-if="batchDetail.issues.length === 0" class="batch-detail-empty">本检查表暂无登记问题。</div>

        <div v-else class="batch-issue-list">
          <div v-for="issue in batchDetail.issues" :key="issue.id" class="batch-issue-card">
            <div class="batch-issue-card-head">
              <div class="batch-issue-title">{{ issue.inspection_table_name || '未命名检查表' }}</div>
              <div class="batch-issue-id">问题 #{{ issue.id }}</div>
            </div>
            <div class="batch-issue-desc">{{ issue.description || '暂无问题描述' }}</div>
            <div class="batch-issue-image-wrap">
              <img v-if="issue.issue_photo" :src="resolveImage(issue.issue_photo)" class="batch-issue-image"
                alt="问题照片" />
              <div v-else class="batch-issue-image-empty">暂无问题照片</div>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import axios from 'axios'
import SignaturePad from 'signature_pad'

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
const currentRole = ref(localStorage.getItem('role') || localStorage.getItem('user_role') || '')
const isSupervisorLike = computed(() => currentRole.value === 'root' || currentRole.value === 'supervisor')

const detectMobileViewport = () => {
  const ua = navigator.userAgent || ''
  const mobileUa = /Android|iPhone|iPad|iPod|Mobile/i.test(ua)
  const coarsePointer = window.matchMedia('(pointer: coarse)').matches
  const narrowScreen = window.innerWidth <= 1024
  return mobileUa || (coarsePointer && narrowScreen)
}

const isMobileView = ref(detectMobileViewport())
const isLandscapeMobile = ref(window.innerWidth > window.innerHeight)
const signatureCanvasRef = ref(null)
const signaturePadInstance = ref(null)
const visualViewportRef = ref(window.visualViewport || null)

const batchDetail = ref({
  visible: false,
  loading: false,
  error: '',
  inspection: null,
  issues: []
})

const signatureDialog = ref({
  visible: false,
  submitting: false,
  error: '',
  record: null
})

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

const groupedInspectionGroups = computed(() => {
  const batchMap = new Map()

  filteredData.value.forEach((item) => {
    const batchKey = String(item.batch_id || `${item.date || ''}__${item.station || ''}`)
    if (!batchMap.has(batchKey)) {
      batchMap.set(batchKey, {
        batchKey,
        batchId: item.batch_id,
        date: item.date,
        station: item.station,
        records: [],
        batchIssueCount: 0,
        batchResult: '正常',
        signedCount: 0,
        rowspan: 0
      })
    }

    const batch = batchMap.get(batchKey)
    batch.records.push(item)
    if (item.sign_status === '已签名确认') {
      batch.signedCount += 1
    }
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

const resolveImage = (path) => {
  const value = String(path || '').trim()
  if (!value) return ''
  if (value.startsWith('http://') || value.startsWith('https://') || value.startsWith('blob:') || value.startsWith('data:')) {
    return value
  }
  if (value.startsWith('/storage/')) {
    return value
  }
  if (value.startsWith('/')) {
    return `/storage${value}`
  }
  return `/storage/${value}`
}

const openInspectionDetail = async (record) => {
  if (!record?.id) {
    batchDetail.value = {
      visible: true,
      loading: false,
      error: '当前检查表缺少巡检记录编号，无法查看详情。',
      inspection: record || null,
      issues: []
    }
    return
  }

  batchDetail.value = {
    visible: true,
    loading: true,
    error: '',
    inspection: record,
    issues: []
  }

  try {
    const userId = localStorage.getItem('user_id') || ''
    const response = await axios.get(`/api/inspections/${record.id}/issues`, {
      params: { user_id: userId }
    })
    batchDetail.value.loading = false
    batchDetail.value.inspection = response.data?.inspection || record
    batchDetail.value.issues = response.data?.issues || []
  } catch (error) {
    batchDetail.value.loading = false
    batchDetail.value.error = error?.response?.data?.error || '加载本表问题失败。'
    batchDetail.value.issues = []
  }
}

const closeBatchDetail = () => {
  batchDetail.value = {
    visible: false,
    loading: false,
    error: '',
    inspection: null,
    issues: []
  }
}

const getSignatureCanvas = () => signatureCanvasRef.value

const initSignaturePad = () => {
  const canvas = getSignatureCanvas()
  if (!canvas) return

  const existingInstance = signaturePadInstance.value
  const existingData = existingInstance && !existingInstance.isEmpty()
    ? existingInstance.toData()
    : null

  if (existingInstance) {
    existingInstance.off()
  }

  const ratio = Math.max(window.devicePixelRatio || 1, 1)
  const rect = canvas.getBoundingClientRect()
  const width = Math.max(Math.round(rect.width || 0), 1)
  const height = Math.max(Math.round(rect.height || 0), 1)

  canvas.width = width * ratio
  canvas.height = height * ratio

  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.scale(ratio, ratio)

  signaturePadInstance.value = new SignaturePad(canvas, {
    minWidth: 1.2,
    maxWidth: 2.8,
    penColor: '#0f172a',
    backgroundColor: 'rgba(255,255,255,0)'
  })

  signaturePadInstance.value.onBegin = () => {
    if (signatureDialog.value) {
      signatureDialog.value.error = ''
    }
  }

  if (existingData && existingData.length) {
    signaturePadInstance.value.fromData(existingData)
  }
}


const handleViewportResize = () => {
  isMobileView.value = detectMobileViewport()
  isLandscapeMobile.value = window.innerWidth > window.innerHeight
}

const openSignatureDialog = async (record) => {
  signatureDialog.value = {
    visible: true,
    submitting: false,
    error: '',
    record
  }

  await nextTick()
}

const closeSignatureDialog = () => {
  if (signaturePadInstance.value) {
    signaturePadInstance.value.off()
  }
  signaturePadInstance.value = null
  signatureDialog.value = {
    visible: false,
    submitting: false,
    error: '',
    record: null
  }
}

const clearSignature = () => {
  if (signaturePadInstance.value) {
    signaturePadInstance.value.clear()
  }
  if (signatureDialog.value) {
    signatureDialog.value.error = ''
  }
}

const submitInspectionSignature = async () => {
  const record = signatureDialog.value.record
  if (!record?.id) {
    signatureDialog.value.error = '当前检查表缺少巡检记录编号，无法提交签名。'
    return
  }

  if (!signaturePadInstance.value || signaturePadInstance.value.isEmpty()) {
    signatureDialog.value.error = '请先完成站经理签名。'
    return
  }

  if (isMobileView.value && !isLandscapeMobile.value) {
    signatureDialog.value.error = '请先将手机横屏后再完成签名。'
    return
  }

  try {
    signatureDialog.value.submitting = true
    signatureDialog.value.error = ''

    const userId = localStorage.getItem('user_id') || ''
    const dataUrl = signaturePadInstance.value.toDataURL('image/png')
    const blob = await fetch(dataUrl).then((res) => res.blob())
    const formData = new FormData()
    formData.append('user_id', userId)
    formData.append('signed_name', `${record.station || '站点'}站经理`)
    formData.append('signature', new File([blob], 'signature.png', { type: 'image/png' }))

    await axios.post(`/api/inspections/${record.id}/sign`, formData)
    closeSignatureDialog()
    await fetchInspections()
  } catch (error) {
    signatureDialog.value.error = error?.response?.data?.error || '提交签名失败。'
  } finally {
    signatureDialog.value.submitting = false
  }
}

const totalPage = computed(() => Math.max(1, Math.ceil(groupedInspectionGroups.value.length / pageSize.value)))

const paginatedInspectionGroups = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return groupedInspectionGroups.value.slice(start, start + pageSize.value)
})

watch([filters, pageSize], () => {
  page.value = 1
}, { deep: true })

watch(totalPage, (value) => {
  if (page.value > value) {
    page.value = value
  }
})

watch(
  () => [signatureDialog.value.visible, isLandscapeMobile.value, isMobileView.value],
  async ([visible, landscape, mobile]) => {
    if (!visible) return
    await nextTick()
    if (!mobile || landscape) {
      initSignaturePad()
    }
  }
)

watch(
  () => signatureDialog.value.visible,
  (visible) => {
    document.body.style.overflow = visible ? 'hidden' : ''
    document.documentElement.style.overflow = visible ? 'hidden' : ''
  }
)

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

const handleVisualViewportChange = () => {
  handleViewportResize()
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('resize', handleViewportResize)
  visualViewportRef.value?.addEventListener('resize', handleVisualViewportChange)
  fetchInspections()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('resize', handleViewportResize)
  visualViewportRef.value?.removeEventListener('resize', handleVisualViewportChange)
  if (signaturePadInstance.value) {
    signaturePadInstance.value.off()
  }
  signaturePadInstance.value = null
  document.body.style.overflow = ''
  document.documentElement.style.overflow = ''
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

.btn-primary {
  border-color: #1d4ed8;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #fff;
  font-weight: 700;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.2);
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
}

.signature-action-btn {
  width: 100%;
  min-width: 220px;
  min-height: 44px;
  white-space: normal;
  line-height: 1.5;
  padding: 10px 14px;
}

.batch-action-btn {
  width: 100%;
  min-width: 96px;
  white-space: normal;
  line-height: 1.5;
  padding: 10px 12px;
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

.mobile-signature-box {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  background: #f8fafc;
}

.mobile-signature-label {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  margin-bottom: 10px;
}

.mobile-signature-time {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
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
  min-width: 1120px;
  border-collapse: collapse;
}

.records-table th,
.records-table td {
  border: 1px solid #e5e7eb;
  padding: 12px 14px;
  text-align: left;
  vertical-align: middle;
  font-size: 14px;
  color: #111827;
  word-break: break-word;
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
  text-align: left;
}

.batch-action-cell,
.batch-signature-cell {
  vertical-align: middle;
  text-align: left;
}

.batch-action-cell {
  min-width: 150px;
}

.batch-signature-cell {
  min-width: 260px;
}

.signature-preview-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.signature-preview-image {
  width: 220px;
  max-width: 100%;
  height: 88px;
  object-fit: contain;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #dbe4ee;
  border-radius: 12px;
  padding: 8px;
  box-sizing: border-box;
}

.signature-preview-time {
  font-size: 12px;
  color: #64748b;
  line-height: 1.6;
}

.signature-status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.4;
}

.signature-status-badge.success {
  background: #ecfdf5;
  color: #15803d;
}

.signature-status-badge.pending {
  background: #eff6ff;
  color: #1d4ed8;
}

.signature-dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.signature-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
  align-items: stretch;
}

.signature-side-card {
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.signature-side-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
}

.signature-side-desc {
  font-size: 13px;
  color: #475569;
  line-height: 1.8;
}

.signature-side-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.7;
}

.signature-pad-card-landscape {
  min-width: 0;
}

.signature-pad-wrap-landscape {
  min-height: 0;
}

.signature-canvas-landscape {
  height: 300px;
}

.signature-dialog {
  width: min(860px, 100%);
  max-height: min(88vh, 920px);
  padding: 24px;
  overflow: auto;
}


.signature-pad-card {
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #fff;
  padding: 18px;
}

.signature-pad-head {
  margin-bottom: 14px;
}


.signature-pad-wrap {
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  overflow: hidden;
}

.signature-canvas {
  display: block;
  width: 100%;
  height: 240px;
  touch-action: none;
  cursor: crosshair;
}

.signature-pad-actions {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.signature-error {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
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

.batch-detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.46);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 1200;
}

.batch-detail-dialog {
  width: min(1040px, 100%);
  max-height: min(88vh, 920px);
  padding: 28px;
  overflow: auto;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.batch-detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
  padding-bottom: 18px;
  border-bottom: 1px solid #e5edf5;
}

.batch-detail-kicker {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 10px;
}

.batch-detail-header h3 {
  margin: 0;
  font-size: 30px;
  line-height: 1.25;
  color: #0f172a;
}

.batch-detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  margin-top: 12px;
  color: #475569;
  font-size: 13px;
}

.batch-detail-meta span {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eef4ff;
  border: 1px solid #dbe7ff;
}

.batch-detail-empty {
  padding: 28px 12px;
  text-align: center;
  color: #64748b;
  font-size: 14px;
}

.batch-issue-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 18px;
}

.batch-issue-card {
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #ffffff;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.batch-issue-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.batch-issue-id {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.batch-issue-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.6;
}

.batch-issue-desc {
  font-size: 14px;
  color: #334155;
  line-height: 1.8;
  white-space: normal;
  word-break: break-word;
  min-height: 78px;
}

.batch-issue-image-wrap {
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

.batch-issue-image {
  display: block;
  width: auto;
  max-width: 100%;
  height: auto;
  max-height: 360px;
  object-fit: contain;
  background: #fff;
}

.batch-issue-image-empty {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 13px;
}

/* Mobile signature board normalized styles */
.mobile-signature-board {
  width: 100vw;
  height: 100dvh;
  height: 100svh;
  max-height: 100dvh;
  max-height: 100svh;
  border-radius: 0;
  padding-top: max(10px, env(safe-area-inset-top));
  padding-right: max(10px, env(safe-area-inset-right));
  padding-bottom: max(10px, env(safe-area-inset-bottom));
  padding-left: max(10px, env(safe-area-inset-left));
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
  position: fixed;
  inset: 0;
  z-index: 1300;
  overscroll-behavior: contain;
  box-sizing: border-box;
}

.mobile-signature-board-top {
  display: none;
}

.mobile-signature-board-title {
  display: none;
}

.mobile-signature-close {
  display: none;
}

.mobile-signature-orientation-overlay .mobile-signature-close {
  display: inline-flex;
  width: auto;
  min-width: 88px;
}


.mobile-signature-canvas-wrap {
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  overflow: hidden;
  min-height: 0;
  height: 100%;
  touch-action: none;
}

.mobile-signature-canvas {
  display: block;
  width: 100%;
  height: 100%;
  min-height: 0;
  max-height: none;
  touch-action: none;
}

.mobile-signature-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 76px;
  gap: 10px;
  align-items: stretch;
  overflow: hidden;
}

.mobile-signature-rail {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
}

.mobile-signature-icon-btn {
  width: 100%;
  flex: 1;
  min-height: 0;
  border: none;
  border-radius: 18px;
  font-size: 28px;
  font-weight: 800;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.14);
}

.mobile-signature-icon-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.mobile-signature-confirm {
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
}

.mobile-signature-reset {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
}

.mobile-signature-close-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.mobile-signature-error {
  margin-top: 0;
}

.mobile-signature-actions {
  display: none;
}

.signature-pad-head-minimal {
  display: none;
  margin: 0;
  padding: 0;
}

.mobile-signature-orientation-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 280px;
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 20px;
  box-sizing: border-box;
}

.mobile-signature-orientation-overlay .btn {
  width: auto;
  min-width: 96px;
}

.mobile-signature-orientation-overlay-inner {
  width: 100%;
  max-width: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
}

.mobile-signature-orientation-overlay-inner .mobile-signature-close {
  margin-top: 6px;
}

.mobile-signature-orientation-icon {
  width: 56px;
  height: 56px;
  border-radius: 999px;
  background: #eff6ff;
  border: 1px solid #dbe7ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #1d4ed8;
  font-weight: 700;
}

.mobile-signature-orientation-title {
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
}

.mobile-signature-orientation-text {
  font-size: 14px;
  line-height: 1.8;
  color: #475569;
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

  .signature-preview-image {
    width: 100%;
    height: 82px;
  }

  .batch-detail-overlay {
    padding: 0;
  }

  .batch-detail-dialog {
    width: min(96vw, 960px);
    padding: 16px;
    max-height: 92vh;
  }

  .batch-detail-header {
    flex-direction: column;
    align-items: stretch;
  }

  .batch-issue-list {
    grid-template-columns: 1fr;
  }

  .batch-detail-meta span {
    width: 100%;
    justify-content: flex-start;
  }

  .signature-dialog {
    width: min(96vw, 960px);
    padding: 14px;
    max-height: 92vh;
  }

  .mobile-signature-board {
    width: 100vw;
    height: 100dvh;
    height: 100svh;
    max-height: 100dvh;
    max-height: 100svh;
    border-radius: 0;
    padding-top: max(8px, env(safe-area-inset-top));
    padding-right: max(8px, env(safe-area-inset-right));
    padding-bottom: max(8px, env(safe-area-inset-bottom));
    padding-left: max(8px, env(safe-area-inset-left));
    gap: 8px;
  }

  .mobile-signature-canvas {
    height: 100%;
    min-height: 0;
    max-height: none;
  }

  .mobile-signature-canvas-wrap {
    height: 100%;
    min-height: 0;
  }

  .mobile-signature-layout {
    grid-template-columns: minmax(0, 1fr) 68px;
    gap: 8px;
  }

  .mobile-signature-icon-btn {
    border-radius: 16px;
    font-size: 24px;
  }
}
</style>
