<template>
  <div class="page-shell my-issues-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">巡检系统</div>
        <h2>{{ currentRole === 'station_manager' ? '我的待整改问题' : '我的待复核问题' }}</h2>
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
          {{ currentRole === 'station_manager' ? '可填写整改结果、整改说明并上传整改照片' : '可提交督导组复核结果、复核说明并上传复核照片' }}
        </div>
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
          <div class="search-select" ref="stationSelectRef">
            <input v-model="filters.station" type="text" placeholder="搜索或选择站点名称" @focus="openFilterDropdown('station')"
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

        <div class="toolbar-item">
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

        <div class="toolbar-item">
          <label>规范ID</label>
          <input v-model="filters.standardId" type="text" placeholder="搜索规范ID" />
        </div>

        <div class="toolbar-item toolbar-item-wide">
          <label>规范详情</label>
          <input v-model="filters.standardDetail" type="text" placeholder="搜索规范详情关键词" />
        </div>

      </div>

      <div class="toolbar-actions">
        <button class="btn btn-secondary" type="button" @click="resetFilters">重置筛选</button>
        <button class="btn btn-secondary" type="button" @click="fetchMyIssues" :disabled="loading">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
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
              <span class="mobile-card-category">{{ item.inspection_table_name || '暂无' }}</span>
              <span :class="statusClass(item.status)">{{ item.status }}</span>
            </div>
            <div class="mobile-card-code">规范ID：{{ item.standard_id || '暂无' }}</div>
          </div>

          <div class="mobile-card-body">
            <div class="mobile-card-row"><span>站点</span><strong>{{ item.station }}</strong></div>

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

            <template v-if="currentRole === 'supervisor'">
              <div class="mobile-card-row"><span>整改结果</span><strong>{{ item.rectification_result || '暂无' }}</strong>
              </div>
              <div class="mobile-card-row mobile-card-row-top">
                <span>整改说明</span>
                <div class="mobile-card-text">{{ item.rectification_note || '暂无' }}</div>
              </div>
            </template>
          </div>

          <div class="mobile-card-images">
            <button class="mobile-image-btn" type="button" @click="preview(resolveImage(item.issue_photo), '问题照片')">
              <img :src="resolveImage(item.issue_photo)" class="mobile-thumb" alt="问题照片" />
              <span>问题照片</span>
            </button>

            <button v-if="currentRole === 'supervisor' && item.rectification_photo" class="mobile-image-btn"
              type="button" @click="preview(resolveImage(item.rectification_photo), '站点反馈整改照片')">
              <img :src="resolveImage(item.rectification_photo)" class="mobile-thumb" alt="整改照片" />
              <span>整改照片</span>
            </button>

            <button v-if="currentRole === 'supervisor' && item.review_photo" class="mobile-image-btn" type="button"
              @click="preview(resolveImage(item.review_photo), '督导组复核照片')">
              <img :src="resolveImage(item.review_photo)" class="mobile-thumb" alt="督导组复核照片" />
              <span>复核照片</span>
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

                <th>检查表</th>
                <th>规范ID</th>
                <th>规范详情</th>
                <th>问题描述</th>

                <th>问题照片</th>
                <template v-if="currentRole === 'supervisor'">
                  <th>站经理整改结果</th>
                  <th>站点反馈整改说明</th>
                  <th>站点反馈整改照片</th>
                  <th>督导组复核照片</th>
                </template>
                <th class="nowrap-col">问题状态</th>
                <th class="nowrap-col action-col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in paginatedData" :key="item.id">
                <td>{{ item.id }}</td>
                <td>{{ item.station }}</td>

                <td>{{ item.inspection_table_name || '暂无' }}</td>
                <td>{{ item.standard_id || '暂无' }}</td>
                <td class="standard-detail-cell">
                  <div class="standard-detail-box">
                    <div class="standard-detail-preview multiline-clamp">{{ formatMultiline(item.standard_detail_text)
                      }}</div>
                    <button class="text-link-btn" type="button" @click="openStandardDetail(item)">查看详情</button>
                  </div>
                </td>
                <td class="long-text">{{ item.description }}</td>
                <td>
                  <button class="image-btn" type="button" @click="preview(resolveImage(item.issue_photo), '问题照片')">
                    <img :src="resolveImage(item.issue_photo)" class="thumb" alt="问题照片" />
                  </button>
                </td>
                <template v-if="currentRole === 'supervisor'">
                  <td>{{ item.rectification_result || '暂无' }}</td>
                  <td class="long-text">{{ item.rectification_note || '暂无' }}</td>
                  <td>
                    <button v-if="item.rectification_photo" class="image-btn" type="button"
                      @click="preview(resolveImage(item.rectification_photo), '站点反馈整改照片')">
                      <img :src="resolveImage(item.rectification_photo)" class="thumb" alt="站点反馈整改照片" />
                    </button>
                    <span v-else>暂无</span>
                  </td>
                  <td>
                    <button v-if="item.review_photo" class="image-btn" type="button"
                      @click="preview(resolveImage(item.review_photo), '督导组复核照片')">
                      <img :src="resolveImage(item.review_photo)" class="thumb" alt="督导组复核照片" />
                    </button>
                    <span v-else>暂无</span>
                  </td>
                </template>
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
                <td :colspan="currentRole === 'supervisor' ? 12 : 8" class="empty-row">
                  {{ currentRole === 'station_manager' ? '当前没有待整改问题。' : '当前没有待复核问题。' }}
                </td>
              </tr>
              <tr v-if="loading">
                <td :colspan="currentRole === 'supervisor' ? 12 : 8" class="empty-row">正在加载数据...</td>
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
            <p>{{ actionDrawer.item?.station }}｜规范ID {{ actionDrawer.item?.standard_id || '暂无' }}</p>
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
                <input id="rectification-photo-upload" class="drawer-upload-input" type="file" accept="image/*"
                  @change="handleRectificationFileChange" />
                <input id="rectification-photo-camera" class="drawer-upload-input" type="file" accept="image/*"
                  capture="environment" @change="handleRectificationFileChange" />

                <label for="rectification-photo-upload" class="drawer-upload-dropzone">
                  <div class="drawer-upload-icon">↑</div>
                  <div class="drawer-upload-title">选择或更换整改照片</div>
                  <div class="drawer-upload-desc">
                    请上传能够清晰反映整改完成情况的现场照片，建议画面完整、重点明确。
                  </div>
                  <div class="drawer-upload-trigger-group">
                    <label for="rectification-photo-camera"
                      class="drawer-upload-trigger drawer-upload-trigger-secondary">拍照上传</label>
                    <label for="rectification-photo-upload" class="drawer-upload-trigger">相册选择</label>
                  </div>
                </label>

                <div v-if="actionForm.rectificationPhotoPreview" class="drawer-image-preview-panel">
                  <img :src="actionForm.rectificationPhotoPreview" alt="整改照片预览" class="drawer-preview-thumb" />
                  <div class="drawer-preview-meta">
                    <div class="drawer-preview-title">已选择整改照片</div>
                    <div class="drawer-preview-name">{{ actionForm.rectificationPhotoFile?.name || '已上传图片' }}</div>
                    <div class="drawer-preview-actions">
                      <label for="rectification-photo-camera"
                        class="btn btn-light btn-sm drawer-preview-btn">重新拍照</label>
                      <label for="rectification-photo-upload"
                        class="btn btn-light btn-sm drawer-preview-btn">相册重选</label>
                      <button class="btn btn-secondary btn-sm drawer-preview-btn" type="button"
                        @click="clearRectificationFile">移除图片</button>
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
              <textarea v-model="actionForm.reviewNote" rows="4" placeholder="请填写复核说明"></textarea>
            </div>

            <div class="form-item">
              <label>复核照片</label>
              <div class="drawer-upload-card">
                <input id="review-photo-upload" class="drawer-upload-input" type="file" accept="image/*"
                  @change="handleReviewFileChange" />
                <input id="review-photo-camera" class="drawer-upload-input" type="file" accept="image/*"
                  capture="environment" @change="handleReviewFileChange" />

                <label for="review-photo-upload" class="drawer-upload-dropzone">
                  <div class="drawer-upload-icon">↑</div>
                  <div class="drawer-upload-title">选择或更换复核照片</div>
                  <div class="drawer-upload-desc">
                    请上传能够清晰反映复核结果的现场照片，建议画面完整、重点明确。
                  </div>
                  <div class="drawer-upload-trigger-group">
                    <label for="review-photo-camera"
                      class="drawer-upload-trigger drawer-upload-trigger-secondary">拍照上传</label>
                    <label for="review-photo-upload" class="drawer-upload-trigger">相册选择</label>
                  </div>
                </label>

                <div v-if="actionForm.reviewPhotoPreview" class="drawer-image-preview-panel">
                  <img :src="actionForm.reviewPhotoPreview" alt="复核照片预览" class="drawer-preview-thumb" />
                  <div class="drawer-preview-meta">
                    <div class="drawer-preview-title">已选择复核照片</div>
                    <div class="drawer-preview-name">{{ actionForm.reviewPhotoFile?.name || '已上传图片' }}</div>
                    <div class="drawer-preview-actions">
                      <label for="review-photo-camera" class="btn btn-light btn-sm drawer-preview-btn">重新拍照</label>
                      <label for="review-photo-upload" class="btn btn-light btn-sm drawer-preview-btn">相册重选</label>
                      <button class="btn btn-secondary btn-sm drawer-preview-btn" type="button"
                        @click="clearReviewFile">
                        移除图片
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <div class="drawer-actions">
            <button class="btn btn-primary" type="button" @click="submitAction" :disabled="submittingAction">
              {{ submittingAction ? '提交中...' : (currentRole === 'station_manager' ? '确认提交整改' : '确认提交复核') }}
            </button>
            <button class="btn btn-secondary" type="button" @click="closeActionDrawer"
              :disabled="submittingAction">取消</button>
          </div>

          <transition name="toast-fade">
            <div v-if="actionMessage" class="submit-toast" :class="actionMessageType">{{ actionMessage }}</div>
          </transition>
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
import {
  compressImageFile,
  getAcceptedImageTypes,
  validateImageType
} from '@/utils/imageUpload'

const currentRole = ref(localStorage.getItem('user_role') || '')
const loading = ref(false)
const submittingAction = ref(false)
const issues = ref([])
const stationSelectRef = ref(null)
const inspectionTableSelectRef = ref(null)

const dropdownVisible = ref({
  station: false,
  inspectionTableName: false
})

const filters = ref({
  status: '',
  station: '',
  inspectionTableName: '',
  standardId: '',
  standardDetail: ''
})

const filteredData = computed(() => {
  return issues.value.filter((item) => {
    const matchedStatus = !filters.value.status || item.status === filters.value.status
    const matchedStation = !filters.value.station || normalizedKeyword(item.station).includes(normalizedKeyword(filters.value.station))
    const matchedInspectionTableName = !filters.value.inspectionTableName || normalizedKeyword(item.inspection_table_name).includes(normalizedKeyword(filters.value.inspectionTableName))
    const matchedStandardId = !filters.value.standardId || normalizedKeyword(item.standard_id).includes(normalizedKeyword(filters.value.standardId))
    const matchedStandardDetail = !filters.value.standardDetail || normalizedKeyword(item.standard_detail_text).includes(normalizedKeyword(filters.value.standardDetail))
    return matchedStatus && matchedStation && matchedInspectionTableName && matchedStandardId && matchedStandardDetail
  })
})

const stationOptions = computed(() => uniqueSortedOptions(issues.value.map((item) => item.station)))
const inspectionTableOptions = computed(() => uniqueSortedOptions(issues.value.map((item) => item.inspection_table_name)))

const filteredStationOptions = computed(() => filterOptionByKeyword(stationOptions.value, filters.value.station))
const filteredInspectionTableOptions = computed(() => filterOptionByKeyword(inspectionTableOptions.value, filters.value.inspectionTableName))

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

const formatMultiline = (value) => String(value || '').replace(/\\n/g, '\n')

const normalizedKeyword = (value) => String(value || '').trim().toLowerCase()

const uniqueSortedOptions = (values) => {
  return [...new Set(values.map((item) => String(item || '').trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
}

const filterOptionByKeyword = (options, keyword) => {
  const normalized = normalizedKeyword(keyword)
  return options.filter((item) => !normalized || normalizedKeyword(item).includes(normalized))
}

const resetFilters = () => {
  filters.value = {
    status: '',
    station: '',
    inspectionTableName: '',
    standardId: '',
    standardDetail: ''
  }
  closeAllDropdowns()
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

const standardDetailState = ref({
  visible: false,
  title: '',
  content: ''
})

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
  reviewNote: '',
  reviewPhotoFile: null,
  reviewPhotoPreview: ''
})

const actionMessage = ref('')
const actionMessageType = ref('info')
let actionMessageTimer = null
const ACCEPTED_IMAGE_TYPES = getAcceptedImageTypes()

const resolveImage = (path) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  const normalizedPath = String(path).startsWith('/') ? path.slice(1) : path
  return `/storage/${normalizedPath}`
}



const fetchMyIssues = async () => {
  const userId = localStorage.getItem('user_id') || ''
  if (!userId) {
    showActionToast('当前登录信息缺失，请重新登录。', 'error')
    return
  }

  try {
    loading.value = true
    const response = await axios.get('/api/my-issues', {
      params: { user_id: userId }
    })
    issues.value = response.data || []
  } catch (error) {
    showActionToast(error?.response?.data?.error || '获取待办问题失败。', 'error')
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
    reviewNote: item.review_note || '',
    reviewPhotoFile: null,
    reviewPhotoPreview: ''
  }
}

const closeActionDrawer = () => {
  if (actionForm.value.rectificationPhotoPreview && actionForm.value.rectificationPhotoPreview.startsWith('blob:')) {
    URL.revokeObjectURL(actionForm.value.rectificationPhotoPreview)
  }
  if (actionForm.value.reviewPhotoPreview && actionForm.value.reviewPhotoPreview.startsWith('blob:')) {
    URL.revokeObjectURL(actionForm.value.reviewPhotoPreview)
  }

  actionDrawer.value = {
    visible: false,
    item: null
  }
  actionMessage.value = ''
  actionMessageType.value = 'info'
}

const handleRectificationFileChange = async (event) => {
  const file = event.target.files?.[0]

  if (!file) {
    clearRectificationFile()
    return
  }

  if (!validateImageType(file)) {
    showActionToast('仅支持上传 JPG、JPEG、PNG、WEBP、HEIC、HEIF 格式图片。', 'error')
    event.target.value = ''
    clearRectificationFile()
    return
  }

  try {
    const compressedFile = await compressImageFile(file)
    actionForm.value.rectificationPhotoFile = compressedFile

    if (
      actionForm.value.rectificationPhotoPreview &&
      actionForm.value.rectificationPhotoPreview.startsWith('blob:')
    ) {
      URL.revokeObjectURL(actionForm.value.rectificationPhotoPreview)
    }
    actionForm.value.rectificationPhotoPreview = URL.createObjectURL(compressedFile)
    if (actionMessageTimer) {
      clearTimeout(actionMessageTimer)
      actionMessageTimer = null
    }
    actionMessage.value = ''
    actionMessageType.value = 'info'
  } catch (error) {
    showActionToast(error?.message || '图片处理失败，请更换图片后重试。', 'error')
    event.target.value = ''
    clearRectificationFile()
  }
}

const clearRectificationFile = () => {
  actionForm.value.rectificationPhotoFile = null
  if (actionForm.value.rectificationPhotoPreview && actionForm.value.rectificationPhotoPreview.startsWith('blob:')) {
    URL.revokeObjectURL(actionForm.value.rectificationPhotoPreview)
  }
  actionForm.value.rectificationPhotoPreview = ''
  const uploadInput = document.getElementById('rectification-photo-upload')
  if (uploadInput) {
    uploadInput.value = ''
  }
  const cameraInput = document.getElementById('rectification-photo-camera')
  if (cameraInput) {
    cameraInput.value = ''
  }
}

const handleReviewFileChange = async (event) => {
  const file = event.target.files?.[0]

  if (!file) {
    clearReviewFile()
    return
  }

  if (!validateImageType(file)) {
    showActionToast('仅支持上传 JPG、JPEG、PNG、WEBP、HEIC、HEIF 格式图片。', 'error')
    event.target.value = ''
    clearReviewFile()
    return
  }

  try {
    const compressedFile = await compressImageFile(file)
    actionForm.value.reviewPhotoFile = compressedFile

    if (actionForm.value.reviewPhotoPreview && actionForm.value.reviewPhotoPreview.startsWith('blob:')) {
      URL.revokeObjectURL(actionForm.value.reviewPhotoPreview)
    }
    actionForm.value.reviewPhotoPreview = URL.createObjectURL(compressedFile)

    if (actionMessageTimer) {
      clearTimeout(actionMessageTimer)
      actionMessageTimer = null
    }
    actionMessage.value = ''
    actionMessageType.value = 'info'
  } catch (error) {
    showActionToast(error?.message || '图片处理失败，请更换图片后重试。', 'error')
    event.target.value = ''
    clearReviewFile()
  }
}

const clearReviewFile = () => {
  actionForm.value.reviewPhotoFile = null
  if (actionForm.value.reviewPhotoPreview && actionForm.value.reviewPhotoPreview.startsWith('blob:')) {
    URL.revokeObjectURL(actionForm.value.reviewPhotoPreview)
  }
  actionForm.value.reviewPhotoPreview = ''
  const uploadInput = document.getElementById('review-photo-upload')
  if (uploadInput) {
    uploadInput.value = ''
  }
  const cameraInput = document.getElementById('review-photo-camera')
  if (cameraInput) {
    cameraInput.value = ''
  }
}

const showActionToast = (message, type = 'info') => {
  if (actionMessageTimer) {
    clearTimeout(actionMessageTimer)
    actionMessageTimer = null
  }

  actionMessageType.value = type
  actionMessage.value = message

  actionMessageTimer = setTimeout(() => {
    actionMessage.value = ''
    actionMessageTimer = null
  }, 2200)
}

const submitAction = async () => {
  if (!actionDrawer.value.item) return

  const userId = localStorage.getItem('user_id') || ''
  if (!userId) {
    showActionToast('当前登录信息缺失，请重新登录。', 'error')
    return
  }

  try {
    submittingAction.value = true
    if (actionMessageTimer) {
      clearTimeout(actionMessageTimer)
      actionMessageTimer = null
    }
    actionMessage.value = ''
    actionMessageType.value = 'info'

    if (currentRole.value === 'station_manager') {
      if (!actionForm.value.rectificationResult) {
        showActionToast('请选择整改结果。', 'error')
        return
      }
      if (!actionForm.value.rectificationNote.trim()) {
        showActionToast('请填写整改说明。', 'error')
        return
      }
      if (!actionForm.value.rectificationPhotoFile) {
        showActionToast('请上传整改照片。', 'error')
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
      await fetchMyIssues()
      closeActionDrawer()
      showActionToast(response.data.message || '整改提交成功。', 'success')
      return
    }

    if (!actionForm.value.reviewResult) {
      showActionToast('请选择督导组复核结果。', 'error')
      return
    }
    if (!actionForm.value.reviewNote.trim()) {
      showActionToast('请填写复核说明。', 'error')
      return
    }
    if (!actionForm.value.reviewPhotoFile) {
      showActionToast('请上传复核照片。', 'error')
      return
    }

    const formData = new FormData()
    formData.append('user_id', userId)
    formData.append('review_result', actionForm.value.reviewResult)
    formData.append('review_note', actionForm.value.reviewNote)
    formData.append('review_photo', actionForm.value.reviewPhotoFile)

    const response = await axios.post(
      `/api/issues/${actionDrawer.value.item.id}/review`,
      formData
    )
    await fetchMyIssues()
    closeActionDrawer()
    showActionToast(response.data.message || '复核提交成功。', 'success')
  } catch (error) {
    showActionToast(error?.response?.data?.error || '提交失败，请稍后重试。', 'error')
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
  document.addEventListener('click', handleClickOutside)
  fetchMyIssues()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  if (actionMessageTimer) {
    clearTimeout(actionMessageTimer)
    actionMessageTimer = null
  }
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
  grid-template-columns: repeat(4, minmax(180px, 1fr));
  gap: 16px;
}

.toolbar-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.toolbar-item-wide {
  grid-column: span 2;
  min-width: 0;
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
  min-width: 1680px;
  border-collapse: collapse;
}

.issues-table th,
.issues-table td {
  border: 1px solid #e5e7eb;
  padding: 10px 12px;
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
  min-width: 200px;
  max-width: 260px;
  white-space: normal;
  line-height: 1.7;
  word-break: break-word;
}

.standard-detail-cell {
  width: 360px;
  min-width: 320px;
  max-width: 360px;
}

.standard-detail-box {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  width: 100%;
  max-width: 336px;
}

.standard-detail-preview {
  width: 100%;
  line-height: 1.75;
  color: #334155;
  word-break: break-word;
}

.multiline-clamp {
  display: -webkit-box;
  -webkit-line-clamp: 2;
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

.thumb {
  width: 88px;
  height: 66px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
}

.issues-table th:nth-child(1),
.issues-table td:nth-child(1) {
  width: 64px;
  min-width: 64px;
  white-space: nowrap;
}

.issues-table th:nth-child(2),
.issues-table td:nth-child(2) {
  width: 116px;
  min-width: 116px;
}

.issues-table th:nth-child(3),
.issues-table td:nth-child(3) {
  width: 126px;
  min-width: 126px;
}

.issues-table th:nth-child(4),
.issues-table td:nth-child(4) {
  width: 92px;
  min-width: 92px;
  white-space: nowrap;
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
  min-height: 168px;
  padding: 22px 18px;
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
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.drawer-upload-title {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

.drawer-upload-desc {
  max-width: 520px;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.drawer-upload-trigger-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
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
  cursor: pointer;
}

.drawer-upload-trigger-secondary {
  background: #eef4ff;
  color: #1d4ed8;
  border: 1px solid #bfd3ff;
}

.drawer-upload-trigger:hover {
  filter: brightness(0.98);
}

.drawer-upload-trigger-secondary:hover {
  background: #e0edff;
  border-color: #93c5fd;
}

.drawer-image-preview-panel {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #fff;
  flex-wrap: wrap;
}

.drawer-preview-thumb {
  width: 148px;
  height: 108px;
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
  min-width: 220px;
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

.submit-toast {
  position: fixed;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: min(calc(100vw - 32px), 420px);
  z-index: 1200;
  font-size: 14px;
  line-height: 1.7;
  color: #2563eb;
  background: rgba(239, 246, 255, 0.98);
  border: 1px solid #bfdbfe;
  border-radius: 14px;
  padding: 12px 14px;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.16);
  backdrop-filter: blur(8px);
  text-align: center;
}

.submit-toast.success {
  color: #166534;
  background: rgba(236, 253, 245, 0.98);
  border-color: #bbf7d0;
}

.submit-toast.error {
  color: #b91c1c;
  background: rgba(254, 242, 242, 0.98);
  border-color: #fecaca;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, calc(-50% + 12px));
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
  .toolbar-grid {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }

  .toolbar-item-wide {
    grid-column: span 2;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .toolbar-item-wide {
    grid-column: span 1;
  }

  .standard-detail-grid {
    grid-template-columns: 1fr;
  }

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

  .toolbar-card {
    display: none;
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
    flex-direction: column;
    align-items: stretch;
  }

  .drawer-preview-thumb {
    width: 100%;
    max-width: none;
    height: auto;
    aspect-ratio: 4 / 3;
  }

  .drawer-preview-meta {
    min-width: 0;
    width: 100%;
    align-items: stretch;
  }

  .drawer-preview-title,
  .drawer-preview-name {
    word-break: break-word;
    text-align: left;
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

  .submit-toast {
    width: min(calc(100vw - 24px), 420px);
    top: 50%;
    font-size: 13px;
    line-height: 1.7;
  }
}
</style>