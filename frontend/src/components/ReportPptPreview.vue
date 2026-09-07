<template>
  <section class="ppt-preview" aria-label="PPT同源预览">
    <header>
      <div>
        <span>PPT 同源预览</span>
        <h3>{{ title }}</h3>
        <p>直接预览导出文件 · 图表和文字可在下载后编辑 · 支持 ← → 翻页</p>
        <small v-if="task?.snapshot_generated_at">成稿时间：{{ task.snapshot_generated_at }}</small>
      </div>
      <strong v-if="ready">{{ page }} / {{ task.slide_count }}</strong>
    </header>
    <div v-if="error" class="state error" role="alert">
      <p>{{ error }}</p>
      <button @click="prepare">重新准备预览</button>
    </div>
    <div v-else-if="!ready" class="state" role="status">
      <span class="pulse" /><strong>{{ task?.stage_message || '正在准备兼容版PPT预览' }}</strong>
      <p>仅排版和转换，不调用AI，不修改报告内容。已处理的成稿会直接复用。</p>
      <progress :value="task?.progress || 3" max="100" />
    </div>
    <template v-else>
      <div class="canvas" :aria-busy="imageLoading">
        <img v-if="imageUrl" :src="imageUrl" :alt="`${title}第${page}页`" />
        <p v-else>正在读取第{{ page }}页…</p>
      </div>
      <nav aria-label="PPT翻页">
        <button :disabled="page <= 1" @click="page--">上一页</button>
        <div>
          <button
            v-for="number in task.slide_count"
            :key="number"
            :aria-current="page === number ? 'page' : undefined"
            :class="{ active: page === number }"
            @click="page = number"
          >
            {{ number }}
          </button>
        </div>
        <button :disabled="page >= task.slide_count" @click="page++">下一页</button>
      </nav>
    </template>
  </section>
</template>
<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
const props = defineProps({
  reportType: String,
  snapshotId: Number,
  generatedAt: String,
  title: String,
})
const emit = defineEmits(['ready'])
const task = ref(null),
  page = ref(1),
  error = ref(''),
  imageUrl = ref(''),
  imageLoading = ref(false)
const ready = computed(() => task.value?.status === 'completed' && task.value.preview_available)
let generation = 0,
  imageGeneration = 0,
  timer,
  requestController,
  imageController
function clearImage() {
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = ''
}
function stop() {
  generation++
  clearTimeout(timer)
  requestController?.abort()
  imageController?.abort()
  imageGeneration++
  clearImage()
}
async function prepare() {
  stop()
  const current = generation
  task.value = null
  page.value = 1
  error.value = ''
  if (!props.snapshotId) {
    error.value = '成稿尚未保存，请稍后重新读取报告。'
    return
  }
  requestController = new AbortController()
  try {
    const { data } = await axios.post(
      '/api/inspection-reports/exports',
      { report_type: props.reportType, snapshot_id: props.snapshotId },
      { signal: requestController.signal },
    )
    if (current !== generation) return
    accept(data.task, current)
  } catch (err) {
    if (current === generation && !axios.isCancel(err))
      error.value = err.response?.data?.error || '准备PPT预览失败，请重试。'
  }
}
function accept(value, current) {
  task.value = value
  if (value?.status === 'failed') {
    error.value = value.error_message || 'PPT处理失败。'
    return
  }
  if (value?.status === 'completed') {
    if (!value.preview_available) {
      error.value = '该文件缺少兼容预览，请重新准备。'
      return
    }
    emit('ready', value)
    loadPage()
    return
  }
  if (!value?.task_id) {
    error.value = '后台未返回有效的PPT任务。'
    return
  }
  timer = setTimeout(async () => {
    try {
      const { data } = await axios.get(`/api/inspection-reports/exports/${value.task_id}`, {
        signal: requestController.signal,
      })
      if (current === generation) accept(data.task, current)
    } catch (err) {
      if (current === generation && !axios.isCancel(err))
        error.value = '读取预览进度失败，后台仍会继续处理，请重试。'
    }
  }, 2500)
}
async function loadPage() {
  imageController?.abort()
  const current = ++imageGeneration
  clearImage()
  if (!ready.value) return
  imageLoading.value = true
  imageController = new AbortController()
  try {
    const { data } = await axios.get(
      `/api/inspection-reports/exports/${task.value.task_id}/slides/${page.value}`,
      { responseType: 'blob', signal: imageController.signal },
    )
    if (current === imageGeneration) imageUrl.value = URL.createObjectURL(data)
  } catch (err) {
    if (current === imageGeneration && !axios.isCancel(err))
      error.value = '读取预览图片失败，请重试。'
  } finally {
    if (current === imageGeneration) imageLoading.value = false
  }
}
function keydown(event) {
  if (
    !ready.value ||
    event.defaultPrevented ||
    event.altKey ||
    event.ctrlKey ||
    event.metaKey ||
    document.querySelector('[role="dialog"]')
  )
    return
  if (event.target?.closest('input,textarea,select,[contenteditable="true"]')) return
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return
  event.preventDefault()
  page.value = Math.max(
    1,
    Math.min(task.value.slide_count, page.value + (event.key === 'ArrowRight' ? 1 : -1)),
  )
}
watch(() => [props.reportType, props.snapshotId, props.generatedAt], prepare, { immediate: true })
watch(page, loadPage)
onMounted(() => window.addEventListener('keydown', keydown))
onBeforeUnmount(() => {
  stop()
  window.removeEventListener('keydown', keydown)
})
</script>
<style scoped>
.ppt-preview {
  border: 1px solid #dbe6ef;
  border-radius: 20px;
  overflow: hidden;
  background: #f4f8fb;
}
.ppt-preview header {
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  background: linear-gradient(120deg, #f7fbff, #edf5fa);
}
header span {
  font-size: 12px;
  color: #197cad;
  letter-spacing: 0.08em;
}
h3 {
  margin: 8px 0;
}
header p,
small {
  color: #637b90;
  font-size: 12px;
}
header strong {
  white-space: nowrap;
  color: #12628c;
}
.state {
  min-height: 260px;
  display: flex;
  padding: 30px;
  text-align: center;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}
.state p {
  color: #678094;
}
.pulse {
  width: 30px;
  height: 30px;
  border: 3px solid #d4e7f3;
  border-top-color: #1682b7;
  border-radius: 50%;
  animation: spin 1.2s linear infinite;
}
.canvas {
  margin: 16px;
  background: #dce3e9;
  min-height: 180px;
  display: grid;
  place-items: center;
}
.canvas img {
  display: block;
  width: 100%;
  height: auto;
  object-fit: contain;
}
.error {
  color: #a12e34;
}
nav {
  display: flex;
  align-items: center;
  padding: 12px 16px 20px;
  gap: 12px;
}
nav > div {
  display: flex;
  flex: 1;
  gap: 6px;
  overflow-x: auto;
  padding: 4px;
}
button {
  border: 1px solid #c5d6e3;
  border-radius: 9px;
  padding: 8px 12px;
  white-space: nowrap;
  background: white;
  color: #365774;
  cursor: pointer;
}
button.active {
  color: white;
  background: #137caf;
  border-color: #137caf;
}
button:disabled {
  opacity: 0.45;
  cursor: default;
}
button:focus-visible {
  outline: 2px solid #1682b7;
  outline-offset: 2px;
}
progress {
  width: min(360px, 90%);
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .pulse {
    animation: none;
  }
}
@media (max-width: 640px) {
  header {
    padding: 14px !important;
  }
  .canvas {
    margin: 5px;
  }
  nav {
    gap: 6px;
    padding: 10px;
  }
  button {
    padding: 8px;
  }
  .state {
    padding: 16px;
  }
}
</style>
