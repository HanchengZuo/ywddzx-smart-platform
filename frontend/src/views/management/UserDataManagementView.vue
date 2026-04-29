<template>
  <div class="page-shell user-management-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">管理系统</div>
        <h2>用户数据管理</h2>
        <p class="page-desc">维护系统用户、角色、所属站点和可操作权限。root 默认拥有全部权限，其他用户可在这里单独开关。</p>
      </div>
      <div v-if="hasPermission" class="header-actions">
        <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchUsers">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
        <button class="btn btn-secondary" type="button" :disabled="exporting" @click="exportUsers">
          {{ exporting ? '导出中...' : '导出备份' }}
        </button>
        <label class="btn btn-secondary file-action" :class="{ disabled: importing }">
          <input type="file" accept="application/json,.json" :disabled="importing" @change="importUsers" />
          <span>{{ importing ? '导入中...' : '导入备份' }}</span>
        </label>
      </div>
    </div>

    <div v-if="!hasPermission" class="card-surface permission-card">
      <div class="permission-icon">!</div>
      <div class="permission-title">无权限访问</div>
      <div class="permission-desc">当前页面仅 root 系统管理员账号可访问。</div>
    </div>

    <template v-else>
      <div v-if="message.text" :class="['message-card', message.type]">{{ message.text }}</div>

      <section class="card-surface editor-card">
        <div class="section-head">
          <div>
            <div class="section-kicker">{{ form.id ? '编辑用户' : '新增用户' }}</div>
            <h3>{{ form.id ? `正在维护：${form.username}` : '创建系统账号' }}</h3>
          </div>
        </div>

        <div class="editor-layout">
          <div class="basic-form">
            <label class="form-field">
              <span>用户名</span>
              <input v-model.trim="form.username" type="text" placeholder="例如：supervisor1" />
            </label>

            <label class="form-field">
              <span>{{ form.id ? '新密码（不填则不修改）' : '初始密码' }}</span>
              <input v-model.trim="form.password" type="text" placeholder="默认可填写 123456" />
            </label>

            <label class="form-field">
              <span>角色</span>
              <select v-model="form.role" :disabled="isEditingRoot" @change="applyRoleDefaults">
                <option v-for="role in editableRoles" :key="role.value" :value="role.value">{{ role.label }}</option>
              </select>
              <small v-if="isEditingRoot" class="field-tip">root 是系统内置管理员，角色固定不可调整。</small>
            </label>

            <label class="form-field">
              <span>姓名</span>
              <input v-model.trim="form.real_name" type="text" placeholder="请输入姓名" />
            </label>

            <label class="form-field">
              <span>手机号</span>
              <input v-model.trim="form.phone" type="text" placeholder="请输入手机号" />
            </label>

            <label v-if="form.role === 'station_manager'" class="form-field">
              <span>所属站点</span>
              <select v-model="form.station_id">
                <option value="">请选择站点</option>
                <option v-for="station in stations" :key="station.id" :value="station.id">
                  {{ station.station_name }}
                </option>
              </select>
            </label>
          </div>

          <div class="permission-panel">
            <div class="permission-panel-head">
              <div>
                <strong>页面权限开关</strong>
                <p>{{ form.role === 'root' ? 'root 固定拥有全部权限，不需要单独配置。' : '按页面能力勾选，该用户即可获得对应查看或操作范围。' }}</p>
              </div>
            </div>

            <div class="permission-groups">
              <div v-for="group in groupedPermissions" :key="group.category" class="permission-group">
                <div class="permission-group-title">{{ group.category }}</div>
                <label v-for="permission in group.items" :key="permission.key" class="permission-item"
                  :class="{ disabled: form.role === 'root' || isPermissionDisabled(permission.key) }">
                  <input v-model="form.permissions[permission.key]" type="checkbox"
                    :disabled="form.role === 'root' || isPermissionDisabled(permission.key)"
                    @change="handlePermissionChange(permission.key)" />
                  <span>
                    <strong>{{ permission.name }}</strong>
                    <small>{{ permission.description }}</small>
                  </span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <div v-if="formError" class="form-error">{{ formError }}</div>

        <div class="form-actions">
          <button class="btn btn-secondary" type="button" @click="resetForm">清空</button>
          <button class="btn btn-primary" type="button" :disabled="saving" @click="saveUser">
            {{ saving ? '保存中...' : form.id ? '保存修改' : '新增用户' }}
          </button>
        </div>
      </section>

      <section class="card-surface table-card">
        <div class="section-head">
          <div>
            <div class="section-kicker">用户清单</div>
            <h3>共 {{ users.length }} 个用户</h3>
          </div>
        </div>

        <div class="table-wrap">
          <table class="user-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>角色</th>
                <th>姓名</th>
                <th>手机号</th>
                <th>所属站点</th>
                <th>权限概览</th>
                <th>创建时间</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="9" class="empty-cell">正在加载用户数据...</td>
              </tr>
              <tr v-else-if="!users.length">
                <td colspan="9" class="empty-cell">暂无用户数据。</td>
              </tr>
              <tr v-for="user in users" :key="user.id" :class="{ active: form.id === user.id }">
                <td>
                  <div class="table-title">{{ user.username }}</div>
                  <div class="table-sub">ID: {{ user.id }}</div>
                </td>
                <td>{{ roleLabel(user.role) }}</td>
                <td>{{ user.real_name || '-' }}</td>
                <td>{{ user.phone || '-' }}</td>
                <td>{{ user.station_name || '-' }}</td>
                <td>
                  <div class="permission-summary">
                    <span v-if="user.role === 'root'" class="permission-chip strong">全部权限</span>
                    <template v-else>
                      <span v-for="item in enabledPermissionLabels(user).slice(0, 3)" :key="item"
                        class="permission-chip">{{ item }}</span>
                      <span v-if="enabledPermissionLabels(user).length > 3" class="permission-chip muted">
                        +{{ enabledPermissionLabels(user).length - 3 }}
                      </span>
                    </template>
                  </div>
                </td>
                <td>{{ user.created_at || '-' }}</td>
                <td>{{ user.updated_at || '-' }}</td>
                <td>
                  <div class="row-actions">
                    <button class="btn btn-secondary btn-sm" type="button" @click="startEdit(user)">编辑</button>
                    <button class="btn btn-danger btn-sm" type="button"
                      :class="{ 'btn-locked': user.role === 'root' }"
                      :disabled="user.role === 'root' || deletingId === user.id"
                      :title="user.role === 'root' ? 'root 系统管理员账号不可删除' : '删除用户'"
                      @click="deleteUser(user)">
                      {{ user.role === 'root' ? '不可删除' : deletingId === user.id ? '删除中' : '删除' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onMounted, reactive, ref } from 'vue'

const currentUserId = localStorage.getItem('user_id') || ''
const currentRole = localStorage.getItem('user_role') || ''
let localPermissions = {}
try {
  localPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
} catch (error) {
  localPermissions = {}
}
const hasPermission = currentRole === 'root'

const users = ref([])
const stations = ref([])
const roles = ref([])
const permissions = ref([])
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const importing = ref(false)
const deletingId = ref(null)
const formError = ref('')
const message = reactive({
  text: '',
  type: 'info'
})

const exclusivePermissionGroups = [
  ['view_own_inspection_issues', 'view_all_inspection_issues'],
  ['view_own_inspection_records', 'view_all_inspection_records'],
  ['view_own_certificates', 'view_all_certificates']
]

const dependentPermissionMap = {
  edit_own_certificates: 'view_own_certificates'
}

const createEmptyForm = () => ({
  id: null,
  username: '',
  password: '',
  role: 'supervisor',
  real_name: '',
  phone: '',
  station_id: '',
  permissions: {}
})

const form = reactive(createEmptyForm())

const groupedPermissions = computed(() => {
  const groups = []
  permissions.value.forEach((permission) => {
    let group = groups.find((item) => item.category === permission.category)
    if (!group) {
      group = {
        category: permission.category,
        items: []
      }
      groups.push(group)
    }
    group.items.push(permission)
  })
  return groups
})

const editableRoles = computed(() => {
  if (form.id && form.role === 'root') {
    return roles.value.filter((item) => item.value === 'root')
  }
  return roles.value.filter((item) => item.value !== 'root')
})

const isEditingRoot = computed(() => Boolean(form.id && form.role === 'root'))

const roleLabel = (role) => {
  return roles.value.find((item) => item.value === role)?.label || role || '-'
}

const setMessage = (text, type = 'info') => {
  message.text = text
  message.type = type
}

const defaultPermissionValue = (permission, role) => {
  if (role === 'root') return true
  return Boolean(permission.defaults?.[role])
}

const buildDefaultPermissions = (role) => {
  const defaults = Object.fromEntries(permissions.value.map((permission) => [
    permission.key,
    defaultPermissionValue(permission, role)
  ]))
  return enforceExclusivePermissions(defaults, role)
}

const enforceExclusivePermissions = (permissionMap, role = form.role) => {
  const nextPermissions = { ...(permissionMap || {}) }
  exclusivePermissionGroups.forEach(([ownKey, allKey]) => {
    if (!nextPermissions[ownKey] || !nextPermissions[allKey]) return
    const allPermission = permissions.value.find((item) => item.key === allKey)
    const ownPermission = permissions.value.find((item) => item.key === ownKey)
    const preferAll = Boolean(allPermission?.defaults?.[role]) && !Boolean(ownPermission?.defaults?.[role])
    if (preferAll) {
      nextPermissions[ownKey] = false
    } else {
      nextPermissions[allKey] = false
    }
  })
  Object.entries(dependentPermissionMap).forEach(([childKey, parentKey]) => {
    if (nextPermissions[childKey] && !nextPermissions[parentKey]) {
      nextPermissions[childKey] = false
    }
  })
  return nextPermissions
}

const isPermissionDisabled = (permissionKey) => {
  const parentKey = dependentPermissionMap[permissionKey]
  return Boolean(parentKey && !form.permissions[parentKey])
}

const handlePermissionChange = (permissionKey) => {
  if (form.permissions[permissionKey]) {
    exclusivePermissionGroups.forEach((group) => {
      if (!group.includes(permissionKey)) return
      group
        .filter((key) => key !== permissionKey)
        .forEach((key) => {
          form.permissions[key] = false
        })
    })
  }

  Object.entries(dependentPermissionMap).forEach(([childKey, parentKey]) => {
    if (permissionKey === parentKey && !form.permissions[parentKey]) {
      form.permissions[childKey] = false
    }
    if (permissionKey === childKey && form.permissions[childKey] && !form.permissions[parentKey]) {
      form.permissions[childKey] = false
    }
  })
  form.permissions = enforceExclusivePermissions(form.permissions, form.role)
}

const applyRoleDefaults = () => {
  form.permissions = buildDefaultPermissions(form.role)
  if (form.role !== 'station_manager') form.station_id = ''
}

const resetForm = () => {
  Object.assign(form, createEmptyForm())
  form.permissions = buildDefaultPermissions(form.role)
  formError.value = ''
  setMessage('')
}

const startEdit = (user) => {
  Object.assign(form, {
    id: user.id,
    username: user.username || '',
    password: '',
    role: user.role || 'supervisor',
    real_name: user.real_name || '',
    phone: user.phone || '',
    station_id: user.station_id || '',
    permissions: enforceExclusivePermissions(user.permissions || {}, user.role || 'supervisor')
  })
  formError.value = ''
  setMessage(`已进入【${user.username}】编辑状态。`, 'info')
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const enabledPermissionLabels = (user) => {
  if (user.role === 'root') return permissions.value.map((item) => `${item.category} · ${item.name}`)
  return permissions.value
    .filter((permission) => Boolean(user.permissions?.[permission.key]))
    .map((permission) => `${permission.category} · ${permission.name}`)
}

const fetchUsers = async () => {
  if (!hasPermission) return

  try {
    loading.value = true
    const response = await axios.get('/api/management/users', {
      params: {
        user_id: currentUserId,
        _ts: Date.now()
      }
    })
    users.value = response.data?.users || []
    stations.value = response.data?.stations || []
    roles.value = response.data?.roles || []
    permissions.value = response.data?.permissions || []
    if (!form.id) form.permissions = buildDefaultPermissions(form.role)
  } catch (error) {
    setMessage(error?.response?.data?.error || '用户数据加载失败。', 'error')
  } finally {
    loading.value = false
  }
}

const getDownloadFileName = (disposition) => {
  const value = String(disposition || '')
  const matched = value.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i)
  const filename = decodeURIComponent(matched?.[1] || matched?.[2] || '')
  return filename || `ywddzx_users_backup_${new Date().toISOString().slice(0, 10)}.json`
}

const exportUsers = async () => {
  try {
    exporting.value = true
    setMessage('')
    const response = await axios.get('/api/management/users/export', {
      params: {
        user_id: currentUserId,
        _ts: Date.now()
      },
      responseType: 'blob'
    })
    const blobUrl = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = getDownloadFileName(response.headers['content-disposition'])
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(blobUrl)
    setMessage('用户数据备份文件已生成。', 'success')
  } catch (error) {
    setMessage('用户数据导出失败，请稍后重试。', 'error')
  } finally {
    exporting.value = false
  }
}

const importUsers = async (event) => {
  const input = event.target
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  if (!file.name.toLowerCase().endsWith('.json')) {
    setMessage('只能导入 JSON 格式的用户备份文件。', 'error')
    return
  }

  const confirmed = window.confirm('导入后会新增或更新备份中的非 root 用户及权限，不会覆盖内置 root。确定继续吗？')
  if (!confirmed) return

  try {
    importing.value = true
    setMessage('')
    const formData = new FormData()
    formData.append('user_id', currentUserId)
    formData.append('file', file)
    const response = await axios.post('/api/management/users/import', formData)
    setMessage(response.data?.message || '用户数据导入完成。', 'success')
    resetForm()
    await fetchUsers()
  } catch (error) {
    setMessage(error?.response?.data?.error || '用户数据导入失败。', 'error')
  } finally {
    importing.value = false
  }
}

const validateForm = () => {
  if (!form.username) return '请填写用户名。'
  if (!form.id && !form.password) return '请填写初始密码。'
  if (!form.role) return '请选择角色。'
  if (!form.real_name) return '请填写用户姓名。'
  if (form.role === 'station_manager' && !form.station_id) return '站点账号必须选择所属站点。'
  return ''
}

const saveUser = async () => {
  formError.value = validateForm()
  if (formError.value) return

  try {
    saving.value = true
    const payload = {
      user_id: currentUserId,
      username: form.username,
      password: form.password,
      role: form.role,
      real_name: form.real_name,
      phone: form.phone,
      station_id: form.station_id,
      permissions: form.permissions
    }
    payload.permissions = enforceExclusivePermissions(payload.permissions, form.role)
    const response = form.id
      ? await axios.put(`/api/management/users/${form.id}`, payload)
      : await axios.post('/api/management/users', payload)
    setMessage(response.data?.message || '用户已保存。', 'success')
    await fetchUsers()
    if (!form.id && response.data?.id) {
      const created = users.value.find((item) => String(item.id) === String(response.data.id))
      if (created) startEdit(created)
    }
  } catch (error) {
    formError.value = error?.response?.data?.error || '用户保存失败。'
  } finally {
    saving.value = false
  }
}

const deleteUser = async (user) => {
  const confirmed = window.confirm(`确定删除用户【${user.username}】吗？`)
  if (!confirmed) return

  try {
    deletingId.value = user.id
    const response = await axios.delete(`/api/management/users/${user.id}`, {
      data: {
        user_id: currentUserId
      }
    })
    setMessage(response.data?.message || '用户已删除。', 'success')
    if (form.id === user.id) resetForm()
    await fetchUsers()
  } catch (error) {
    setMessage(error?.response?.data?.error || '用户删除失败。', 'error')
  } finally {
    deletingId.value = null
  }
}

onMounted(fetchUsers)
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
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 12px;
}

.page-header h2,
.section-head h3 {
  margin: 0;
  color: #0f172a;
}

.page-header h2 {
  font-size: 34px;
}

.page-desc {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.header-actions,
.form-actions,
.row-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.editor-card,
.table-card {
  padding: 24px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.editor-layout {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.basic-form,
.permission-panel {
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  background: #f8fafc;
  padding: 18px;
}

.basic-form {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  background:
    linear-gradient(135deg, rgba(239, 246, 255, 0.94), rgba(248, 250, 252, 0.98)),
    #f8fafc;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-field span {
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.form-field input,
.form-field select {
  width: 100%;
  height: 42px;
  border: 1px solid #d7e0ea;
  border-radius: 12px;
  padding: 0 12px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
}

.form-field select:disabled {
  color: #64748b;
  background: #f1f5f9;
}

.field-tip {
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.permission-panel-head strong {
  display: block;
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.permission-panel-head p {
  margin: 5px 0 14px;
  color: #64748b;
  font-size: 13px;
}

.permission-groups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.permission-group {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
}

.permission-group-title {
  margin-bottom: 10px;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 900;
}

.permission-item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 0;
  border-top: 1px solid #eef2f7;
}

.permission-item:first-of-type {
  border-top: 0;
}

.permission-item input {
  margin-top: 3px;
}

.permission-item strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
}

.permission-item small {
  display: block;
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.permission-item.disabled {
  opacity: 0.62;
}

.table-wrap {
  overflow-x: auto;
}

.user-table {
  min-width: 1300px;
  width: 100%;
  border-collapse: collapse;
}

.user-table th,
.user-table td {
  padding: 13px 12px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  white-space: nowrap;
  vertical-align: middle;
  color: #0f172a;
  font-size: 13px;
}

.user-table th {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.user-table tr.active td {
  background: #eff6ff;
}

.table-title {
  font-size: 14px;
  font-weight: 900;
}

.table-sub {
  margin-top: 5px;
  color: #64748b;
  font-size: 12px;
}

.permission-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 320px;
}

.permission-chip {
  display: inline-flex;
  padding: 5px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
}

.permission-chip.strong {
  background: #ecfdf5;
  color: #15803d;
}

.permission-chip.muted {
  background: #f1f5f9;
  color: #64748b;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 22px 12px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  min-height: 38px;
  padding: 0 14px;
  border-radius: 11px;
  border: 1px solid #d7e0ea;
  background: #fff;
  color: #0f172a;
  font-size: 13px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
}

.btn-sm {
  min-height: 32px;
  padding: 0 10px;
  font-size: 12px;
}

.btn-primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.btn-danger {
  border-color: #fecaca;
  color: #dc2626;
}

.btn-locked {
  border-color: #cbd5e1;
  background: #f1f5f9;
  color: #94a3b8;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.file-action {
  position: relative;
  height: 38px;
}

.file-action input {
  display: none;
}

.file-action span {
  pointer-events: none;
}

.file-action.disabled {
  pointer-events: none;
  cursor: not-allowed;
  opacity: 0.6;
}

.form-error,
.message-card {
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.7;
}

.form-error,
.message-card.error {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #dc2626;
}

.message-card.success {
  border: 1px solid #bbf7d0;
  background: #ecfdf5;
  color: #15803d;
}

.message-card.info {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
}

.form-error {
  margin-top: 14px;
}

.form-actions {
  justify-content: flex-end;
  margin-top: 18px;
}

.permission-card {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 28px;
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

@media (max-width: 1280px) {
  .permission-groups {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .basic-form,
  .permission-groups {
    grid-template-columns: 1fr;
  }
}
</style>
