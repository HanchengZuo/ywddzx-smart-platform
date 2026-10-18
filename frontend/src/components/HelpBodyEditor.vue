<template>
  <div class="block-editor">
    <div class="block-toolbar" role="group" aria-label="插入图文内容">
      <button type="button" @click="add('paragraph')">＋ 段落</button
      ><button type="button" @click="add('heading')">小节标题</button
      ><button type="button" @click="add('steps')">操作步骤</button
      ><button type="button" @click="add('note')">注意事项</button>
      <label
        >插入流程图<select :value="''" aria-label="选择流程图插入正文" @change="insertImage">
          <option value="" disabled>选择图片…</option>
          <option v-for="asset in images" :key="asset.id" :value="asset.id">
            {{ asset.title }}
          </option>
        </select></label
      >
    </div>
    <p class="editor-hint">
      点击内容块后插入，新内容会出现在其下方。图片和文字可上下移动，阅读效果与预览一致。
    </p>
    <section
      v-for="(block, index) in blocks"
      :key="block.key"
      class="content-block"
      :class="{ selected: selected === block.key }"
      @focusin="selected = block.key"
      @click="selected = block.key"
    >
      <header>
        <span>{{ labels[block.type] }} {{ index + 1 }}</span>
        <div>
          <button
            type="button"
            :disabled="index === 0"
            :aria-label="`上移第${index + 1}个内容块`"
            @click.stop="move(index, -1)"
          >
            上移</button
          ><button
            type="button"
            :disabled="index === blocks.length - 1"
            :aria-label="`下移第${index + 1}个内容块`"
            @click.stop="move(index, 1)"
          >
            下移</button
          ><button
            type="button"
            :aria-label="`删除第${index + 1}个内容块`"
            @click.stop="remove(index)"
          >
            删除
          </button>
        </div>
      </header>
      <template v-if="block.type === 'image'">
        <HelpInlineImage
          :asset="images.find((asset) => asset.id === block.assetId) || null"
          :caption="block.caption"
          :width="block.width"
          :allow-download="false"
        />
        <div class="image-options">
          <label
            >图片说明<input
              v-model="block.caption"
              maxlength="160"
              placeholder="说明这张图展示的内容"
              @input="emitBody" /></label
          ><label
            >显示宽度<select v-model.number="block.width" @change="emitBody">
              <option :value="100">整行</option>
              <option :value="75">75%</option>
              <option :value="50">50%</option>
            </select></label
          >
        </div>
      </template>
      <input
        v-else-if="block.type === 'heading'"
        v-model="block.text"
        class="heading-input"
        aria-label="小节标题"
        placeholder="输入小节标题"
        @input="emitBody"
      />
      <textarea
        v-else-if="block.type === 'steps' || block.type === 'list'"
        :value="block.items.join('\n')"
        rows="4"
        :aria-label="labels[block.type]"
        placeholder="每行写一个步骤，不需要填写序号"
        @input="setItems(block, $event.target.value)"
      />
      <input
        v-else-if="block.type === 'note'"
        v-model="block.text"
        aria-label="注意事项"
        placeholder="输入操作提醒"
        @input="emitBody"
      />
      <textarea
        v-else
        v-model="block.text"
        rows="4"
        aria-label="正文段落"
        placeholder="输入这一步的操作说明…"
        @input="emitBody"
      />
    </section>
    <button v-if="!blocks.length" class="empty-add" type="button" @click="add('paragraph')">
      开始编写第一段使用说明
    </button>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import HelpInlineImage from './HelpInlineImage.vue'
import { parseHelpBody, serializeHelpBlocks } from '@/utils/helpContent'
const props = defineProps({
  modelValue: { type: String, default: '' },
  images: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])
let sequence = 0,
  lastEmitted = null
const withKeys = (body) => parseHelpBody(body).map((block) => ({ ...block, key: ++sequence }))
const blocks = ref(withKeys(props.modelValue)),
  selected = ref(null)
const labels = {
  paragraph: '正文',
  heading: '标题',
  note: '提示',
  steps: '步骤',
  list: '列表',
  image: '正文图片',
}
watch(
  () => props.modelValue,
  (body) => {
    if (body !== lastEmitted) {
      blocks.value = withKeys(body)
      selected.value = null
    }
  },
)
function emitBody() {
  lastEmitted = serializeHelpBlocks(blocks.value)
  emit('update:modelValue', lastEmitted)
}
function add(type, asset = null) {
  const block = { key: ++sequence, type, text: '' }
  if (type === 'steps') block.items = ['']
  if (type === 'image')
    Object.assign(block, { assetId: asset.id, caption: asset.title, width: 100 })
  const index = blocks.value.findIndex((item) => item.key === selected.value)
  blocks.value.splice(index < 0 ? blocks.value.length : index + 1, 0, block)
  selected.value = block.key
  emitBody()
}
function insertImage(event) {
  const asset = props.images.find((item) => item.id === event.target.value)
  if (asset) add('image', asset)
  event.target.value = ''
}
function move(index, direction) {
  const [block] = blocks.value.splice(index, 1)
  blocks.value.splice(index + direction, 0, block)
  selected.value = block.key
  emitBody()
}
function remove(index) {
  if (window.confirm('确定删除这个内容块？')) {
    blocks.value.splice(index, 1)
    emitBody()
  }
}
function setItems(block, text) {
  block.items = text.split('\n')
  emitBody()
}
</script>
<style scoped>
.block-toolbar {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
  align-items: center;
  padding: 12px;
  border: 1px solid #dce6ef;
  background: #f6f9fc;
  border-radius: 10px;
  margin-top: 14px;
}
button,
select {
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  color: #2c628e;
  border: 1px solid #cfdeeb;
  background: #fff;
  border-radius: 7px;
  padding: 8px 10px;
}
.block-toolbar label {
  display: flex;
  gap: 7px;
  align-items: center;
  font-size: 12px;
  color: #536e85;
}
.editor-hint {
  font-size: 12px;
  color: #7b8da0;
  line-height: 1.8;
}
.content-block {
  padding: 12px 14px;
  border: 1px solid #e1e8ef;
  border-radius: 10px;
  margin-top: 12px;
  background: #fff;
}
.content-block.selected {
  border-color: #83b2d9;
  box-shadow: 0 0 0 2px #2c82c30c;
}
.content-block > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: #7d91a4;
  margin-bottom: 10px;
}
header > div {
  display: flex;
  gap: 5px;
}
header button {
  font-size: 11px;
  padding: 5px 8px;
}
input,
textarea {
  font: inherit;
  font-size: 14px;
  color: #2b4256;
  width: 100%;
  border: 0;
  background: #fafcfe;
  border-radius: 6px;
  padding: 11px;
  box-sizing: border-box;
  line-height: 1.9;
}
textarea {
  resize: vertical;
}
.heading-input {
  font-size: 18px;
  font-weight: 700;
}
.image-options {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
}
.image-options label {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: #698096;
}
.empty-add {
  display: block;
  width: 100%;
  padding: 30px;
  border-style: dashed;
  background: #f9fbfe;
}
button:disabled {
  opacity: 0.35;
  cursor: default;
}
:focus-visible {
  outline: 3px solid #83b9df;
  outline-offset: 2px;
}
@media (max-width: 600px) {
  .block-toolbar label {
    width: 100%;
  }
  .block-toolbar select {
    flex: 1;
    min-width: 0;
  }
  .image-options {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
