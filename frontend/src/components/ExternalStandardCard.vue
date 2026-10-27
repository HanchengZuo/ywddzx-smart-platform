<template>
  <article class="external-standard-card">
    <div class="external-standard-top">
      <span>外部规范ID {{ standard.external_standard_id }}</span>
      <em :class="{ linked: standard.linked_internal_standard_id }">
        {{ standard.linked_internal_standard_id
          ? `${compact ? '内部' : '已关联内部规范'} ${standard.linked_internal_standard_id}`
          : '未关联内部规范' }}
      </em>
    </div>
    <p>{{ standard.standard_detail_text || '暂无外部规范详情。' }}</p>
  </article>
</template>
<script setup>
defineProps({ standard: { type: Object, required: true }, compact: Boolean })
</script>
<style scoped>
.external-standard-card { flex-shrink:0; padding:14px; border:1px solid #e5edf5; border-radius:16px; background:#fff; }
.external-standard-top { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:8px; }
.external-standard-top span { color:#1d4ed8; font-size:13px; font-weight:900; }
.external-standard-top em { flex:0 0 auto; padding:4px 9px; border-radius:999px; background:#f1f5f9; color:#64748b; font-size:12px; font-style:normal; font-weight:900; }
.external-standard-top em.linked { background:#ecfdf5; color:#15803d; }
p { margin:0; color:#334155; font-size:13px; line-height:1.8; white-space:pre-line; overflow-wrap:anywhere; }
@media (max-width: 768px) {
  .external-standard-top { flex-direction:column; align-items:flex-start; }
}
</style>
