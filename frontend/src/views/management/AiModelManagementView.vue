<template>
  <div class="page-shell model-page">
    <header class="card-surface model-header">
      <div><div class="page-kicker">管理系统</div><h2>大模型管理</h2><p>把合适的模型用在合适的业务里。统一设置，或为每个调用场景单独选择。</p></div>
      <button class="btn btn-secondary" :disabled="loading || saving" @click="reload">刷新配置</button>
    </header>

    <p v-if="error" role="alert" class="notice error">{{ error }}</p>
    <p v-if="message" role="status" class="notice success">{{ message }}</p>
    <div v-if="loading && !loaded" class="card-surface loading">正在读取模型配置…</div>
    <template v-if="loaded">
      <section class="provider-grid" aria-label="服务端密钥状态">
        <article v-for="(provider, index) in providers" :key="provider.id" class="card-surface provider-card">
          <span class="provider-index">0{{ index + 1 }}</span>
          <div><h3>{{ provider.name }}</h3><code>{{ provider.key_env }}</code></div>
          <span class="key-status" :class="{ ready: provider.configured }">{{ provider.configured ? 'Key 已配置' : 'Key 未配置' }}</span>
        </article>
      </section>
      <section class="card-surface default-panel">
        <div class="default-copy"><span class="section-kicker">全局默认</span><h3>一次选择，覆盖所有场景</h3><p>场景可单独指定模型；选择“应用到全部场景”将清除单独配置。确认保存后生效。</p></div>
        <div class="default-controls">
          <label for="default-model">默认厂家与模型</label>
          <select id="default-model" v-model="draft.default_model" :disabled="saving">
            <optgroup v-for="provider in providers" :key="provider.id" :label="provider.name">
              <option v-for="model in providerModels(provider.id)" :key="model.id" :value="model.id" :disabled="!provider.configured">{{ model.name }}{{ provider.configured ? '' : '（未配置Key）' }}</option>
            </optgroup>
          </select>
          <button class="btn btn-secondary" :disabled="saving" @click="unify">应用到全部场景</button>
        </div>
      </section>

      <section class="scene-section">
        <div class="scene-toolbar"><div><span class="section-kicker">调用场景清单</span><h3>{{ scenarios.length }} 个场景 · {{ Object.keys(draft.overrides).length }} 项单独配置</h3></div><input v-model.trim="keyword" type="search" aria-label="搜索调用场景" placeholder="搜索报告、分类、选题…" /></div>
        <div v-if="!groups.length" class="card-surface loading">没有匹配的调用场景。</div>
        <section v-for="group in groups" :key="group.name" class="card-surface scene-group">
          <header><h3>{{ group.name }}</h3><span>{{ group.items.length }} 个调用场景</span></header>
          <div v-for="scene in group.items" :key="scene.id" class="scene-row">
            <div class="scene-description"><strong>{{ scene.name }}</strong><p>{{ scene.description }}</p></div>
            <div class="scene-selector"><label :for="'scene-' + scene.id">{{ draft.overrides[scene.id] ? '单独指定' : '跟随全局默认' }}</label>
              <select :id="'scene-' + scene.id" :value="draft.overrides[scene.id] || ''" :disabled="saving" @change="selectScene(scene.id, $event.target.value)">
                <option value="">跟随默认 · {{ modelName(draft.default_model) }}</option>
                <optgroup v-for="provider in providers" :key="provider.id" :label="provider.name">
                  <option v-for="model in providerModels(provider.id)" :key="model.id" :value="model.id" :disabled="!provider.configured">{{ model.name }}{{ provider.configured ? '' : '（未配置Key）' }}</option>
                </optgroup>
              </select>
            </div>
          </div>
        </section>
      </section>
      <section class="card-surface behavior-note"><h3>生效与费用说明</h3><p>保存后用于后续调用，不重跑已有报告。报告分析缓存按模型区分；按问题 ID 持久保存的分类及人工调整仍优先复用，不会因为切换模型重复付费。处理中的单次 AI 调用继续使用启动时的模型。GLM 系列保留必要思考，其他厂家按场景适配参数。</p><p>Key 状态仅表示后端读到了环境变量，不代表账户已开通模型、余额充足或网络连通。本页不发起付费测试，不显示或存储密钥。实际调用和结果可到“AI调用统计”查看。</p></section>
      <section v-if="events.length" class="card-surface event-panel"><h3>最近配置记录</h3><div v-for="(event, index) in events" :key="index" class="event-row"><strong>{{ event.actor_name || '管理员' }}</strong><time>{{ formatTime(event.created_at) }}</time><span>默认 {{ modelName(event.after_config.default_model) }} · {{ Object.keys(event.after_config.overrides || {}).length }} 项单独配置</span></div></section>
      <footer class="card-surface save-bar"><div><strong>{{ dirty ? '有未保存的调整' : '当前配置已保存' }}</strong><small>{{ settings.updated_by_name ? `最后保存：${settings.updated_by_name} · ${formatTime(settings.updated_at)}` : '初始配置：全部沿用 DeepSeek-V4-Pro' }}</small></div><div class="save-actions"><button class="btn btn-secondary" :disabled="!dirty || saving" @click="resetDraft">放弃调整</button><button class="btn btn-primary" :disabled="!dirty || saving || loading" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button></div></footer>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import axios from 'axios'
import { routingKey, groupAiScenes, aiModelDisplayName } from '@/utils/aiModelSettings'

const loading = ref(false)
const saving = ref(false)
const loaded = ref(false)
const error = ref('')
const message = ref('')
const keyword = ref('')
const providers = ref([])
const models = ref([])
const scenarios = ref([])
const events = ref([])
const settings = ref({ default_model: '', overrides: {}, revision: 0 })
const draft = reactive({ default_model: '', overrides: {} })
const dirty = computed(() => routingKey(draft) !== routingKey(settings.value))
const groups = computed(() => groupAiScenes(scenarios.value, keyword.value))
const providerModels = (id) => models.value.filter((model) => model.provider === id)
const modelName = (id) => models.value.find((model) => model.id === id)?.name || aiModelDisplayName(id)
const formatTime = (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : ''
const resetDraft = () => { draft.default_model = settings.value.default_model; draft.overrides = { ...settings.value.overrides } }
const selectScene = (id, model) => {
  if (!model) delete draft.overrides[id]
  else draft.overrides[id] = model
}
const apply = (data) => {
  settings.value = data.settings
  providers.value = data.providers
  models.value = data.models
  scenarios.value = data.scenarios
  events.value = data.events
  loaded.value = true
  resetDraft()
}
const reload = async () => {
  if (dirty.value && !window.confirm('刷新将放弃未保存的调整，是否继续？')) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get('/api/management/ai-models')
    if (!data.success) throw new Error(data.error)
    apply(data)
  } catch (err) { error.value = err.response?.data?.error || err.message || '读取配置失败。' }
  finally { loading.value = false }
}
const unify = () => {
  if (!window.confirm(`将全部 ${scenarios.value.length} 个场景设为 ${modelName(draft.default_model)}，清除单独配置？点击保存后才生效。`)) return
  draft.overrides = {}
  message.value = '已统一设置到草稿，请点击“保存配置”生效。'
}
const save = async () => {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const { data } = await axios.put('/api/management/ai-models', { ...draft, revision: settings.value.revision })
    if (!data.success) throw new Error(data.error)
    apply(data)
    message.value = '模型配置已保存，后续调用将采用最新设置。'
  } catch (err) { error.value = err.response?.data?.error || err.message || '保存配置失败。' }
  finally { saving.value = false }
}
onBeforeRouteLeave(() => !dirty.value || window.confirm('还有未保存的模型调整，确定离开？'))
onMounted(reload)
</script>

<style scoped>
.model-page { display: grid; gap: 20px; padding-bottom: 24px; color: #182c45; }
.card-surface { background: #fff; border: 1px solid #dce6ef; border-radius: 20px; box-shadow: 0 10px 28px #17334c07; }
.page-kicker { color: #1680ad; font-size: 12px; font-weight: 700; letter-spacing: 1.5px; }
.model-header { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 28px; background: radial-gradient(ellipse at right top, #e5f3fa, transparent 60%), #fff; }
h2 { font-size: 27px; margin: 7px 0 10px; }
h3 { font-size: 17px; margin: 0; }
p { color: #66778c; line-height: 1.8; margin: 6px 0 0; }
.provider-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.provider-card { padding: 20px; display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.provider-index { color: #91b2c9; font-size: 12px; font-weight: 700; padding-top: 4px; }
.provider-card code { display: block; margin-top: 8px; font-size: 11px; color: #72859a; overflow-wrap: anywhere; }
.key-status { display: inline-flex; margin-top: 2px; margin-left: auto; background: #fff4e8; color: #9c5915; border-radius: 20px; padding: 4px 9px; font-size: 11px; white-space: nowrap; }
.key-status.ready { background: #e9f6f0; color: #1e7455; }
.default-panel { display: grid; grid-template-columns: 1fr minmax(300px, 420px); gap: 32px; padding: 26px 28px; border-top: 3px solid #1680ad; }
.section-kicker { font-size: 11px; font-weight: 700; letter-spacing: 1.5px; color: #1680ad; display: block; margin-bottom: 8px; }
.default-controls { display: grid; grid-template-columns: 1fr auto; gap: 9px; align-content: center; }
.default-controls label { grid-column: 1 / -1; }
label { font-size: 12px; color: #657991; }
select, input { min-height: 42px; border: 1px solid #cedce7; border-radius: 9px; padding: 9px 12px; background: white; color: #263d55; font-size: 13px; width: 100%; box-sizing: border-box; }
select:focus, input:focus { outline: 2px solid #8cc5e2; outline-offset: 2px; }
.scene-section { display: grid; gap: 16px; }
.scene-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin: 6px 0; }
.scene-toolbar input { max-width: 300px; }
.scene-group { overflow: hidden; }
.scene-group header { padding: 16px 24px; display: flex; justify-content: space-between; background: #f5f9fc; border-bottom: 1px solid #e5edf3; }
.scene-group header span { color: #7a8b9d; font-size: 12px; }
.scene-row { display: grid; grid-template-columns: 1fr minmax(250px, 340px); gap: 28px; padding: 20px 24px; align-items: center; }
.scene-row + .scene-row { border-top: 1px solid #edf1f5; }
.scene-description strong { font-size: 15px; }
.scene-description p { font-size: 12px; }
.scene-selector { display: grid; gap: 6px; }
.behavior-note, .event-panel { padding: 24px 28px; }
.behavior-note p { font-size: 12px; }
.event-row { display: flex; gap: 16px; flex-wrap: wrap; padding-top: 15px; font-size: 12px; color: #6d7e91; }
.event-row strong { color: #344e68; min-width: 70px; }
.save-bar { position: sticky; bottom: 16px; z-index: 5; display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 18px 24px; box-shadow: 0 8px 32px #14385118; border: 1px solid #d6e5ef; }
.save-bar strong { font-size: 14px; }.save-bar small { display: block; color: #78899d; font-size: 11px; margin-top: 6px; }.save-actions { display: flex; gap: 10px; flex-shrink: 0; }
.notice { padding: 14px 20px; border-radius: 10px; margin: 0; font-size: 13px; }.notice.error { color: #a43d3d; background: #fff0f0; }.notice.success { color: #226b50; background: #eaf6ef; }
.loading { text-align: center; padding: 36px; color: #74879b; }
@media (max-width: 1200px) { .provider-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.default-panel { grid-template-columns: 1fr; gap: 18px; } }
@media (max-width: 640px) { .model-page { gap: 14px; }.model-header { padding: 20px; flex-wrap: wrap; }h2 { font-size: 23px; }.provider-card { padding: 14px; gap: 8px; }.provider-card h3 { font-size: 15px; }.key-status { margin-left: 0; }.default-panel, .behavior-note, .event-panel { padding: 20px; }.default-controls { grid-template-columns: 1fr; }.scene-toolbar { align-items: stretch; flex-direction: column; }.scene-toolbar input { max-width: none; }.scene-row { grid-template-columns: 1fr; padding: 18px; gap: 14px; }.scene-group header { padding: 16px 18px; }.save-bar { bottom: 8px; padding: 14px; flex-wrap: wrap; }.save-actions { width: 100%; }.save-actions .btn { flex: 1; }.event-row { gap: 6px 12px; } }
</style>
