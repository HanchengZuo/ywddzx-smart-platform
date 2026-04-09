<template>
  <div class="page-shell">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">考核系统</div>
        <h2>考核系统</h2>
      </div>
    </div>

    <div class="card-surface content-card">
      <div v-if="hasPermission" class="placeholder-block">
        <div class="placeholder-title">考核系统内容建设中</div>
        <div class="placeholder-desc">当前页面预留为考核模块入口，后续可继续接入考核台账、考核明细、统计分析等功能。</div>
      </div>

      <div v-else class="permission-card">
        <div class="permission-icon">!</div>
        <div class="permission-title">无权限访问</div>
        <div class="permission-desc">当前账号无权访问考核系统，请使用督导组账号登录后操作。</div>
      </div>
    </div>
  </div>
</template>

<script setup>
const currentRole = localStorage.getItem('user_role') || ''
const hasPermission = currentRole === 'supervisor'
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-surface {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dbe4ee;
  border-radius: 22px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
}

.page-header {
  padding: 24px 28px;
}

.page-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 14px;
}

.page-header h2 {
  margin: 0;
  font-size: 34px;
  color: #0f172a;
}

.content-card {
  padding: 28px;
}

.placeholder-block,
.permission-card {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 32px 20px;
  border-radius: 18px;
  background: #f8fafc;
}

.permission-card {
  border: 1px dashed #cbd5e1;
}

.permission-icon {
  width: 56px;
  height: 56px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 28px;
  font-weight: 800;
  margin-bottom: 14px;
}

.placeholder-title,
.permission-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 8px;
}

.placeholder-desc,
.permission-desc {
  font-size: 14px;
  line-height: 1.8;
  color: #64748b;
  max-width: 520px;
}
</style>