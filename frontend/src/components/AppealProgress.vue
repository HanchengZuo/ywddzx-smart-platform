<template>
  <div class="appeal-progress" aria-label="申诉处理进度">
    <section v-for="(step, index) in steps" :key="step.title" :class="['step', step.state]">
      <div class="step-top"><span class="node">{{ index + 1 }}</span><span class="stage-state">{{ step.label }}</span></div>
      <h4>{{ step.title }}</h4><strong class="owner">{{ step.owner }}</strong>
      <p class="handler">{{ step.handler }}</p><time>{{ step.time || '尚未处理' }}</time>
      <p class="reason">{{ step.reason }}</p>
    </section>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { appealProgressSteps } from '@/utils/appealPresentation'
const props = defineProps({ item: { type: Object, required: true }, reviewers: { type: Array, default: () => [] } })
const steps = computed(() => appealProgressSteps(props.item, props.reviewers))
</script>
<style scoped>
.appeal-progress { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 18px; margin: 24px 0; }
.step { --accent: #9aaabe; position: relative; min-width: 0; padding: 18px; border: 1px solid #e1e8f1; border-radius: 16px; background: linear-gradient(145deg,#fff,#f5f8fc); }
.step:not(:last-child)::after { content: ''; position: absolute; width: 19px; height: 3px; top: 35px; left: 100%; background: var(--accent); }
.step.done { --accent: #229577; border-color: #c6e8dc; background: linear-gradient(145deg,#fff,#effaf5); }
.step.active { --accent: #2887c8; border-color: #95ccee; background: radial-gradient(ellipse at top right,#dff2ff,transparent 75%),#fff; box-shadow: 0 0 18px #2b98dc25; }
.step.rejected { --accent: #d24747; border-color: #efbebe; background: linear-gradient(145deg,#fff,#fff1f0); }
.step-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.node { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; color: white; background: var(--accent); font-weight: 700; }
.active .node { animation: beacon 2.5s ease-in-out infinite; }
.stage-state { color: var(--accent); font-size: 12px; font-weight: 700; }
h4 { font-size: 16px; margin: 14px 0 8px; color: #233b53; }.owner { color: #3f607c; font-size: 14px; overflow-wrap: anywhere; }
.handler,time { color: #718096; font-size: 12px; line-height: 1.6; }.handler { min-height: 20px; margin: 10px 0 2px; }.reason { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; font-size: 14px; margin: 12px 0 0; }
@keyframes beacon { 50% { box-shadow: 0 0 0 6px #2887c819,0 0 18px #2887c860; } }
@media(prefers-reduced-motion:reduce) { .active .node { animation: none; } }
@media(max-width:700px) { .appeal-progress { grid-template-columns: 1fr; gap: 16px; }.step:not(:last-child)::after { left: 34px; top: 100%; width: 3px; height: 17px; } }
</style>
