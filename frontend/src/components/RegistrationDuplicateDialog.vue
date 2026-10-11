<template>
  <dialog ref="dialog" class="duplicate-dialog" aria-labelledby="duplicate-title" @cancel.prevent="finish(false)">
    <header>
      <span class="duplicate-label">重复登记提醒</span>
      <h3 id="duplicate-title">本站本月已有相同规范的问题</h3>
      <p>{{ warning.station }} · {{ warning.month }} · 已有 {{ warning.duplicates.length }} 条记录</p>
    </header>
    <div class="duplicate-content">
      <p class="duplicate-note">请先核对已有问题。若是不同现象或仍需再次记录，可以继续登记；取消不会清空本次填写的内容。</p>
      <article v-for="(issue, index) in warning.duplicates" :key="index" class="duplicate-issue">
        <strong>规范 ID {{ issue.standard_id }}</strong>
        <span v-if="issue.issue_id">问题 #{{ issue.issue_id }} · {{ issue.registered_at }}</span>
        <p>{{ issue.description ?? '该规范已有登记记录；受数据权限限制，当前账号不能查看其内容。' }}</p>
      </article>
    </div>
    <footer>
      <button autofocus type="button" class="btn btn-secondary" @click="finish(false)">返回检查</button>
      <button type="button" class="btn btn-primary" @click="finish(true)">仍然继续登记</button>
    </footer>
  </dialog>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
defineProps({ warning: { type: Object, required: true } })
const emit = defineEmits(['resolve'])
const dialog = ref(null)
let settled = false
const finish = (confirmed) => {
  if (settled) return
  settled = true
  dialog.value?.close()
  emit('resolve', confirmed)
}
onMounted(() => dialog.value.showModal())
onBeforeUnmount(() => finish(false))
</script>

<style scoped>
.duplicate-dialog { width: min(640px, calc(100vw - 24px)); max-height: calc(100dvh - 32px); padding: 0; border: 1px solid #dbe4ef; border-radius: 20px; color: #1e293b; box-shadow: 0 24px 80px #0f172a40; }
.duplicate-dialog[open] { display: flex; flex-direction: column; }
.duplicate-dialog::backdrop { background: #0f172a80; }
header { padding: 22px 24px 16px; background: #fff8ed; }
.duplicate-label { color: #b45309; font-size: 13px; font-weight: 700; }
h3 { margin: 8px 0; font-size: 20px; }
header p { margin: 0; color: #64748b; font-size: 14px; }
.duplicate-content { overflow: auto; padding: 16px 24px; }
.duplicate-note { margin: 0 0 14px; font-size: 14px; line-height: 1.7; }
.duplicate-issue { border: 1px solid #dbe4ef; border-radius: 12px; padding: 14px; margin-bottom: 12px; }
.duplicate-issue strong, .duplicate-issue span { display: block; }
.duplicate-issue span { margin-top: 6px; color: #64748b; font-size: 12px; }
.duplicate-issue p { margin: 10px 0 0; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
footer { display: flex; justify-content: flex-end; gap: 12px; padding: 16px 24px; border-top: 1px solid #e2e8f0; }
@media (max-width: 600px) { header, .duplicate-content, footer { padding: 16px; } h3 { font-size: 18px; } footer button { flex: 1; } }
</style>
