<template>
  <div ref="host" class="edition-select" @keydown.esc="open = false">
    <button type="button" class="edition-control" :aria-expanded="open" @click="open = !open">
      <span>{{ modelValue.length ? modelValue.join('、') : '选择检查表及版本' }}</span><span>⌄</span>
    </button>
    <div v-if="open" class="edition-popup">
      <input v-model="search" placeholder="搜索检查表 / 版本" aria-label="搜索检查表及版本" />
      <p v-if="error" role="alert">{{ error }} <button type="button" @click="load">重试</button></p>
      <p v-else-if="loading">正在读取版本…</p>
      <template v-else>
        <details v-for="table in matches" :key="table.id" :open="!!search">
          <summary>{{ table.table_name }} <small>{{ table.versions?.length || 1 }} 个版本</small></summary>
          <button type="button" :class="{ selected: modelValue.includes(table.table_name) }" @click="toggle(table.table_name)">{{ modelValue.includes(table.table_name) ? '✓ ' : '' }}全部版本</button>
          <button v-for="v in table.versions" :key="v.id" type="button" :class="{ selected: modelValue.includes(token(table,v)) }" @click="toggle(token(table,v))">
            <span>{{ modelValue.includes(token(table,v)) ? '✓ ' : '' }}v{{ v.version_number }} · {{ v.version_name }}</span>
            <small :class="{ enabled: v.is_active }">{{ v.is_active ? '启用' : '历史 / 停用' }}</small>
          </button>
        </details>
        <p v-if="!matches.length">暂无匹配检查表</p>
      </template>
      <footer><button type="button" @click="$emit('update:modelValue', [])">清空</button><button type="button" @click="open = false">完成</button></footer>
    </div>
  </div>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import axios from 'axios'
const props = defineProps({ modelValue: { type: Array, default: () => [] }, options: { type: Array, default: () => [] }, scope: { type: String, default: 'issues' } })
const emit = defineEmits(['update:modelValue'])
const host = ref(null), open = ref(false), search = ref(''), rows = ref([]), loading = ref(false), error = ref('')
const token = (table, version) => `${table.table_name} · v${version.version_number}`
const matches = computed(() => rows.value.filter(t => (!props.options.length || props.options.includes(t.table_name)) &&
  `${t.table_name} ${t.versions?.map(v => `v${v.version_number} ${v.version_name}`).join(' ')}`.toLowerCase().includes(search.value.toLowerCase())))
function toggle(value) {
  emit('update:modelValue', props.modelValue.includes(value) ? props.modelValue.filter(v => v !== value) : [...props.modelValue, value])
}
async function load() {
  loading.value = true; error.value = ''
  try { rows.value = (await axios.get('/api/inspection-tables', { params: { user_id: localStorage.getItem('user_id'), scope: props.scope, include_inactive: 1 } })).data }
  catch { error.value = '版本目录加载失败。' }
  finally { loading.value = false }
}
const outside = event => { if (!host.value?.contains(event.target)) open.value = false }
onMounted(() => { load(); document.addEventListener('pointerdown', outside) })
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside))
</script>
<style scoped>
.edition-select{position:relative;min-width:0}.edition-control{display:flex;justify-content:space-between;gap:12px;width:100%;min-height:44px;border:1px solid #c9d8e5;border-radius:10px;background:white;padding:10px 12px;text-align:left;color:#294b65;font:inherit}.edition-control span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.edition-popup{position:absolute;z-index:60;top:calc(100% + 6px);left:0;min-width:100%;width:min(440px,85vw);max-height:460px;overflow:auto;background:white;border:1px solid #bdd0df;border-radius:12px;box-shadow:0 14px 35px #173b5626;padding:10px}.edition-popup input{box-sizing:border-box;width:100%;padding:10px;border:1px solid #c9d8e5;border-radius:8px}.edition-popup summary{padding:12px 6px;cursor:pointer;font-weight:600;color:#173b56}.edition-popup small{color:#7b8fa0;font-size:12px}.edition-popup button{display:flex;align-items:center;justify-content:space-between;gap:10px;border:0;border-radius:6px;background:transparent;padding:10px 12px;width:100%;text-align:left;color:#294b65;font:inherit;cursor:pointer}.edition-popup button:hover,.edition-popup button.selected{background:#e6f3f5;color:#156b76}.edition-popup .enabled{color:#16816e}.edition-popup footer{display:flex;border-top:1px solid #e6edf3;margin-top:8px;position:sticky;bottom:-10px;background:white}.edition-popup footer button{text-align:center;justify-content:center}
</style>
