<template>
  <Teleport to="body">
    <div class="appeal-overlay" @click.self="!saving && $emit('close')">
      <section class="appeal-dialog" role="dialog" aria-modal="true" aria-labelledby="appeal-title">
        <h3 id="appeal-title">发起问题申诉 · #{{ item.id }}</h3>
        <p class="appeal-context">{{ item.station }} · {{ item.inspection_table_name }}</p>
        <p class="appeal-description">{{ item.description }}</p>
        <div class="appeal-notice">每个问题只能申诉一次。提交后问题暂停整改，进入所属片区初审，片区通过后由授权质安部终审。任一级拒绝后恢复整改，不可再次申诉。</div>
        <label for="appeal-reason">申诉理由（必填）</label>
        <textarea id="appeal-reason" v-model="reason" maxlength="4000" rows="5" placeholder="请具体说明申诉依据及问题实际情况" :disabled="saving"></textarea>
        <p v-if="error" class="appeal-error" role="alert">{{ error }}</p>
        <footer><button type="button" :disabled="saving" @click="$emit('close')">取消</button><button class="primary" type="button" :disabled="saving || !reason.trim()" @click="submit">{{ saving ? '正在提交…' : '提交申诉并前往申诉空间' }}</button></footer>
      </section>
    </div>
  </Teleport>
</template>
<script setup>
import { ref } from 'vue'
import axios from 'axios'
const props = defineProps({ item: { type: Object, required: true } })
const emit = defineEmits(['close', 'submitted'])
const reason = ref('')
const saving = ref(false)
const error = ref('')
async function submit() {
  if (saving.value || !reason.value.trim()) return
  saving.value = true
  error.value = ''
  try {
    await axios.post(`/api/issues/${props.item.id}/appeals`, { reason: reason.value.trim() })
    emit('submitted')
  } catch (err) {
    error.value = err.response?.data?.error || '提交失败，请稍后重试。'
  } finally { saving.value = false }
}
</script>
<style scoped>
.appeal-overlay { position: fixed; inset: 0; z-index: 4000; display: grid; place-items: center; background: #13223a88; padding: 18px; }
.appeal-dialog { width: min(600px, 100%); max-height: 90dvh; overflow-y: auto; background: white; padding: 24px; border-radius: 20px; box-shadow: 0 20px 70px #12213d33; box-sizing: border-box; }
h3 { margin: 0 0 12px; color: #17283f; }
.appeal-context { color: #64748b; font-size: 13px; }
.appeal-description { white-space: pre-wrap; overflow-wrap: anywhere; }
.appeal-notice { padding: 14px; margin: 16px 0; background: #edf6fe; border-radius: 12px; line-height: 1.7; color: #27618a; font-size: 13px; }
label { display: block; margin-bottom: 8px; font-weight: 600; }
textarea { width: 100%; box-sizing: border-box; border: 1px solid #cbd9e7; border-radius: 10px; padding: 12px; font: inherit; font-size: 16px; resize: vertical; }
footer { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 10px; margin-top: 20px; }
button { padding: 10px 16px; background: white; border: 1px solid #cbd9e7; border-radius: 10px; cursor: pointer; }
button.primary { background: #1976ac; color: white; border-color: #1976ac; }
button:disabled { opacity: .55; cursor: default; }
.appeal-error { color: #b42318; }
</style>
