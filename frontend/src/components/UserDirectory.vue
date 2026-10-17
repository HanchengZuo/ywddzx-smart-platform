<template>
  <div class="user-directory">
    <header class="directory-header">
      <div><p class="directory-eyebrow">账号目录</p><h3>用户清单 <span>{{ users.length }}</span></h3><p>查找账号，查看生效权限，集中维护用户信息。</p></div>
      <button class="directory-primary" type="button" :disabled="loading" @click="$emit('create')">＋ 新增用户</button>
    </header>

    <div class="directory-metrics" aria-label="账号概况">
      <span><strong>{{ roleCount }}</strong> 种账号角色</span>
      <span><strong>{{ customCount }}</strong> 个个性化配置</span>
      <span>点击权限概览可查看完整权限与数据范围</span>
    </div>

    <div class="directory-filters">
      <label class="directory-search"><span>搜索用户</span><input v-model.trim="filters.keyword" type="search" placeholder="ID、用户名、姓名、手机号、站点或片区" /></label>
      <label><span>角色</span><select v-model="filters.role"><option value="">全部角色</option><option v-for="role in roles" :key="role.value" :value="role.value">{{ role.label }}</option></select></label>
      <label><span>所属片区</span><select v-model="filters.region"><option value="">全部片区</option><option v-for="region in regions" :key="region" :value="region">{{ region }}</option></select></label>
      <label><span>权限配置</span><select v-model="filters.configuration"><option value="">全部配置</option><option value="template">角色模板</option><option value="custom">个性化配置</option><option value="builtin">内置管理员</option></select></label>
    </div>
    <div class="directory-results">
      <p role="status">{{ loading ? '正在加载账号…' : `找到 ${filtered.length} 个用户` }}<span v-if="isFiltered"> / 全部 {{ users.length }} 个</span></p>
      <div><button v-if="isFiltered" class="directory-text-button" type="button" @click="clearFilters">清除筛选</button><label class="directory-sort"><span>排序</span><select v-model="filters.sort"><option value="default">默认角色顺序</option><option value="name">按姓名</option><option value="updated">最近更新优先</option></select></label></div>
    </div>

    <div v-if="loading" class="directory-loading" role="status"><span></span>正在读取用户清单，请稍候…</div>
    <div v-else-if="!filtered.length" class="directory-empty"><strong>没有匹配的用户</strong><p>试试更短的关键词，或调整角色、片区与权限配置条件。</p><button type="button" class="directory-secondary" @click="clearFilters">清除筛选</button></div>
    <template v-else>
      <div class="directory-table-wrap" tabindex="0" aria-label="用户清单，可横向滚动">
        <table class="directory-table">
          <thead><tr><th scope="col">账号与联系方式</th><th scope="col">角色</th><th scope="col">所属范围</th><th scope="col">权限概览</th><th scope="col">维护时间</th><th scope="col">操作</th></tr></thead>
          <tbody><tr v-for="entry in entries" :key="entry.user.id" :class="{ editing: editingId === entry.user.id }">
            <td><div class="directory-identity"><span class="directory-avatar" :class="{ admin: entry.user.role === 'root' }" aria-hidden="true">{{ userInitial(entry.user) }}</span><div><strong>{{ entry.user.real_name || entry.user.username }}</strong><span>{{ entry.user.username }} <i>· ID {{ entry.user.id }}</i></span><small>{{ entry.user.phone || '未填写手机号' }}</small></div></div></td>
            <td><span class="directory-role" :class="{ manager: entry.user.role === 'supervisor_manager', station: entry.user.role === 'station_manager' }">{{ label(entry.user.role) }}</span><small v-if="editingId === entry.user.id" class="directory-editing">正在编辑</small></td>
            <td class="directory-scope"><strong>{{ entry.user.role === 'root' ? '全局数据' : entry.user.station_name || (entry.regions.length ? entry.regions.join('、') : '未绑定站点') }}</strong><span>{{ entry.user.role === 'root' ? '内置管理员，不受业务范围限制' : entry.user.station_name ? entry.regions.join('、') || '片区未填写' : '具体数据范围见权限详情' }}</span></td>
            <td><button class="directory-permission" type="button" :aria-label="`查看 ${entry.user.username} 的权限详情`" title="查看完整权限与生效数据范围" @click="$emit('permissions', entry.user)"><span class="directory-config" :class="entry.summary.kind">{{ entry.summary.label }}</span><strong>{{ entry.summary.enabled }}<small> / {{ entry.summary.total }} 项已开启</small><em aria-hidden="true">›</em></strong></button></td>
            <td class="directory-times"><span>更新 {{ entry.user.updated_at || '未记录' }}</span><small>创建 {{ entry.user.created_at || '未记录' }}</small></td>
            <td><UserAccountActions :user="entry.user" :resetting="resetting" :deleting="deletingId === entry.user.id" @edit="$emit('edit', $event)" @reset="$emit('reset', $event)" @delete="$emit('delete', $event)" /></td>
          </tr></tbody>
        </table>
      </div>

      <div class="directory-mobile-list">
        <article v-for="entry in entries" :key="entry.user.id" class="directory-mobile-card" :class="{ editing: editingId === entry.user.id }">
          <div class="directory-mobile-head"><div class="directory-identity"><span class="directory-avatar" aria-hidden="true">{{ userInitial(entry.user) }}</span><div><strong>{{ entry.user.real_name || entry.user.username }}</strong><span>{{ entry.user.username }} · ID {{ entry.user.id }}</span></div></div><span class="directory-role">{{ label(entry.user.role) }}</span></div>
          <dl><div><dt>手机号</dt><dd>{{ entry.user.phone || '未填写' }}</dd></div><div><dt>所属范围</dt><dd>{{ entry.user.role === 'root' ? '全局数据，不受业务范围限制' : [entry.user.station_name, ...entry.regions].filter(Boolean).join(' · ') || '未绑定站点，详见权限范围' }}</dd></div><div><dt>更新于</dt><dd>{{ entry.user.updated_at || '未记录' }}</dd></div><div><dt>创建于</dt><dd>{{ entry.user.created_at || '未记录' }}</dd></div></dl>
          <button class="directory-mobile-permission" type="button" :aria-label="`查看 ${entry.user.username} 的权限详情`" @click="$emit('permissions', entry.user)"><span class="directory-config" :class="entry.summary.kind">{{ entry.summary.label }}</span><span><strong>{{ entry.summary.enabled }}/{{ entry.summary.total }}</strong> 项已开启 <b>查看详情 ›</b></span></button>
          <div class="directory-mobile-actions"><small v-if="editingId === entry.user.id" class="directory-editing">正在编辑</small><UserAccountActions :user="entry.user" :resetting="resetting" :deleting="deletingId === entry.user.id" @edit="$emit('edit', $event)" @reset="$emit('reset', $event)" @delete="$emit('delete', $event)" /></div>
        </article>
      </div>

      <footer class="directory-pagination">
        <p>第 {{ start }}–{{ end }} 条，共 {{ filtered.length }} 条</p>
        <nav aria-label="用户清单分页"><label>每页 <select v-model.number="pageSize"><option :value="10">10</option><option :value="20">20</option><option :value="50">50</option></select></label><button type="button" :disabled="page === 1" @click="page--">上一页</button><button v-for="number in pageNumbers" :key="number" type="button" :class="{ active: page === number }" :aria-label="`第 ${number} 页`" :aria-current="page === number ? 'page' : undefined" @click="page = number">{{ number }}</button><button type="button" :disabled="page === pageCount" @click="page++">下一页</button></nav>
      </footer>
    </template>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import UserAccountActions from './UserAccountActions.vue'
import { directoryPageNumbers, filterDirectoryUsers, permissionConfiguration, permissionSummary, roleLabelFor, userInitial, userRegions } from '../utils/userDirectory.js'
const props = defineProps({ users: { type: Array, default: () => [] }, roles: { type: Array, default: () => [] }, catalog: { type: Array, default: () => [] }, loading: Boolean, editingId: Number, deletingId: Number, resetting: Boolean })
defineEmits(['create', 'edit', 'reset', 'delete', 'permissions'])
const filters = reactive({ keyword: '', role: '', region: '', configuration: '', sort: 'default' })
const page = ref(1)
const pageSize = ref(10)
const label = role => roleLabelFor(props.roles, role)
const regions = computed(() => [...new Set(props.users.flatMap(userRegions))].sort((a, b) => a.localeCompare(b, 'zh-CN')))
const roleCount = computed(() => new Set(props.users.map(user => user.role)).size)
const customCount = computed(() => props.users.filter(user => permissionConfiguration(user) === 'custom').length)
const filtered = computed(() => filterDirectoryUsers(props.users, filters, props.roles))
const isFiltered = computed(() => Boolean(filters.keyword || filters.role || filters.region || filters.configuration))
const pageCount = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value)))
const pageNumbers = computed(() => directoryPageNumbers(page.value, pageCount.value))
const start = computed(() => (page.value - 1) * pageSize.value + 1)
const end = computed(() => Math.min(page.value * pageSize.value, filtered.value.length))
const entries = computed(() => filtered.value.slice(start.value - 1, end.value).map(user => ({ user, summary: permissionSummary(user, props.catalog), regions: userRegions(user) })))
const clearFilters = () => Object.assign(filters, { keyword: '', role: '', region: '', configuration: '', sort: 'default' })
watch(() => [filters.keyword, filters.role, filters.region, filters.configuration, filters.sort, pageSize.value], () => { page.value = 1 }, { flush: 'sync' })
watch(pageCount, value => { page.value = Math.min(page.value, value) }, { flush: 'sync' })
</script>

<style scoped>
.user-directory, .user-directory * { box-sizing: border-box; }
.user-directory { color: #172033; min-width: 0; }
.directory-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.directory-eyebrow { margin: 0 0 5px; color: #2563eb; font-size: 12px; font-weight: 800; }
h3 { margin: 0; font-size: 22px; letter-spacing: -.02em; }
h3 > span { display: inline-block; margin-left: 7px; padding: 3px 8px; border-radius: 7px; background: #edf3fa; color: #53657e; font-size: 13px; vertical-align: middle; font-variant-numeric: tabular-nums; }
.directory-header > div > p:last-child { margin: 7px 0 0; color: #64748b; font-size: 13px; line-height: 1.6; }
button, input, select { font: inherit; }
button { cursor: pointer; }
.directory-primary, .directory-secondary { min-height: 38px; padding: 0 15px; border: 1px solid #d7e0ea; border-radius: 10px; background: #fff; color: #475569; font-size: 13px; font-weight: 700; white-space: nowrap; }
.directory-primary { color: #fff; background: #2563eb; border-color: #2563eb; }
button:disabled { cursor: not-allowed; opacity: .45; }
button:focus-visible, input:focus-visible, select:focus-visible, .directory-table-wrap:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.directory-metrics { display: flex; flex-wrap: wrap; gap: 10px 22px; padding: 16px 0; margin: 4px 0 0; color: #64748b; font-size: 12px; }
.directory-metrics strong { color: #334155; font-size: 14px; margin-right: 3px; }
.directory-metrics > span:last-child { margin-left: auto; }
.directory-filters { display: grid; grid-template-columns: minmax(240px, 2fr) repeat(3, minmax(130px, 1fr)); gap: 12px; padding: 16px; border: 1px solid #e2e8f0; border-radius: 13px; background: #f8fafc; }
.directory-filters label { display: grid; gap: 7px; min-width: 0; font-size: 12px; font-weight: 700; color: #475569; }
.directory-filters input, .directory-filters select { width: 100%; min-width: 0; height: 38px; padding: 0 10px; border: 1px solid #d7e0ea; border-radius: 8px; background: #fff; color: #172033; font-size: 13px; }
.directory-results { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin: 14px 0; font-size: 12px; color: #475569; }
.directory-results p { margin: 0; font-weight: 700; }
.directory-results p span { font-weight: 400; color: #64748b; }
.directory-results > div { display: flex; align-items: center; gap: 12px; }
.directory-sort { display: flex; align-items: center; gap: 7px; }
.directory-sort select { min-height: 32px; border: 1px solid #e2e8f0; border-radius: 7px; background: #fff; color: #475569; padding: 0 6px; font-size: 12px; }
.directory-text-button { padding: 4px; border: 0; background: transparent; color: #2563eb; font-size: 12px; }
.directory-table-wrap { overflow: auto; border: 1px solid #e2e8f0; border-radius: 12px; scrollbar-gutter: stable; }
.directory-table { width: 100%; min-width: 1050px; border-collapse: collapse; text-align: left; font-size: 13px; }
th { padding: 12px 14px; background: #f7f9fc; color: #64748b; font-size: 12px; font-weight: 700; white-space: nowrap; }
td { padding: 12px 14px; border-top: 1px solid #edf1f6; vertical-align: middle; }
tbody tr:hover td { background: #fafcff; }
tr.editing td { background: #f0f7ff; }
.directory-identity { display: flex; align-items: center; gap: 11px; min-width: 180px; }
.directory-avatar { display: grid; place-items: center; flex: 0 0 36px; width: 36px; height: 36px; border: 1px solid #dce7f7; border-radius: 11px; background: #edf4ff; color: #285d9c; font-size: 15px; font-weight: 800; }
.directory-avatar.admin { border-color: #d7e6de; color: #15734b; background: #edf8f2; }
.directory-identity strong, .directory-identity span:not(.directory-avatar), .directory-identity small { display: block; overflow-wrap: anywhere; }
.directory-identity strong { font-size: 14px; line-height: 1.5; }
.directory-identity div > span { color: #64748b; font-size: 12px; margin-top: 3px; }
.directory-identity i { font-style: normal; color: #94a3b8; white-space: nowrap; }
.directory-identity small { color: #64748b; margin-top: 4px; font-size: 12px; }
.directory-role { display: inline-block; padding: 5px 8px; border-radius: 7px; background: #f0f4f8; color: #52637a; white-space: nowrap; font-size: 12px; font-weight: 700; }
.directory-role.manager { background: #eaf2ff; color: #1d4ed8; }
.directory-role.station { background: #f0f8f5; color: #217052; }
.directory-editing { display: block; margin-top: 7px; color: #2563eb; font-size: 11px; }
.directory-scope { min-width: 140px; max-width: 210px; }
.directory-scope strong { display: block; font-size: 12px; font-weight: 600; line-height: 1.7; overflow-wrap: anywhere; }
.directory-scope > span { display: block; font-size: 11px; margin-top: 4px; color: #8491a5; line-height: 1.6; }
.directory-permission { min-width: 165px; width: 100%; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 10px; text-align: left; background: #fff; }
.directory-permission:hover { border-color: #93b9f7; background: #f7faff; }
.directory-config { display: inline-block; font-size: 11px; color: #64748b; font-weight: 600; }
.directory-config.custom { color: #9a5c13; }
.directory-config.builtin { color: #14744f; }
.directory-permission > strong { display: flex; align-items: baseline; gap: 3px; margin-top: 4px; color: #1e293b; font-size: 17px; font-variant-numeric: tabular-nums; }
.directory-permission strong small { color: #64748b; font-size: 11px; font-weight: 400; white-space: nowrap; }
.directory-permission em { margin-left: auto; font-size: 19px; font-style: normal; color: #2563eb; }
.directory-times { white-space: nowrap; font-size: 11px; color: #52637a; line-height: 1.7; }
.directory-times small { display: block; margin-top: 4px; color: #94a3b8; font-size: 11px; }
.directory-loading, .directory-empty { display: grid; place-items: center; gap: 14px; min-height: 240px; padding: 30px 15px; text-align: center; color: #64748b; border: 1px dashed #dbe4ee; border-radius: 12px; font-size: 13px; }
.directory-loading span { width: 26px; height: 26px; border: 3px solid #dbeafe; border-top-color: #2563eb; border-radius: 50%; animation: loading-turn 1s linear infinite; }
.directory-empty { gap: 10px; }
.directory-empty strong { color: #334155; font-size: 16px; }
.directory-empty p { margin: 0; line-height: 1.7; }
.directory-pagination { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-top: 16px; font-size: 12px; color: #64748b; }
.directory-pagination p { margin: 0; }
.directory-pagination nav, .directory-pagination label { display: flex; gap: 6px; align-items: center; }
.directory-pagination label { margin-right: 8px; }
.directory-pagination select { height: 32px; padding: 0 6px; border: 1px solid #d7e0ea; border-radius: 7px; background: #fff; }
.directory-pagination button { min-width: 32px; height: 32px; padding: 0 8px; border: 1px solid #e2e8f0; border-radius: 7px; color: #475569; background: #fff; font-size: 12px; }
.directory-pagination button.active { color: #fff; border-color: #2563eb; background: #2563eb; }
.directory-mobile-list { display: none; }
@keyframes loading-turn { to { transform: rotate(360deg); } }
@media (max-width: 1100px) { .directory-filters { grid-template-columns: repeat(3, minmax(0, 1fr)); } .directory-search { grid-column: 1/-1; } .directory-metrics > span:last-child { margin-left: 0; } }
@media (max-width: 760px) {
  .directory-header { align-items: flex-start; } h3 { font-size: 20px; }
  .directory-header > div > p:last-child { max-width: 220px; }
  .directory-filters { padding: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .directory-filters label:last-child { grid-column: 1/-1; }
  .directory-table-wrap { display: none; }
  .directory-mobile-list { display: grid; gap: 12px; }
  .directory-mobile-card { min-width: 0; padding: 15px; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; }
  .directory-mobile-card.editing { border-color: #93c5fd; background: #f8fbff; }
  .directory-mobile-head { display: flex; align-items: flex-start; flex-wrap: wrap; gap: 9px; justify-content: space-between; }
  .directory-identity { min-width: 0; }
  .directory-mobile-head .directory-role { font-size: 11px; }
  dl { display: grid; gap: 8px; margin: 15px 0; font-size: 12px; }
  dl > div { display: grid; grid-template-columns: 56px minmax(0, 1fr); gap: 10px; }
  dt { color: #94a3b8; } dd { margin: 0; color: #475569; line-height: 1.6; overflow-wrap: anywhere; }
  .directory-mobile-permission { display: flex; width: 100%; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; padding: 12px; border: 1px solid #dbeafe; border-radius: 9px; background: #f8fbff; font-size: 12px; color: #64748b; }
  .directory-mobile-permission strong { color: #1e293b; font-size: 14px; }
  .directory-mobile-permission b { margin-left: 8px; font-size: 11px; color: #2563eb; }
  .directory-mobile-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  .directory-pagination { flex-direction: column; align-items: flex-start; }
  .directory-pagination nav { width: 100%; flex-wrap: wrap; }
  .directory-pagination label { width: 100%; margin-bottom: 5px; }
  .directory-pagination button { flex: 1; }
}
@media (prefers-reduced-motion: reduce) { .directory-loading span { animation: none; } }
</style>
