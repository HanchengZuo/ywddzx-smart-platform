<template>
  <section class="phrase-panel">
    <div>
      <small>检查内容短语 / REPORT PHRASES</small>
      <h3>设备设施规范短语</h3>
      <p>编辑报告统计和选题使用的短语，不改动原始问题或规范。保存后重新生成报告生效。</p>
    </div>
    <button :disabled="loading" @click="open">查看与调整短语</button>
    <p v-if="error" role="alert">{{ error }}</p>
    <Teleport to="body"
      ><dialog ref="dialog" class="phrase-dialog" @cancel.prevent="close">
        <header>
          <div>
            <small>设备设施检查表（现场）</small>
            <h3>检查内容短语</h3>
          </div>
          <button :disabled="saving" aria-label="关闭短语面板" @click="close">关闭 ×</button>
        </header>
        <div class="phrase-tools">
          <input
            v-model="keyword"
            aria-label="搜索规范短语"
            placeholder="搜索规范ID、检查内容或短语"
          /><span>{{ visible.length }} 条规范 · 不调用 AI</span>
        </div>
        <p v-if="error" role="alert">{{ error }}</p>
        <div class="phrase-list">
          <article v-for="row in visible" :key="row.external_standard_id">
            <div>
              <strong>规范 {{ row.external_standard_id }}</strong>
              <p>{{ row.fields['检查内容'] || row.fields['检查事项'] || '未填写检查内容' }}</p>
            </div>
            <label
              >检查内容短语<input
                v-model="draft[row.external_standard_id]"
                :disabled="saving"
                maxlength="100"
                :aria-label="`规范 ${row.external_standard_id} 的短语`"
            /></label>
          </article>
          <p v-if="!visible.length">没有匹配的规范。</p>
        </div>
        <footer>
          <span>{{
            meta.updated_by_name
              ? `最近保存：${meta.updated_by_name} · ${meta.updated_at}`
              : '尚未人工调整，采用规范字段或既有参考短语。'
          }}</span
          ><button :disabled="saving || !dirty" @click="save">
            {{ saving ? '保存中…' : '保存短语' }}
          </button>
        </footer>
      </dialog></Teleport
    >
  </section>
</template>
<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'
const emit = defineEmits(['saved'])
const dialog = ref(null),
  rows = ref([]),
  draft = ref({}),
  meta = ref({}),
  signature = ref(''),
  keyword = ref(''),
  error = ref(''),
  loading = ref(false),
  saving = ref(false)
const visible = computed(() =>
  rows.value.filter((r) =>
    `${r.external_standard_id} ${Object.values(r.fields).join(' ')} ${draft.value[r.external_standard_id]}`.includes(
      keyword.value.trim(),
    ),
  ),
)
const dirty = computed(() =>
  rows.value.some((r) => draft.value[r.external_standard_id] !== r.phrase),
)
function adopt(data) {
  rows.value = data.standards
  draft.value = Object.fromEntries(rows.value.map((r) => [r.external_standard_id, r.phrase]))
  meta.value = data.meta
  signature.value = data.data_signature
}
async function open() {
  loading.value = true
  error.value = ''
  try {
    adopt((await axios.get('/api/inspection-reports/equipment-phrases')).data)
    keyword.value = ''
    dialog.value.showModal()
  } catch (e) {
    error.value = e.response?.data?.error || '短语读取失败，请重试。'
  } finally {
    loading.value = false
  }
}
function close() {
  if (!saving.value) dialog.value.close()
}
async function save() {
  saving.value = true
  error.value = ''
  try {
    const phrases = Object.fromEntries(
      rows.value
        .filter((r) => draft.value[r.external_standard_id] !== r.phrase)
        .map((r) => [r.external_standard_id, draft.value[r.external_standard_id]]),
    )
    adopt(
      (
        await axios.put('/api/inspection-reports/equipment-phrases', {
          phrases,
          revision: meta.value.revision,
          data_signature: signature.value,
        })
      ).data,
    )
    emit('saved')
    dialog.value.close()
  } catch (e) {
    error.value = e.response?.data?.error || '保存失败，请重试。'
  } finally {
    saving.value = false
  }
}
</script>
<style scoped>
.phrase-panel {
  display: flex;
  gap: 20px;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  border: 1px solid #bfd1df;
  border-left: 5px solid #1f7486;
  border-radius: 16px;
  background: #f6fafc;
  color: #244659;
  margin: 20px 0;
}
.phrase-panel h3 {
  margin: 8px 0;
}
.phrase-panel p {
  margin: 8px 0;
  line-height: 1.7;
}
.phrase-panel small {
  color: #287788;
  font-weight: 700;
}
button {
  border: 1px solid #acc8d9;
  border-radius: 9px;
  background: #1e6683;
  color: #fff;
  padding: 11px 17px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
.phrase-dialog {
  width: min(1000px, 94vw);
  max-height: 88dvh;
  padding: 0;
  border: 1px solid #abc3d3;
  border-radius: 18px;
  color: #244659;
}
.phrase-dialog::backdrop {
  background: #11283c99;
}
.phrase-dialog[open] {
  display: flex;
  flex-direction: column;
}
.phrase-dialog header,
.phrase-dialog footer,
.phrase-tools {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  background: #f2f7fa;
}
.phrase-dialog h3 {
  margin: 8px 0 0;
}
.phrase-list {
  overflow: auto;
  padding: 0 24px;
}
.phrase-list article {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  padding: 20px 0;
  border-bottom: 1px solid #dde8ef;
}
.phrase-list p {
  font-size: 14px;
  line-height: 1.7;
  color: #587084;
  white-space: pre-wrap;
}
.phrase-list label {
  font-size: 13px;
  display: grid;
  gap: 8px;
  align-content: center;
}
input {
  padding: 12px;
  border: 1px solid #afc9d8;
  border-radius: 8px;
  width: 100%;
  box-sizing: border-box;
  font: inherit;
  color: #173e54;
}
.phrase-tools input {
  max-width: 480px;
}
.phrase-dialog footer span {
  font-size: 13px;
  color: #587084;
}
[role='alert'] {
  color: #b23428;
  padding: 0 24px;
}
@media (max-width: 650px) {
  .phrase-panel,
  .phrase-tools,
  .phrase-dialog footer {
    flex-direction: column;
    align-items: stretch;
  }
  .phrase-list article {
    grid-template-columns: 1fr;
    gap: 8px;
  }
  .phrase-dialog {
    width: 96vw;
  }
  .phrase-dialog header,
  .phrase-dialog footer,
  .phrase-tools {
    padding: 16px;
  }
  .phrase-list {
    padding: 0 16px;
  }
}
</style>
