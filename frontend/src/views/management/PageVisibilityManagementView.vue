<template>
  <div class="page-shell page-visibility-page">
    <section class="page-visibility-hero">
      <div>
        <div class="page-kicker">管理系统</div>
        <h2>页面显示管理</h2>
        <p>root 可以统一控制各业务页面是否在菜单栏展示；当某个系统下所有子页面都被隐藏时，该系统分组也会自动隐藏。</p>
      </div>
      <div class="hero-actions">
        <button class="btn btn-secondary" type="button" :disabled="loading || saving" @click="loadSettings">
          {{ loading ? '刷新中...' : '刷新配置' }}
        </button>
        <button class="btn btn-primary" type="button" :disabled="loading || saving" @click="saveSettings">
          {{ saving ? '保存中...' : '保存显示设置' }}
        </button>
      </div>
    </section>

    <section v-if="!isRoot" class="card-surface permission-card">
      <div class="permission-icon">!</div>
      <div class="permission-title">无权访问页面显示管理</div>
      <div class="permission-desc">该功能仅 root 系统管理员账号可以操作。</div>
    </section>

    <template v-else>
      <section class="visibility-summary-grid">
        <div class="summary-card primary">
          <span>可管理页面</span>
          <strong>{{ totalPages }}</strong>
          <small>按菜单真实页面统计</small>
        </div>
        <div class="summary-card">
          <span>当前显示</span>
          <strong>{{ visibleCount }}</strong>
          <small>会出现在左侧菜单中</small>
        </div>
        <div class="summary-card hidden">
          <span>当前隐藏</span>
          <strong>{{ hiddenCount }}</strong>
          <small>菜单和直接访问都会被拦截</small>
        </div>
      </section>

      <div v-if="message" class="visibility-toast" :class="{ error: messageType === 'error' }">{{ message }}</div>

      <section class="card-surface visibility-guide">
        <div>
          <strong>使用提示</strong>
          <span>页面隐藏是全局开关，和用户权限是两层逻辑：用户先要有权限，其次页面也必须处于显示状态。</span>
        </div>
        <button class="mini-action" type="button" :disabled="saving" @click="showAllPages">一键全部显示</button>
      </section>

      <section class="visibility-groups">
        <article v-for="group in groupedPages" :key="group.key" class="visibility-group card-surface">
          <div class="group-head">
            <div>
              <h3>{{ group.title }}</h3>
              <p>{{ group.description }}</p>
            </div>
            <div class="group-status" :class="{ muted: group.visibleCount === 0 }">
              {{ group.visibleCount }}/{{ group.pages.length }} 显示
            </div>
          </div>

          <div class="page-toggle-list">
            <div v-for="page in group.pages" :key="page.key" class="page-toggle-row" :class="{ hidden: !isVisible(page.key) }">
              <div class="page-toggle-main">
                <strong>{{ page.title }}</strong>
                <span>{{ page.description }}</span>
                <em>{{ page.path }}</em>
              </div>
              <label class="visibility-switch">
                <input type="checkbox" :checked="isVisible(page.key)" @change="setVisible(page.key, $event.target.checked)" />
                <span class="switch-track">
                  <span class="switch-thumb"></span>
                </span>
                <b>{{ isVisible(page.key) ? '显示' : '隐藏' }}</b>
              </label>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import { PAGE_VISIBILITY_GROUPS, PAGE_VISIBILITY_PAGES } from '@/config/pageVisibilityCatalog'
import { refreshPageVisibilityAndNotify } from '@/utils/pageVisibility'

const loading = ref(false)
const saving = ref(false)
const message = ref('')
const messageType = ref('success')
const settings = reactive({})

const userId = () => localStorage.getItem('user_id') || ''
const isRoot = computed(() => localStorage.getItem('user_role') === 'root')
const totalPages = computed(() => PAGE_VISIBILITY_PAGES.length)
const visibleCount = computed(() => PAGE_VISIBILITY_PAGES.filter((page) => isVisible(page.key)).length)
const hiddenCount = computed(() => Math.max(0, totalPages.value - visibleCount.value))
const groupedPages = computed(() => PAGE_VISIBILITY_GROUPS.map((group) => {
  const pages = group.pages.map((page) => ({
    ...page,
    visible: isVisible(page.key)
  }))
  return {
    ...group,
    pages,
    visibleCount: pages.filter((page) => page.visible).length
  }
}))

const showMessage = (text, type = 'success') => {
  message.value = text
  messageType.value = type
  window.setTimeout(() => {
    if (message.value === text) message.value = ''
  }, 2600)
}

const applySettings = (rawSettings = {}) => {
  PAGE_VISIBILITY_PAGES.forEach((page) => {
    settings[page.key] = rawSettings[page.key] !== false
  })
}

const isVisible = (key) => settings[key] !== false

const setVisible = (key, value) => {
  settings[key] = Boolean(value)
}

const showAllPages = () => {
  PAGE_VISIBILITY_PAGES.forEach((page) => {
    settings[page.key] = true
  })
  showMessage('已临时切换为全部显示，点击保存后生效。')
}

const loadSettings = async () => {
  if (!isRoot.value) return
  loading.value = true
  message.value = ''
  try {
    const response = await axios.get('/api/management/page-visibility', {
      params: { user_id: userId() }
    })
    if (!response.data?.success) throw new Error(response.data?.error || '页面显示配置读取失败。')
    applySettings(response.data.settings || {})
  } catch (error) {
    showMessage(error?.response?.data?.error || error.message || '页面显示配置读取失败。', 'error')
  } finally {
    loading.value = false
  }
}

const saveSettings = async () => {
  if (!isRoot.value) return
  saving.value = true
  message.value = ''
  try {
    const pages = PAGE_VISIBILITY_PAGES.map((page) => ({
      page_key: page.key,
      is_visible: isVisible(page.key)
    }))
    const response = await axios.put('/api/management/page-visibility', {
      user_id: userId(),
      pages
    })
    if (!response.data?.success) throw new Error(response.data?.error || '页面显示配置保存失败。')
    applySettings(response.data.settings || {})
    await refreshPageVisibilityAndNotify()
    showMessage(response.data.message || '页面显示设置已保存。')
  } catch (error) {
    showMessage(error?.response?.data?.error || error.message || '页面显示配置保存失败。', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<style scoped>
.page-visibility-page {
  display: grid;
  gap: 18px;
}

.card-surface,
.page-visibility-hero,
.summary-card {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 24px;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
}

.page-visibility-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 26px;
  background:
    radial-gradient(circle at 10% 18%, rgba(14, 165, 233, 0.18), transparent 32%),
    linear-gradient(135deg, rgba(239, 246, 255, 0.98), rgba(240, 253, 244, 0.98));
}

.page-kicker {
  color: #0f766e;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.14em;
}

.page-visibility-hero h2 {
  margin: 8px 0;
  color: #0f172a;
  font-size: 30px;
}

.page-visibility-hero p,
.visibility-guide span,
.group-head p,
.page-toggle-main span,
.page-toggle-main em,
.summary-card small {
  color: #64748b;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.visibility-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.summary-card {
  padding: 18px;
  display: grid;
  gap: 6px;
}

.summary-card span {
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.summary-card strong {
  color: #0f172a;
  font-size: 30px;
}

.summary-card.primary {
  background: linear-gradient(135deg, #0f766e, #2563eb);
}

.summary-card.primary span,
.summary-card.primary strong,
.summary-card.primary small {
  color: #fff;
}

.summary-card.hidden strong {
  color: #dc2626;
}

.visibility-toast {
  padding: 13px 16px;
  border-radius: 16px;
  background: #ecfdf5;
  border: 1px solid rgba(16, 185, 129, 0.28);
  color: #047857;
  font-weight: 800;
}

.visibility-toast.error {
  background: #fef2f2;
  border-color: rgba(248, 113, 113, 0.34);
  color: #b91c1c;
}

.visibility-guide {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
}

.visibility-guide div {
  display: grid;
  gap: 4px;
}

.visibility-guide strong {
  color: #0f172a;
}

.mini-action {
  border: 0;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-weight: 900;
  padding: 9px 14px;
  cursor: pointer;
  white-space: nowrap;
}

.mini-action:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.visibility-groups {
  display: grid;
  gap: 16px;
}

.visibility-group {
  overflow: hidden;
}

.group-head {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 22px;
  background:
    linear-gradient(90deg, rgba(15, 118, 110, 0.08), rgba(37, 99, 235, 0.06)),
    #fff;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.group-head h3 {
  margin: 0 0 6px;
  color: #0f172a;
  font-size: 20px;
}

.group-head p {
  margin: 0;
}

.group-status {
  align-self: flex-start;
  padding: 8px 12px;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
  font-size: 13px;
  font-weight: 900;
  white-space: nowrap;
}

.group-status.muted {
  background: #fee2e2;
  color: #b91c1c;
}

.page-toggle-list {
  display: grid;
}

.page-toggle-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
  padding: 17px 22px;
  border-top: 1px solid rgba(226, 232, 240, 0.9);
}

.page-toggle-row:first-child {
  border-top: 0;
}

.page-toggle-row.hidden {
  background: rgba(248, 250, 252, 0.84);
}

.page-toggle-main {
  display: grid;
  gap: 5px;
}

.page-toggle-main strong {
  color: #0f172a;
  font-size: 16px;
}

.page-toggle-main em {
  font-style: normal;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}

.visibility-switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.visibility-switch input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.switch-track {
  position: relative;
  width: 54px;
  height: 30px;
  border-radius: 999px;
  background: #cbd5e1;
  transition: background 0.18s ease, box-shadow 0.18s ease;
}

.switch-thumb {
  position: absolute;
  top: 4px;
  left: 4px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 3px 10px rgba(15, 23, 42, 0.22);
  transition: transform 0.18s ease;
}

.visibility-switch input:checked + .switch-track {
  background: linear-gradient(135deg, #0f766e, #2563eb);
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.18);
}

.visibility-switch input:checked + .switch-track .switch-thumb {
  transform: translateX(24px);
}

.visibility-switch b {
  color: #334155;
  font-size: 13px;
  min-width: 28px;
}

.permission-card {
  padding: 32px;
  text-align: center;
}

.permission-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 12px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #fef2f2;
  color: #dc2626;
  font-weight: 900;
}

.permission-title {
  color: #0f172a;
  font-weight: 900;
  font-size: 18px;
}

.permission-desc {
  margin-top: 8px;
  color: #64748b;
}

@media (max-width: 860px) {
  .page-visibility-hero,
  .visibility-guide,
  .group-head {
    align-items: stretch;
    flex-direction: column;
  }

  .visibility-summary-grid {
    grid-template-columns: 1fr;
  }

  .hero-actions {
    justify-content: stretch;
  }

  .hero-actions .btn {
    flex: 1;
  }

  .page-toggle-row {
    grid-template-columns: 1fr;
  }

  .visibility-switch {
    justify-content: space-between;
    border-radius: 16px;
    background: #f8fafc;
    padding: 10px 12px;
  }
}
</style>
