<template>
  <div class="personal-permission-row">
    <div><strong>{{ permission.name }}<em :class="{ enabled }">{{ enabled ? '当前生效：开启' : '当前生效：关闭' }}</em></strong><p>{{ permission.description }}</p><small>角色通用权限：{{ inherited ? '开启' : '关闭' }}</small></div>
    <label><span class="sr-only">{{ permission.name }}的个人设置</span><select :value="mode" :disabled="disabled" @change="$emit('change', $event.target.value)"><option value="inherit">继承角色</option><option value="allow">单独开启</option><option value="deny">单独关闭</option></select></label>
  </div>
</template>
<script setup>
defineProps({ permission: { type: Object, required: true }, mode: { type: String, default: 'inherit' }, enabled: Boolean, inherited: Boolean, disabled: Boolean })
defineEmits(['change'])
</script>
<style scoped>
.personal-permission-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; }
.personal-permission-row > div { min-width: 0; }
strong { font-size: 13px; line-height: 1.8; color: #1e293b; }
em { display: inline-block; margin-left: 8px; font-size: 10px; font-style: normal; font-weight: 500; color: #94a3b8; } em.enabled { color: #168059; }
p { font-size: 12px; line-height: 1.7; color: #64748b; margin: 5px 0; } small { color: #94a3b8; font-size: 11px; }
select { min-height: 36px; border: 1px solid #cbd5e1; border-radius: 8px; color: #334155; background: #f8fafc; padding: 0 8px; font: inherit; font-size: 12px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
select:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
@media(max-width:600px) { .personal-permission-row { flex-direction: column; align-items: stretch; } select { width: 100%; } }
</style>
