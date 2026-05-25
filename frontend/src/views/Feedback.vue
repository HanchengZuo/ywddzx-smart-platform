<template>
  <div class="page-shell feedback-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">公共功能</div>
        <h2>系统反馈</h2>
        <p class="page-desc">所有反馈公开可见，任何登录用户都可以提交问题、补充截图，并在反馈下方参与讨论。</p>
      </div>
      <div class="user-card">
        <span>当前反馈人</span>
        <strong>{{ currentUser.name }}</strong>
        <small>{{ currentUser.phone || '未填写手机号' }}</small>
      </div>
    </div>

    <transition name="toast-fade">
      <div v-if="message.text" class="feedback-toast card-surface" :class="message.type">
        {{ message.text }}
      </div>
    </transition>

    <transition name="ai-submit-fade">
      <div v-if="submitting" class="ai-submit-overlay">
        <div class="ai-submit-card card-surface">
          <div class="ai-submit-orb">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <div class="section-kicker">AI 标题生成中</div>
          <h3>正在发布反馈</h3>
          <p>系统正在上传截图并调用 DeepSeek 生成反馈标题，请稍候，完成后会自动刷新反馈列表。</p>
          <div class="ai-submit-progress">
            <div></div>
          </div>
        </div>
      </div>
    </transition>

    <div class="layout-grid">
      <section class="card-surface feedback-form-card">
        <div class="section-head">
          <div>
            <div class="section-kicker">提交反馈</div>
            <h3>把问题说清楚，大家一起跟进</h3>
          </div>
          <span class="open-chip">公开</span>
        </div>

        <form class="feedback-form" @submit.prevent="submitFeedback">
          <div class="form-grid">
            <label class="field-block">
              <span>反馈类型</span>
              <select v-model="form.feedback_type">
                <option v-for="item in feedbackTypes" :key="item" :value="item">{{ item }}</option>
              </select>
            </label>

            <label class="field-block">
              <span>问题模块</span>
              <select v-model="form.module">
                <option v-for="item in moduleOptions" :key="item" :value="item">{{ item }}</option>
              </select>
            </label>

            <label class="field-block full-width">
              <span>详细说明</span>
              <textarea v-model.trim="form.description" rows="6" maxlength="3000"
                placeholder="请描述出现位置、操作步骤、实际现象和你期望的效果。系统会根据说明自动生成反馈标题。"></textarea>
            </label>

            <div ref="feedbackScreenshotUploadSectionRef" class="field-block full-width screenshot-upload-anchor">
              <span>上传截图</span>
              <div class="upload-zone" :class="{ 'drag-active': isScreenshotDragActive }" role="button" tabindex="0"
                :aria-disabled="submitting || screenshotProcessing" @click="openScreenshotPicker"
                @keydown.enter.prevent="openScreenshotPicker" @keydown.space.prevent="openScreenshotPicker"
                @dragenter.prevent="handleScreenshotDragEnter" @dragover.prevent="handleScreenshotDragOver"
                @dragleave.prevent="handleScreenshotDragLeave" @drop.prevent="handleScreenshotDrop"
                @paste="handleScreenshotPaste">
                <input id="feedback-screenshots" class="upload-input" type="file" accept="image/*" multiple
                  :disabled="submitting || screenshotProcessing" @change="handleScreenshotChange" />
                <input id="feedback-screenshots-camera" class="upload-input" type="file" accept="image/*"
                  capture="environment" :disabled="submitting || screenshotProcessing"
                  @change="handleScreenshotChange" />
                <div class="upload-icon">↑</div>
                <strong>{{ screenshotProcessing ? '正在处理截图...' : '选择、拖拽或粘贴截图' }}</strong>
                <small>支持多张图片，最多 6 张。系统会先压缩截图，再随反馈一起提交。</small>
                <div class="upload-trigger-group">
                  <label for="feedback-screenshots-camera" class="upload-trigger upload-trigger-secondary"
                    @click.stop>拍照上传</label>
                  <label for="feedback-screenshots" class="upload-trigger" @click.stop>相册选择</label>
                </div>
              </div>

              <div v-if="screenshotPreviews.length" class="screenshot-preview-grid">
                <div v-for="(item, index) in screenshotPreviews" :key="item.url" class="screenshot-preview">
                  <img :src="item.url" alt="反馈截图预览" />
                  <button type="button" @click="removeScreenshot(index)">移除</button>
                </div>
              </div>
            </div>
          </div>

          <div class="form-actions">
            <button class="ghost-btn" type="button" :disabled="submitting || screenshotProcessing" @click="resetForm">清空</button>
            <button class="primary-btn" type="submit" :disabled="submitting || screenshotProcessing">
              {{ submitting ? '提交中...' : screenshotProcessing ? '处理截图中...' : '发布反馈' }}
            </button>
          </div>
        </form>
      </section>

      <aside class="side-panel">
        <div class="card-surface stat-card">
          <span>公开反馈</span>
          <strong>{{ feedbacks.length }}</strong>
          <small>其中 {{ acceptedCount }} 条已采纳</small>
        </div>
        <div class="card-surface stat-card">
          <span>讨论总数</span>
          <strong>{{ totalComments }}</strong>
          <small>持续补充上下文更容易定位问题</small>
        </div>
        <div class="card-surface rule-card">
          <h3>反馈建议</h3>
          <p>请把页面位置、操作步骤、实际现象和期望效果写清楚。标题会由 AI 自动生成，截图越具体，后续定位越快。</p>
        </div>
      </aside>
    </div>

    <section class="card-surface feedback-board">
      <div class="board-head">
        <div>
          <div class="section-kicker">反馈广场</div>
          <h3>公开反馈与讨论</h3>
        </div>
        <div class="board-filters">
          <select v-model="filters.feedback_type">
            <option value="">全部类型</option>
            <option v-for="item in feedbackTypes" :key="item" :value="item">{{ item }}</option>
          </select>
          <select v-model="filters.module">
            <option value="">全部模块</option>
            <option v-for="item in moduleOptions" :key="item" :value="item">{{ item }}</option>
          </select>
        </div>
      </div>

      <div v-if="loading" class="empty-card">正在加载反馈...</div>
      <div v-else-if="filteredFeedbacks.length === 0" class="empty-card">
        当前没有符合条件的反馈。可以先发布第一条，把问题留在这里。
      </div>

      <div v-else class="feedback-list">
        <article v-for="item in filteredFeedbacks" :key="item.id" class="feedback-thread"
          :class="{ accepted: item.is_accepted }">
          <div class="thread-head">
            <div>
              <div class="thread-tags">
                <span v-if="item.is_accepted" class="accepted-tag">已采纳</span>
                <span>{{ item.feedback_type }}</span>
                <span>{{ item.module }}</span>
              </div>
              <h3>{{ item.title }}</h3>
            </div>
            <div v-if="item.can_accept || item.can_delete" class="thread-actions">
              <button v-if="item.can_accept" class="accept-btn" :class="{ active: item.is_accepted }" type="button"
                :disabled="acceptingId === item.id" @click="toggleFeedbackAccepted(item)">
                {{ acceptingId === item.id ? '处理中' : item.is_accepted ? '取消采纳' : '标记采纳' }}
              </button>
              <button v-if="item.can_delete" class="danger-btn" type="button" @click="deleteFeedback(item)">
                删除
              </button>
            </div>
          </div>

          <div class="thread-author">
            <strong>{{ item.author_name || '未知用户' }}</strong>
            <span>{{ item.author_phone || '未填写手机号' }}</span>
            <span>{{ roleLabel(item.author_role) }}</span>
            <span>{{ item.created_at }}</span>
          </div>

          <div v-if="item.is_accepted" class="accepted-banner">
            <strong>该反馈已被采纳</strong>
            <span>{{ item.accepted_at ? `采纳时间：${item.accepted_at}` : '已进入后续优化跟进范围' }}</span>
          </div>

          <p class="thread-desc">{{ item.description }}</p>

          <div v-if="item.screenshots?.length" class="thread-screenshots">
            <button v-for="shot in item.screenshots" :key="shot.id" type="button" @click="previewImage(shot.file_path)">
              <img :src="resolveStorageUrl(shot.file_path)" alt="反馈截图" />
            </button>
          </div>

          <div class="comment-panel">
            <div class="comment-title">讨论 {{ item.comments?.length || 0 }}</div>
            <div v-if="item.comments?.length" class="comment-list">
              <div v-for="comment in item.comments" :key="comment.id" class="comment-item">
                <div class="comment-meta">
                  <strong>{{ comment.author_name || '未知用户' }}</strong>
                  <span>{{ comment.author_phone || '未填写手机号' }}</span>
                  <span>{{ comment.created_at }}</span>
                  <button v-if="comment.can_delete" type="button" @click="deleteComment(comment)">删除</button>
                </div>
                <p>{{ comment.comment_text }}</p>
              </div>
            </div>

            <form class="comment-form" @submit.prevent="submitComment(item)">
              <input v-model.trim="commentDrafts[item.id]" maxlength="1200" placeholder="参与讨论，补充现象、原因或处理建议" />
              <button class="ghost-btn" type="submit" :disabled="commentSubmittingId === item.id">
                {{ commentSubmittingId === item.id ? '发布中' : '回复' }}
              </button>
            </form>
          </div>
        </article>
      </div>
    </section>

    <div v-if="preview.visible" class="image-preview-overlay" @click.self="closePreview">
      <div class="image-preview-dialog" @wheel.prevent="handlePreviewWheel" @dblclick="resetPreviewScale">
        <img :src="preview.url" :style="previewImageStyle" alt="反馈截图预览" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import axios from 'axios'
import {
  clearFileInputsById,
  getImageFilesFromClipboardEvent,
  getImageFilesFromDataTransfer,
  hasImageInDataTransfer,
  isDesktopImageDropEnabled,
  prepareImagePreviewList,
  revokeObjectUrl,
  revokePreviewList,
  scrollImageUploadIntoView
} from '@/utils/imageUpload'
import {
  createLocalDraftManager,
  draftAssetToFile,
  fileToDraftAsset
} from '@/utils/localDraft'

const defaultFeedbackTypes = ['Bug反馈', '功能建议', '界面优化', '流程建议', '其他']
const defaultModules = [
  '巡检系统',
  '巡检规范库',
  '检查表原件库',
  '巡检计划',
  '证照管理',
  '考核系统',
  '培训系统',
  '培训材料库',
  '车辆管理系统',
  '数据备份管理',
  '用户数据管理',
  '站点数据管理',
  '检查表数据管理',
  '巡检规范库数据管理',
  '管理系统',
  '公共功能',
  '登录与账号',
  '其他'
]

const currentUser = computed(() => ({
  name: localStorage.getItem('real_name') || localStorage.getItem('username') || '未命名用户',
  phone: localStorage.getItem('phone') || '',
  role: localStorage.getItem('user_role') || ''
}))

const feedbacks = ref([])
const feedbackTypes = ref(defaultFeedbackTypes)
const moduleOptions = ref(defaultModules)
const loading = ref(false)
const submitting = ref(false)
const screenshotProcessing = ref(false)
const commentSubmittingId = ref(null)
const acceptingId = ref(null)
const screenshotFiles = ref([])
const screenshotPreviews = ref([])
const screenshotDraftAssets = ref([])
const feedbackScreenshotUploadSectionRef = ref(null)
const isScreenshotDragActive = ref(false)
const commentDrafts = reactive({})
const filters = reactive({
  feedback_type: '',
  module: ''
})
const form = reactive({
  feedback_type: 'Bug反馈',
  module: '巡检系统',
  description: ''
})

const buildFeedbackDraftData = () => ({
  form: { ...form },
  screenshots: screenshotDraftAssets.value
})

const buildFeedbackDraftFallbackData = (data) => ({
  ...data,
  screenshots: []
})

const isFeedbackDraftEmpty = (data) => {
  const draftForm = data?.form || {}
  return !String(draftForm.description || '').trim() &&
    !data?.screenshots?.length &&
    (!draftForm.feedback_type || draftForm.feedback_type === (feedbackTypes.value[0] || 'Bug反馈')) &&
    (!draftForm.module || draftForm.module === (moduleOptions.value[0] || '巡检系统'))
}
const message = reactive({
  text: '',
  type: 'info'
})
const preview = reactive({
  visible: false,
  url: '',
  scale: 1
})
let messageTimer = null
let screenshotDragDepth = 0
const SCREENSHOT_LIMIT = 6
const FEEDBACK_DRAFT_SCOPE = 'system-feedback'
let feedbackDraftManager = null
let feedbackDraftReady = false

const totalComments = computed(() => feedbacks.value.reduce((sum, item) => sum + (item.comments?.length || 0), 0))
const acceptedCount = computed(() => feedbacks.value.filter((item) => item.is_accepted).length)
const filteredFeedbacks = computed(() => {
  return feedbacks.value.filter((item) => {
    const typeMatched = !filters.feedback_type || item.feedback_type === filters.feedback_type
    const moduleMatched = !filters.module || item.module === filters.module
    return typeMatched && moduleMatched
  })
})

const setMessage = (text, type = 'info') => {
  if (messageTimer) {
    clearTimeout(messageTimer)
    messageTimer = null
  }
  message.text = text
  message.type = type
  if (!text) return
  messageTimer = setTimeout(() => {
    message.text = ''
    messageTimer = null
  }, 2600)
}

feedbackDraftManager = createLocalDraftManager(FEEDBACK_DRAFT_SCOPE, {
  collect: buildFeedbackDraftData,
  collectFallback: buildFeedbackDraftFallbackData,
  isEmpty: isFeedbackDraftEmpty,
  onFallback: () => setMessage('反馈文字草稿已自动保存，截图较大需重新选择。', 'info')
})

const handleFeedbackBeforeUnload = () => {
  feedbackDraftManager?.flush()
}

const roleLabel = (role) => {
  const map = {
    root: '系统管理员',
    supervisor: '督导组',
    station_manager: '站点账号'
  }
  return map[role] || role || '未知角色'
}

const resolveStorageUrl = (path) => {
  const value = String(path || '').trim()
  if (!value) return ''
  if (value.startsWith('http://') || value.startsWith('https://') || value.startsWith('data:') || value.startsWith('blob:')) {
    return value
  }
  if (value.startsWith('/storage/')) return value
  if (value.startsWith('/')) return `/storage${value}`
  return `/storage/${value}`
}

const releasePreviews = () => {
  revokePreviewList(screenshotPreviews.value)
  screenshotPreviews.value = []
}

const scrollToScreenshotUpload = async () => {
  await nextTick()
  scrollImageUploadIntoView(feedbackScreenshotUploadSectionRef.value)
}

const processScreenshotFiles = async (files = [], options = {}) => {
  if (submitting.value || screenshotProcessing.value) return false

  const selectedFiles = Array.from(files || []).filter(Boolean)
  if (!selectedFiles.length) return false

  const remainingCount = Math.max(0, SCREENSHOT_LIMIT - screenshotFiles.value.length)
  if (remainingCount <= 0) {
    setMessage('最多上传 6 张截图，请先移除已有截图后再添加。', 'error')
    return false
  }

  const filesToProcess = selectedFiles.slice(0, remainingCount)
  if (selectedFiles.length > remainingCount) {
    setMessage('最多上传 6 张截图，已自动保留前 6 张。', 'error')
  }

  screenshotProcessing.value = true
  let uploaded = false

  try {
    const result = await prepareImagePreviewList(filesToProcess, {
      limit: SCREENSHOT_LIMIT,
      existingCount: screenshotFiles.value.length,
      maxUploadBytes: 500 * 1024,
      maxWidth: 1600
    })

    if (result.files.length) {
      screenshotFiles.value = [...screenshotFiles.value, ...result.files].slice(0, SCREENSHOT_LIMIT)
      screenshotPreviews.value = [...screenshotPreviews.value, ...result.previews].slice(0, SCREENSHOT_LIMIT)
      const draftAssets = await Promise.all(result.files.map(async (file) => {
        try {
          return await fileToDraftAsset(file)
        } catch {
          return null
        }
      }))
      screenshotDraftAssets.value = [
        ...screenshotDraftAssets.value,
        ...draftAssets.filter(Boolean)
      ].slice(0, SCREENSHOT_LIMIT)
      uploaded = true
    }

    if (result.failedCount) {
      setMessage('部分截图无法读取或格式不支持，请尽量上传 JPG、PNG、WEBP 截图。', 'error')
    } else if (result.files.length) {
      setMessage('截图已压缩处理，可以发布反馈。', 'success')
    }
  } catch (error) {
    setMessage(error?.message || '截图处理失败，请更换图片后重试。', 'error')
  } finally {
    screenshotProcessing.value = false
  }

  if (uploaded && options.follow) {
    await scrollToScreenshotUpload()
  }

  return uploaded
}

const handleScreenshotChange = async (event) => {
  const selectedFiles = Array.from(event.target.files || [])
  event.target.value = ''
  await processScreenshotFiles(selectedFiles)
}

const openScreenshotPicker = () => {
  if (submitting.value || screenshotProcessing.value) return
  document.getElementById('feedback-screenshots')?.click()
}

const handleScreenshotDragEnter = (event) => {
  if (!isDesktopImageDropEnabled() || !hasImageInDataTransfer(event.dataTransfer)) return
  screenshotDragDepth += 1
  isScreenshotDragActive.value = true
}

const handleScreenshotDragOver = (event) => {
  if (!isDesktopImageDropEnabled() || !hasImageInDataTransfer(event.dataTransfer)) return
  event.dataTransfer.dropEffect = 'copy'
  isScreenshotDragActive.value = true
}

const handleScreenshotDragLeave = () => {
  if (!isDesktopImageDropEnabled()) return
  screenshotDragDepth = Math.max(screenshotDragDepth - 1, 0)
  if (screenshotDragDepth === 0) {
    isScreenshotDragActive.value = false
  }
}

const handleScreenshotDrop = async (event) => {
  if (!isDesktopImageDropEnabled()) return
  screenshotDragDepth = 0
  isScreenshotDragActive.value = false
  const files = getImageFilesFromDataTransfer(event.dataTransfer)
  if (!files.length) {
    setMessage('请拖入图片文件。', 'error')
    return
  }
  await processScreenshotFiles(files, { follow: true })
}

const handleScreenshotPaste = async (event) => {
  const files = getImageFilesFromClipboardEvent(event)
  if (!files.length) {
    setMessage('剪贴板里没有可上传的图片。', 'error')
    return
  }
  event.preventDefault()
  screenshotDragDepth = 0
  isScreenshotDragActive.value = false
  await processScreenshotFiles(files, { follow: true })
}

const handleWindowScreenshotPaste = async (event) => {
  if (event.defaultPrevented || submitting.value || screenshotProcessing.value) return
  const files = getImageFilesFromClipboardEvent(event)
  if (!files.length) return
  event.preventDefault()
  screenshotDragDepth = 0
  isScreenshotDragActive.value = false
  await processScreenshotFiles(files, { follow: true })
}

const removeScreenshot = (index) => {
  revokeObjectUrl(screenshotPreviews.value[index]?.url)
  const nextFiles = screenshotFiles.value.filter((_, fileIndex) => fileIndex !== index)
  const nextPreviews = screenshotPreviews.value.filter((_, previewIndex) => previewIndex !== index)
  const nextDraftAssets = screenshotDraftAssets.value.filter((_, assetIndex) => assetIndex !== index)
  screenshotFiles.value = nextFiles
  screenshotPreviews.value = nextPreviews
  screenshotDraftAssets.value = nextDraftAssets
}

const resetForm = () => {
  form.feedback_type = feedbackTypes.value[0] || 'Bug反馈'
  form.module = moduleOptions.value[0] || '巡检系统'
  form.description = ''
  screenshotFiles.value = []
  screenshotDraftAssets.value = []
  releasePreviews()
  isScreenshotDragActive.value = false
  screenshotDragDepth = 0
  clearFileInputsById(['feedback-screenshots', 'feedback-screenshots-camera'])
  feedbackDraftManager?.clear()
}

const restoreFeedbackDraft = async () => {
  const draft = feedbackDraftManager?.load()?.data
  if (!draft || isFeedbackDraftEmpty(draft)) return false

  await feedbackDraftManager.pause(async () => {
    const draftForm = draft.form || {}
    form.feedback_type = feedbackTypes.value.includes(draftForm.feedback_type)
      ? draftForm.feedback_type
      : feedbackTypes.value[0] || 'Bug反馈'
    form.module = moduleOptions.value.includes(draftForm.module)
      ? draftForm.module
      : moduleOptions.value[0] || '巡检系统'
    form.description = draftForm.description || ''

    const restoredAssets = Array.isArray(draft.screenshots) ? draft.screenshots.slice(0, SCREENSHOT_LIMIT) : []
    const restoredFiles = []
    const restoredPreviews = []
    const restoredDraftAssets = []
    for (const asset of restoredAssets) {
      try {
        const file = await draftAssetToFile(asset)
        if (!file) continue
        restoredFiles.push(file)
        restoredDraftAssets.push(asset)
        restoredPreviews.push({
          file,
          url: URL.createObjectURL(file)
        })
      } catch {
        // 图片草稿损坏时跳过，文字草稿仍然恢复。
      }
    }

    screenshotFiles.value = restoredFiles
    screenshotDraftAssets.value = restoredDraftAssets
    releasePreviews()
    screenshotPreviews.value = restoredPreviews
  })

  setMessage('已恢复上次未提交的反馈草稿。', 'success')
  return true
}

const fetchFeedbacks = async () => {
  try {
    loading.value = true
    const response = await axios.get('/api/feedbacks', {
      params: { _ts: Date.now() }
    })
    feedbacks.value = response.data?.items || []
    feedbackTypes.value = response.data?.options?.feedback_types || defaultFeedbackTypes
    moduleOptions.value = response.data?.options?.modules || defaultModules
    if (!feedbackTypes.value.includes(form.feedback_type)) form.feedback_type = feedbackTypes.value[0] || 'Bug反馈'
    if (!moduleOptions.value.includes(form.module)) form.module = moduleOptions.value[0] || '巡检系统'
  } catch (error) {
    setMessage(error?.response?.data?.error || '反馈数据加载失败。', 'error')
  } finally {
    loading.value = false
  }
}

const validateForm = () => {
  if (!form.feedback_type) return '请选择反馈类型。'
  if (!form.module) return '请选择问题模块。'
  if (!form.description) return '请填写详细说明。'
  return ''
}

const submitFeedback = async () => {
  if (screenshotProcessing.value) {
    setMessage('截图仍在处理，请稍候再发布。', 'error')
    return
  }

  const error = validateForm()
  if (error) {
    setMessage(error, 'error')
    return
  }

  try {
    submitting.value = true
    const payload = new FormData()
    payload.append('feedback_type', form.feedback_type)
    payload.append('module', form.module)
    payload.append('description', form.description)
    screenshotFiles.value.forEach((file) => {
      payload.append('screenshots', file)
    })
    const response = await axios.post('/api/feedbacks', payload, {
      timeout: 120000
    })
    if (response.data?.ai_title_generated === false) {
      setMessage('反馈已提交，AI标题生成失败，已使用默认标题。', 'success')
    } else {
      setMessage(response.data?.message || '反馈已发布。', 'success')
    }
    resetForm()
    await fetchFeedbacks()
  } catch (error) {
    const isTimeout = error?.code === 'ECONNABORTED'
    setMessage(
      isTimeout
        ? '反馈提交超时，请检查截图大小或稍后重试。'
        : error?.response?.data?.error || '反馈提交失败。',
      'error'
    )
  } finally {
    submitting.value = false
  }
}

const submitComment = async (item) => {
  const text = String(commentDrafts[item.id] || '').trim()
  if (!text) {
    setMessage('请填写讨论内容。', 'error')
    return
  }
  try {
    commentSubmittingId.value = item.id
    const response = await axios.post(`/api/feedbacks/${item.id}/comments`, {
      comment_text: text
    })
    commentDrafts[item.id] = ''
    const comment = response.data?.comment
    if (comment) {
      item.comments = [...(item.comments || []), comment]
    } else {
      await fetchFeedbacks()
    }
  } catch (error) {
    setMessage(error?.response?.data?.error || '讨论发布失败。', 'error')
  } finally {
    commentSubmittingId.value = null
  }
}

const toggleFeedbackAccepted = async (item) => {
  const nextAccepted = !item.is_accepted
  try {
    acceptingId.value = item.id
    const response = await axios.patch(`/api/feedbacks/${item.id}/acceptance`, {
      accepted: nextAccepted
    })
    const updated = response.data?.feedback || {}
    item.is_accepted = Boolean(updated.is_accepted)
    item.accepted_at = updated.accepted_at || ''
    item.accepted_by = updated.accepted_by || null
    setMessage(response.data?.message || (nextAccepted ? '反馈已标记为已采纳。' : '反馈已取消采纳。'), 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || '反馈采纳状态更新失败。', 'error')
  } finally {
    acceptingId.value = null
  }
}

const deleteFeedback = async (item) => {
  if (!window.confirm(`确定删除反馈【${item.title}】吗？删除后讨论和截图都会同步删除。`)) return
  try {
    await axios.delete(`/api/feedbacks/${item.id}`)
    setMessage('反馈已删除。', 'success')
    await fetchFeedbacks()
  } catch (error) {
    setMessage(error?.response?.data?.error || '反馈删除失败。', 'error')
  }
}

const deleteComment = async (comment) => {
  if (!window.confirm('确定删除这条讨论吗？')) return
  try {
    await axios.delete(`/api/feedback-comments/${comment.id}`)
    setMessage('讨论已删除。', 'success')
    await fetchFeedbacks()
  } catch (error) {
    setMessage(error?.response?.data?.error || '讨论删除失败。', 'error')
  }
}

const previewImage = (path) => {
  preview.url = resolveStorageUrl(path)
  preview.scale = 1
  preview.visible = true
}

const closePreview = () => {
  preview.visible = false
  preview.url = ''
  preview.scale = 1
}

const previewImageStyle = computed(() => ({
  transform: `scale(${preview.scale})`
}))

const resetPreviewScale = () => {
  preview.scale = 1
}

const handlePreviewWheel = (event) => {
  const delta = event.deltaY > 0 ? -0.12 : 0.12
  const nextScale = preview.scale + delta
  preview.scale = Math.min(4, Math.max(0.5, Number(nextScale.toFixed(2))))
}

watch(
  [() => form.feedback_type, () => form.module, () => form.description, screenshotDraftAssets],
  () => {
    if (!feedbackDraftReady) return
    feedbackDraftManager?.scheduleSave()
  },
  { deep: true }
)

onMounted(async () => {
  window.addEventListener('paste', handleWindowScreenshotPaste)
  window.addEventListener('beforeunload', handleFeedbackBeforeUnload)
  await fetchFeedbacks()
  await restoreFeedbackDraft()
  feedbackDraftReady = true
})

onBeforeUnmount(() => {
  feedbackDraftManager?.flush()
  feedbackDraftManager?.destroy()
  window.removeEventListener('paste', handleWindowScreenshotPaste)
  window.removeEventListener('beforeunload', handleFeedbackBeforeUnload)
  if (messageTimer) clearTimeout(messageTimer)
  releasePreviews()
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
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.07);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 26px 28px;
  background:
    radial-gradient(circle at 88% 12%, rgba(37, 99, 235, 0.14), transparent 28%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.96));
}

.page-kicker,
.section-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 12px;
}

.page-header h2,
.section-head h3,
.board-head h3 {
  margin: 0;
  color: #0f172a;
}

.page-header h2 {
  font-size: 34px;
}

.page-desc {
  max-width: 720px;
  margin: 10px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.user-card {
  min-width: 180px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid #e2e8f0;
}

.user-card span,
.user-card small {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.user-card strong {
  display: block;
  margin: 5px 0;
  color: #0f172a;
  font-size: 18px;
}

.feedback-toast {
  position: fixed;
  left: 50%;
  top: 84px;
  z-index: 3000;
  transform: translateX(-50%);
  min-width: min(420px, calc(100vw - 32px));
  padding: 14px 18px;
  text-align: center;
  font-size: 14px;
  font-weight: 800;
}

.feedback-toast.success {
  color: #166534;
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.feedback-toast.error {
  color: #991b1b;
  background: #fef2f2;
  border-color: #fecaca;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}

.ai-submit-overlay {
  position: fixed;
  inset: 0;
  z-index: 4200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at 50% 22%, rgba(37, 99, 235, 0.22), transparent 32%),
    rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.ai-submit-card {
  width: min(440px, calc(100vw - 36px));
  padding: 30px 28px;
  text-align: center;
  background:
    radial-gradient(circle at 50% 0%, rgba(37, 99, 235, 0.12), transparent 34%),
    rgba(255, 255, 255, 0.98);
}

.ai-submit-orb {
  position: relative;
  width: 78px;
  height: 78px;
  margin: 0 auto 18px;
  border-radius: 28px;
  background:
    radial-gradient(circle at 34% 28%, rgba(255, 255, 255, 0.94), transparent 26%),
    linear-gradient(135deg, #dbeafe 0%, #2563eb 100%);
  box-shadow: 0 22px 42px rgba(37, 99, 235, 0.28);
}

.ai-submit-orb span {
  position: absolute;
  inset: 10px;
  border-radius: 24px;
  border: 2px solid rgba(255, 255, 255, 0.72);
  animation: aiPulse 1.8s ease-in-out infinite;
}

.ai-submit-orb span:nth-child(2) {
  inset: 18px;
  animation-delay: 0.2s;
}

.ai-submit-orb span:nth-child(3) {
  inset: 27px;
  animation-delay: 0.4s;
}

.ai-submit-card h3 {
  margin: 0;
  color: #0f172a;
  font-size: 22px;
}

.ai-submit-card p {
  margin: 10px 0 20px;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.ai-submit-progress {
  overflow: hidden;
  height: 9px;
  border-radius: 999px;
  background: #e2e8f0;
}

.ai-submit-progress div {
  width: 46%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #93c5fd 0%, #2563eb 52%, #0f766e 100%);
  animation: aiProgress 1.35s ease-in-out infinite;
}

.ai-submit-fade-enter-active,
.ai-submit-fade-leave-active {
  transition: opacity 0.2s ease;
}

.ai-submit-fade-enter-from,
.ai-submit-fade-leave-to {
  opacity: 0;
}

@keyframes aiPulse {
  0%,
  100% {
    transform: scale(0.9);
    opacity: 0.52;
  }

  50% {
    transform: scale(1.08);
    opacity: 1;
  }
}

@keyframes aiProgress {
  0% {
    transform: translateX(-110%);
  }

  55% {
    transform: translateX(60%);
  }

  100% {
    transform: translateX(230%);
  }
}

.layout-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 20px;
  align-items: stretch;
}

.feedback-form-card,
.feedback-board,
.stat-card,
.rule-card {
  padding: 22px;
}

.section-head,
.board-head,
.thread-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.open-chip,
.thread-tags span {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  background: #ecfdf5;
  color: #047857;
  font-size: 12px;
  font-weight: 800;
}

.feedback-form {
  margin-top: 18px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.full-width {
  grid-column: 1 / -1;
}

.field-block span {
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.field-block input,
.field-block select,
.field-block textarea,
.board-filters select,
.comment-form input {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 14px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  box-sizing: border-box;
}

.field-block input,
.field-block select,
.board-filters select,
.comment-form input {
  height: 44px;
  padding: 0 12px;
}

.field-block textarea {
  padding: 12px;
  resize: vertical;
  line-height: 1.7;
}

.screenshot-upload-anchor {
  scroll-margin-top: 96px;
}

.upload-zone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 174px;
  padding: 22px;
  text-align: center;
  border: 1.5px dashed #93c5fd;
  border-radius: 18px;
  background:
    radial-gradient(circle at 50% 0%, rgba(37, 99, 235, 0.1), transparent 34%),
    #f8fbff;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease, background 0.2s ease;
}

.upload-zone:hover {
  border-color: #2563eb;
  box-shadow: 0 16px 34px rgba(37, 99, 235, 0.12);
}

.upload-zone.drag-active {
  transform: translateY(-1px);
  border-color: #1d4ed8;
  background:
    radial-gradient(circle at 50% 0%, rgba(37, 99, 235, 0.16), transparent 38%),
    #eff6ff;
  box-shadow: 0 18px 38px rgba(37, 99, 235, 0.18);
}

.upload-zone[aria-disabled='true'] {
  cursor: not-allowed;
  opacity: 0.72;
}

.upload-input {
  display: none;
}

.upload-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 18px;
  color: #1d4ed8;
  font-size: 28px;
  font-weight: 900;
  background: #dbeafe;
}

.upload-zone strong {
  color: #1d4ed8;
  font-size: 15px;
}

.upload-zone small {
  max-width: 480px;
  color: #64748b;
  line-height: 1.6;
}

.upload-trigger-group {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 4px;
}

.upload-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 104px;
  padding: 9px 14px;
  border-radius: 999px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.upload-trigger-secondary {
  color: #1d4ed8;
  background: #dbeafe;
}

.upload-trigger:hover {
  transform: translateY(-1px);
  background: #1d4ed8;
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.16);
}

.upload-trigger-secondary:hover {
  color: #fff;
}

.screenshot-preview-grid,
.thread-screenshots {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.screenshot-preview,
.thread-screenshots button {
  position: relative;
  overflow: hidden;
  border: 1px solid #dbe4ee;
  border-radius: 16px;
  background: #f8fafc;
  aspect-ratio: 4 / 3;
}

.screenshot-preview img,
.thread-screenshots img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.screenshot-preview button {
  position: absolute;
  right: 6px;
  top: 6px;
  border: none;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.74);
  color: #fff;
  cursor: pointer;
}

.thread-screenshots button {
  padding: 0;
  cursor: pointer;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 18px;
}

.primary-btn,
.ghost-btn,
.danger-btn,
.accept-btn {
  height: 42px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid #d1d5db;
  font-weight: 800;
  cursor: pointer;
}

.primary-btn {
  border-color: #1d4ed8;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
}

.ghost-btn {
  background: #fff;
  color: #0f172a;
}

.danger-btn {
  height: 36px;
  border-color: #fecaca;
  background: #fff1f2;
  color: #b91c1c;
}

.accept-btn {
  height: 36px;
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}

.accept-btn.active {
  border-color: #86efac;
  background: linear-gradient(135deg, #22c55e, #16a34a);
  color: #fff;
  box-shadow: 0 10px 22px rgba(22, 163, 74, 0.16);
}

.primary-btn:disabled,
.ghost-btn:disabled,
.accept-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.side-panel {
  display: grid;
  grid-template-rows: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.35fr);
  gap: 14px;
  min-height: 100%;
}

.stat-card,
.rule-card {
  display: flex;
  flex-direction: column;
}

.stat-card {
  justify-content: center;
  background:
    radial-gradient(circle at 100% 0%, rgba(37, 99, 235, 0.1), transparent 28%),
    rgba(255, 255, 255, 0.96);
}

.rule-card {
  justify-content: center;
  background:
    radial-gradient(circle at 100% 0%, rgba(15, 118, 110, 0.12), transparent 30%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.96));
}

.stat-card span,
.stat-card small {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.stat-card strong {
  display: block;
  margin: 8px 0;
  color: #0f172a;
  font-size: 34px;
}

.rule-card h3 {
  margin: 0 0 8px;
  color: #0f172a;
}

.rule-card p {
  margin: 0;
  color: #64748b;
  line-height: 1.8;
}

.board-filters {
  display: flex;
  gap: 10px;
}

.feedback-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 18px;
}

.feedback-thread {
  position: relative;
  overflow: hidden;
  padding: 18px 18px 18px 24px;
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  background:
    radial-gradient(circle at 100% 0%, rgba(37, 99, 235, 0.08), transparent 24%),
    #ffffff;
}

.feedback-thread::before {
  content: "";
  position: absolute;
  left: 0;
  top: 16px;
  bottom: 16px;
  width: 6px;
  border-radius: 0 999px 999px 0;
  background: linear-gradient(180deg, #2563eb, #14b8a6);
}

.feedback-thread.accepted {
  border-color: #86efac;
  background:
    linear-gradient(135deg, rgba(240, 253, 244, 0.92), rgba(255, 255, 255, 0.98) 44%),
    radial-gradient(circle at 100% 0%, rgba(34, 197, 94, 0.18), transparent 28%);
  box-shadow: 0 18px 38px rgba(22, 163, 74, 0.1);
}

.feedback-thread.accepted::before {
  background: linear-gradient(180deg, #22c55e, #16a34a);
}

.thread-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.thread-tags span:last-child {
  background: #eff6ff;
  color: #1d4ed8;
}

.thread-tags .accepted-tag {
  border: 1px solid #86efac;
  background: #dcfce7;
  color: #047857;
}

.thread-head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
}

.thread-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.thread-author {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 12px;
  color: #64748b;
  font-size: 13px;
}

.thread-author strong {
  color: #334155;
}

.accepted-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  padding: 11px 13px;
  border: 1px solid #bbf7d0;
  border-radius: 16px;
  background: rgba(240, 253, 244, 0.88);
  color: #166534;
}

.accepted-banner strong {
  font-size: 14px;
  font-weight: 900;
}

.accepted-banner span {
  color: #15803d;
  font-size: 12px;
  font-weight: 800;
}

.thread-desc {
  margin: 14px 0 0;
  color: #334155;
  line-height: 1.85;
  white-space: pre-wrap;
}

.comment-panel {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed #cbd5e1;
}

.comment-title {
  color: #0f172a;
  font-size: 14px;
  font-weight: 900;
}

.comment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

.comment-item {
  padding: 12px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #e7edf4;
}

.comment-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}

.comment-meta strong {
  color: #0f172a;
}

.comment-meta button {
  border: none;
  background: transparent;
  color: #b91c1c;
  cursor: pointer;
  font-weight: 800;
}

.comment-item p {
  margin: 8px 0 0;
  color: #334155;
  line-height: 1.75;
  white-space: pre-wrap;
}

.comment-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  margin-top: 12px;
}

.empty-card {
  margin-top: 18px;
  padding: 30px;
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  color: #64748b;
  text-align: center;
  background: #f8fafc;
}

.image-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.76);
}

.image-preview-dialog {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: min(960px, 96vw);
  max-height: 92vh;
  overflow: visible;
  cursor: zoom-in;
}

.image-preview-dialog img {
  display: block;
  max-width: 100%;
  max-height: 92vh;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 24px 54px rgba(15, 23, 42, 0.32);
  transform-origin: center center;
  transition: transform 0.12s ease-out;
  will-change: transform;
}

@media (max-width: 1024px) {
  .layout-grid {
    grid-template-columns: 1fr;
  }

  .side-panel {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    grid-template-rows: auto;
    min-height: auto;
  }
}

@media (max-width: 720px) {
  .page-header,
  .section-head,
  .board-head,
  .thread-head {
    flex-direction: column;
  }

  .page-header {
    padding: 20px;
  }

  .page-header h2 {
    font-size: 28px;
  }

  .user-card {
    width: 100%;
    box-sizing: border-box;
  }

  .form-grid,
  .side-panel {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }

  .board-filters,
  .form-actions,
  .comment-form {
    width: 100%;
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .primary-btn,
  .ghost-btn,
  .danger-btn,
  .accept-btn {
    width: 100%;
  }

  .thread-actions,
  .accepted-banner {
    width: 100%;
  }

  .accepted-banner {
    align-items: flex-start;
    flex-direction: column;
  }

  .feedback-form-card,
  .feedback-board,
  .stat-card,
  .rule-card {
    padding: 18px;
  }
}
</style>
