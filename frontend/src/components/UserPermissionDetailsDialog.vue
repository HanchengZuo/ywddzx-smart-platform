<template>
  <Teleport to="body">
    <dialog ref="dialog" class="user-permission-dialog" aria-labelledby="user-permission-title" @cancel.prevent="$emit('close')" @close="$emit('close')" @click="closeOnBackdrop">
      <div v-if="user" class="permission-inspector">
        <header class="inspector-header">
          <div><span class="inspector-eyebrow">用户权限 · 只读查看</span><h3 id="user-permission-title">{{ user.real_name || user.username }} 的权限</h3><p>{{ user.username }} · ID {{ user.id }} <span>{{ roleLabelFor(roles, user.role) }}</span></p></div>
          <button class="inspector-close" type="button" aria-label="关闭权限详情" autofocus @click="$emit('close')">×</button>
        </header>
        <div class="inspector-summary"><div><span>已开启</span><strong>{{ summary.enabled }}<small> / {{ summary.total }} 项</small></strong></div><div><span>未开启</span><strong>{{ summary.disabled }}<small> 项</small></strong></div><div><span>配置方式</span><strong class="inspector-configuration">{{ summary.label }}</strong></div></div>
        <p class="inspector-notice">展示该用户已保存的生效权限，不受当前未保存的编辑内容影响。范围限制与角色约束组合生效，最终以服务端校验为准。</p>
        <div class="inspector-toolbar"><span>{{ matchedCount }} 项匹配权限</span><label><span>权限状态</span><select v-model="status"><option value="all">全部权限</option><option value="enabled">仅已开启</option><option value="disabled">仅未开启</option></select></label></div>
        <div class="inspector-workspace">
          <PermissionCategoryNav v-model:keyword="keyword" :groups="filteredGroups" :permissions="user.permissions || {}" :role="user.role" :active="activeCategory" controls="user-permission-inspector-detail" @select="activeCategory = $event" />
          <section id="user-permission-inspector-detail" ref="detail" class="inspector-detail" aria-live="polite">
            <template v-if="activeGroup"><div class="inspector-category-head"><h4>{{ activeGroup.category }}</h4><span>{{ activeGroup.items.filter(item => item.enabled).length }} 项已开启</span></div>
              <article v-for="permission in activeGroup.items" :key="permission.key" class="inspector-permission" :class="{ enabled: permission.enabled }">
                <div class="inspector-permission-head"><strong>{{ permission.name }}</strong><span class="inspector-state" :class="{ enabled: permission.enabled }">{{ permission.enabled ? '已开启' : '未开启' }}</span></div>
                <p>{{ permission.description }}</p><div class="inspector-origin"><span>{{ permission.source }}</span><code>{{ permission.key }}</code></div>
                <div v-if="permission.scope" class="inspector-scope"><strong>{{ permission.scope.title }}</strong><ul><li v-for="value in permission.scope.values" :key="value">{{ value }}</li></ul></div>
              </article>
            </template>
            <div v-else class="inspector-empty"><strong>没有匹配的权限</strong><p>调整搜索词或权限状态后重试。</p></div>
          </section>
        </div>
        <footer><span>最后更新 {{ user.updated_at || '未记录' }}</span><div><button class="inspector-secondary" type="button" @click="$emit('close')">关闭</button><button class="inspector-primary" type="button" @click="editUser">编辑该用户</button></div></footer>
      </div>
    </dialog>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import PermissionCategoryNav from './PermissionCategoryNav.vue'
import { resolvePermissionCategory } from '../utils/permissionPanel.js'
import { permissionSummary, roleLabelFor, userPermissionGroups } from '../utils/userDirectory.js'

const props = defineProps({ user: { type: Object, default: null }, catalog: { type: Array, default: () => [] }, roles: { type: Array, default: () => [] }, tables: { type: Array, default: () => [] }, roleOverrides: { type: Object, default: () => ({}) } })
const emit = defineEmits(['close', 'edit'])
const dialog = ref(null)
const detail = ref(null)
const keyword = ref('')
const status = ref('all')
const activeCategory = ref('')
const summary = computed(() => permissionSummary(props.user || {}, props.catalog))
const groups = computed(() => userPermissionGroups(props.user, props.catalog, props.tables, props.roleOverrides))
const filteredGroups = computed(() => {
  const query = keyword.value.trim().toLocaleLowerCase()
  return groups.value.map(group => ({ ...group, items: group.items.filter(item => (
    (status.value === 'all' || item.enabled === (status.value === 'enabled')) &&
    (!query || [group.category, item.name, item.description, item.key, item.source, ...(item.scope?.values || [])]
      .some(value => String(value || '').toLocaleLowerCase().includes(query)))
  )) })).filter(group => group.items.length)
})
const matchedCount = computed(() => filteredGroups.value.reduce((total, group) => total + group.items.length, 0))
const activeGroup = computed(() => filteredGroups.value.find(group => group.category === activeCategory.value))
watch(filteredGroups, groups => { activeCategory.value = resolvePermissionCategory(groups, activeCategory.value) }, { immediate: true })
watch(activeCategory, () => { if (detail.value) detail.value.scrollTop = 0 }, { flush: 'post' })
watch(() => props.user?.id, async id => {
  keyword.value = ''
  status.value = 'all'
  activeCategory.value = resolvePermissionCategory(filteredGroups.value, '')
  await nextTick()
  if (id && props.user?.id === id && !dialog.value?.open) dialog.value?.showModal()
  if (!props.user) dialog.value?.close()
}, { immediate: true })
const closeOnBackdrop = event => {
  if (event.target !== dialog.value) return
  const bounds = dialog.value.getBoundingClientRect()
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) emit('close')
}
const editUser = () => { const user = props.user; emit('close'); if (user) emit('edit', user) }
onBeforeUnmount(() => dialog.value?.close())
</script>

<style scoped>
.user-permission-dialog, .user-permission-dialog * { box-sizing: border-box; }
.user-permission-dialog { width: min(1100px, calc(100vw - 32px)); height: min(880px, calc(100dvh - 32px)); max-width: none; max-height: none; margin: auto; padding: 0; border: 1px solid #dbe4ee; border-radius: 20px; color: #172033; overflow: hidden; box-shadow: 0 32px 100px #0f172a40; }
.user-permission-dialog::backdrop { background: #0f172a75; backdrop-filter: blur(4px); }
.permission-inspector { display: flex; flex-direction: column; height: 100%; padding: 24px; background: linear-gradient(155deg, #f5f9ff, #fff 32%); }
.inspector-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.inspector-header > div { min-width: 0; }
.inspector-eyebrow { color: #2563eb; font-size: 12px; font-weight: 700; }
h3 { margin: 5px 0 7px; font-size: 22px; overflow-wrap: anywhere; }
.inspector-header p { margin: 0; color: #64748b; font-size: 12px; line-height: 1.8; overflow-wrap: anywhere; }
.inspector-header p span { display: inline-block; margin-left: 8px; color: #475569; }
button, select { font: inherit; }
button { cursor: pointer; }
.inspector-close { width: 34px; height: 34px; flex-shrink: 0; padding: 0; border: 0; border-radius: 9px; background: #edf2f8; color: #52637a; font-size: 24px; }
.inspector-summary { display: grid; grid-template-columns: 1fr 1fr 1.2fr; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; margin-top: 18px; }
.inspector-summary > div { padding: 13px 16px; }
.inspector-summary > div + div { border-left: 1px solid #edf1f6; }
.inspector-summary span { display: block; color: #64748b; font-size: 11px; margin-bottom: 5px; }
.inspector-summary strong { color: #1e3a5f; font-size: 24px; font-variant-numeric: tabular-nums; }
.inspector-summary small { color: #94a3b8; font-size: 12px; font-weight: 400; }
.inspector-summary .inspector-configuration { font-size: 15px; line-height: 30px; }
.inspector-notice { margin: 10px 0; color: #8491a5; font-size: 11px; line-height: 1.7; }
.inspector-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 0 0 12px; color: #64748b; font-size: 12px; }
.inspector-toolbar label { display: flex; align-items: center; gap: 8px; }
.inspector-toolbar select { height: 32px; border: 1px solid #d7e0ea; border-radius: 8px; padding: 0 8px; background: #fff; color: #334155; font-size: 12px; }
.inspector-workspace { display: grid; grid-template-columns: 215px minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); gap: 16px; flex: 1; min-height: 0; overflow: hidden; overflow-anchor: none; }
.inspector-detail { min-width: 0; min-height: 0; padding: 2px 5px; overflow: auto; scrollbar-gutter: stable; overscroll-behavior: contain; overflow-anchor: none; }
.inspector-category-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; padding: 10px 0 14px; }
h4 { margin: 0; color: #1d4ed8; font-size: 15px; }
.inspector-category-head > span { color: #94a3b8; font-size: 11px; }
.inspector-permission { border: 1px solid #e2e8f0; border-radius: 12px; padding: 15px; margin-bottom: 10px; background: #fafbfc; }
.inspector-permission.enabled { background: #fff; }
.inspector-permission-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.inspector-permission-head > strong { font-size: 13px; line-height: 1.7; }
.inspector-state { flex-shrink: 0; border-radius: 6px; padding: 4px 7px; color: #8491a5; background: #edf1f5; font-size: 11px; }
.inspector-state.enabled { color: #16734f; background: #eaf7ef; }
.inspector-permission > p { color: #64748b; font-size: 12px; line-height: 1.8; margin: 7px 0; }
.inspector-origin { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; color: #94a3b8; font-size: 10px; }
.inspector-origin > span { padding: 2px 5px; border: 1px solid #e2e8f0; border-radius: 4px; color: #64748b; }
code { overflow-wrap: anywhere; font-size: 10px; }
.inspector-scope { margin-top: 11px; padding: 11px; background: #f5f9ff; border-radius: 8px; }
.inspector-scope > strong { color: #536d91; font-size: 11px; }
.inspector-scope ul { display: flex; flex-wrap: wrap; gap: 6px; list-style: none; margin: 8px 0 0; padding: 0; }
.inspector-scope li { color: #3e5c87; border: 1px solid #dce7f7; border-radius: 6px; padding: 5px 7px; background: #fff; font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; }
.inspector-empty { padding: 50px 10px; color: #8491a5; text-align: center; font-size: 13px; }
footer { flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding-top: 16px; margin-top: 16px; border-top: 1px solid #e2e8f0; }
footer > span { color: #94a3b8; font-size: 11px; }
footer > div { display: flex; gap: 8px; }
.inspector-primary, .inspector-secondary { min-height: 36px; padding: 0 14px; border: 1px solid #d7e0ea; border-radius: 9px; background: #fff; color: #475569; font-size: 12px; font-weight: 700; white-space: nowrap; }
.inspector-primary { color: #fff; border-color: #2563eb; background: #2563eb; }
button:focus-visible, select:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
@media (max-width: 980px) { .inspector-workspace { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); gap: 10px; } }
@media (max-width: 600px) {
  .user-permission-dialog { width: calc(100vw - 16px); height: calc(100dvh - 16px); border-radius: 14px; }
  .permission-inspector { padding: 14px; } h3 { font-size: 18px; }
  .inspector-summary { margin-top: 12px; } .inspector-summary > div { padding: 10px; }
  .inspector-summary strong { font-size: 21px; } .inspector-summary small { font-size: 10px; }
  .inspector-summary .inspector-configuration { font-size: 13px; line-height: 26px; }
  .inspector-notice { font-size: 10px; margin: 8px 0; }
  .inspector-permission { padding: 12px; }
  footer { padding-top: 10px; margin-top: 10px; flex-wrap: wrap; }
  footer > div { margin-left: auto; }
}
</style>
