<template>
  <article class="external-standard-card">
    <div class="external-standard-top">
      <span class="external-standard-id">外部规范ID {{ standard.external_standard_id }}</span>
      <div class="external-standard-badges">
        <em :class="{ linked: standard.is_active }">{{ standard.is_active ? '启用' : standard.standard_enabled === false ? '规范已停用' : '所属版本未启用' }}</em>
        <em class="external-standard-link" :class="{ linked: standard.linked_internal_standard_id }">
          {{ standard.linked_internal_standard_id
            ? `${compact ? '内部' : '已关联内部规范'} ${standard.linked_internal_standard_id}`
            : '未关联内部规范' }}
        </em>
      </div>
    </div>
    <p>{{ standard.standard_detail_text || '暂无外部规范详情。' }}</p>
  </article>
</template>
<script setup>
defineProps({ standard: { type: Object, required: true }, compact: Boolean })
</script>
<style scoped>
.external-standard-card { flex-shrink:0; padding:14px; border:1px solid #e5edf5; border-radius:16px; background:#fff; }
.external-standard-top { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:6px 12px; margin-bottom:8px; }
.external-standard-badges { display:flex; flex-wrap:wrap; align-items:center; justify-content:flex-end; gap:6px 8px; max-width:100%; margin-inline-start:auto; }
.external-standard-id { color:#1d4ed8; font-size:13px; font-weight:900; overflow-wrap:anywhere; }
.external-standard-top em { max-width:100%; box-sizing:border-box; padding:4px 9px; border-radius:999px; background:#f1f5f9; color:#64748b; font-size:12px; font-style:normal; font-weight:900; overflow-wrap:anywhere; }
.external-standard-top em.linked { background:#ecfdf5; color:#15803d; }
p { margin:0; color:#334155; font-size:13px; line-height:1.8; white-space:pre-line; overflow-wrap:anywhere; }
</style>
