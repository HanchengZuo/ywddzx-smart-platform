<template>
  <aside class="permission-category-sidebar">
    <label class="permission-search">
      <span>查找页面权限</span>
      <input :value="keyword" type="search" placeholder="搜索页面或权限"
        @input="$emit('update:keyword', $event.target.value)" />
    </label>
    <nav class="permission-category-nav" aria-label="页面权限分类">
      <button v-for="group in groups" :key="group.category" type="button"
        class="permission-category-button" :class="{ active: active === group.category }"
        :aria-pressed="active === group.category" :aria-controls="controls"
        @click="$emit('select', group.category)">
        <span>{{ group.category }}</span>
        <small>{{ countEnabledPermissions(group, permissions, role) }}/{{ group.items.length }}</small>
      </button>
      <p v-if="!groups.length" class="permission-empty">没有匹配的页面或权限</p>
    </nav>
  </aside>
</template>

<script setup>
import { countEnabledPermissions } from '../utils/permissionPanel.js'
defineProps({ groups: Array, permissions: Object, role: String, keyword: String, active: String, controls: String })
defineEmits(['update:keyword', 'select'])
</script>

<style scoped>
.permission-category-sidebar { display: flex; flex-direction: column; min-width: 0; min-height: 0; height: 100%; box-sizing: border-box; padding: 10px; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; }
.permission-search { display: grid; gap: 7px; padding: 4px 3px 12px; color: #475569; font-size: 12px; font-weight: 800; }
.permission-search input { box-sizing: border-box; min-width: 0; width: 100%; height: 36px; border: 1px solid #d7e0ea; border-radius: 9px; padding: 0 9px; font: inherit; background: #f8fafc; }
.permission-category-nav { display: flex; flex-direction: column; gap: 4px; min-height: 0; overflow: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.permission-category-button { display: flex; flex-shrink: 0; align-items: center; justify-content: space-between; gap: 10px; width: 100%; padding: 11px 10px; border: 1px solid transparent; border-radius: 9px; background: transparent; color: #475569; text-align: left; font: inherit; font-size: 13px; cursor: pointer; }
.permission-category-button span { min-width: 0; line-height: 1.5; }
.permission-category-button small { flex-shrink: 0; padding: 2px 6px; border-radius: 6px; background: #f1f5f9; color: #64748b; font-size: 11px; font-variant-numeric: tabular-nums; }
.permission-category-button:hover { background: #f8fafc; }
.permission-category-button.active { border-color: #bfdbfe; background: #eff6ff; color: #1d4ed8; font-weight: 800; }
.permission-category-button.active small { background: #dbeafe; color: #1d4ed8; }
.permission-category-button:focus-visible, input:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.permission-empty { margin: 12px 4px; color: #64748b; font-size: 12px; line-height: 1.7; }
@media (max-width: 980px) {
  .permission-category-sidebar { height: auto; }
  .permission-category-nav { flex-direction: row; max-height: none; padding-bottom: 4px; }
  .permission-category-button { width: auto; }
  .permission-category-button span { white-space: nowrap; }
}
</style>
