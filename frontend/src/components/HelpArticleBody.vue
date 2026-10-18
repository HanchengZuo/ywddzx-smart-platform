<template>
  <div class="help-body">
    <nav v-if="headings.length > 1" class="article-toc" aria-label="本篇目录">
      <strong>本篇内容</strong
      ><button
        v-for="heading in headings"
        :key="heading.id"
        type="button"
        @click="jump(heading.id)"
      >
        {{ heading.text }}
      </button>
    </nav>
    <article ref="article">
      <template v-for="(block, index) in blocks" :key="index">
        <h3 v-if="block.type === 'heading'" :data-section="block.id">{{ block.text }}</h3>
        <ol v-else-if="block.type === 'steps'">
          <li v-for="(text, n) in block.items" :key="n">{{ text }}</li>
        </ol>
        <ul v-else-if="block.type === 'list'">
          <li v-for="(text, n) in block.items" :key="n">{{ text }}</li>
        </ul>
        <aside v-else-if="block.type === 'note'" class="article-note">{{ block.text }}</aside>
        <HelpInlineImage
          v-else-if="block.type === 'image'"
          :asset="images.find((asset) => asset.id === block.assetId) || null"
          :caption="block.caption"
          :width="block.width"
        />
        <p v-else>{{ block.text }}</p>
      </template>
    </article>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { parseHelpBody } from '@/utils/helpContent'
import HelpInlineImage from './HelpInlineImage.vue'
const props = defineProps({
  body: { type: String, default: '' },
  images: { type: Array, default: () => [] },
})
const article = ref(null)
const blocks = computed(() => parseHelpBody(props.body))
const headings = computed(() => blocks.value.filter((item) => item.type === 'heading'))
const jump = (id) =>
  article.value
    ?.querySelector(`[data-section="${id}"]`)
    ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
</script>
<style scoped>
.help-body {
  color: #33465a;
  font-size: 15px;
  line-height: 1.95;
  overflow-wrap: anywhere;
}
.article-toc {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  padding: 16px 18px;
  background: #f5f8fc;
  border: 1px solid #e2eaf2;
  border-radius: 12px;
  margin-bottom: 24px;
}
.article-toc strong {
  flex-basis: 100%;
  color: #213c57;
  font-size: 12px;
}
.article-toc button {
  font: inherit;
  font-size: 12px;
  color: #2c6da5;
  cursor: pointer;
  background: none;
  border: 0;
  padding: 0;
  text-align: left;
}
article h3 {
  font-size: 18px;
  color: #173c5f;
  margin: 28px 0 12px;
  scroll-margin-top: 110px;
}
article h3:first-child {
  margin-top: 0;
}
article p {
  white-space: pre-line;
  margin: 12px 0;
}
article ul,
article ol {
  padding-left: 24px;
  margin: 12px 0;
}
article li {
  padding-left: 5px;
  margin: 8px 0;
}
article li::marker {
  color: #2f75ac;
  font-weight: 700;
}
.article-note {
  padding: 13px 16px;
  border-left: 3px solid #d0aa50;
  border-radius: 0 8px 8px 0;
  background: #fffbef;
  color: #786335;
  font-size: 13px;
  margin: 20px 0;
}
button:focus-visible {
  outline: 3px solid #78b8e4;
  outline-offset: 3px;
}
</style>
