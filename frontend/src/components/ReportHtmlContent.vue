<template>
  <div class="html-report-content">
    <nav v-if="sections.length > 1" class="html-contents" aria-label="HTML报告目录">
      <strong>报告目录</strong>
      <button
        v-for="section in sections"
        :key="section.id"
        type="button"
        @click="goToSection(section.id)"
      >
        {{ section.title }}
      </button>
    </nav>
    <article
      v-for="section in sections"
      :id="section.id"
      :key="section.id"
      class="html-chapter"
      tabindex="-1"
    >
      <h2>{{ section.title }}</h2>
      <p v-for="(paragraph, index) in section.paragraphs" :key="index">{{ paragraph }}</p>
      <template v-for="(data, index) in section.tables" :key="`table-${index}`">
        <div
          v-if="data.rows.length"
          class="html-table-wrap"
          tabindex="0"
          role="region"
          :aria-label="`${section.title}数据表`"
        >
          <table>
            <thead>
              <tr>
                <th v-for="(heading, column) in data.headings" :key="column" scope="col">
                  {{ heading }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rowIndex) in data.rows" :key="rowIndex">
                <td v-for="(cell, column) in row" :key="column" :colspan="cell?.colspan || 1">
                  {{ cellText(cell) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <section v-for="(item, index) in section.items" :key="`item-${index}`" class="html-analysis">
        <h3 v-if="item.title">{{ item.title }}</h3>
        <p v-if="item.content">{{ item.content }}</p>
      </section>
      <div
        v-if="section.issues.length"
        class="html-issues"
        :class="{ single: section.issues.length === 1 }"
      >
        <section v-for="(issue, index) in section.issues" :key="`${issue.issue_id}-${index}`">
          <h3>{{ issue.station_name || '问题记录' }}</h3>
          <p>{{ issue.description || '该成稿未保存问题描述。' }}</p>
          <figure v-if="issue.issue_photo">
            <button
              type="button"
              :aria-label="`放大查看${issue.station_name || '问题'}照片`"
              @click="$emit('photo', issue)"
            >
              <img
                :src="resolveImage(issue.issue_photo)"
                :alt="`${issue.station_name || '问题'}照片`"
                loading="lazy"
              />
            </button>
            <figcaption>
              {{ issue.station_name
              }}<span v-if="issue.issue_id"> · 问题 {{ issue.issue_id }}</span>
            </figcaption>
          </figure>
        </section>
      </div>
      <p
        v-if="
          !section.paragraphs.length &&
          !section.items.length &&
          !section.issues.length &&
          !section.tables.some((data) => data.rows.length)
        "
        class="html-empty"
      >
        此成稿没有保存该章节的详细内容，请查看PPT预览。
      </p>
    </article>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { buildReportHtmlSections } from '@/utils/reportHtmlContent'
const props = defineProps({
  report: { type: Object, required: true },
  reportType: String,
  resolveImage: { type: Function, required: true },
})
defineEmits(['photo'])
const sections = computed(() => buildReportHtmlSections(props.report, props.reportType))
const cellText = (value) => (value && typeof value === 'object' ? value.text : (value ?? ''))
function goToSection(id) {
  const section = document.getElementById(id)
  section?.scrollIntoView({
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    block: 'start',
  })
  section?.focus({ preventScroll: true })
}
</script>
<style scoped>
.html-report-content {
  color: #1b3045;
  font-size: 16px;
  line-height: 1.85;
}
.html-contents {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 18px;
  margin-bottom: 24px;
  background: #edf3f8;
  border: 1px solid #b8cbdc;
  border-radius: 10px;
}
.html-contents > strong {
  flex-basis: 100%;
  color: #153b59;
}
.html-contents button {
  color: #254d6b;
  background: #fff;
  border: 1px solid #b8cbdc;
  padding: 7px 10px;
  border-radius: 6px;
  text-align: left;
  cursor: pointer;
  font-size: 13px;
  line-height: 1.5;
}
.html-contents button:hover {
  background: #dcebf6;
  border-color: #547f9e;
}
.html-chapter {
  padding: 0 0 28px;
  margin-bottom: 28px;
  border-bottom: 1px solid #c4d2de;
  scroll-margin-top: 22px;
}
.html-chapter h2 {
  padding: 12px 16px;
  background: #183e5a;
  color: #fff;
  border-radius: 6px;
  font-size: 19px;
  margin: 0 0 18px;
  line-height: 1.6;
}
.html-chapter h3 {
  color: #183e5a;
  font-size: 17px;
  margin: 0 0 8px;
}
.html-chapter p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 12px 0;
}
.html-table-wrap {
  overflow-x: auto;
  margin: 18px 0;
  border: 1px solid #afc3d3;
  border-radius: 8px;
}
table {
  border-collapse: collapse;
  width: 100%;
  font-size: 14px;
  line-height: 1.65;
}
th,
td {
  padding: 11px 13px;
  border-bottom: 1px solid #ccdae5;
  text-align: left;
  overflow-wrap: anywhere;
  min-width: 75px;
}
th {
  color: #193d58;
  background: #e4eef6;
  font-weight: 700;
}
tbody tr:nth-child(even) {
  background: #f4f7fa;
}
td:nth-child(2) {
  min-width: 115px;
}
.html-analysis {
  margin: 18px 0;
}
.html-issues {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 18px;
}
.html-issues.single {
  grid-template-columns: 1fr;
}
.html-issues > section {
  padding: 16px;
  border: 1px solid #c0d0de;
  border-radius: 8px;
  min-width: 0;
}
figure {
  margin: 12px 0 0;
}
figure button {
  padding: 0;
  border: 0;
  background: #edf3f8;
  width: 100%;
  cursor: zoom-in;
}
figure img {
  display: block;
  width: 100%;
  max-height: 360px;
  object-fit: contain;
}
figcaption {
  color: #445e73;
  text-align: center;
  font-size: 13px;
}
.html-empty {
  color: #50677b;
}
:is(button, .html-table-wrap, .html-chapter):focus-visible {
  outline: 2px solid #126b9a;
  outline-offset: 3px;
}
@media (max-width: 700px) {
  .html-report-content {
    font-size: 15px;
  }
  .html-issues {
    grid-template-columns: 1fr;
  }
  .html-chapter h2 {
    font-size: 17px;
  }
  .html-contents {
    padding: 12px;
  }
  th,
  td {
    padding: 9px;
  }
}
</style>
