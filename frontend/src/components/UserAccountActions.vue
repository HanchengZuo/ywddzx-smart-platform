<template>
  <div class="account-actions" :aria-label="`${user.username} 的账号操作`">
    <button class="account-edit" type="button" :disabled="disabled || deleting" @click="$emit('edit', user)">编辑</button>
    <button class="account-reset" type="button" :disabled="disabled || user.role === 'root' || resetting || deleting"
      :title="user.role === 'root' ? 'root 使用 Passkey 登录，无需重置密码' : '生成随机初始密码，原登录会话将失效'"
      @click="$emit('reset', user)">{{ user.role === 'root' ? 'Passkey 账号' : '重置密码' }}</button>
    <button class="account-delete" type="button" :disabled="disabled || user.role === 'root' || deleting"
      :title="user.role === 'root' ? '内置管理员不可删除' : '删除此账号，需要再次确认'"
      @click="$emit('delete', user)">{{ deleting ? '删除中' : '删除' }}</button>
  </div>
</template>

<script setup>
defineProps({ user: { type: Object, required: true }, disabled: Boolean, resetting: Boolean, deleting: Boolean })
defineEmits(['edit', 'reset', 'delete'])
</script>

<style scoped>
.account-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
button { min-height: 32px; padding: 0 10px; border: 1px solid transparent; border-radius: 8px; font: inherit; font-size: 12px; font-weight: 700; white-space: nowrap; cursor: pointer; }
.account-edit { color: #1d4ed8; background: #eff6ff; border-color: #dbeafe; }
.account-reset { color: #9a3412; background: #fff7ed; border-color: #ffedd5; }
.account-delete { color: #b91c1c; background: #fff; }
button:hover:not(:disabled) { filter: brightness(.97); }
button:disabled { opacity: .45; cursor: not-allowed; }
button:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
</style>
