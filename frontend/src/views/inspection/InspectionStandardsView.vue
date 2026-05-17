<template>
  <div v-if="hasPermission" class="page-shell standards-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>巡检规范库</h2>
        <p class="page-desc">业务督导中心部门通过整理归纳外部规范库，从而自建形成的内部巡检规范库。</p>
      </div>
      <div class="header-badges">
        <span class="status-pill info">内部规范 {{ filteredStandards.length }}</span>
        <span class="status-pill success">已挂载 {{ linkedCount }}</span>
      </div>
    </div>

    <div class="filter-card card-surface">
      <div class="filter-card-head">
        <div>
          <strong>筛选规范</strong>
          <span>导出会使用当前筛选后的全部内部规范</span>
        </div>
        <div class="filter-result-chip">当前 {{ filteredStandards.length }} 条</div>
      </div>

      <div class="filter-layout">
        <label class="filter-item keyword-filter">
          <span>关键词搜索</span>
          <input v-model.trim="keyword" type="search" placeholder="搜索内部规范ID、字段内容或外部规范ID" />
        </label>

        <div v-if="filterableFields.length" class="filter-fields">
          <label v-for="field in filterableFields" :key="field.field_key" class="filter-item">
            <span>{{ field.field_label }}</span>
            <select v-model="fieldFilters[field.field_key]">
              <option :value="FILTER_ALL_VALUE">全部</option>
              <option v-for="value in getFieldFilterOptions(field.field_key)" :key="value" :value="value">
                {{ value }}
              </option>
            </select>
          </label>
        </div>

        <div class="filter-actions">
          <button v-if="hasActiveFieldFilters" class="btn btn-light" type="button" @click="clearFieldFilters">
            清空筛选
          </button>
          <button class="btn btn-primary" type="button" :disabled="loading || exporting || !filteredStandards.length"
            @click="exportFilteredStandards">
            {{ exporting ? '生成PDF中...' : '导出数据' }}
          </button>
          <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchStandards">
            {{ loading ? '刷新中...' : '刷新数据' }}
          </button>
        </div>
      </div>
    </div>

    <div class="content-grid">
      <section class="list-card card-surface">
        <div class="list-toolbar">
          <div>
            <div class="list-count">共 {{ filteredStandards.length }} 条内部规范</div>
            <div class="list-page-info">第 {{ page }} / {{ totalPages }} 页</div>
          </div>
        </div>

        <div class="standard-list">
          <button v-for="item in paginatedStandards" :key="item.id" type="button" class="standard-card"
            :class="{ active: activeStandard?.id === item.id }" @click="selectStandard(item)">
            <div class="standard-card-top">
              <span class="internal-code">{{ item.internal_standard_id }}</span>
              <span :class="['status-pill', item.linked_externals?.length ? 'success' : 'neutral']">
                {{ item.linked_externals?.length ? `关联 ${item.linked_externals.length}` : '未关联外部规范' }}
              </span>
            </div>
            <div class="standard-card-fields">
              <span v-for="field in shortInternalFields" :key="field.field_key" class="standard-field-chip">
                <em>{{ field.field_label }}</em>
                <strong>{{ getFieldValue(item, field.field_key) || '-' }}</strong>
              </span>
            </div>
            <p v-if="getLongFieldPreview(item)" class="standard-long-preview">{{ getLongFieldPreview(item) }}</p>
            <p v-else-if="!shortInternalFields.length" class="standard-long-preview">暂无字段内容</p>
          </button>

          <div v-if="!loading && !filteredStandards.length" class="empty-block">
            暂无内部巡检规范。
          </div>
          <div v-if="loading" class="empty-block">正在加载内部巡检规范...</div>
        </div>

        <div v-if="filteredStandards.length" class="pagination-bar">
          <button class="btn btn-secondary btn-sm" type="button" :disabled="page <= 1" @click="goToPage(1)">首页</button>
          <button class="btn btn-secondary btn-sm" type="button" :disabled="page <= 1" @click="goToPage(page - 1)">上一页</button>
          <button v-for="item in visiblePageItems" :key="item.key" type="button" class="page-btn"
            :class="{ active: item.value === page }" :disabled="item.type === 'ellipsis'" @click="goToPage(item.value)">
            {{ item.type === 'ellipsis' ? '...' : item.value }}
          </button>
          <button class="btn btn-secondary btn-sm" type="button" :disabled="page >= totalPages" @click="goToPage(page + 1)">下一页</button>
          <button class="btn btn-secondary btn-sm" type="button" :disabled="page >= totalPages" @click="goToPage(totalPages)">末页</button>
        </div>
      </section>

      <section class="detail-card card-surface">
        <template v-if="activeStandard">
          <div class="detail-head">
            <div>
              <div class="section-kicker">内部规范详情</div>
              <h3>{{ activeStandard.internal_standard_id }}</h3>
              <p>{{ formatFieldSummary(activeStandard) }}</p>
            </div>
          </div>

          <div class="detail-block">
            <strong>内部规范字段</strong>
            <div class="internal-field-grid">
              <div v-for="field in internalFields" :key="field.field_key" class="internal-field-item"
                :class="{ long: field.is_long_text }">
                <span>{{ field.field_label }}</span>
                <strong>{{ getFieldValue(activeStandard, field.field_key) || '-' }}</strong>
              </div>
            </div>
          </div>

          <div class="detail-block">
            <strong>关联外部规范</strong>
            <div v-if="activeStandard.linked_externals?.length" class="external-link-list">
              <article v-for="link in activeStandard.linked_externals" :key="link.external_standard_id"
                class="external-link-card">
                <div>
                  <span>外部规范ID {{ link.external_standard_id }}</span>
                  <strong>{{ link.inspection_table_name || '未知检查表' }}</strong>
                </div>
                <p>{{ link.standard_detail_text || '暂无外部规范详情。' }}</p>
              </article>
            </div>
            <div v-else class="empty-inline">这条内部规范暂未挂载外部规范。</div>
          </div>
        </template>

        <div v-else class="empty-block detail-empty">
          请选择一条内部巡检规范查看详情。
        </div>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="mobileDialogVisible && activeStandard" class="mobile-detail-modal" @click.self="mobileDialogVisible = false">
        <section class="mobile-detail-sheet card-surface">
          <div class="modal-handle"></div>
          <button class="modal-close" type="button" @click="mobileDialogVisible = false">×</button>
          <div class="section-kicker">内部规范详情</div>
          <h3>{{ activeStandard.internal_standard_id }}</h3>
          <p class="path-line">{{ formatFieldSummary(activeStandard) }}</p>
          <div class="detail-block">
            <strong>内部规范字段</strong>
            <div class="internal-field-grid">
              <div v-for="field in internalFields" :key="field.field_key" class="internal-field-item"
                :class="{ long: field.is_long_text }">
                <span>{{ field.field_label }}</span>
                <strong>{{ getFieldValue(activeStandard, field.field_key) || '-' }}</strong>
              </div>
            </div>
          </div>
          <div class="detail-block">
            <strong>关联外部规范</strong>
            <div v-if="activeStandard.linked_externals?.length" class="external-link-list">
              <article v-for="link in activeStandard.linked_externals" :key="link.external_standard_id"
                class="external-link-card">
                <span>外部规范ID {{ link.external_standard_id }}</span>
                <strong>{{ link.inspection_table_name || '未知检查表' }}</strong>
                <p>{{ link.standard_detail_text || '暂无外部规范详情。' }}</p>
              </article>
            </div>
            <div v-else class="empty-inline">这条内部规范暂未挂载外部规范。</div>
          </div>
        </section>
      </div>
    </Teleport>
  </div>

  <div v-else class="card-surface permission-card">
    <div class="permission-icon">!</div>
    <div class="permission-title">无权限访问</div>
    <div class="permission-desc">当前账号无权访问巡检规范库。</div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

const currentRole = localStorage.getItem('user_role') || ''
let localPermissions = {}
try {
  localPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  localPermissions = {}
}

const hasPermission = currentRole === 'root' || Boolean(localPermissions.view_inspection_standards)
const FILTER_ALL_VALUE = '__ALL__'
const loading = ref(false)
const exporting = ref(false)
const standards = ref([])
const internalFields = ref([])
const activeStandard = ref(null)
const keyword = ref('')
const page = ref(1)
const pageSize = 8
const mobileDialogVisible = ref(false)
const isMobile = ref(false)
const fieldFilters = reactive({})

const linkedCount = computed(() => standards.value.filter((item) => item.linked_externals?.length).length)
const filterableFields = computed(() => internalFields.value.filter((field) => field.is_filterable))
const shortInternalFields = computed(() => internalFields.value.filter((field) => !field.is_long_text))
const longInternalFields = computed(() => internalFields.value.filter((field) => field.is_long_text))
const hasActiveFieldFilters = computed(() => {
  return filterableFields.value.some((field) => String(fieldFilters[field.field_key] || FILTER_ALL_VALUE).trim() !== FILTER_ALL_VALUE)
})

const getFieldValue = (item, fieldKey) => {
  return String(item?.field_values?.[fieldKey] ?? '').trim()
}

const formatFieldSummary = (item) => {
  const values = internalFields.value
    .map((field) => getFieldValue(item, field.field_key))
    .filter(Boolean)
  return values.length ? values.join(' / ') : '未设置字段内容'
}

const getPrimaryFieldValue = (item) => {
  const firstField = internalFields.value[0]
  if (!firstField) return item?.content || ''
  return getFieldValue(item, firstField.field_key)
}

const getLongFieldPreview = (item) => {
  const values = longInternalFields.value
    .map((field) => {
      const value = getFieldValue(item, field.field_key)
      return value ? `${field.field_label}：${value}` : ''
    })
    .filter(Boolean)
  return values.join('\n')
}

const filteredStandards = computed(() => {
  const text = keyword.value.toLowerCase()
  return standards.value.filter((item) => {
    const keywordMatched = !text || [
      item.internal_standard_id,
      formatFieldSummary(item),
      ...internalFields.value.map((field) => getFieldValue(item, field.field_key)),
      ...(item.linked_externals || []).map((link) => `${link.external_standard_id} ${link.inspection_table_name} ${link.standard_detail_text}`)
    ].join(' ').toLowerCase().includes(text)
    if (!keywordMatched) return false

    return filterableFields.value.every((field) => {
      const filterValue = String(fieldFilters[field.field_key] || FILTER_ALL_VALUE).trim()
      return filterValue === FILTER_ALL_VALUE || getFieldValue(item, field.field_key) === filterValue
    })
  })
})

const getFieldFilterOptions = (fieldKey) => {
  return [...new Set(
    standards.value
      .map((item) => getFieldValue(item, fieldKey))
      .filter(Boolean)
  )].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

const ensureFieldFilters = () => {
  const keys = new Set(filterableFields.value.map((field) => field.field_key))
  Object.keys(fieldFilters).forEach((key) => {
    if (!keys.has(key)) delete fieldFilters[key]
  })
  keys.forEach((key) => {
    if (!Object.prototype.hasOwnProperty.call(fieldFilters, key)) {
      fieldFilters[key] = FILTER_ALL_VALUE
    }
  })
}

const clearFieldFilters = () => {
  Object.keys(fieldFilters).forEach((key) => {
    fieldFilters[key] = FILTER_ALL_VALUE
  })
}

const escapeHtml = (value) => {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const htmlWithLineBreaks = (value, fallback = '-') => {
  const text = String(value ?? '').trim() || fallback
  return escapeHtml(text).replace(/\n/g, '<br>')
}

const formatExportDateTime = (date = new Date()) => {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const buildExportFilterSummary = () => {
  const parts = []
  const text = keyword.value.trim()
  if (text) parts.push(`关键词：${text}`)
  filterableFields.value.forEach((field) => {
    const value = String(fieldFilters[field.field_key] || FILTER_ALL_VALUE).trim()
    if (value && value !== FILTER_ALL_VALUE) parts.push(`${field.field_label}：${value}`)
  })
  return parts.length ? parts.join('；') : '全部'
}

const buildExportFieldItems = (item) => {
  if (!internalFields.value.length) {
    return `<div class="field-item long"><span>内部规范内容</span><strong>${htmlWithLineBreaks(item.content || formatFieldSummary(item))}</strong></div>`
  }
  return internalFields.value.map((field) => {
    const value = getFieldValue(item, field.field_key) || '-'
    return `
      <div class="field-item ${field.is_long_text ? 'long' : ''}">
        <span>${escapeHtml(field.field_label)}</span>
        <strong>${htmlWithLineBreaks(value)}</strong>
      </div>
    `
  }).join('')
}

const buildExportExternalLinks = (item) => {
  const links = item.linked_externals || []
  if (!links.length) {
    return '<span class="external-empty">未关联外部规范</span>'
  }
  return links.map((link) => `
    <span class="external-tag">
      ${escapeHtml(link.external_standard_id || '-')} · ${escapeHtml(link.inspection_table_name || '未知检查表')}
    </span>
  `).join('')
}

const buildStandardsExportDocument = () => {
  const rows = filteredStandards.value.map((item, index) => `
    <article class="standard-row">
      <div class="row-head">
        <div>
          <span class="row-index">${index + 1}</span>
          <strong>${escapeHtml(item.internal_standard_id || '-')}</strong>
        </div>
        <span>关联外部规范 ${item.linked_externals?.length || 0} 条</span>
      </div>
      <div class="field-grid">
        ${buildExportFieldItems(item)}
      </div>
      <div class="external-line">
        <em>外部规范</em>
        <div>${buildExportExternalLinks(item)}</div>
      </div>
    </article>
  `).join('')

  return `
    <main class="document">
      <header class="doc-head">
        <div>
          <h1>巡检规范库导出</h1>
          <div class="subtitle">仅导出内部规范内容；外部规范仅保留外部规范ID和检查表名称。</div>
        </div>
        <div class="meta">
          <div>导出时间：${escapeHtml(formatExportDateTime())}</div>
          <div>规范数量：${filteredStandards.value.length} 条</div>
        </div>
      </header>
      <div class="filter-line">筛选条件：${escapeHtml(buildExportFilterSummary())}</div>
      ${rows || '<div class="filter-line">当前筛选条件下暂无内部规范。</div>'}
    </main>
  `
}

const buildExportStyles = () => `
  * { box-sizing: border-box; }
  .document {
    width: 794px;
    padding: 30px;
    color: #111827;
    background: #ffffff;
    font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
    font-size: 9.5px;
    line-height: 1.45;
  }
  .doc-head {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 14px;
    padding-bottom: 6px;
    margin-bottom: 7px;
    border-bottom: 1.5px solid #0f766e;
  }
  h1 {
    margin: 0 0 3px;
    font-size: 18px;
    letter-spacing: 0.04em;
  }
  .subtitle,
  .meta {
    color: #64748b;
  }
  .meta {
    text-align: right;
    white-space: nowrap;
  }
  .filter-line {
    margin: 0 0 7px;
    padding: 5px 7px;
    border: 1px solid #dbe4ee;
    border-radius: 6px;
    background: #f8fafc;
    color: #334155;
  }
  .standard-row {
    break-inside: avoid;
    margin-bottom: 5px;
    padding: 6px 7px;
    border: 1px solid #cbd5e1;
    border-radius: 7px;
  }
  .row-head {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding-bottom: 4px;
    margin-bottom: 5px;
    border-bottom: 1px solid #e2e8f0;
  }
  .row-head strong {
    color: #0f766e;
    font-size: 11px;
  }
  .row-head span:last-child {
    color: #64748b;
  }
  .row-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    margin-right: 5px;
    border-radius: 999px;
    background: #ecfeff;
    color: #0f766e;
    font-weight: 800;
  }
  .field-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 3px 8px;
  }
  .field-item {
    min-width: 0;
    display: flex;
    gap: 4px;
    align-items: flex-start;
    padding: 2px 0;
  }
  .field-item.long {
    grid-column: 1 / -1;
  }
  .field-item span {
    flex: 0 0 auto;
    max-width: 72px;
    color: #64748b;
    font-weight: 700;
  }
  .field-item strong {
    min-width: 0;
    color: #111827;
    font-weight: 500;
    word-break: break-word;
  }
  .external-line {
    display: grid;
    grid-template-columns: 52px minmax(0, 1fr);
    gap: 6px;
    margin-top: 5px;
    padding-top: 5px;
    border-top: 1px dashed #cbd5e1;
  }
  .external-line em {
    color: #64748b;
    font-style: normal;
    font-weight: 800;
  }
  .external-tag,
  .external-empty {
    display: inline-block;
    margin: 0 4px 3px 0;
    padding: 2px 5px;
    border-radius: 999px;
    background: #f1f5f9;
    color: #334155;
    white-space: nowrap;
  }
  .external-empty {
    color: #94a3b8;
  }
`

const buildPdfBlobFromExportDocument = async () => {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
    import('html2canvas'),
    import('jspdf')
  ])
  const host = document.createElement('div')
  host.style.position = 'fixed'
  host.style.left = '-10000px'
  host.style.top = '0'
  host.style.width = '794px'
  host.style.background = '#fff'
  host.style.zIndex = '-1'
  host.innerHTML = `<style>${buildExportStyles()}</style>${buildStandardsExportDocument()}`
  document.body.appendChild(host)

  try {
    if (document.fonts?.ready) {
      await document.fonts.ready
    }
    const documentNode = host.querySelector('.document')
    if (!documentNode) {
      throw new Error('PDF 渲染容器初始化失败。')
    }
    const canvas = await html2canvas(documentNode, {
      backgroundColor: '#ffffff',
      scale: 2,
      useCORS: true,
      windowWidth: 794
    })
    const pdf = new jsPDF({ orientation: 'p', unit: 'pt', format: 'a4', compress: true })
    const pageWidth = pdf.internal.pageSize.getWidth()
    const pageHeight = pdf.internal.pageSize.getHeight()
    const pageCanvasHeight = Math.floor(canvas.width * (pageHeight / pageWidth))
    const pageCanvas = document.createElement('canvas')
    const pageContext = pageCanvas.getContext('2d')
    if (!pageContext) {
      throw new Error('PDF 渲染容器初始化失败。')
    }
    pageCanvas.width = canvas.width

    let sourceY = 0
    let pageIndex = 0
    while (sourceY < canvas.height) {
      const sliceHeight = Math.min(pageCanvasHeight, canvas.height - sourceY)
      pageCanvas.height = sliceHeight
      pageContext.clearRect(0, 0, pageCanvas.width, pageCanvas.height)
      pageContext.fillStyle = '#ffffff'
      pageContext.fillRect(0, 0, pageCanvas.width, pageCanvas.height)
      pageContext.drawImage(canvas, 0, sourceY, canvas.width, sliceHeight, 0, 0, canvas.width, sliceHeight)
      const imageData = pageCanvas.toDataURL('image/jpeg', 0.92)
      const imageHeight = (sliceHeight / canvas.width) * pageWidth
      if (pageIndex > 0) pdf.addPage()
      pdf.addImage(imageData, 'JPEG', 0, 0, pageWidth, imageHeight)
      sourceY += sliceHeight
      pageIndex += 1
    }

    return pdf.output('blob')
  } finally {
    host.remove()
  }
}

const exportFilteredStandards = async () => {
  if (exporting.value || loading.value || !filteredStandards.value.length) return
  const previewWindow = window.open('', '_blank')
  if (!previewWindow) {
    window.alert('浏览器阻止了导出窗口，请允许弹窗后再打开 PDF。')
    return
  }

  try {
    exporting.value = true
    previewWindow.document.open()
    previewWindow.document.write('<!doctype html><meta charset="utf-8"><title>正在生成PDF</title><body style="font-family: sans-serif; padding: 32px; color: #0f172a;">正在生成巡检规范库 PDF，请稍候...</body>')
    previewWindow.document.close()

    const pdfBlob = await buildPdfBlobFromExportDocument()
    const pdfUrl = URL.createObjectURL(pdfBlob)
    previewWindow.location.href = pdfUrl
    setTimeout(() => URL.revokeObjectURL(pdfUrl), 120000)
  } catch {
    if (previewWindow && !previewWindow.closed) {
      previewWindow.document.open()
      previewWindow.document.write('<!doctype html><meta charset="utf-8"><title>导出失败</title><body style="font-family: sans-serif; padding: 32px;">导出失败，请稍后重试。</body>')
      previewWindow.document.close()
    }
    window.alert('导出失败，请稍后重试。')
  } finally {
    exporting.value = false
  }
}

const totalPages = computed(() => Math.max(1, Math.ceil(filteredStandards.value.length / pageSize)))

const visiblePageItems = computed(() => {
  const total = totalPages.value
  const current = page.value
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => ({ type: 'page', value: index + 1, key: `p-${index + 1}` }))
  }
  const pages = new Set([1, total, current, current - 1, current + 1])
  const sorted = [...pages].filter((item) => item >= 1 && item <= total).sort((a, b) => a - b)
  const result = []
  sorted.forEach((value, index) => {
    const previous = sorted[index - 1]
    if (index > 0 && value - previous > 1) result.push({ type: 'ellipsis', key: `e-${previous}-${value}` })
    result.push({ type: 'page', value, key: `p-${value}` })
  })
  return result
})

const paginatedStandards = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredStandards.value.slice(start, start + pageSize)
})

const goToPage = (target) => {
  const next = Number.parseInt(target, 10)
  if (!Number.isFinite(next)) return
  page.value = Math.min(Math.max(next, 1), totalPages.value)
}

const selectStandard = (item) => {
  activeStandard.value = item
  if (isMobile.value) mobileDialogVisible.value = true
}

const syncViewport = () => {
  isMobile.value = window.matchMedia('(max-width: 768px)').matches
}

const fetchStandards = async () => {
  if (!hasPermission) return
  try {
    loading.value = true
    const response = await axios.get('/api/inspection-internal-standards', {
      params: { keyword: keyword.value, _ts: Date.now() }
    })
    internalFields.value = response.data?.fields || []
    ensureFieldFilters()
    standards.value = response.data?.items || []
    if (!activeStandard.value || !standards.value.some((item) => item.id === activeStandard.value.id)) {
      activeStandard.value = standards.value[0] || null
    }
  } finally {
    loading.value = false
  }
}

watch(keyword, () => {
  page.value = 1
})

watch(fieldFilters, () => {
  page.value = 1
}, { deep: true })

watch(filteredStandards, () => {
  if (page.value > totalPages.value) page.value = totalPages.value
})

onMounted(() => {
  syncViewport()
  window.addEventListener('resize', syncViewport)
  fetchStandards()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncViewport)
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

.page-header,
.filter-card,
.list-card,
.detail-card {
  padding: 22px;
}

.page-header {
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
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 900;
  margin-bottom: 12px;
}

.page-header h2,
.detail-head h3 {
  margin: 0;
  color: #0f172a;
}

.page-header h2 {
  font-size: 34px;
}

.page-desc,
.detail-head p,
.standard-card p,
.detail-block p,
.external-link-card p {
  color: #64748b;
  line-height: 1.8;
  white-space: pre-line;
}

.header-badges,
.pagination-bar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.list-card .pagination-bar {
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid #e5edf5;
  align-items: center;
}

.filter-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background:
    radial-gradient(circle at top right, rgba(20, 184, 166, 0.1), transparent 34%),
    rgba(255, 255, 255, 0.96);
}

.filter-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid #e5edf5;
}

.filter-card-head strong {
  display: block;
  color: #0f172a;
  font-size: 18px;
  font-weight: 900;
  margin-bottom: 4px;
}

.filter-card-head span {
  color: #64748b;
  font-size: 13px;
}

.filter-result-chip {
  flex: 0 0 auto;
  padding: 8px 12px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 13px;
  font-weight: 900;
}

.filter-layout {
  display: grid;
  grid-template-columns: minmax(260px, 1.35fr) minmax(320px, 2fr) auto;
  gap: 14px;
  align-items: end;
}

.filter-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.keyword-filter input {
  min-width: 0;
}

.filter-item span,
.detail-block strong {
  color: #374151;
  font-size: 14px;
  font-weight: 900;
}

.filter-item input,
.filter-item select {
  height: 44px;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 0 14px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(320px, 430px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.list-toolbar {
  margin-bottom: 14px;
}

.list-count {
  color: #0f172a;
  font-weight: 900;
}

.list-page-info,
.path-line,
.empty-inline {
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.standard-list,
.external-link-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.standard-card {
  width: 100%;
  border: 1px solid #e5edf5;
  border-radius: 18px;
  background: #fff;
  padding: 15px;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;
}

.standard-card:hover,
.standard-card.active {
  border-color: #5eead4;
  background: #f0fdfa;
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.12);
}

.standard-card-top,
.detail-head,
.external-link-card div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.standard-card-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.standard-field-chip {
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid #e5edf5;
  border-radius: 13px;
  background: #f8fafc;
}

.standard-field-chip em {
  display: block;
  color: #64748b;
  font-size: 11px;
  font-style: normal;
  font-weight: 900;
  margin-bottom: 4px;
}

.standard-field-chip strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.standard-long-preview {
  margin: 12px 0 0;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
  line-height: 1.75;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.internal-code {
  color: #0f766e;
  font-size: 16px;
  font-weight: 900;
}

.detail-block {
  padding: 16px;
  border: 1px solid #e5edf5;
  border-radius: 18px;
  background: #f8fafc;
  margin-top: 14px;
}

.detail-block > strong {
  display: block;
  margin-bottom: 13px;
}

.internal-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.internal-field-item {
  padding: 11px 12px;
  border: 1px solid #e5edf5;
  border-radius: 14px;
  background: #fff;
}

.internal-field-item.long {
  grid-column: 1 / -1;
}

.internal-field-item span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
  margin-bottom: 5px;
}

.internal-field-item strong {
  color: #0f172a;
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-line;
  word-break: break-word;
}

.external-link-card {
  padding: 14px;
  border: 1px solid #dbe4ee;
  border-radius: 16px;
  background: #fff;
}

.external-link-list {
  gap: 14px;
}

.external-link-card span {
  color: #0f766e;
  font-weight: 900;
}

.external-link-card strong {
  color: #0f172a;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 900;
}

.status-pill.info {
  background: #ecfeff;
  color: #0f766e;
}

.status-pill.success {
  background: #ecfdf5;
  color: #15803d;
}

.status-pill.neutral {
  background: #f1f5f9;
  color: #475569;
}

.btn,
.page-btn {
  min-height: 40px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  font-weight: 800;
  cursor: pointer;
}

.btn-secondary:hover:not(:disabled),
.btn-light:hover:not(:disabled),
.page-btn:hover:not(:disabled),
.page-btn.active {
  border-color: #0f766e;
  background: #f0fdfa;
  color: #0f766e;
}

.btn-light {
  background: #f8fafc;
}

.btn-primary {
  border-color: #0f766e;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #fff;
  box-shadow: 0 10px 22px rgba(20, 184, 166, 0.18);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 14px 26px rgba(20, 184, 166, 0.24);
}

.btn-primary:disabled {
  opacity: 0.58;
  cursor: not-allowed;
  box-shadow: none;
}

.btn-sm {
  min-height: 34px;
  padding: 0 11px;
  font-size: 12px;
}

.empty-block {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  text-align: center;
}

.permission-card {
  min-height: 320px;
  margin: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 32px;
}

.permission-icon {
  width: 56px;
  height: 56px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ecfeff;
  color: #0f766e;
  font-size: 28px;
  font-weight: 900;
  margin-bottom: 14px;
}

.permission-title {
  color: #0f172a;
  font-size: 22px;
  font-weight: 900;
}

.permission-desc {
  color: #64748b;
}

.mobile-detail-modal {
  position: fixed;
  inset: 0;
  z-index: 1800;
  display: none;
  align-items: center;
  justify-content: center;
  padding: 14px;
  background: rgba(15, 23, 42, 0.48);
  backdrop-filter: blur(10px);
}

.mobile-detail-sheet {
  position: relative;
  width: 100%;
  max-width: 560px;
  max-height: 86vh;
  overflow: auto;
  padding: 18px;
  border-radius: 26px;
}

.modal-handle {
  width: 44px;
  height: 5px;
  border-radius: 999px;
  margin: 0 auto 14px;
  background: #cbd5e1;
}

.modal-close {
  position: absolute;
  right: 16px;
  top: 14px;
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 14px;
  background: #f1f5f9;
  color: #334155;
  font-size: 26px;
}

@media (max-width: 1080px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

  .filter-layout {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .page-header,
  .filter-card,
  .standard-card-top,
  .detail-head,
  .external-link-card div {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: stretch;
  }

  .internal-field-grid {
    grid-template-columns: 1fr;
  }

  .standard-card-fields {
    grid-template-columns: 1fr;
  }

  .detail-card {
    display: none;
  }

  .mobile-detail-modal {
    display: flex;
  }

  .page-header h2 {
    font-size: 29px;
  }

  .filter-card-head {
    flex-direction: column;
  }

  .filter-result-chip {
    width: fit-content;
  }

  .filter-fields {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    width: 100%;
  }

  .filter-actions .btn {
    width: 100%;
  }
}
</style>
