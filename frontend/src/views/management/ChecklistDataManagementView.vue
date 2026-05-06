<template>
  <div class="page-shell checklist-management-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">管理系统</div>
        <h2>巡检表数据管理</h2>
        <p class="page-desc">管理检查表字段结构，并在选中检查表后维护对应规范数据。</p>
      </div>
      <div v-if="hasPermission" class="header-actions">
        <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchChecklists">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
        <button class="btn btn-secondary" type="button" :disabled="backupExporting" @click="exportBackup">
          {{ backupExporting ? '导出中...' : '导出备份' }}
        </button>
        <button class="btn btn-import" type="button" :disabled="backupImporting" @click="triggerBackupImport">
          {{ backupImporting ? '导入中...' : '导入备份覆盖' }}
        </button>
        <input ref="backupFileInputRef" class="hidden-file-input" type="file" accept="application/json,.json"
          :disabled="backupImporting" @change="importBackup" />
        <button class="btn btn-primary" type="button" @click="openCreateDialog">新建检查表</button>
      </div>
    </div>

    <div v-if="!hasPermission" class="card-surface permission-card">
      <div class="permission-icon">!</div>
      <div class="permission-title">无权限访问</div>
      <div class="permission-desc">当前页面仅 root 系统管理员账号可访问和操作。</div>
    </div>

    <template v-else>
      <div v-if="message.text" :class="['message-card', message.type]">{{ message.text }}</div>

      <div class="management-layout">
        <section class="card-surface list-card">
          <div class="section-head">
            <div>
              <div class="section-kicker">检查表清单</div>
              <h3>共 {{ checklists.length }} 张检查表</h3>
            </div>
          </div>

          <div class="checklist-list">
            <article v-for="item in checklists" :key="item.id" class="checklist-item"
              :class="{ active: selectedChecklist && String(selectedChecklist.id) === String(item.id) }"
              @click="selectChecklist(item)">
              <div>
                <div class="table-code">{{ item.table_code }}</div>
                <strong>{{ item.table_name }}</strong>
                <p>{{ item.description || '暂无说明。' }}</p>
              </div>
              <div class="item-meta">
                <span :class="['status-pill', item.is_active ? 'success' : 'neutral']">
                  {{ item.is_active ? '启用' : '停用' }}
                </span>
                <span>{{ item.fields?.length || 0 }} 个字段</span>
                <span>{{ item.standard_count || 0 }} 条规范</span>
              </div>
              <div class="item-actions">
                <button class="btn btn-secondary btn-sm" type="button" @click.stop="openEditDialog(item)">
                  编辑检查表
                </button>
                <button class="btn btn-danger btn-sm" type="button" :disabled="deletingId === item.id"
                  @click.stop="deleteChecklist(item)">
                  {{ deletingId === item.id ? '删除中...' : '删除' }}
                </button>
              </div>
            </article>
            <div v-if="!loading && !checklists.length" class="empty-block">
              暂无检查表，请点击右上角“新建检查表”开始配置。
            </div>
          </div>
        </section>

        <section class="card-surface standards-card">
          <div v-if="selectedChecklist" class="standards-panel">
            <div class="pane-head">
              <div>
                <div class="section-kicker">规范数据清单</div>
                <h3>{{ selectedChecklist.table_name }}</h3>
                <p>{{ selectedChecklist.description || '当前检查表暂无说明。' }}</p>
              </div>
              <button class="btn btn-primary" type="button" @click="openStandardDialog">维护规范数据</button>
            </div>

            <div class="summary-grid">
              <div>
                <span>检查表编码</span>
                <strong>{{ selectedChecklist.table_code }}</strong>
              </div>
              <div>
                <span>字段数量</span>
                <strong>{{ selectedFields.length }} 个字段</strong>
              </div>
              <div>
                <span>规范数量</span>
                <strong>{{ standardState.total }} 条</strong>
              </div>
            </div>

            <div class="standard-list-card embedded-list-card">
              <div class="standard-toolbar">
                <div>
                  <strong>已维护规范</strong>
                  <span>规范ID由系统自动生成；此处用于查看和快速检索。</span>
                </div>
                <div class="standard-toolbar-controls">
                  <label class="standard-search">
                    <input v-model.trim="standardState.keyword" type="search" placeholder="搜索规范ID或字段内容"
                      @keyup.enter="fetchStandards(standardState, selectedChecklist.id, selectedFields, 1)" />
                    <button class="btn btn-secondary btn-sm" type="button"
                      @click="fetchStandards(standardState, selectedChecklist.id, selectedFields, 1)">
                      搜索
                    </button>
                  </label>
                  <select v-model.number="standardState.pageSize"
                    @change="fetchStandards(standardState, selectedChecklist.id, selectedFields, 1)">
                    <option :value="8">8条/页</option>
                    <option :value="15">15条/页</option>
                    <option :value="30">30条/页</option>
                  </select>
                </div>
              </div>

              <div v-if="standardState.loading" class="standard-empty">规范数据加载中...</div>
              <div v-else-if="!standardState.items.length" class="standard-empty">
                暂无规范数据，请点击“维护规范数据”新增。
              </div>
              <div v-else class="standard-table-wrap">
                <table class="standard-table">
                  <thead>
                    <tr>
                      <th>规范ID</th>
                      <th v-for="field in selectedFields" :key="field.field_key">{{ field.field_label }}</th>
                      <th>创建时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in standardState.items" :key="item.standard_id">
                      <td class="standard-id-cell">{{ item.standard_id }}</td>
                      <td v-for="field in selectedFields" :key="field.field_key">
                        {{ getStandardValue(item, field.field_key) || '-' }}
                      </td>
                      <td>{{ item.created_at || '-' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div class="pagination-bar">
                <span>共 {{ standardState.total }} 条，第 {{ standardState.page }} / {{ standardState.totalPages }} 页</span>
                <div>
                  <button class="btn btn-secondary btn-sm" type="button" :disabled="standardState.page <= 1"
                    @click="changeStandardPage(standardState, selectedChecklist.id, selectedFields, standardState.page - 1)">
                    上一页
                  </button>
                  <button class="btn btn-secondary btn-sm" type="button"
                    :disabled="standardState.page >= standardState.totalPages"
                    @click="changeStandardPage(standardState, selectedChecklist.id, selectedFields, standardState.page + 1)">
                    下一页
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="empty-block empty-standards">
            请先在左侧选择一张检查表；如果还没有检查表，请点击右上角新建。
          </div>
        </section>
      </div>
    </template>

    <div v-if="createDialog.visible" class="dialog-backdrop" @click.self="closeCreateDialog">
      <section class="edit-dialog create-dialog card-surface">
        <div class="dialog-head">
          <div>
            <div class="section-kicker">新建检查表</div>
            <h3>配置检查表与字段</h3>
            <p>新建检查表只需要定义基础信息和字段结构，规范数据创建后再维护。</p>
          </div>
          <button class="dialog-close" type="button" @click="closeCreateDialog">×</button>
        </div>

        <div class="dialog-body">
          <div class="edit-section">
            <div class="edit-section-head">
              <strong>基础信息</strong>
            </div>

            <div class="form-grid">
              <label class="form-field">
                <span>检查表名称</span>
                <input v-model.trim="form.table_name" type="text" placeholder="例如：安全管理检查表" />
              </label>

              <label class="form-field">
                <span>检查表编码</span>
                <div class="auto-code-field">
                  <input v-model.trim="form.table_code" type="text" disabled />
                  <strong>系统生成</strong>
                </div>
                <small>用户无需填写；物理表名将自动生成为 inspection_table_编码。</small>
              </label>

              <label class="form-field span-2">
                <span>检查表说明</span>
                <textarea v-model.trim="form.description" rows="3" placeholder="说明这张检查表的使用场景"></textarea>
              </label>

              <label class="switch-field">
                <input v-model="form.is_active" type="checkbox" />
                <span>启用这张检查表</span>
              </label>
            </div>
          </div>

          <div class="edit-section">
            <div class="edit-section-head">
              <strong>字段结构</strong>
              <button class="btn btn-secondary btn-sm" type="button" @click="addField">添加字段</button>
            </div>

            <div class="field-table">
              <div class="field-row field-row-head">
                <span>字段名称</span>
                <span>筛选</span>
                <span>操作</span>
              </div>
              <div v-for="(field, index) in form.fields" :key="field.local_id" class="field-row">
                <label>
                  <input v-model.trim="field.field_label" type="text" placeholder="检查内容" />
                </label>
                <label class="mini-check">
                  <input v-model="field.is_filterable" type="checkbox" />
                  <span>可筛选</span>
                </label>
                <button class="btn btn-danger btn-sm" type="button" :disabled="form.fields.length <= 1"
                  @click="removeField(index)">
                  删除
                </button>
              </div>
            </div>

            <div class="schema-note">
              字段隐藏标识由系统按检查表编码自动生成，具备全局唯一识别性；用户只需要维护字段名称。
            </div>
          </div>
        </div>

        <div class="dialog-actions">
          <button class="btn btn-secondary" type="button" @click="closeCreateDialog">取消</button>
          <button class="btn btn-primary" type="button" :disabled="saving" @click="saveChecklist">
            {{ saving ? '创建中...' : '创建检查表' }}
          </button>
        </div>
      </section>
    </div>

    <div v-if="editDialog.visible" class="dialog-backdrop" @click.self="closeEditDialog">
      <section class="edit-dialog card-surface">
        <div class="dialog-head">
          <div>
            <div class="section-kicker">编辑检查表</div>
            <h3>{{ editDialog.table_name || '未命名检查表' }}</h3>
            <p>这里只维护检查表基础信息和字段结构；规范数据请在右侧清单进入维护。</p>
          </div>
          <button class="dialog-close" type="button" @click="closeEditDialog">×</button>
        </div>

        <div class="dialog-body">
          <div class="edit-section">
            <div class="edit-section-head">
              <strong>基础信息</strong>
              <span :class="['status-pill', editDialog.is_active ? 'success' : 'neutral']">
                {{ editDialog.is_active ? '启用' : '停用' }}
              </span>
            </div>

            <div class="form-grid">
              <label class="form-field">
                <span>检查表名称</span>
                <input v-model.trim="editDialog.table_name" type="text" placeholder="请输入检查表名称" />
              </label>

              <label class="form-field">
                <span>检查表编码</span>
                <div class="auto-code-field">
                  <input v-model.trim="editDialog.table_code" type="text" disabled />
                  <strong>不可修改</strong>
                </div>
              </label>

              <label class="form-field span-2">
                <span>检查表说明</span>
                <textarea v-model.trim="editDialog.description" rows="3" placeholder="说明这张检查表的使用场景"></textarea>
              </label>

              <label class="switch-field">
                <input v-model="editDialog.is_active" type="checkbox" />
                <span>启用这张检查表</span>
              </label>
            </div>
          </div>

          <div class="edit-section">
            <div class="edit-section-head">
              <strong>字段结构</strong>
              <button class="btn btn-secondary btn-sm" type="button" @click="addEditField">添加字段</button>
            </div>

            <div class="field-table">
              <div class="field-row field-row-head">
                <span>字段名称</span>
                <span>筛选</span>
                <span>操作</span>
              </div>
              <div v-for="(field, index) in editDialog.fields" :key="field.local_id" class="field-row">
                <label>
                  <input v-model.trim="field.field_label" type="text" placeholder="检查内容" />
                </label>
                <label class="mini-check">
                  <input v-model="field.is_filterable" type="checkbox" />
                  <span>可筛选</span>
                </label>
                <button class="btn btn-danger btn-sm" type="button" :disabled="editDialog.fields.length <= 1"
                  @click="removeEditField(index)">
                  删除
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="dialog-actions">
          <button class="btn btn-secondary" type="button" @click="closeEditDialog">关闭</button>
          <button class="btn btn-primary" type="button" :disabled="editDialog.saving" @click="saveEditDialog">
            {{ editDialog.saving ? '保存中...' : '保存编辑' }}
          </button>
        </div>
      </section>
    </div>

    <div v-if="standardDialog.visible && selectedChecklist" class="dialog-backdrop" @click.self="closeStandardDialog">
      <section class="edit-dialog standard-dialog card-surface">
        <div class="dialog-head">
          <div>
            <div class="section-kicker">规范数据维护</div>
            <h3>{{ selectedChecklist.table_name }}</h3>
            <p>规范ID由系统自动生成，新增和编辑时只需要维护字段内容。</p>
          </div>
          <button class="dialog-close" type="button" @click="closeStandardDialog">×</button>
        </div>

        <div class="dialog-body">
          <div class="standard-manager">
            <div class="standard-editor-card">
              <div class="standard-section-head">
                <div>
                  <strong>新增规范</strong>
                  <span>保存后系统会自动分配下一条规范ID。</span>
                </div>
              </div>

              <div class="standard-form-grid">
                <label v-for="field in selectedFields" :key="field.field_key" class="form-field">
                  <span>{{ field.field_label }}</span>
                  <textarea v-model.trim="standardState.draft.values[field.field_key]" rows="2"
                    :placeholder="`填写${field.field_label}`"></textarea>
                </label>
              </div>

              <div class="standard-form-actions">
                <button class="btn btn-secondary" type="button" @click="resetStandardDraft(standardState, selectedFields)">
                  清空新增内容
                </button>
                <button class="btn btn-primary" type="button" :disabled="standardState.saving"
                  @click="createStandard(standardState, selectedChecklist.id, selectedFields)">
                  {{ standardState.saving ? '保存中...' : '新增规范' }}
                </button>
              </div>
            </div>

            <div v-if="standardState.editingDraft" class="standard-editor-card editing-panel">
              <div class="standard-section-head">
                <div>
                  <strong>编辑规范</strong>
                  <span>规范ID {{ standardState.editingStandardId }} 为系统生成，不支持修改。</span>
                </div>
                <button class="btn btn-secondary btn-sm" type="button" @click="cancelEditStandard(standardState)">
                  取消编辑
                </button>
              </div>

              <div class="standard-form-grid">
                <label v-for="field in selectedFields" :key="field.field_key" class="form-field">
                  <span>{{ field.field_label }}</span>
                  <textarea v-model.trim="standardState.editingDraft.values[field.field_key]" rows="2"></textarea>
                </label>
              </div>

              <div class="standard-form-actions">
                <button class="btn btn-secondary" type="button" @click="cancelEditStandard(standardState)">取消</button>
                <button class="btn btn-primary" type="button" :disabled="standardState.saving"
                  @click="saveEditingStandard(standardState, selectedChecklist.id, selectedFields)">
                  {{ standardState.saving ? '保存中...' : '保存修改' }}
                </button>
              </div>
            </div>

            <div class="standard-list-card">
              <div class="standard-toolbar">
                <div>
                  <strong>规范数据清单</strong>
                  <span>可在这里编辑或删除现有规范。</span>
                </div>
                <div class="standard-toolbar-controls">
                  <label class="standard-search">
                    <input v-model.trim="standardState.keyword" type="search" placeholder="搜索规范ID或字段内容"
                      @keyup.enter="fetchStandards(standardState, selectedChecklist.id, selectedFields, 1)" />
                    <button class="btn btn-secondary btn-sm" type="button"
                      @click="fetchStandards(standardState, selectedChecklist.id, selectedFields, 1)">
                      搜索
                    </button>
                  </label>
                  <select v-model.number="standardState.pageSize"
                    @change="fetchStandards(standardState, selectedChecklist.id, selectedFields, 1)">
                    <option :value="8">8条/页</option>
                    <option :value="15">15条/页</option>
                    <option :value="30">30条/页</option>
                  </select>
                </div>
              </div>

              <div v-if="standardState.loading" class="standard-empty">规范数据加载中...</div>
              <div v-else-if="!standardState.items.length" class="standard-empty">
                暂无规范数据，可以先在上方新增第一条。
              </div>
              <div v-else class="standard-table-wrap">
                <table class="standard-table">
                  <thead>
                    <tr>
                      <th>规范ID</th>
                      <th v-for="field in selectedFields" :key="field.field_key">{{ field.field_label }}</th>
                      <th>创建时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in standardState.items" :key="item.standard_id">
                      <td class="standard-id-cell">{{ item.standard_id }}</td>
                      <td v-for="field in selectedFields" :key="field.field_key">
                        {{ getStandardValue(item, field.field_key) || '-' }}
                      </td>
                      <td>{{ item.created_at || '-' }}</td>
                      <td>
                        <div class="row-actions">
                          <button class="btn btn-secondary btn-sm" type="button"
                            @click="startEditStandard(standardState, item, selectedFields)">
                            编辑
                          </button>
                          <button class="btn btn-danger btn-sm" type="button"
                            :disabled="standardState.deletingId === item.standard_id"
                            @click="deleteStandard(standardState, selectedChecklist.id, selectedFields, item)">
                            {{ standardState.deletingId === item.standard_id ? '删除中...' : '删除' }}
                          </button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div class="pagination-bar">
                <span>共 {{ standardState.total }} 条，第 {{ standardState.page }} / {{ standardState.totalPages }} 页</span>
                <div>
                  <button class="btn btn-secondary btn-sm" type="button" :disabled="standardState.page <= 1"
                    @click="changeStandardPage(standardState, selectedChecklist.id, selectedFields, standardState.page - 1)">
                    上一页
                  </button>
                  <button class="btn btn-secondary btn-sm" type="button"
                    :disabled="standardState.page >= standardState.totalPages"
                    @click="changeStandardPage(standardState, selectedChecklist.id, selectedFields, standardState.page + 1)">
                    下一页
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="dialog-actions">
          <button class="btn btn-secondary" type="button" @click="closeStandardDialog">关闭</button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onMounted, reactive, ref } from 'vue'

const currentUserId = localStorage.getItem('user_id') || ''
const currentRole = localStorage.getItem('user_role') || ''
const hasPermission = currentRole === 'root'

const loading = ref(false)
const saving = ref(false)
const deletingId = ref(null)
const backupExporting = ref(false)
const backupImporting = ref(false)
const backupFileInputRef = ref(null)
const checklists = ref([])
const selectedChecklist = ref(null)
const message = reactive({
  text: '',
  type: 'info'
})

const selectedFields = computed(() => selectedChecklist.value?.fields || [])

const normalizeKey = (value) => String(value || '')
  .trim()
  .toLowerCase()
  .replace(/[^a-z0-9_]+/g, '_')
  .replace(/^_+|_+$/g, '')
  .replace(/_+/g, '_')

const createDefaultCode = () => {
  const now = new Date()
  const stamp = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
    String(now.getHours()).padStart(2, '0'),
    String(now.getMinutes()).padStart(2, '0'),
    String(now.getSeconds()).padStart(2, '0')
  ].join('')
  const suffix = Math.random().toString(36).slice(2, 6)
  return `checklist_${stamp}_${suffix}`
}

const createFieldKey = (tableCode, index = 1) => {
  const normalizedTableCode = normalizeKey(tableCode || createDefaultCode())
  const orderText = String(Math.max(Number(index) || 1, 1)).padStart(3, '0')
  const suffix = Math.random().toString(36).slice(2, 8)
  return `f_${normalizedTableCode}_${orderText}_${suffix}`
}

const createField = (field = {}, index = 1, tableCode = '') => ({
  local_id: field.id || `${Date.now()}_${Math.random().toString(16).slice(2)}`,
  field_key: field.field_key || createFieldKey(tableCode, index),
  field_label: field.field_label || '',
  is_filterable: field.is_filterable ?? true
})

const defaultFields = (tableCode) => [
  createField({ field_label: '序号' }, 1, tableCode),
  createField({ field_label: '检查内容' }, 2, tableCode),
  createField({ field_label: '规范要求' }, 3, tableCode),
  createField({ field_label: '检查方法' }, 4, tableCode)
]

const createEmptyForm = () => {
  const tableCode = createDefaultCode()
  return {
    id: null,
    table_code: tableCode,
    table_name: '',
    description: '',
    is_active: true,
    fields: defaultFields(tableCode)
  }
}

const form = reactive(createEmptyForm())

const createStandardDraft = (fields = []) => ({
  values: fields.reduce((result, field) => {
    result[field.field_key] = ''
    return result
  }, {})
})

const createStandardState = () => ({
  items: [],
  page: 1,
  pageSize: 8,
  total: 0,
  totalPages: 1,
  keyword: '',
  loading: false,
  saving: false,
  deletingId: null,
  draft: createStandardDraft(),
  editingStandardId: null,
  editingDraft: null
})

const createDialog = reactive({ visible: false })
const standardDialog = reactive({ visible: false })
const editDialog = reactive({
  visible: false,
  id: null,
  table_code: '',
  table_name: '',
  description: '',
  is_active: true,
  fields: [],
  standard_count: 0,
  physical_table_name: '',
  saving: false
})

const standardState = reactive(createStandardState())
let messageTimer = null

const setMessage = (text, type = 'info') => {
  if (messageTimer) {
    window.clearTimeout(messageTimer)
    messageTimer = null
  }
  message.text = text
  message.type = type
  if (text) {
    messageTimer = window.setTimeout(() => {
      message.text = ''
      messageTimer = null
    }, 2600)
  }
}

const ensureStandardDraftFields = (draft, fields = []) => {
  if (!draft.values) draft.values = {}
  fields.forEach((field) => {
    if (!(field.field_key in draft.values)) draft.values[field.field_key] = ''
  })
}

const resetStandardDraft = (state, fields = []) => {
  state.draft = createStandardDraft(fields)
}

const resetStandardState = (state, fields = []) => {
  const pageSize = state.pageSize || 8
  state.items = []
  state.page = 1
  state.pageSize = pageSize
  state.total = 0
  state.totalPages = 1
  state.keyword = ''
  state.loading = false
  state.saving = false
  state.deletingId = null
  state.draft = createStandardDraft(fields)
  state.editingStandardId = null
  state.editingDraft = null
}

const getStandardValue = (item, fieldKey) => {
  const value = item?.[fieldKey]
  return value === null || value === undefined ? '' : String(value)
}

const buildStandardPayload = (draft, fields) => {
  if (!fields.length) throw new Error('请先配置检查表字段。')
  const values = {}
  fields.forEach((field) => {
    values[field.field_key] = String(draft?.values?.[field.field_key] ?? '').trim()
  })
  if (!Object.values(values).some((value) => value)) {
    throw new Error('请至少填写一项规范内容。')
  }
  return {
    user_id: currentUserId,
    values
  }
}

const buildChecklistPayload = (source) => ({
  user_id: currentUserId,
  table_code: normalizeKey(source.table_code),
  table_name: source.table_name,
  description: source.description,
  is_active: source.is_active,
  fields: source.fields.map((field) => ({
    field_key: normalizeKey(field.field_key),
    field_label: field.field_label,
    is_filterable: Boolean(field.is_filterable)
  }))
})

const validateFieldRows = (fields, tableCode) => {
  const keys = new Set()
  const labels = new Set()
  for (const field of fields) {
    field.field_key = normalizeKey(field.field_key)
    if (!field.field_key) {
      field.field_key = createFieldKey(tableCode, fields.indexOf(field) + 1)
    }
    if (!field.field_label) return '请填写字段名称。'
    if (['id', 'standard_id', 'created_at', 'updated_at'].includes(field.field_key)) {
      return '字段系统标识生成异常，请重新进入页面后再试。'
    }
    if (keys.has(field.field_key)) return '字段系统标识重复，请重新进入页面后再试。'
    if (labels.has(field.field_label)) return `字段名称【${field.field_label}】重复。`
    keys.add(field.field_key)
    labels.add(field.field_label)
  }
  return ''
}

const fetchStandards = async (state, checklistId, fields = [], page = state.page) => {
  if (!checklistId) {
    resetStandardState(state, fields)
    return null
  }
  ensureStandardDraftFields(state.draft, fields)
  if (state.editingDraft) ensureStandardDraftFields(state.editingDraft, fields)
  try {
    state.loading = true
    const response = await axios.get(`/api/management/checklists/${checklistId}/standards`, {
      params: {
        user_id: currentUserId,
        page,
        page_size: state.pageSize,
        keyword: state.keyword,
        _ts: Date.now()
      }
    })
    state.items = response.data?.items || []
    state.page = Number(response.data?.page || 1)
    state.pageSize = Number(response.data?.page_size || state.pageSize || 8)
    state.total = Number(response.data?.total || 0)
    state.totalPages = Number(response.data?.total_pages || 1)
    if (selectedChecklist.value && String(selectedChecklist.value.id) === String(checklistId)) {
      selectedChecklist.value.standard_count = state.total
    }
    return response.data
  } catch (error) {
    setMessage(error?.response?.data?.error || '规范数据加载失败。', 'error')
    return null
  } finally {
    state.loading = false
  }
}

const fetchChecklists = async (options = {}) => {
  if (!hasPermission) return
  const reloadStandards = options.reloadStandards !== false
  const previousSelectedId = selectedChecklist.value?.id
  try {
    loading.value = true
    const response = await axios.get('/api/management/checklists', {
      params: {
        user_id: currentUserId,
        _ts: Date.now()
      }
    })
    checklists.value = response.data?.checklists || []
    const nextSelected = previousSelectedId
      ? checklists.value.find((item) => String(item.id) === String(previousSelectedId))
      : checklists.value[0]
    selectedChecklist.value = nextSelected || null
    if (selectedChecklist.value && reloadStandards) {
      await fetchStandards(standardState, selectedChecklist.value.id, selectedFields.value, standardState.page || 1)
    } else if (!selectedChecklist.value) {
      resetStandardState(standardState)
    }
  } catch (error) {
    setMessage(error?.response?.data?.error || '检查表数据加载失败。', 'error')
  } finally {
    loading.value = false
  }
}

const selectChecklist = async (item, options = {}) => {
  selectedChecklist.value = item
  resetStandardState(standardState, selectedFields.value)
  await fetchStandards(standardState, item.id, selectedFields.value, 1)
  if (!options.silent) setMessage(`已选择【${item.table_name}】。`, 'info')
}

const openCreateDialog = () => {
  Object.assign(form, createEmptyForm())
  createDialog.visible = true
  setMessage('')
}

const closeCreateDialog = () => {
  createDialog.visible = false
}

const hydrateEditDialog = (item) => {
  Object.assign(editDialog, {
    visible: true,
    id: item.id,
    table_code: item.table_code || '',
    table_name: item.table_name || '',
    description: item.description || '',
    is_active: Boolean(item.is_active),
    fields: (item.fields || []).map((field, index) => createField(field, index + 1, item.table_code)),
    standard_count: Number(item.standard_count || 0),
    physical_table_name: item.physical_table_name || '',
    saving: false
  })
  if (!editDialog.fields.length) editDialog.fields = defaultFields(item.table_code)
}

const openEditDialog = (item) => {
  hydrateEditDialog(item)
  setMessage('')
}

const closeEditDialog = () => {
  editDialog.visible = false
}

const openStandardDialog = () => {
  if (!selectedChecklist.value) return
  resetStandardDraft(standardState, selectedFields.value)
  standardState.editingStandardId = null
  standardState.editingDraft = null
  standardDialog.visible = true
}

const closeStandardDialog = () => {
  standardDialog.visible = false
  standardState.editingStandardId = null
  standardState.editingDraft = null
}

const addField = () => {
  form.fields.push(createField({}, form.fields.length + 1, form.table_code))
}

const removeField = (index) => {
  form.fields.splice(index, 1)
}

const addEditField = () => {
  editDialog.fields.push(createField({}, editDialog.fields.length + 1, editDialog.table_code))
}

const removeEditField = (index) => {
  editDialog.fields.splice(index, 1)
}

const saveChecklist = async () => {
  const fieldError = validateFieldRows(form.fields, form.table_code)
  if (fieldError) {
    setMessage(fieldError, 'error')
    return
  }

  try {
    saving.value = true
    const response = await axios.post('/api/management/checklists', buildChecklistPayload(form))
    const newId = response.data?.id
    createDialog.visible = false
    setMessage(response.data?.message || '检查表已创建。', 'success')
    await fetchChecklists({ reloadStandards: false })
    const latest = checklists.value.find((item) => String(item.id) === String(newId))
    if (latest) await selectChecklist(latest, { silent: true })
  } catch (error) {
    setMessage(error?.response?.data?.error || '检查表创建失败。', 'error')
  } finally {
    saving.value = false
  }
}

const saveEditDialog = async () => {
  if (!editDialog.id) return
  const fieldError = validateFieldRows(editDialog.fields, editDialog.table_code)
  if (fieldError) {
    setMessage(fieldError, 'error')
    return
  }

  try {
    editDialog.saving = true
    const response = await axios.put(`/api/management/checklists/${editDialog.id}`, buildChecklistPayload(editDialog))
    const editedId = editDialog.id
    closeEditDialog()
    await fetchChecklists({ reloadStandards: false })
    const latest = checklists.value.find((item) => String(item.id) === String(editedId))
    if (latest) {
      if (selectedChecklist.value && String(selectedChecklist.value.id) === String(latest.id)) {
        selectedChecklist.value = latest
        await fetchStandards(standardState, latest.id, selectedFields.value, 1)
      }
    }
    setMessage(response.data?.message || '检查表编辑已保存。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || '检查表编辑保存失败。', 'error')
  } finally {
    editDialog.saving = false
  }
}

const deleteChecklist = async (item) => {
  if (!item?.id) return
  const confirmed = window.confirm(`确定删除【${item.table_name || '当前检查表'}】吗？删除会同时移除字段结构、规范数据和对应物理表。`)
  if (!confirmed) return

  try {
    deletingId.value = item.id
    setMessage('')
    const response = await axios.delete(`/api/management/checklists/${item.id}`, {
      data: { user_id: currentUserId }
    })
    if (String(editDialog.id) === String(item.id)) closeEditDialog()
    if (selectedChecklist.value && String(selectedChecklist.value.id) === String(item.id)) {
      selectedChecklist.value = null
      closeStandardDialog()
    }
    await fetchChecklists()
    setMessage(response.data?.message || '检查表已删除。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || '检查表删除失败。', 'error')
  } finally {
    deletingId.value = null
  }
}

const getDownloadFileName = (disposition, fallback) => {
  const value = String(disposition || '')
  const matched = value.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i)
  return decodeURIComponent(matched?.[1] || matched?.[2] || '') || fallback
}

const exportBackup = async () => {
  try {
    backupExporting.value = true
    setMessage('')
    const response = await axios.get('/api/management/checklists/export', {
      params: {
        user_id: currentUserId,
        _ts: Date.now()
      },
      responseType: 'blob'
    })
    const blobUrl = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = getDownloadFileName(
      response.headers['content-disposition'],
      `ywddzx_checklists_backup_${new Date().toISOString().slice(0, 10)}.json`
    )
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(blobUrl)
    setMessage('巡检表数据备份文件已生成。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || '巡检表数据导出失败。', 'error')
  } finally {
    backupExporting.value = false
  }
}

const triggerBackupImport = () => {
  backupFileInputRef.value?.click()
}

const importBackup = async (event) => {
  const input = event.target
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  if (!file.name.toLowerCase().endsWith('.json')) {
    setMessage('只能导入 JSON 格式的巡检表备份文件。', 'error')
    return
  }

  const confirmed = window.confirm('导入备份会覆盖当前所有巡检表配置与规范数据。若当前检查表已被业务数据引用且备份不包含它，系统会阻止导入。确定继续吗？')
  if (!confirmed) return

  try {
    backupImporting.value = true
    setMessage('')
    const formData = new FormData()
    formData.append('user_id', currentUserId)
    formData.append('file', file)
    const response = await axios.post('/api/management/checklists/import', formData)
    createDialog.visible = false
    editDialog.visible = false
    standardDialog.visible = false
    selectedChecklist.value = null
    setMessage(response.data?.message || '巡检表备份已导入。', 'success')
    await fetchChecklists()
  } catch (error) {
    setMessage(error?.response?.data?.error || '巡检表备份导入失败。', 'error')
  } finally {
    backupImporting.value = false
  }
}

const refreshChecklistMetaAfterStandardChange = async (state, checklistId, fields, page = state.page) => {
  await fetchStandards(state, checklistId, fields, page)
  await fetchChecklists({ reloadStandards: false })
  const latest = checklists.value.find((item) => String(item.id) === String(checklistId))
  if (latest) selectedChecklist.value = latest
}

const createStandard = async (state, checklistId, fields = []) => {
  if (!checklistId) return
  try {
    state.saving = true
    const payload = buildStandardPayload(state.draft, fields)
    const response = await axios.post(`/api/management/checklists/${checklistId}/standards`, payload)
    resetStandardDraft(state, fields)
    await refreshChecklistMetaAfterStandardChange(state, checklistId, fields, 1)
    setMessage(response.data?.message || '规范数据已新增。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || error?.message || '规范数据新增失败。', 'error')
  } finally {
    state.saving = false
  }
}

const startEditStandard = (state, item, fields = []) => {
  state.editingStandardId = item?.standard_id
  state.editingDraft = {
    values: fields.reduce((result, field) => {
      result[field.field_key] = getStandardValue(item, field.field_key)
      return result
    }, {})
  }
}

const cancelEditStandard = (state) => {
  state.editingStandardId = null
  state.editingDraft = null
}

const saveEditingStandard = async (state, checklistId, fields = []) => {
  if (!checklistId || state.editingStandardId === null || !state.editingDraft) return
  try {
    state.saving = true
    const payload = buildStandardPayload(state.editingDraft, fields)
    const response = await axios.put(
      `/api/management/checklists/${checklistId}/standards/${encodeURIComponent(state.editingStandardId)}`,
      payload
    )
    cancelEditStandard(state)
    await refreshChecklistMetaAfterStandardChange(state, checklistId, fields, state.page)
    setMessage(response.data?.message || '规范数据已保存。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || error?.message || '规范数据保存失败。', 'error')
  } finally {
    state.saving = false
  }
}

const deleteStandard = async (state, checklistId, fields = [], item) => {
  if (!checklistId || !item?.standard_id) return
  const confirmed = window.confirm(`确定删除规范ID【${item.standard_id}】吗？`)
  if (!confirmed) return

  try {
    state.deletingId = item.standard_id
    const response = await axios.delete(
      `/api/management/checklists/${checklistId}/standards/${encodeURIComponent(item.standard_id)}`,
      { data: { user_id: currentUserId } }
    )
    if (String(state.editingStandardId) === String(item.standard_id)) cancelEditStandard(state)
    const nextPage = state.items.length <= 1 && state.page > 1 ? state.page - 1 : state.page
    await refreshChecklistMetaAfterStandardChange(state, checklistId, fields, nextPage)
    setMessage(response.data?.message || '规范数据已删除。', 'success')
  } catch (error) {
    setMessage(error?.response?.data?.error || '规范数据删除失败。', 'error')
  } finally {
    state.deletingId = null
  }
}

const changeStandardPage = (state, checklistId, fields = [], page) => {
  fetchStandards(state, checklistId, fields, page)
}

onMounted(fetchChecklists)
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
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.page-kicker,
.section-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0e7490;
  font-size: 12px;
  font-weight: 900;
  margin-bottom: 10px;
}

.page-header h2,
.section-head h3,
.pane-head h3 {
  margin: 0;
  color: #0f172a;
}

.page-header h2 {
  font-size: 32px;
}

.page-desc,
.pane-head p,
.checklist-item p,
.dialog-head p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.header-actions,
.form-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.message-card {
  position: fixed;
  top: 96px;
  left: 50%;
  z-index: 160;
  min-width: min(420px, calc(100vw - 40px));
  text-align: center;
  padding: 13px 16px;
  border-radius: 16px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 14px;
  font-weight: 800;
  box-shadow: 0 20px 46px rgba(15, 23, 42, 0.18);
  transform: translateX(-50%);
  animation: toast-flash 2.6s ease both;
}

.message-card.success {
  border-color: #bbf7d0;
  background: #ecfdf5;
  color: #15803d;
}

.message-card.error {
  border-color: #fecaca;
  background: #fef2f2;
  color: #dc2626;
}

@keyframes toast-flash {
  0% {
    opacity: 0;
    transform: translate(-50%, -12px) scale(0.96);
  }
  12%,
  78% {
    opacity: 1;
    transform: translate(-50%, 0) scale(1);
  }
  18%,
  30% {
    filter: brightness(1.08);
  }
  24%,
  36% {
    filter: brightness(1);
  }
  100% {
    opacity: 0;
    transform: translate(-50%, -8px) scale(0.98);
  }
}

.management-layout {
  display: grid;
  grid-template-columns: minmax(320px, 390px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.list-card,
.standards-card {
  padding: 20px;
}

.section-head,
.pane-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.checklist-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 780px;
  overflow: auto;
  padding-right: 4px;
}

.checklist-item {
  width: 100%;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 18px;
  padding: 15px;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 12px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.checklist-item:hover,
.checklist-item.active {
  border-color: #67e8f9;
  background: linear-gradient(180deg, #ecfeff 0%, #ffffff 100%);
}

.table-code {
  color: #0891b2;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.04em;
}

.checklist-item strong {
  display: block;
  margin-top: 5px;
  color: #0f172a;
  font-size: 16px;
}

.item-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.item-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 900;
}

.status-pill.success {
  background: #ecfdf5;
  color: #15803d;
}

.status-pill.neutral {
  background: #f1f5f9;
  color: #475569;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-grid div {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.summary-grid span {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 6px;
}

.summary-grid strong {
  color: #0f172a;
  word-break: break-word;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.form-field,
.switch-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.form-field span,
.switch-field span {
  color: #334155;
  font-size: 13px;
  font-weight: 900;
}

.form-field input,
.form-field select,
.form-field textarea {
  width: 100%;
  border: 1px solid #d7e0ea;
  border-radius: 14px;
  background: #fff;
  padding: 11px 12px;
  color: #0f172a;
  font-size: 14px;
  box-sizing: border-box;
}

.form-field input:disabled {
  background: #f1f5f9;
  color: #64748b;
}

.form-field small {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.span-2 {
  grid-column: 1 / -1;
}

.auto-code-field {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}

.auto-code-field input {
  cursor: not-allowed;
  border-color: #cbd5e1;
  background: #f1f5f9;
  color: #64748b;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.auto-code-field strong {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  padding: 0 12px;
  border-radius: 12px;
  background: #e2e8f0;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}

.switch-field {
  flex-direction: row;
  align-items: center;
  min-height: 44px;
}

.field-table {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-row {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 110px 80px;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
}

.field-row-head {
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}

.field-row input[type='text'] {
  width: 100%;
  border: 1px solid #d7e0ea;
  border-radius: 12px;
  padding: 10px;
  box-sizing: border-box;
}

.mini-check {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #475569;
  font-size: 13px;
  font-weight: 800;
}

.schema-note {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
  line-height: 1.7;
}

.standard-manager {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.standard-editor-card,
.standard-list-card {
  border: 1px solid #dbe4ee;
  border-radius: 22px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 18px;
}

.embedded-list-card {
  background: #fff;
}

.editing-panel {
  border-color: #bae6fd;
  background: linear-gradient(180deg, #f0f9ff 0%, #ffffff 100%);
}

.standard-section-head,
.standard-toolbar,
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.standard-section-head {
  margin-bottom: 14px;
}

.standard-section-head strong,
.standard-toolbar strong {
  display: block;
  color: #0f172a;
  font-size: 16px;
  margin-bottom: 5px;
}

.standard-section-head span,
.standard-toolbar span {
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.standard-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.standard-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.standard-toolbar {
  align-items: flex-start;
  margin-bottom: 14px;
}

.standard-toolbar-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.standard-search {
  min-width: min(360px, 100%);
  display: grid;
  grid-template-columns: minmax(180px, 1fr) auto;
  gap: 8px;
}

.standard-search input,
.standard-toolbar-controls select {
  min-height: 38px;
  border: 1px solid #d7e0ea;
  border-radius: 12px;
  background: #fff;
  padding: 0 12px;
  color: #0f172a;
  font-size: 13px;
  box-sizing: border-box;
}

.standard-table-wrap {
  width: 100%;
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
}

.standard-table {
  width: 100%;
  min-width: 820px;
  border-collapse: separate;
  border-spacing: 0;
}

.standard-table th,
.standard-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  vertical-align: top;
  color: #334155;
  font-size: 13px;
  line-height: 1.6;
  max-width: 260px;
}

.standard-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}

.standard-table tbody tr:last-child td {
  border-bottom: 0;
}

.standard-id-cell {
  color: #0e7490;
  font-weight: 900;
  white-space: nowrap;
}

.row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: nowrap;
}

.standard-empty {
  min-height: 150px;
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
  text-align: center;
}

.pagination-bar {
  margin-top: 14px;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.pagination-bar > div {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.empty-block,
.permission-card {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748b;
  line-height: 1.8;
}

.empty-standards {
  min-height: 560px;
}

.permission-card {
  flex-direction: column;
  margin: 24px;
  padding: 32px;
}

.permission-icon {
  width: 56px;
  height: 56px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ecfeff;
  color: #0891b2;
  font-size: 28px;
  font-weight: 900;
  margin-bottom: 14px;
}

.permission-title {
  font-size: 22px;
  font-weight: 900;
  color: #0f172a;
  margin-bottom: 8px;
}

.permission-desc {
  color: #64748b;
  font-size: 14px;
}

.btn {
  min-height: 42px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s ease;
}

.btn-sm {
  min-height: 34px;
  padding: 0 12px;
  font-size: 12px;
}

.btn-primary {
  border-color: #0891b2;
  background: #0891b2;
  color: #fff;
}

.btn-danger {
  border-color: #fecaca;
  background: #fef2f2;
  color: #dc2626;
}

.btn-import {
  border-color: #fed7aa;
  background: #fff7ed;
  color: #c2410c;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.hidden-file-input {
  display: none;
}

.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  justify-content: flex-end;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(6px);
}

.edit-dialog {
  width: min(940px, calc(100vw - 32px));
  height: calc(100vh - 32px);
  margin: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.standard-dialog {
  width: min(1120px, calc(100vw - 32px));
}

.dialog-head {
  padding: 22px 24px 18px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.dialog-head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 24px;
}

.dialog-close {
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
}

.dialog-body {
  flex: 1;
  overflow: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.edit-section {
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  padding: 18px;
  background: #fff;
}

.edit-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.edit-section-head strong {
  color: #0f172a;
  font-size: 16px;
}

.dialog-actions {
  padding: 16px 24px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  background: #f8fafc;
}

@media (max-width: 1180px) {
  .management-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .page-header,
  .pane-head,
  .standard-toolbar,
  .pagination-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .form-grid,
  .standard-form-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .field-row {
    grid-template-columns: 1fr;
  }

  .dialog-backdrop {
    justify-content: center;
  }

  .edit-dialog,
  .standard-dialog {
    width: calc(100vw - 20px);
    height: calc(100vh - 20px);
    margin: 10px;
  }

  .dialog-head,
  .dialog-body,
  .dialog-actions {
    padding-left: 16px;
    padding-right: 16px;
  }

  .standard-toolbar-controls,
  .standard-search {
    width: 100%;
  }

  .standard-search {
    grid-template-columns: 1fr;
  }
}
</style>
