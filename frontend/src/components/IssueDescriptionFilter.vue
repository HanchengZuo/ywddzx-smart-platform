<template>
  <div class="description-search">
    <input
      :value="modelValue"
      aria-label="问题描述关键词"
      :aria-invalid="Boolean(error)"
      aria-describedby="issue-description-search-help"
      placeholder="例如：接地 锈蚀（多个词用空格或逗号分隔）"
      @input="$emit('update:modelValue', $event.target.value)"
      @keydown.enter="applyOnEnter"
    />
    <div class="description-search-options" role="group" aria-label="问题描述匹配方式">
      <button
        v-for="option in modes"
        :key="option.value"
        type="button"
        :aria-pressed="matchMode === option.value"
        :class="{ active: matchMode === option.value }"
        @click="$emit('update:matchMode', option.value)"
      >
        {{ option.label }}
      </button>
      <span v-if="keywords.length" class="keyword-count">{{ keywords.length }} 个关键词</span>
    </div>
    <div v-if="keywords.length && !error" class="description-keywords" aria-label="已输入关键词">
      <span v-for="keyword in keywords" :key="keyword.toLowerCase()" class="description-keyword">
        <span>{{ keyword }}</span>
        <button type="button" :aria-label="`移除关键词 ${keyword}`" @click="removeKeyword(keyword)">
          ×
        </button>
      </span>
    </div>
    <p
      id="issue-description-search-help"
      class="description-search-help"
      :class="{ error }"
      :role="error ? 'alert' : undefined"
    >
      {{
        error ||
        (matchMode === 'any'
          ? '任一包含：命中其中任意一个关键词即可。点击“开始筛选”后生效。'
          : '全部包含：同一条问题需含所有关键词，顺序不限。点击“开始筛选”后生效。')
      }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { descriptionFilterError, parseDescriptionKeywords } from '@/utils/issueDescriptionFilter'

const props = defineProps({
  modelValue: { type: String, default: '' },
  matchMode: { type: String, default: 'all' },
})
const emit = defineEmits(['update:modelValue', 'update:matchMode', 'apply'])
const keywords = computed(() => parseDescriptionKeywords(props.modelValue))
const error = computed(() => descriptionFilterError(props.modelValue))
const modes = [
  { value: 'all', label: '全部包含' },
  { value: 'any', label: '任一包含' },
]
const removeKeyword = (keyword) =>
  emit('update:modelValue', keywords.value.filter((item) => item !== keyword).join(' '))
const applyOnEnter = (event) => {
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  if (!error.value) emit('apply')
}
</script>

<style scoped>
.description-search {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.description-search input {
  width: 100%;
  height: 42px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 14px;
  box-sizing: border-box;
}
.description-search-options {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.description-search-options button {
  padding: 5px 10px;
  border: 1px solid #d5dfec;
  border-radius: 7px;
  background: #fff;
  color: #52657c;
  font-size: 12px;
  cursor: pointer;
}
.description-search-options button.active {
  border-color: #2563eb;
  color: #1d4ed8;
  background: #eff6ff;
  font-weight: 600;
}
.keyword-count {
  font-size: 12px;
  color: #64748b;
}
.description-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.description-keyword {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  padding: 3px 7px;
  border-radius: 6px;
  background: #eef4fc;
  color: #215b9c;
  font-size: 12px;
}
.description-keyword > span {
  overflow-wrap: anywhere;
  min-width: 0;
}
.description-keyword button {
  border: 0;
  background: none;
  color: inherit;
  font-size: 16px;
  cursor: pointer;
  padding: 0 3px;
  flex-shrink: 0;
}
.description-search-help {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}
.description-search-help.error {
  color: #b91c1c;
}
@media (max-width: 768px) {
  .description-search input {
    height: 46px;
    font-size: 15px;
  }
  .description-search-options button {
    min-height: 36px;
  }
  .description-keyword button {
    min-width: 28px;
    min-height: 28px;
  }
}
</style>
