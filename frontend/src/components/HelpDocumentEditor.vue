<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="help-editor"
      aria-labelledby="help-editor-title"
      @cancel.prevent="close"
    >
      <header>
        <div>
          <small>帮助文档维护</small>
          <h3 id="help-editor-title">{{ item ? '编辑使用说明' : '新增使用说明' }}</h3>
        </div>
        <button type="button" :disabled="saving" aria-label="关闭编辑器" @click="close">×</button>
      </header>
      <p class="editor-notice">
        保存草稿不会改变用户正在阅读的内容；发布后所有用户可见。可在下方预览实际阅读效果。
      </p>
      <form @submit.prevent="save('publish')">
        <div class="editor-fields">
          <label
            >标题<input
              v-model="content.title"
              maxlength="100"
              required
              minlength="2"
              placeholder="例如：站点如何提交整改"
          /></label>
          <label
            >分类<input
              v-model="content.category"
              list="help-categories"
              required
              maxlength="40"
              minlength="2" /><datalist id="help-categories">
              <option v-for="category in categories" :key="category" :value="category" /></datalist
          ></label>
          <label class="wide"
            >一句话摘要<textarea
              v-model="content.summary"
              rows="2"
              maxlength="300"
              placeholder="告诉用户这篇文档能解决什么问题"
            />
          </label>
          <label class="wide"
            >检索标签（用逗号分隔）<input v-model="tagText" placeholder="整改、站点、照片"
          /></label>
        </div>
        <div class="editor-switch">
          <strong>操作说明</strong
          ><button type="button" :class="{ active: preview }" @click="preview = !preview">
            {{ preview ? '继续编辑' : '预览阅读效果' }}
          </button>
        </div>
        <div v-if="!preview" class="writing-tools">
          <button type="button" @click="insert('## 小节标题\n')">添加小节</button
          ><button type="button" @click="insert('1. 第一步\n2. 第二步\n')">添加步骤</button
          ><button type="button" @click="insert('> 注意事项\n')">添加提示</button>
        </div>
        <HelpArticleBody v-if="preview" class="editor-preview" :body="content.body" />
        <textarea
          v-else
          ref="bodyInput"
          v-model="content.body"
          class="body-input"
          rows="14"
          required
          minlength="2"
          maxlength="16000"
          aria-label="帮助文档正文"
          placeholder="说明适用人群、操作入口、步骤与注意事项。可使用上方按钮插入小节、步骤和提示。"
        />
        <fieldset>
          <legend>参考流程附件（可选）</legend>
          <label v-for="attachment in attachments" :key="attachment.id"
            ><input v-model="content.attachments" type="checkbox" :value="attachment.id" />{{
              attachment.title
            }}
            · {{ attachment.format }}</label
          >
        </fieldset>
        <p v-if="item" class="last-saved">
          当前版本 {{ item.revision }} · 最后维护：{{ item.updated_by || '系统预置' }}
          {{ formatTime(item.updated_at) }}
        </p>
        <p v-if="error" class="editor-error" role="alert">{{ error }}</p>
        <footer>
          <button type="button" :disabled="saving" @click="close">取消</button
          ><button type="button" :disabled="saving" @click="save('draft')">
            {{ saving === 'draft' ? '保存中…' : '保存草稿' }}</button
          ><button class="primary" type="submit" :disabled="saving">
            {{ saving === 'publish' ? '发布中…' : '发布文档' }}
          </button>
        </footer>
      </form>
    </dialog>
  </Teleport>
</template>
<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import axios from 'axios'
import HelpArticleBody from './HelpArticleBody.vue'
import { blankHelpContent } from '@/utils/helpContent'
const props = defineProps({
  item: { type: Object, default: null },
  attachments: { type: Array, default: () => [] },
  categories: { type: Array, default: () => [] },
})
const emit = defineEmits(['close', 'saved'])
const dialog = ref(null),
  bodyInput = ref(null),
  preview = ref(false),
  error = ref(''),
  saving = ref('')
const content = reactive(JSON.parse(JSON.stringify(props.item?.content || blankHelpContent())))
const tagText = ref(content.tags.join('、'))
const initial = JSON.stringify(content)
let disposed = false
const dirty = () =>
  JSON.stringify({
    ...content,
    tags: tagText.value
      .split(/[,，、]/)
      .map((text) => text.trim())
      .filter(Boolean),
  }) !== initial
const formatTime = (value) =>
  value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : ''
function close() {
  if (saving.value) return
  if (dirty() && !window.confirm('尚有未保存的修改，确定离开编辑吗？')) return
  emit('close')
}
async function insert(text) {
  const input = bodyInput.value
  const start = input?.selectionStart ?? content.body.length,
    end = input?.selectionEnd ?? start
  const prefix = start > 0 && content.body[start - 1] !== '\n' ? '\n' : ''
  content.body = content.body.slice(0, start) + prefix + text + content.body.slice(end)
  await nextTick()
  input?.focus()
  input?.setSelectionRange(start + prefix.length, start + prefix.length + text.length)
}
async function save(action) {
  if (saving.value) return
  saving.value = action
  error.value = ''
  try {
    const data = {
      action,
      revision: props.item?.revision || 0,
      content: {
        ...content,
        tags: tagText.value
          .split(/[,，、]/)
          .map((text) => text.trim())
          .filter(Boolean),
      },
    }
    const response = props.item
      ? await axios.put(`/api/help-documents/${props.item.id}`, data)
      : await axios.post('/api/help-documents', data)
    if (!disposed) emit('saved', response.data.item, action)
  } catch (failure) {
    if (!disposed)
      error.value = failure.response?.data?.error || '保存失败，请稍后重试；当前输入已保留。'
  } finally {
    if (!disposed) saving.value = ''
  }
}
onMounted(() => dialog.value?.showModal())
onBeforeRouteLeave(
  () => !saving.value && (!dirty() || window.confirm('尚有未保存的修改，确定离开此页面吗？')),
)
onBeforeUnmount(() => {
  disposed = true
  dialog.value?.close()
})
</script>
<style scoped>
.help-editor {
  width: min(900px, calc(100vw - 24px));
  max-height: calc(100dvh - 32px);
  overflow: auto;
  margin: auto;
  border: 1px solid #d5e2ef;
  padding: 24px;
  border-radius: 20px;
  color: #1d3953;
  box-sizing: border-box;
  box-shadow: 0 25px 90px #0c24494d;
}
.help-editor::backdrop {
  background: #10283d99;
  backdrop-filter: blur(4px);
}
header,
footer,
.editor-switch {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}
header h3 {
  margin: 5px 0 0;
  font-size: 22px;
}
header small {
  color: #4279a6;
}
button {
  font: inherit;
  font-size: 13px;
  border: 1px solid #d2dfeb;
  border-radius: 8px;
  background: #f8fafc;
  color: #2a567c;
  padding: 9px 13px;
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button.primary {
  background: #1e65a3;
  color: #fff;
  border-color: #1e65a3;
}
.editor-notice {
  font-size: 13px;
  line-height: 1.8;
  padding: 12px;
  background: #f0f6fc;
  border-radius: 10px;
}
.editor-fields {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 14px;
  margin: 20px 0;
}
label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 13px;
}
.wide {
  grid-column: 1 / -1;
}
input:not([type='checkbox']),
textarea {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  border: 1px solid #d6e1eb;
  border-radius: 8px;
  padding: 11px;
  color: #223c54;
  background: #fff;
  font: inherit;
  font-size: 14px;
}
.writing-tools {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 12px 0;
}
.writing-tools button {
  font-size: 12px;
}
.body-input {
  margin-top: 12px;
  line-height: 1.9;
  resize: vertical;
}
.editor-preview {
  padding: 22px;
  border: 1px solid #dce6ee;
  border-radius: 10px;
  min-height: 220px;
  margin: 14px 0;
}
fieldset {
  border: 1px solid #dde7ef;
  border-radius: 10px;
  margin: 18px 0;
  padding: 14px;
}
legend {
  font-size: 13px;
}
fieldset label {
  flex-direction: row;
  align-items: center;
  margin: 8px 0;
}
.last-saved {
  font-size: 12px;
  color: #75879a;
}
.editor-error {
  color: #b84436;
  background: #fff0ec;
  padding: 12px;
  border-radius: 9px;
  font-size: 13px;
}
footer {
  justify-content: flex-end;
  margin-top: 20px;
  flex-wrap: wrap;
}
:focus-visible {
  outline: 3px solid #83bcea;
  outline-offset: 2px;
}
@media (max-width: 600px) {
  .help-editor {
    padding: 18px;
  }
  .editor-fields {
    grid-template-columns: 1fr;
  }
}
</style>
