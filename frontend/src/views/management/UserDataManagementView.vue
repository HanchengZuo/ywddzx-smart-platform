<template>
  <div class="page-shell user-management-page">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">管理系统</div>
        <h2>用户数据管理</h2>
        <p class="page-desc">维护系统用户、角色、所属站点和可操作权限。root 默认拥有全部权限，其他用户可在这里单独开关。</p>
      </div>
      <div v-if="hasPermission" class="header-actions">
        <button class="btn btn-primary birthday-action-btn" type="button" :disabled="birthdayDialog.loading"
          @click="openBirthdayDialog">
          生日祝福管理
        </button>
        <button class="btn btn-primary" type="button" :disabled="loading" @click="openRolePermissionDialog">
          角色通用权限
        </button>
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
      <transition name="toast-fade">
        <div v-if="message.text" :class="['message-toast', message.type]">{{ message.text }}</div>
      </transition>

      <Teleport to="body"><dialog ref="userEditorDialog" class="user-editor-dialog" :class="{ 'permission-mode': editorMode === 'permissions' }" aria-labelledby="user-editor-title" @cancel.prevent="closeEditor" @click="closeEditorBackdrop">
      <section class="editor-card">
        <div class="section-head">
          <div>
            <div class="section-kicker">{{ editorMode === 'permissions' ? '个性化权限' : form.id ? '编辑用户' : '新增用户' }}</div>
            <h3 v-if="form.id" id="user-editor-title" class="editing-heading">
              <span>{{ editorMode === 'permissions' ? '配置权限' : '账号资料' }}</span>
              <strong>{{ form.username }}</strong>
            </h3>
            <h3 v-else id="user-editor-title">创建系统账号</h3>
          </div>
          <button class="btn btn-secondary btn-sm" type="button" :disabled="saving" @click="closeEditor">关闭</button>
        </div>

        <div class="editor-layout">
          <div v-if="editorMode === 'account'" class="basic-form">
            <p class="account-inheritance-note">{{ form.id ? '此处仅编辑账号资料，不修改个人权限。' : '初始密码由系统自动生成，创建成功后仅显示一次，首次登录必须修改。新用户默认继承角色通用权限。' }}</p>
            <label class="form-field">
              <span>用户名</span>
              <input v-model.trim="form.username" type="text" maxlength="80" autofocus placeholder="例如：supervisor1" />
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
              <input v-model.trim="form.phone" type="tel" maxlength="40" placeholder="请输入手机号" />
            </label>

            <div v-if="form.role === 'area_account'" class="station-picker-card area-account-region-card">
              <div class="station-picker-head">
                <div>
                  <strong>绑定片区</strong>
                  <p>片区归属用于隔离账号数据，不属于个人权限覆盖。</p>
                </div>
                <span>{{ areaAccountRegion || '未选择片区' }}</span>
              </div>

              <div class="station-picker-grid single">
                <label class="form-field">
                  <span>所属片区/归属地</span>
                  <select v-model="areaAccountRegion" @change="applyAreaAccountRegionScope">
                    <option value="">请选择片区/归属地</option>
                    <option v-for="region in stationRegionOptions" :key="region" :value="region">
                      {{ region }}
                    </option>
                  </select>
                </label>
              </div>
            </div>

            <div v-if="form.role === 'station_manager'" class="station-picker-card">
              <div class="station-picker-head">
                <div>
                  <strong>绑定站点</strong>
                  <p>为站点账号指定可访问的唯一站点数据范围。</p>
                </div>
                <span>{{ filteredStations.length }} 个可选站点</span>
              </div>

              <div class="station-picker-grid">
                <label class="form-field">
                  <span>所属片区/归属地</span>
                  <select v-model="stationRegionFilter">
                    <option value="">全部片区</option>
                    <option v-for="region in stationRegionOptions" :key="region" :value="region">
                      {{ region }}
                    </option>
                  </select>
                </label>

                <label class="form-field">
                  <span>搜索站点</span>
                  <input v-model.trim="stationKeyword" type="text" placeholder="输入站名、HOS编码或片区" />
                </label>

                <label class="form-field station-select-field">
                  <span>所属站点</span>
                  <select v-model="form.station_id">
                    <option value="">请选择站点</option>
                    <option v-for="station in filteredStations" :key="station.id" :value="station.id">
                      {{ station.region || '未填写片区' }} · {{ station.station_name }}{{ station.hos_station_code ? ` · ${station.hos_station_code}` : '' }}
                    </option>
                  </select>
                </label>
              </div>
            </div>
          </div>

          <div v-if="editorMode === 'permissions'" class="permission-panel">
            <div class="permission-panel-head">
              <div>
                <strong>页面权限开关</strong>
                <p>{{ form.role === 'root' ? 'root 固定拥有全部权限，不需要单独配置。' : '未单独设置的权限随角色通用权限变化；单独开启或关闭优先于角色设置，仍受依赖规则约束。' }}</p>
              </div>
              <span class="permission-overview">{{ roleLabel(form.role) }} · {{ enabledPermissionCount }} / {{ permissions.length }} 项已开启</span>
            </div>

            <div class="permission-workspace">
              <PermissionCategoryNav v-model:keyword="permissionKeyword" :groups="filteredPermissionGroups"
                :permissions="form.permissions" :role="form.role" :active="activePermissionCategory"
                controls="user-permission-detail" @select="selectPermissionCategory" />
            <div id="user-permission-detail" ref="permissionDetailRef" class="permission-groups user-permission-groups">
              <div v-for="group in visiblePermissionGroups" :key="group.category" class="permission-group">
                <div class="permission-group-title">
                  <span>{{ group.category }}</span>
                  <em v-if="group.hasScopedLayout">先定范围</em>
                </div>

                <div v-if="group.readonlyItems.length" class="permission-section readonly-section">
                  <div class="permission-section-label">通用规则</div>
                  <label v-for="permission in group.readonlyItems" :key="permission.key"
                    class="permission-item permission-item-readonly disabled">
                    <input type="checkbox" checked disabled />
                    <span>
                      <strong>{{ permission.name }}<em>只读展示</em></strong>
                      <small>{{ permission.description }}</small>
                    </span>
                  </label>
                </div>

                <div v-if="group.scopeItems.length" class="permission-section">
                  <div class="permission-section-label">1 数据范围</div>
                  <UserPermissionToggle v-for="permission in group.scopeItems" :key="permission.key" :permission="permission"
                    :mode="personalPermissionMode(permission.key)" :enabled="Boolean(form.permissions[permission.key])"
                    :inherited="Boolean(buildDefaultPermissions(form.role)[permission.key])" :disabled="form.role === 'root'"
                    @change="setPersonalPermission(permission.key, $event)" />
                </div>

                <div v-if="group.actionItems.length" class="permission-section">
                  <div class="permission-section-label">2 范围内操作</div>
                  <UserPermissionToggle v-for="permission in group.actionItems" :key="permission.key" :permission="permission"
                    :mode="personalPermissionMode(permission.key)" :enabled="Boolean(form.permissions[permission.key])"
                    :inherited="Boolean(buildDefaultPermissions(form.role)[permission.key])" :disabled="form.role === 'root'"
                    @change="setPersonalPermission(permission.key, $event)" />
                </div>

                <div v-if="group.regularItems.length" class="permission-section">
                  <div v-if="group.hasScopedLayout" class="permission-section-label">其他权限</div>
                  <UserPermissionToggle v-for="permission in group.regularItems" :key="permission.key" :permission="permission"
                    :mode="personalPermissionMode(permission.key)" :enabled="Boolean(form.permissions[permission.key])"
                    :inherited="Boolean(buildDefaultPermissions(form.role)[permission.key])" :disabled="form.role === 'root'"
                    @change="setPersonalPermission(permission.key, $event)" />
                </div>

                <div v-if="inspectionScopeConfigForCategory(group.category)" class="inspection-scope-panel"
                  :class="{ disabled: isInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey) }">
                  <div class="inspection-scope-head">
                    <div>
                      <strong>{{ inspectionScopeConfigForCategory(group.category).title }}</strong>
                      <p>{{ inspectionScopeConfigForCategory(group.category).description }}</p>
                    </div>
                    <span>{{ selectedInspectionScopeSummary(inspectionScopeConfigForCategory(group.category).permissionKey) }}</span>
                  </div>

                  <label class="scope-inheritance"><input type="checkbox" :checked="scopeInherited[inspectionScopeConfigForCategory(group.category).permissionKey]" @change="setScopeInheritance(inspectionScopeConfigForCategory(group.category).permissionKey, $event.target.checked)" />沿用角色通用检查表范围</label>
                  <div class="inspection-scope-actions">
                    <button class="btn btn-secondary btn-sm" type="button"
                      :disabled="isInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey) || !hasRoleDefaultInspectionScope(form.role)"
                      @click="applyRoleDefaultScope(inspectionScopeConfigForCategory(group.category).permissionKey)">
                      {{ roleDefaultScopeActionLabel }}
                    </button>
                    <button class="btn btn-secondary btn-sm" type="button"
                      :disabled="isInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey)"
                      @click="selectAllInspectionTables(inspectionScopeConfigForCategory(group.category).permissionKey)">
                      全选
                    </button>
                    <button class="btn btn-secondary btn-sm" type="button"
                      :disabled="isInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey)"
                      @click="clearInspectionTableScope(inspectionScopeConfigForCategory(group.category).permissionKey)">
                      清空
                    </button>
                  </div>

                  <div class="inspection-scope-grid">
                    <label v-for="table in inspectionTables" :key="`${group.category}-${table.id}`"
                      class="inspection-scope-item"
                      :class="{
                        checked: isInspectionTableSelected(inspectionScopeConfigForCategory(group.category).permissionKey, table.id),
                        disabled: isInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey)
                      }">
                      <input type="checkbox"
                        :checked="isInspectionTableSelected(inspectionScopeConfigForCategory(group.category).permissionKey, table.id)"
                        :disabled="isInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey)"
                        @change="toggleInspectionTableScope(inspectionScopeConfigForCategory(group.category).permissionKey, table.id, $event.target.checked)" />
                      <span>
                        <strong>{{ table.table_name }}</strong>
                        <small>
                          {{ table.checklist_mode_label || '检查表' }}
                          <em v-for="label in table.default_scope_role_labels || []" :key="label">
                            {{ defaultScopeBadgeLabel(label) }}
                          </em>
                        </small>
                      </span>
                    </label>
                  </div>
                </div>

                <div v-if="form.role !== 'area_account' && stationRegionScopeConfigForCategory(group.category)" class="inspection-scope-panel region-scope-panel"
                  :class="{ disabled: isStationRegionScopeDisabled(stationRegionScopeConfigForCategory(group.category).permissionKey) }">
                  <div class="inspection-scope-head">
                    <div>
                      <strong>{{ stationRegionScopeConfigForCategory(group.category).title }}</strong>
                      <p>{{ stationRegionScopeConfigForCategory(group.category).description }}</p>
                    </div>
                    <span>{{ selectedStationRegionScopeSummary(stationRegionScopeConfigForCategory(group.category).permissionKey) }}</span>
                  </div>

                  <label class="scope-inheritance"><input type="checkbox" :checked="scopeInherited[stationRegionScopeConfigForCategory(group.category).permissionKey]" @change="setScopeInheritance(stationRegionScopeConfigForCategory(group.category).permissionKey, $event.target.checked)" />沿用角色通用片区范围</label>
                  <div class="inspection-scope-actions">
                    <button class="btn btn-secondary btn-sm" type="button"
                      :disabled="isStationRegionScopeDisabled(stationRegionScopeConfigForCategory(group.category).permissionKey)"
                      @click="selectAllStationRegions(stationRegionScopeConfigForCategory(group.category).permissionKey)">
                      全选片区
                    </button>
                    <button class="btn btn-secondary btn-sm" type="button"
                      :disabled="isStationRegionScopeDisabled(stationRegionScopeConfigForCategory(group.category).permissionKey)"
                      @click="clearStationRegionScope(stationRegionScopeConfigForCategory(group.category).permissionKey)">
                      清空
                    </button>
                  </div>

                  <div class="inspection-scope-grid region-scope-grid">
                    <label v-for="region in stationRegionOptions" :key="`${group.category}-${region}`"
                      class="inspection-scope-item region-scope-item"
                      :class="{
                        checked: isStationRegionSelected(stationRegionScopeConfigForCategory(group.category).permissionKey, region),
                        disabled: isStationRegionScopeDisabled(stationRegionScopeConfigForCategory(group.category).permissionKey)
                      }">
                      <input type="checkbox"
                        :checked="isStationRegionSelected(stationRegionScopeConfigForCategory(group.category).permissionKey, region)"
                        :disabled="isStationRegionScopeDisabled(stationRegionScopeConfigForCategory(group.category).permissionKey)"
                        @change="toggleStationRegionScope(stationRegionScopeConfigForCategory(group.category).permissionKey, region, $event.target.checked)" />
                      <span>
                        <strong>{{ region }}</strong>
                        <small>{{ stationCountByRegion(region) }} 个站点</small>
                      </span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
            </div>
          </div>
        </div>

        <div v-if="formError" class="form-error">{{ formError }}</div>

        <div class="form-actions">
          <button class="btn btn-secondary" type="button" :disabled="saving" @click="closeEditor">取消</button>
          <button class="btn btn-primary" type="button" :disabled="saving" @click="saveUser">
            {{ saving ? '保存中...' : editorMode === 'permissions' ? '保存个人权限' : form.id ? '保存资料' : '创建并生成初始密码' }}
          </button>
        </div>
      </section></dialog></Teleport>

      <section class="card-surface table-card">
        <UserDirectory :users="users" :roles="roles" :catalog="permissions" :loading="loading" :editing-id="editorOpen ? form.id : null"
          :resetting="resetPasswordDialog.loading" :deleting-id="deletingId" @create="openCreateUser"
          @edit="startEdit" @reset="openPasswordReset" @delete="deleteUser" @permissions="openPermissionDetails" />
      </section>
    </template>

    <AccountPasswordResetDialog :visible="resetPasswordDialog.visible" :loading="resetPasswordDialog.loading"
      :target="resetPasswordDialog.target" :credential="resetPasswordDialog.credential" :error="resetPasswordDialog.error"
      @confirm="resetUserPassword" @close="closePasswordReset" />
    <UserPermissionDetailsDialog :user="permissionDetailsUser" :catalog="permissions" :roles="roles" :tables="inspectionTables"
      :role-overrides="rolePermissionOverrides[permissionDetailsUser?.role] || {}" @close="permissionDetailsId = null" @edit="startPermissionEdit" />

    <div v-if="birthdayDialog.visible" class="modal-backdrop birthday-modal-backdrop" @click.self="closeBirthdayDialog">
      <div class="birthday-management-modal card-surface">
        <div class="modal-head">
          <div>
            <div class="section-kicker">员工关怀</div>
            <h3>生日祝福管理</h3>
            <p>维护用户生日信息。生日当天用户登录后，会看到生日祝福动效和工作感谢时间。</p>
          </div>
          <button class="close-btn" type="button" @click="closeBirthdayDialog">×</button>
        </div>

        <div class="birthday-toolbar">
          <div>
            <strong>当前名单 {{ birthdayRows.length }} 人</strong>
            <span>测试按钮不会修改生日日期，只用于 root 预览正式登录动效。</span>
          </div>
          <button class="btn btn-secondary btn-sm" type="button" :disabled="birthdayDialog.loading"
            @click="fetchBirthdays">
            {{ birthdayDialog.loading ? '刷新中...' : '刷新生日信息' }}
          </button>
        </div>

        <div class="birthday-table-wrap">
          <table class="birthday-table">
            <thead>
              <tr>
                <th>姓名</th>
                <th>生日月份</th>
                <th>生日日期</th>
                <th>匹配账号</th>
                <th>最后更新</th>
                <th>测试</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="birthdayDialog.loading">
                <td colspan="6" class="empty-cell">正在加载生日信息...</td>
              </tr>
              <tr v-else-if="!birthdayRows.length">
                <td colspan="6" class="empty-cell">暂无生日信息。</td>
              </tr>
              <template v-else>
                <tr v-for="row in birthdayRows" :key="row.id || row.real_name">
                  <td>
                    <div class="birthday-name-cell">
                      <strong>{{ row.real_name }}</strong>
                      <span>{{ formatBirthdayLabel(row) }}</span>
                    </div>
                  </td>
                  <td>
                    <select v-model.number="row.birthday_month" class="birthday-select" @change="normalizeBirthdayDay(row)">
                      <option v-for="month in birthdayMonthOptions" :key="month" :value="month">{{ month }} 月</option>
                    </select>
                  </td>
                  <td>
                    <select v-model.number="row.birthday_day" class="birthday-select">
                      <option v-for="day in birthdayDayOptions(row.birthday_month)" :key="day" :value="day">{{ day }} 日</option>
                    </select>
                  </td>
                  <td>
                    <div v-if="row.matched_username" class="birthday-user-match">
                      <strong>{{ row.matched_username }}</strong>
                      <span>{{ roleLabel(row.matched_role) }}{{ row.matched_phone ? ` · ${row.matched_phone}` : '' }}</span>
                    </div>
                    <span v-else class="birthday-unmatched">暂未匹配系统账号</span>
                  </td>
                  <td>{{ row.updated_at || '-' }}</td>
                  <td>
                    <button class="btn btn-secondary btn-sm" type="button" @click="previewBirthdayBlessing(row)">
                      测试动效
                    </button>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <div v-if="birthdayDialog.error" class="form-error">{{ birthdayDialog.error }}</div>
        <div class="modal-actions">
          <button class="btn btn-secondary" type="button" @click="closeBirthdayDialog">取消</button>
          <button class="btn btn-primary" type="button" :disabled="birthdayDialog.saving" @click="saveBirthdays">
            {{ birthdayDialog.saving ? '保存中...' : '保存生日信息' }}
          </button>
        </div>
      </div>
    </div>

    <Teleport to="body">
    <div v-if="rolePermissionDialog.visible" class="modal-backdrop" @click.self="closeRolePermissionDialog">
      <div class="role-permission-modal card-surface">
        <div class="modal-head">
          <div>
            <div class="section-kicker">角色通用权限</div>
            <h3>配置角色默认权限模板</h3>
            <p>这里保存的是角色通用权限。已有个性化权限的用户仍按个人配置生效，不会被角色模板覆盖。</p>
          </div>
          <button class="close-btn" type="button" @click="closeRolePermissionDialog">×</button>
        </div>

        <div class="role-template-toolbar">
          <label class="form-field">
            <span>选择角色</span>
            <select v-model="rolePermissionDialog.role" @change="loadRoleTemplatePermissions">
              <option v-for="role in roleTemplateRoles" :key="role.value" :value="role.value">{{ role.label }}</option>
            </select>
          </label>
          <div class="role-template-note">
            <strong>{{ roleLabel(rolePermissionDialog.role) }}</strong>
            <span>这里统一配置页面权限、检查表范围和片区范围；单个用户若另有个性化配置，会优先生效。</span>
          </div>
        </div>

        <div class="permission-workspace role-template-workspace">
          <PermissionCategoryNav v-model:keyword="rolePermissionKeyword" :groups="filteredRolePermissionGroups"
            :permissions="rolePermissionDialog.permissions" :role="rolePermissionDialog.role" :active="activeRolePermissionCategory"
            controls="role-permission-detail" @select="selectRolePermissionCategory" />
        <div id="role-permission-detail" ref="rolePermissionDetailRef" class="permission-groups user-permission-groups role-template-groups">
          <div v-for="group in visibleRolePermissionGroups" :key="`role-${group.category}`" class="permission-group">
            <div class="permission-group-title">
              <span>{{ group.category }}</span>
              <em v-if="group.hasScopedLayout">角色默认</em>
            </div>

            <div v-if="group.scopeItems.length" class="permission-section">
              <div class="permission-section-label">1 数据范围</div>
              <label v-for="permission in group.scopeItems" :key="permission.key" class="permission-item permission-item-scope"
                :class="{ disabled: isRolePermissionDisabled(permission.key) }">
                <input v-model="rolePermissionDialog.permissions[permission.key]" type="checkbox"
                  :disabled="isRolePermissionDisabled(permission.key)"
                  @change="handleRolePermissionChange(permission.key)" />
                <span>
                  <strong>{{ permission.name }}</strong>
                  <small>{{ permission.description }}</small>
                </span>
              </label>
            </div>

            <div v-if="group.actionItems.length" class="permission-section">
              <div class="permission-section-label">2 范围内操作</div>
              <label v-for="permission in group.actionItems" :key="permission.key" class="permission-item permission-item-action"
                :class="{ disabled: isRolePermissionDisabled(permission.key) }">
                <input v-model="rolePermissionDialog.permissions[permission.key]" type="checkbox"
                  :disabled="isRolePermissionDisabled(permission.key)"
                  @change="handleRolePermissionChange(permission.key)" />
                <span>
                  <strong>{{ permission.name }}</strong>
                  <small>{{ permission.description }}</small>
                </span>
              </label>
            </div>

            <div v-if="group.regularItems.length" class="permission-section">
              <div v-if="group.hasScopedLayout" class="permission-section-label">其他权限</div>
              <label v-for="permission in group.regularItems" :key="permission.key" class="permission-item"
                :class="{ disabled: isRolePermissionDisabled(permission.key) }">
                <input v-model="rolePermissionDialog.permissions[permission.key]" type="checkbox"
                  :disabled="isRolePermissionDisabled(permission.key)"
                  @change="handleRolePermissionChange(permission.key)" />
                <span>
                  <strong>{{ permission.name }}</strong>
                  <small>{{ permission.description }}</small>
                </span>
              </label>
            </div>

            <div v-if="inspectionScopeConfigForCategory(group.category)" class="inspection-scope-panel role-scope-panel"
              :class="{ disabled: isRoleInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey) }">
              <div class="inspection-scope-head">
                <div>
                  <strong>{{ inspectionScopeConfigForCategory(group.category).title }}</strong>
                  <p>{{ inspectionScopeConfigForCategory(group.category).description }}</p>
                </div>
                <span>{{ selectedRoleInspectionScopeSummary(inspectionScopeConfigForCategory(group.category).permissionKey) }}</span>
              </div>

              <div class="inspection-scope-actions">
                <button class="btn btn-secondary btn-sm" type="button"
                  :disabled="isRoleInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey) || !hasRoleDefaultInspectionScope(rolePermissionDialog.role)"
                  @click="applyRoleDefaultScopeForTemplate(inspectionScopeConfigForCategory(group.category).permissionKey)">
                  {{ roleTemplateDefaultScopeActionLabel }}
                </button>
                <button class="btn btn-secondary btn-sm" type="button"
                  :disabled="isRoleInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey)"
                  @click="selectAllRoleInspectionTables(inspectionScopeConfigForCategory(group.category).permissionKey)">
                  全选
                </button>
                <button class="btn btn-secondary btn-sm" type="button"
                  :disabled="isRoleInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey)"
                  @click="clearRoleInspectionTableScope(inspectionScopeConfigForCategory(group.category).permissionKey)">
                  清空
                </button>
              </div>

              <div class="inspection-scope-grid">
                <label v-for="table in inspectionTables" :key="`role-${group.category}-${table.id}`"
                  class="inspection-scope-item"
                  :class="{
                    checked: isRoleInspectionTableSelected(inspectionScopeConfigForCategory(group.category).permissionKey, table.id),
                    disabled: isRoleInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey)
                  }">
                  <input type="checkbox"
                    :checked="isRoleInspectionTableSelected(inspectionScopeConfigForCategory(group.category).permissionKey, table.id)"
                    :disabled="isRoleInspectionScopeDisabled(inspectionScopeConfigForCategory(group.category).permissionKey)"
                    @change="toggleRoleInspectionTableScope(inspectionScopeConfigForCategory(group.category).permissionKey, table.id, $event.target.checked)" />
                  <span>
                    <strong>{{ table.table_name }}</strong>
                    <small>
                      {{ table.checklist_mode_label || '检查表' }}
                      <em v-for="label in table.default_scope_role_labels || []" :key="label">
                        {{ defaultScopeBadgeLabel(label) }}
                      </em>
                    </small>
                  </span>
                </label>
              </div>
            </div>

            <div v-if="stationRegionScopeConfigForCategory(group.category)" class="inspection-scope-panel region-scope-panel role-scope-panel"
              :class="{ disabled: isRoleStationRegionScopeDisabled(stationRegionScopeConfigForCategory(group.category).permissionKey) }">
              <div class="inspection-scope-head">
                <div>
                  <strong>{{ stationRegionScopeConfigForCategory(group.category).title }}</strong>
                  <p>{{ stationRegionScopeConfigForCategory(group.category).description }}</p>
                </div>
                <span>{{ selectedRoleStationRegionScopeSummary(stationRegionScopeConfigForCategory(group.category).permissionKey) }}</span>
              </div>

              <div class="inspection-scope-actions">
                <button class="btn btn-secondary btn-sm" type="button"
                  :disabled="isRoleStationRegionScopeDisabled(stationRegionScopeConfigForCategory(group.category).permissionKey)"
                  @click="selectAllRoleStationRegions(stationRegionScopeConfigForCategory(group.category).permissionKey)">
                  全选片区
                </button>
                <button class="btn btn-secondary btn-sm" type="button"
                  :disabled="isRoleStationRegionScopeDisabled(stationRegionScopeConfigForCategory(group.category).permissionKey)"
                  @click="clearRoleStationRegionScope(stationRegionScopeConfigForCategory(group.category).permissionKey)">
                  清空
                </button>
              </div>

              <div class="inspection-scope-grid region-scope-grid">
                <label v-for="region in stationRegionOptions" :key="`role-${group.category}-${region}`"
                  class="inspection-scope-item region-scope-item"
                  :class="{
                    checked: isRoleStationRegionSelected(stationRegionScopeConfigForCategory(group.category).permissionKey, region),
                    disabled: isRoleStationRegionScopeDisabled(stationRegionScopeConfigForCategory(group.category).permissionKey)
                  }">
                  <input type="checkbox"
                    :checked="isRoleStationRegionSelected(stationRegionScopeConfigForCategory(group.category).permissionKey, region)"
                    :disabled="isRoleStationRegionScopeDisabled(stationRegionScopeConfigForCategory(group.category).permissionKey)"
                    @change="toggleRoleStationRegionScope(stationRegionScopeConfigForCategory(group.category).permissionKey, region, $event.target.checked)" />
                  <span>
                    <strong>{{ region }}</strong>
                    <small>{{ stationCountByRegion(region) }} 个站点</small>
                  </span>
                </label>
              </div>
            </div>
          </div>
        </div>

        </div>
        <div v-if="rolePermissionDialog.error" class="form-error">{{ rolePermissionDialog.error }}</div>
        <div class="modal-actions">
          <button class="btn btn-secondary" type="button" @click="resetRoleTemplateToSystemDefaults">
            恢复系统默认
          </button>
          <button class="btn btn-secondary" type="button" @click="closeRolePermissionDialog">取消</button>
          <button class="btn btn-primary" type="button" :disabled="rolePermissionDialog.saving" @click="saveRolePermissions">
            {{ rolePermissionDialog.saving ? '保存中...' : '保存角色模板' }}
          </button>
        </div>
      </div>
    </div>
    </Teleport>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { clearAuthSession } from '@/utils/authSession'
import AccountPasswordResetDialog from '@/components/AccountPasswordResetDialog.vue'
import UserDirectory from '@/components/UserDirectory.vue'
import UserPermissionDetailsDialog from '@/components/UserPermissionDetailsDialog.vue'
import PermissionCategoryNav from '@/components/PermissionCategoryNav.vue'
import UserPermissionToggle from '@/components/UserPermissionToggle.vue'
import { filterPermissionGroups, resolvePermissionCategory, sortPermissionGroups } from '@/utils/permissionPanel'
import { isSupervisorRole } from '@/utils/roles'
import { changePermissionOverride, personalScopeDraft, previewPersonalPermissions } from '@/utils/userDirectory'

const currentUserId = localStorage.getItem('user_id') || ''
const currentRole = localStorage.getItem('user_role') || ''
const hasPermission = currentRole === 'root'

const users = ref([])
const stations = ref([])
const inspectionTables = ref([])
const roleDefaultInspectionTableScopeIds = ref({})
const rolePermissionOverrides = ref({})
const roleEffectivePermissions = ref({})
const roleInspectionTableScopeIds = ref({})
const roleStationRegionScopeValues = ref({})
const stationRegionFilter = ref('')
const stationKeyword = ref('')
const areaAccountRegion = ref('')
const roles = ref([])
const permissions = ref([])
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const importing = ref(false)
const deletingId = ref(null)
const resetPasswordDialog = reactive({ visible: false, loading: false, target: null, credential: null, error: '' })
const permissionKeyword = ref('')
const activePermissionCategory = ref('')
const permissionDetailRef = ref(null)
const rolePermissionKeyword = ref('')
const activeRolePermissionCategory = ref('')
const rolePermissionDetailRef = ref(null)
const editorOpen = ref(false)
const editorMode = ref('account')
const userEditorDialog = ref(null)
const scopeInherited = reactive({})
watch(editorOpen, async open => {
  await nextTick()
  if (open && !userEditorDialog.value?.open) userEditorDialog.value?.showModal()
  if (!open) userEditorDialog.value?.close()
})
const permissionDetailsId = ref(null)
const permissionDetailsUser = computed(() => users.value.find(user => user.id === permissionDetailsId.value) || null)
const openPermissionDetails = user => { permissionDetailsId.value = user.id }
const selectPermissionCategory = (category) => { activePermissionCategory.value = category }
const selectRolePermissionCategory = (category) => { activeRolePermissionCategory.value = category }
watch(activePermissionCategory, () => { if (permissionDetailRef.value) permissionDetailRef.value.scrollTop = 0 }, { flush: 'post' })
watch(activeRolePermissionCategory, () => { if (rolePermissionDetailRef.value) rolePermissionDetailRef.value.scrollTop = 0 }, { flush: 'post' })
const formError = ref('')
const message = reactive({
  text: '',
  type: 'info'
})
let messageTimer = null
const birthdayRows = ref([])
const birthdayDialog = reactive({
  visible: false,
  loading: false,
  saving: false,
  error: ''
})
const birthdayMonthOptions = Array.from({ length: 12 }, (_, index) => index + 1)


const exclusivePermissionGroups = [
  ['view_own_inspection_issues', 'limit_issue_station_region_scope', 'view_all_inspection_issues'],
  ['view_own_inspection_records', 'limit_record_station_region_scope', 'view_all_inspection_records'],
  ['view_own_certificates', 'limit_certificate_station_region_scope', 'view_all_certificates']
]

const dependentPermissionMap = {
  edit_own_certificates: 'view_own_certificates',
  adjust_station_scores: 'view_station_scores',
  reset_station_account_password: 'manage_stations',
  generate_inspection_reports: 'view_inspection_reports'
}

const anyDependentPermissionMap = {
  edit_inspection_issues: ['view_all_inspection_issues'],
  delete_inspection_issues: ['view_all_inspection_issues'],
  audit_inspection_issues: ['view_all_inspection_issues'],
  change_issue_inspector: ['view_all_inspection_issues'],
  delete_inspection_records: ['view_all_inspection_records'],
  reset_inspection_signature: ['view_all_inspection_records']
}

const inspectionTableScopePermissionKeys = [
  'limit_issue_inspection_table_scope',
  'limit_record_inspection_table_scope',
  'limit_plan_inspection_table_scope'
]

const stationRegionScopePermissionKeys = [
  'limit_issue_station_region_scope',
  'limit_record_station_region_scope',
  'limit_plan_station_region_scope',
  'limit_certificate_station_region_scope'
]

const inspectionScopeConfigs = {
  '巡检问题列表': {
    permissionKey: 'limit_issue_inspection_table_scope',
    title: '巡检问题检查表范围',
    description: '启用后，限制巡检问题列表和亮点列表可见的检查表范围；亮点沿用问题审核权限。'
  },
  '巡检记录': {
    permissionKey: 'limit_record_inspection_table_scope',
    title: '巡检记录检查表范围',
    description: '启用后，只限制巡检记录能看到哪些检查表的记录。'
  },
  '巡检计划': {
    permissionKey: 'limit_plan_inspection_table_scope',
    title: '巡检计划检查表范围',
    description: '启用后，只限制巡检计划能看到哪些检查表的计划。'
  }
}

const stationRegionScopeConfigs = {
  '巡检问题列表': {
    permissionKey: 'limit_issue_station_region_scope',
    title: '巡检问题片区站点范围',
    description: '选择“查看片区站点数据”后，在这里指定可查看哪些片区/归属地的站点问题。'
  },
  '巡检记录': {
    permissionKey: 'limit_record_station_region_scope',
    title: '巡检记录片区站点范围',
    description: '选择“查看片区站点数据”后，在这里指定可查看哪些片区/归属地的站点记录。'
  },
  '巡检计划': {
    permissionKey: 'limit_plan_station_region_scope',
    title: '巡检计划片区站点范围',
    description: '选择“查看片区站点数据”后，只统计和展示选定片区/归属地内站点的巡检计划。'
  },
  '站点证照有效期管理': {
    permissionKey: 'limit_certificate_station_region_scope',
    title: '证照管理片区站点范围',
    description: '选择“查看片区站点数据”后，只展示选定片区/归属地内站点的证照有效期和提醒。'
  }
}

function createEmptyInspectionScopeMap() {
  return Object.fromEntries(inspectionTableScopePermissionKeys.map((key) => [key, []]))
}

function createEmptyStationRegionScopeMap() {
  return Object.fromEntries(stationRegionScopePermissionKeys.map((key) => [key, []]))
}

const normalizeInspectionScopeMap = (value) => {
  const emptyMap = createEmptyInspectionScopeMap()
  if (Array.isArray(value)) {
    return Object.fromEntries(inspectionTableScopePermissionKeys.map((key) => [key, [...value]]))
  }
  if (!value || typeof value !== 'object') return emptyMap
  return Object.fromEntries(inspectionTableScopePermissionKeys.map((key) => [
    key,
    Array.isArray(value[key]) ? [...value[key]] : []
  ]))
}

const normalizeStationRegionScopeMap = (value) => {
  const emptyMap = createEmptyStationRegionScopeMap()
  if (Array.isArray(value)) {
    return Object.fromEntries(stationRegionScopePermissionKeys.map((key) => [key, [...value]]))
  }
  if (!value || typeof value !== 'object') return emptyMap
  return Object.fromEntries(stationRegionScopePermissionKeys.map((key) => [
    key,
    Array.isArray(value[key]) ? [...value[key]] : []
  ]))
}

const scopedPermissionLayouts = {
  '巡检问题列表': {
    scopeKeys: ['view_own_inspection_issues', 'limit_issue_station_region_scope', 'view_all_inspection_issues', 'limit_issue_inspection_table_scope'],
    actionKeys: ['edit_inspection_issues', 'delete_inspection_issues', 'audit_inspection_issues', 'change_issue_inspector'],
    readonlyItems: [
      {
        key: 'creator_issue_controls',
        name: '编辑/删除自己提交的问题',
        description: '通用规则：督导组成员提交的问题，在站点尚未整改反馈前，可自动维护自己的问题描述和照片。'
      }
    ]
  },
  '巡检记录': {
    scopeKeys: ['view_own_inspection_records', 'limit_record_station_region_scope', 'view_all_inspection_records', 'limit_record_inspection_table_scope'],
    actionKeys: ['delete_inspection_records', 'reset_inspection_signature']
  },
  '巡检计划': {
    scopeKeys: ['view_inspection_plans', 'limit_plan_inspection_table_scope', 'limit_plan_station_region_scope'],
    actionKeys: ['manage_inspection_plans']
  },
  '站点证照有效期管理': {
    scopeKeys: ['view_own_certificates', 'limit_certificate_station_region_scope', 'view_all_certificates'],
    actionKeys: ['edit_own_certificates']
  }
}

const createEmptyForm = () => ({
  id: null,
  username: '',
  role: 'supervisor',
  real_name: '',
  phone: '',
  station_id: '',
  inspection_table_scope_ids: createEmptyInspectionScopeMap(),
  station_region_scope_values: createEmptyStationRegionScopeMap(),
  permissions: {},
  permission_overrides: {}
})

const form = reactive(createEmptyForm())

const rolePermissionDialog = reactive({
  visible: false,
  role: 'supervisor',
  permissions: {},
  inspection_table_scope_ids: createEmptyInspectionScopeMap(),
  station_region_scope_values: createEmptyStationRegionScopeMap(),
  saving: false,
  error: ''
})

const buildPermissionGroupsFor = (role, includeReadonlyItems = true) => {
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

  return sortPermissionGroups(groups).map((group) => {
    const layout = scopedPermissionLayouts[group.category]
    if (!layout) {
      return {
        ...group,
        hasScopedLayout: false,
        readonlyItems: [],
        scopeItems: [],
        actionItems: [],
        regularItems: group.items
      }
    }

    const scopeKeys = new Set(layout.scopeKeys || [])
    const actionKeys = new Set(layout.actionKeys || [])
    const readonlyItems = includeReadonlyItems && isSupervisorRole(role) ? (layout.readonlyItems || []) : []
    return {
      ...group,
      hasScopedLayout: true,
      readonlyItems,
      scopeItems: group.items.filter((item) => scopeKeys.has(item.key)),
      actionItems: group.items.filter((item) => actionKeys.has(item.key)),
      regularItems: group.items.filter((item) => !scopeKeys.has(item.key) && !actionKeys.has(item.key))
    }
  })
}

const groupedPermissions = computed(() => buildPermissionGroupsFor(form.role, true))
const filteredPermissionGroups = computed(() => filterPermissionGroups(groupedPermissions.value, permissionKeyword.value))
const visiblePermissionGroups = computed(() => filteredPermissionGroups.value.filter((group) => group.category === activePermissionCategory.value))
const enabledPermissionCount = computed(() => permissions.value.filter((item) => form.role === 'root' || form.permissions[item.key]).length)
watch(filteredPermissionGroups, (groups) => {
  activePermissionCategory.value = resolvePermissionCategory(groups, activePermissionCategory.value)
}, { immediate: true })
const roleTemplatePermissionGroups = computed(() => buildPermissionGroupsFor(rolePermissionDialog.role, false))
const filteredRolePermissionGroups = computed(() => filterPermissionGroups(roleTemplatePermissionGroups.value, rolePermissionKeyword.value))
const visibleRolePermissionGroups = computed(() => filteredRolePermissionGroups.value.filter((group) => group.category === activeRolePermissionCategory.value))
watch(filteredRolePermissionGroups, (groups) => {
  activeRolePermissionCategory.value = resolvePermissionCategory(groups, activeRolePermissionCategory.value)
}, { immediate: true })
const roleTemplateRoles = computed(() => roles.value.filter((item) => item.value !== 'root'))

const stationRegionOptions = computed(() => {
  return Array.from(
    new Set(stations.value.map((station) => station.region || '未填写片区'))
  ).sort((a, b) => a.localeCompare(b, 'zh-CN'))
})

const stationCountByRegion = (region) => {
  const normalizedRegion = region || '未填写片区'
  return stations.value.filter((station) => (station.region || '未填写片区') === normalizedRegion).length
}

const applyAreaAccountRegionScope = () => {
  if (form.role !== 'area_account') return
  const regionValues = areaAccountRegion.value ? [areaAccountRegion.value] : []
  if (!form.station_region_scope_values || typeof form.station_region_scope_values !== 'object') {
    form.station_region_scope_values = createEmptyStationRegionScopeMap()
  }
  stationRegionScopePermissionKeys.forEach((key) => {
    form.permissions[key] = true
    form.station_region_scope_values[key] = [...regionValues]
  })
  form.permissions.view_own_inspection_issues = false
  form.permissions.view_all_inspection_issues = false
  form.permissions.view_own_inspection_records = false
  form.permissions.view_all_inspection_records = false
  form.permissions.view_own_certificates = false
  form.permissions.view_all_certificates = false
  form.permissions.edit_own_certificates = false
  form.permissions = enforceExclusivePermissions(form.permissions, form.role)
}

const firstAreaAccountRegionFromScope = (scopeMap) => {
  const normalized = normalizeStationRegionScopeMap(scopeMap)
  for (const key of stationRegionScopePermissionKeys) {
    const value = normalized[key]?.[0]
    if (value) return value
  }
  return ''
}

const filteredStations = computed(() => {
  const keyword = stationKeyword.value.trim().toLowerCase()
  return stations.value.filter((station) => {
    const region = station.region || '未填写片区'
    if (stationRegionFilter.value && region !== stationRegionFilter.value) return false
    if (!keyword) return true
    return [
      region,
      station.station_name,
      station.hos_station_code
    ].some((value) => String(value || '').toLowerCase().includes(keyword))
  })
})

const editableRoles = computed(() => {
  if (form.id && form.role === 'root') {
    return roles.value.filter((item) => item.value === 'root')
  }
  return roles.value.filter((item) => item.value !== 'root')
})

const isEditingRoot = computed(() => Boolean(form.id && form.role === 'root'))
const inspectionScopeConfigForCategory = (category) => inspectionScopeConfigs[category] || null
const stationRegionScopeConfigForCategory = (category) => stationRegionScopeConfigs[category] || null
const getRoleDefaultInspectionTableIds = (role = form.role) => {
  const ids = roleDefaultInspectionTableScopeIds.value?.[role]
  return Array.isArray(ids) ? ids : []
}
const hasRoleDefaultInspectionScope = (role = form.role) => getRoleDefaultInspectionTableIds(role).length > 0
const roleDefaultScopeActionLabel = computed(() => {
  const label = roleLabel(form.role)
  if (!label || label === form.role) return '部门默认'
  return `${label.replace(/账号$/, '')}默认`
})
const roleTemplateDefaultScopeActionLabel = computed(() => {
  const label = roleLabel(rolePermissionDialog.role)
  if (!label || label === rolePermissionDialog.role) return '角色默认'
  return `${label.replace(/账号$/, '')}默认`
})
const defaultScopeBadgeLabel = (label) => `${String(label || '').replace(/账号$/, '')}默认`
const isInspectionScopeDisabled = (permissionKey) => scopeInherited[permissionKey] || (
  form.role === 'root' || !form.permissions?.[permissionKey]
)
const isStationRegionScopeDisabled = (permissionKey) => scopeInherited[permissionKey] || (
  form.role === 'root' || !form.permissions?.[permissionKey]
)
const selectedInspectionScopeSummary = (permissionKey) => {
  if (form.role === 'root') return 'root 不受限制'
  if (!form.permissions?.[permissionKey]) return '未启用'
  const count = Array.isArray(form.inspection_table_scope_ids?.[permissionKey])
    ? form.inspection_table_scope_ids[permissionKey].length
    : 0
  return count ? `已选择 ${count} 张` : '未选择检查表'
}
const selectedStationRegionScopeSummary = (permissionKey) => {
  if (form.role === 'root') return 'root 不受限制'
  if (!form.permissions?.[permissionKey]) return '未启用'
  const count = Array.isArray(form.station_region_scope_values?.[permissionKey])
    ? form.station_region_scope_values[permissionKey].length
    : 0
  return count ? `已选择 ${count} 个片区` : '未选择片区'
}

const roleLabel = (role) => {
  return roles.value.find((item) => item.value === role)?.label || role || '-'
}

const setMessage = (text, type = 'info') => {
  if (messageTimer) {
    clearTimeout(messageTimer)
    messageTimer = null
  }

  message.text = text
  message.type = type
  if (!text) return

  messageTimer = setTimeout(() => {
    message.text = ''
    messageTimer = null
  }, 2400)
}

const birthdayDayOptions = (month) => {
  const normalizedMonth = Number(month) || 1
  const dayCount = new Date(2026, normalizedMonth, 0).getDate()
  return Array.from({ length: dayCount }, (_, index) => index + 1)
}

const formatBirthdayLabel = (row) => {
  const month = Number(row?.birthday_month || 0)
  const day = Number(row?.birthday_day || 0)
  return month && day ? `${month}月${day}日` : '-'
}

const normalizeBirthdayRow = (row = {}) => {
  const month = Number(row.birthday_month || 1)
  const validDays = birthdayDayOptions(month)
  const day = validDays.includes(Number(row.birthday_day)) ? Number(row.birthday_day) : 1
  return {
    ...row,
    birthday_month: month,
    birthday_day: day
  }
}

const normalizeBirthdayDay = (row) => {
  if (!row) return
  const validDays = birthdayDayOptions(row.birthday_month)
  const currentDay = Number(row.birthday_day || 1)
  if (!validDays.includes(currentDay)) {
    row.birthday_day = validDays[validDays.length - 1] || 1
  }
}

const fetchBirthdays = async () => {
  if (!hasPermission) return
  try {
    birthdayDialog.loading = true
    birthdayDialog.error = ''
    const response = await axios.get('/api/management/user-birthdays', {
      params: {
        user_id: currentUserId,
        _ts: Date.now()
      }
    })
    birthdayRows.value = (response.data?.birthdays || []).map(normalizeBirthdayRow)
  } catch (error) {
    birthdayDialog.error = error?.response?.data?.error || '生日信息加载失败。'
    setMessage(birthdayDialog.error, 'error')
  } finally {
    birthdayDialog.loading = false
  }
}

const openBirthdayDialog = async () => {
  birthdayDialog.visible = true
  await fetchBirthdays()
}

const closeBirthdayDialog = () => {
  birthdayDialog.visible = false
  birthdayDialog.error = ''
}

const saveBirthdays = async () => {
  try {
    birthdayDialog.saving = true
    birthdayDialog.error = ''
    const payloadRows = birthdayRows.value.map((row) => ({
      real_name: row.real_name,
      birthday_month: row.birthday_month,
      birthday_day: row.birthday_day
    }))
    const response = await axios.put('/api/management/user-birthdays', {
      user_id: currentUserId,
      birthdays: payloadRows
    })
    setMessage(response.data?.message || '生日信息已保存。', 'success')
    await fetchBirthdays()
  } catch (error) {
    birthdayDialog.error = error?.response?.data?.error || '生日信息保存失败。'
    setMessage(birthdayDialog.error, 'error')
  } finally {
    birthdayDialog.saving = false
  }
}

const previewBirthdayBlessing = (row) => {
  const event = row?.birthday_event || {
    is_test: true,
    real_name: row?.real_name || '伙伴',
    birthday_label: formatBirthdayLabel(row),
    birthday_month: row?.birthday_month,
    birthday_day: row?.birthday_day,
    event_key: `test:${Date.now()}:${row?.real_name || 'user'}`,
    work_days: 0
  }
  window.dispatchEvent(new CustomEvent('birthday-blessing-preview', {
    detail: {
      ...event,
      is_test: true,
      is_today: true,
      real_name: row?.real_name || event.real_name,
      birthday_label: formatBirthdayLabel(row),
      birthday_month: row?.birthday_month,
      birthday_day: row?.birthday_day,
      event_key: `test:${Date.now()}:${row?.real_name || event.real_name}`
    }
  }))
}

const defaultPermissionValue = (permission, role) => {
  if (role === 'root') return true
  return Boolean(permission.defaults?.[role])
}

const buildSystemDefaultPermissions = (role) => {
  const defaults = Object.fromEntries(permissions.value.map((permission) => [
    permission.key,
    defaultPermissionValue(permission, role)
  ]))
  return enforceExclusivePermissions(defaults, role)
}

const buildDefaultPermissions = (role) => {
  if (role === 'root') return buildSystemDefaultPermissions(role)
  const roleTemplate = roleEffectivePermissions.value?.[role]
  if (roleTemplate && Object.keys(roleTemplate).length) {
    return enforceExclusivePermissions({ ...roleTemplate }, role)
  }
  return buildSystemDefaultPermissions(role)
}

const enforceExclusivePermissions = (permissionMap, role = form.role) => {
  const nextPermissions = { ...permissionMap }
  if (role === 'root') return nextPermissions

  exclusivePermissionGroups.forEach((group) => {
    const activeKeys = group.filter((key) => nextPermissions[key])
    if (activeKeys.length <= 1) return

    const defaultActiveKeys = activeKeys.filter((key) => {
      const permission = permissions.value.find((item) => item.key === key)
      return Boolean(permission?.defaults?.[role])
    })
    const keepKey = defaultActiveKeys.length === 1 ? defaultActiveKeys[0] : activeKeys[0]
    activeKeys.forEach((key) => {
      nextPermissions[key] = key === keepKey
    })
  })
  Object.entries(dependentPermissionMap).forEach(([childKey, parentKey]) => {
    if (nextPermissions[childKey] && !nextPermissions[parentKey]) {
      nextPermissions[childKey] = false
    }
  })
  Object.entries(anyDependentPermissionMap).forEach(([childKey, parentKeys]) => {
    if (nextPermissions[childKey] && !parentKeys.some((parentKey) => nextPermissions[parentKey])) {
      nextPermissions[childKey] = false
    }
  })
  return nextPermissions
}

const isPermissionDisabledForMap = (permissionMap, permissionKey) => {
  const parentKey = dependentPermissionMap[permissionKey]
  if (parentKey && !permissionMap?.[parentKey]) return true
  const parentKeys = anyDependentPermissionMap[permissionKey]
  return Boolean(parentKeys && !parentKeys.some((key) => permissionMap?.[key]))
}

const isRolePermissionDisabled = (permissionKey) => {
  if (permissionKey === 'review_quality_appeals') return currentRole !== 'root' || rolePermissionDialog.role !== 'quality_safety'
  return isPermissionDisabledForMap(rolePermissionDialog.permissions, permissionKey)
}

const personalPermissionMode = key => Object.hasOwn(form.permission_overrides, key) ? (form.permission_overrides[key] ? 'allow' : 'deny') : 'inherit'
const refreshPersonalPreview = () => {
  form.permissions = previewPersonalPermissions(buildDefaultPermissions(form.role), form.permission_overrides,
    exclusivePermissionGroups, enforceExclusivePermissions, form.role)
}
const setPersonalPermission = (key, mode) => {
  form.permission_overrides = changePermissionOverride(form.permission_overrides, key, mode, exclusivePermissionGroups)
  refreshPersonalPreview()
}
const setScopeInheritance = (key, inherited) => {
  scopeInherited[key] = inherited
  if (inherited) {
    if (inspectionTableScopePermissionKeys.includes(key)) form.inspection_table_scope_ids[key] = [...(buildRoleTemplateInspectionScopeMap(form.role)[key] || [])]
    else form.station_region_scope_values[key] = [...(buildRoleTemplateStationRegionScopeMap(form.role)[key] || [])]
  }
}

const handleRolePermissionChange = (permissionKey) => {
  if (rolePermissionDialog.permissions[permissionKey]) {
    exclusivePermissionGroups.forEach((group) => {
      if (!group.includes(permissionKey)) return
      group
        .filter((key) => key !== permissionKey)
        .forEach((key) => {
          rolePermissionDialog.permissions[key] = false
        })
    })
  }

  Object.entries(dependentPermissionMap).forEach(([childKey, parentKey]) => {
    if (permissionKey === parentKey && !rolePermissionDialog.permissions[parentKey]) {
      rolePermissionDialog.permissions[childKey] = false
    }
    if (permissionKey === childKey && rolePermissionDialog.permissions[childKey] && !rolePermissionDialog.permissions[parentKey]) {
      rolePermissionDialog.permissions[childKey] = false
    }
  })
  Object.entries(anyDependentPermissionMap).forEach(([childKey, parentKeys]) => {
    if (parentKeys.includes(permissionKey) && !parentKeys.some((key) => rolePermissionDialog.permissions[key])) {
      rolePermissionDialog.permissions[childKey] = false
    }
    if (permissionKey === childKey && rolePermissionDialog.permissions[childKey] && !parentKeys.some((key) => rolePermissionDialog.permissions[key])) {
      rolePermissionDialog.permissions[childKey] = false
    }
  })
  rolePermissionDialog.permissions = enforceExclusivePermissions(
    rolePermissionDialog.permissions,
    rolePermissionDialog.role
  )

  if (
    inspectionTableScopePermissionKeys.includes(permissionKey) &&
    rolePermissionDialog.permissions[permissionKey] &&
    hasRoleDefaultInspectionScope(rolePermissionDialog.role) &&
    !rolePermissionDialog.inspection_table_scope_ids[permissionKey]?.length
  ) {
    rolePermissionDialog.inspection_table_scope_ids[permissionKey] = [
      ...getRoleDefaultInspectionTableIds(rolePermissionDialog.role)
    ]
  }
}

const applyRoleDefaults = () => {
  form.permissions = buildDefaultPermissions(form.role)
  form.inspection_table_scope_ids = createRoleInspectionScopeMap(form.role)
  form.station_region_scope_values = createEmptyStationRegionScopeMap()
  if (form.role === 'area_account') {
    form.station_id = ''
    stationRegionFilter.value = ''
    stationKeyword.value = ''
    applyAreaAccountRegionScope()
    return
  }
  areaAccountRegion.value = ''
  if (form.role !== 'station_manager') {
    form.station_id = ''
    stationRegionFilter.value = ''
    stationKeyword.value = ''
  }
}

const loadRoleTemplatePermissions = () => {
  rolePermissionDialog.permissions = buildDefaultPermissions(rolePermissionDialog.role)
  rolePermissionDialog.inspection_table_scope_ids = buildRoleTemplateInspectionScopeMap(rolePermissionDialog.role)
  rolePermissionDialog.station_region_scope_values = buildRoleTemplateStationRegionScopeMap(rolePermissionDialog.role)
  rolePermissionDialog.error = ''
}

const openRolePermissionDialog = () => {
  const firstRole = roleTemplateRoles.value.find((item) => item.value === rolePermissionDialog.role) || roleTemplateRoles.value[0]
  rolePermissionDialog.role = firstRole?.value || 'supervisor'
  loadRoleTemplatePermissions()
  rolePermissionDialog.visible = true
}

const closeRolePermissionDialog = () => {
  if (rolePermissionDialog.saving) return
  rolePermissionDialog.visible = false
  rolePermissionDialog.error = ''
}

const resetRoleTemplateToSystemDefaults = () => {
  rolePermissionDialog.permissions = buildSystemDefaultPermissions(rolePermissionDialog.role)
  rolePermissionDialog.inspection_table_scope_ids = createRoleInspectionScopeMap(rolePermissionDialog.role)
  rolePermissionDialog.station_region_scope_values = createEmptyStationRegionScopeMap()
  rolePermissionDialog.error = ''
}

const validateRoleTemplate = () => {
  if (
    inspectionTables.value.length > 0 &&
    inspectionTableScopePermissionKeys.some((key) => (
      rolePermissionDialog.permissions?.[key] && !ensureRoleInspectionScopeList(key).length
    ))
  ) {
    return '已启用检查表范围限制，请至少为对应页面选择一张检查表。'
  }
  if (
    rolePermissionDialog.role !== 'area_account' &&
    stationRegionScopePermissionKeys.some((key) => (
      rolePermissionDialog.permissions?.[key] && !ensureRoleStationRegionScopeList(key).length
    ))
  ) {
    return '已启用片区范围限制，请至少为对应页面选择一个所属片区/归属地。'
  }
  return ''
}

const saveRolePermissions = async () => {
  try {
    const validationMessage = validateRoleTemplate()
    if (validationMessage) {
      rolePermissionDialog.error = validationMessage
      setMessage(validationMessage, 'error')
      return
    }
    rolePermissionDialog.saving = true
    rolePermissionDialog.error = ''
    const payloadPermissions = enforceExclusivePermissions(
      { ...rolePermissionDialog.permissions },
      rolePermissionDialog.role
    )
    const response = await axios.put(`/api/management/role-permissions/${rolePermissionDialog.role}`, {
      user_id: currentUserId,
      permissions: payloadPermissions,
      inspection_table_scope_ids: rolePermissionDialog.inspection_table_scope_ids,
      station_region_scope_values: rolePermissionDialog.station_region_scope_values
    })
    rolePermissionOverrides.value = {
      ...rolePermissionOverrides.value,
      [rolePermissionDialog.role]: response.data?.role_permission_overrides || {}
    }
    roleEffectivePermissions.value = {
      ...roleEffectivePermissions.value,
      [rolePermissionDialog.role]: response.data?.role_effective_permissions || payloadPermissions
    }
    roleInspectionTableScopeIds.value = {
      ...roleInspectionTableScopeIds.value,
      [rolePermissionDialog.role]: normalizeInspectionScopeMap(response.data?.role_inspection_table_scope_ids)
    }
    roleStationRegionScopeValues.value = {
      ...roleStationRegionScopeValues.value,
      [rolePermissionDialog.role]: normalizeStationRegionScopeMap(response.data?.role_station_region_scope_values)
    }
    rolePermissionDialog.permissions = buildDefaultPermissions(rolePermissionDialog.role)
    rolePermissionDialog.inspection_table_scope_ids = buildRoleTemplateInspectionScopeMap(rolePermissionDialog.role)
    rolePermissionDialog.station_region_scope_values = buildRoleTemplateStationRegionScopeMap(rolePermissionDialog.role)
    setMessage(response.data?.message || '角色通用权限已保存。', 'success')
    await fetchUsers()
  } catch (error) {
    rolePermissionDialog.error = error?.response?.data?.error || '角色通用权限保存失败。'
    setMessage(rolePermissionDialog.error, 'error')
  } finally {
    rolePermissionDialog.saving = false
  }
}

const createRoleInspectionScopeMap = (role) => {
  const defaultIds = getRoleDefaultInspectionTableIds(role)
  if (!defaultIds.length) return createEmptyInspectionScopeMap()
  return Object.fromEntries(
    inspectionTableScopePermissionKeys.map((key) => [key, [...defaultIds]])
  )
}

const buildRoleTemplateInspectionScopeMap = (role) => {
  const roleScopeMap = roleInspectionTableScopeIds.value?.[role]
  if (roleScopeMap && typeof roleScopeMap === 'object') {
    return normalizeInspectionScopeMap(roleScopeMap)
  }
  return createRoleInspectionScopeMap(role)
}

const buildRoleTemplateStationRegionScopeMap = (role) => {
  const roleScopeMap = roleStationRegionScopeValues.value?.[role]
  if (roleScopeMap && typeof roleScopeMap === 'object') {
    return normalizeStationRegionScopeMap(roleScopeMap)
  }
  return createEmptyStationRegionScopeMap()
}

const ensureInspectionScopeList = (permissionKey) => {
  if (!form.inspection_table_scope_ids || typeof form.inspection_table_scope_ids !== 'object') {
    form.inspection_table_scope_ids = createEmptyInspectionScopeMap()
  }
  if (!Array.isArray(form.inspection_table_scope_ids[permissionKey])) {
    form.inspection_table_scope_ids[permissionKey] = []
  }
  return form.inspection_table_scope_ids[permissionKey]
}

const ensureStationRegionScopeList = (permissionKey) => {
  if (!form.station_region_scope_values || typeof form.station_region_scope_values !== 'object') {
    form.station_region_scope_values = createEmptyStationRegionScopeMap()
  }
  if (!Array.isArray(form.station_region_scope_values[permissionKey])) {
    form.station_region_scope_values[permissionKey] = []
  }
  return form.station_region_scope_values[permissionKey]
}

const ensureRoleInspectionScopeList = (permissionKey) => {
  if (!rolePermissionDialog.inspection_table_scope_ids || typeof rolePermissionDialog.inspection_table_scope_ids !== 'object') {
    rolePermissionDialog.inspection_table_scope_ids = createEmptyInspectionScopeMap()
  }
  if (!Array.isArray(rolePermissionDialog.inspection_table_scope_ids[permissionKey])) {
    rolePermissionDialog.inspection_table_scope_ids[permissionKey] = []
  }
  return rolePermissionDialog.inspection_table_scope_ids[permissionKey]
}

const ensureRoleStationRegionScopeList = (permissionKey) => {
  if (!rolePermissionDialog.station_region_scope_values || typeof rolePermissionDialog.station_region_scope_values !== 'object') {
    rolePermissionDialog.station_region_scope_values = createEmptyStationRegionScopeMap()
  }
  if (!Array.isArray(rolePermissionDialog.station_region_scope_values[permissionKey])) {
    rolePermissionDialog.station_region_scope_values[permissionKey] = []
  }
  return rolePermissionDialog.station_region_scope_values[permissionKey]
}

const isRoleInspectionScopeDisabled = (permissionKey) => !rolePermissionDialog.permissions?.[permissionKey]
const isRoleStationRegionScopeDisabled = (permissionKey) => !rolePermissionDialog.permissions?.[permissionKey]

const selectedRoleInspectionScopeSummary = (permissionKey) => {
  if (!rolePermissionDialog.permissions?.[permissionKey]) return '未启用'
  const count = ensureRoleInspectionScopeList(permissionKey).length
  return count ? `已选择 ${count} 张` : '未选择检查表'
}

const selectedRoleStationRegionScopeSummary = (permissionKey) => {
  if (!rolePermissionDialog.permissions?.[permissionKey]) return '未启用'
  const count = ensureRoleStationRegionScopeList(permissionKey).length
  return count ? `已选择 ${count} 个片区` : '未选择片区'
}

const isInspectionTableSelected = (permissionKey, tableId) => {
  return ensureInspectionScopeList(permissionKey).some((id) => String(id) === String(tableId))
}

const isRoleInspectionTableSelected = (permissionKey, tableId) => {
  return ensureRoleInspectionScopeList(permissionKey).some((id) => String(id) === String(tableId))
}

const toggleInspectionTableScope = (permissionKey, tableId, checked) => {
  if (isInspectionScopeDisabled(permissionKey)) return
  const current = ensureInspectionScopeList(permissionKey)
  const normalizedTableId = Number(tableId)
  if (checked) {
    if (!current.some((id) => String(id) === String(normalizedTableId))) {
      form.inspection_table_scope_ids[permissionKey] = [...current, normalizedTableId]
    }
    return
  }
  form.inspection_table_scope_ids[permissionKey] = current.filter((id) => String(id) !== String(normalizedTableId))
}

const toggleRoleInspectionTableScope = (permissionKey, tableId, checked) => {
  if (isRoleInspectionScopeDisabled(permissionKey)) return
  const current = ensureRoleInspectionScopeList(permissionKey)
  const normalizedTableId = Number(tableId)
  if (checked) {
    if (!current.some((id) => String(id) === String(normalizedTableId))) {
      rolePermissionDialog.inspection_table_scope_ids[permissionKey] = [...current, normalizedTableId]
    }
    return
  }
  rolePermissionDialog.inspection_table_scope_ids[permissionKey] = current.filter((id) => String(id) !== String(normalizedTableId))
}

const applyRoleDefaultScope = (permissionKey) => {
  if (isInspectionScopeDisabled(permissionKey)) return
  form.inspection_table_scope_ids[permissionKey] = [...getRoleDefaultInspectionTableIds(form.role)]
}

const applyRoleDefaultScopeForTemplate = (permissionKey) => {
  if (isRoleInspectionScopeDisabled(permissionKey)) return
  rolePermissionDialog.inspection_table_scope_ids[permissionKey] = [
    ...getRoleDefaultInspectionTableIds(rolePermissionDialog.role)
  ]
}

const selectAllInspectionTables = (permissionKey) => {
  if (isInspectionScopeDisabled(permissionKey)) return
  form.inspection_table_scope_ids[permissionKey] = inspectionTables.value.map((table) => table.id)
}

const selectAllRoleInspectionTables = (permissionKey) => {
  if (isRoleInspectionScopeDisabled(permissionKey)) return
  rolePermissionDialog.inspection_table_scope_ids[permissionKey] = inspectionTables.value.map((table) => table.id)
}

const clearInspectionTableScope = (permissionKey) => {
  if (isInspectionScopeDisabled(permissionKey)) return
  form.inspection_table_scope_ids[permissionKey] = []
}

const clearRoleInspectionTableScope = (permissionKey) => {
  if (isRoleInspectionScopeDisabled(permissionKey)) return
  rolePermissionDialog.inspection_table_scope_ids[permissionKey] = []
}

const isStationRegionSelected = (permissionKey, region) => {
  return ensureStationRegionScopeList(permissionKey).some((value) => value === region)
}

const isRoleStationRegionSelected = (permissionKey, region) => {
  return ensureRoleStationRegionScopeList(permissionKey).some((value) => value === region)
}

const toggleStationRegionScope = (permissionKey, region, checked) => {
  if (isStationRegionScopeDisabled(permissionKey)) return
  const current = ensureStationRegionScopeList(permissionKey)
  if (checked) {
    if (!current.includes(region)) {
      form.station_region_scope_values[permissionKey] = [...current, region]
    }
    return
  }
  form.station_region_scope_values[permissionKey] = current.filter((value) => value !== region)
}

const toggleRoleStationRegionScope = (permissionKey, region, checked) => {
  if (isRoleStationRegionScopeDisabled(permissionKey)) return
  const current = ensureRoleStationRegionScopeList(permissionKey)
  if (checked) {
    if (!current.includes(region)) {
      rolePermissionDialog.station_region_scope_values[permissionKey] = [...current, region]
    }
    return
  }
  rolePermissionDialog.station_region_scope_values[permissionKey] = current.filter((value) => value !== region)
}

const selectAllStationRegions = (permissionKey) => {
  if (isStationRegionScopeDisabled(permissionKey)) return
  form.station_region_scope_values[permissionKey] = [...stationRegionOptions.value]
}

const selectAllRoleStationRegions = (permissionKey) => {
  if (isRoleStationRegionScopeDisabled(permissionKey)) return
  rolePermissionDialog.station_region_scope_values[permissionKey] = [...stationRegionOptions.value]
}

const clearStationRegionScope = (permissionKey) => {
  if (isStationRegionScopeDisabled(permissionKey)) return
  form.station_region_scope_values[permissionKey] = []
}

const clearRoleStationRegionScope = (permissionKey) => {
  if (isRoleStationRegionScopeDisabled(permissionKey)) return
  rolePermissionDialog.station_region_scope_values[permissionKey] = []
}

const resetForm = (options = {}) => {
  Object.assign(form, createEmptyForm())
  form.permissions = buildDefaultPermissions(form.role)
  form.inspection_table_scope_ids = createRoleInspectionScopeMap(form.role)
  form.station_region_scope_values = createEmptyStationRegionScopeMap()
  stationRegionFilter.value = ''
  stationKeyword.value = ''
  areaAccountRegion.value = ''
  formError.value = ''
  if (!options.keepMessage) setMessage('')
}

const closeEditor = () => { if (!saving.value) { editorOpen.value = false; formError.value = '' } }
const closeEditorBackdrop = event => {
  if (event.target !== userEditorDialog.value) return
  const bounds = userEditorDialog.value.getBoundingClientRect()
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) closeEditor()
}
const openCreateUser = () => { resetForm(); editorMode.value = 'account'; editorOpen.value = true }

const startEdit = (user, mode = 'account') => {
  editorMode.value = mode
  editorOpen.value = true
  Object.assign(form, {
    id: user.id,
    username: user.username || '',
    role: user.role || 'supervisor',
    real_name: user.real_name || '',
    phone: user.phone || '',
    station_id: user.station_id || '',
    inspection_table_scope_ids: normalizeInspectionScopeMap(personalScopeDraft(user.inspection_table_scope_ids, user.inspection_table_scope_overrides)),
    station_region_scope_values: normalizeStationRegionScopeMap(personalScopeDraft(user.station_region_scope_values, user.station_region_scope_overrides)),
    permissions: enforceExclusivePermissions(user.permissions || {}, user.role || 'supervisor'),
    permission_overrides: { ...(user.permission_overrides || {}) }
  })
  inspectionTableScopePermissionKeys.forEach(key => { scopeInherited[key] = !user.inspection_table_scope_overrides?.[key]?.length })
  stationRegionScopePermissionKeys.forEach(key => { scopeInherited[key] = !user.station_region_scope_overrides?.[key]?.length })
  const station = stations.value.find((item) => String(item.id) === String(user.station_id || ''))
  stationRegionFilter.value = station?.region || ''
  stationKeyword.value = ''
  areaAccountRegion.value = user.role === 'area_account'
    ? firstAreaAccountRegionFromScope(user.station_region_scope_values)
    : ''
  formError.value = ''
  setMessage(`已进入【${user.username}】编辑状态。`, 'info')
}

const startPermissionEdit = user => startEdit(user, 'permissions')

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
    inspectionTables.value = response.data?.inspection_tables || []
    roleDefaultInspectionTableScopeIds.value = response.data?.role_default_inspection_table_scope_ids || {
      quality_safety: response.data?.quality_safety_default_inspection_table_ids || [],
      development_plan: response.data?.development_plan_default_inspection_table_ids || [],
      oil_gas: response.data?.oil_gas_default_inspection_table_ids || [],
      non_oil: response.data?.non_oil_default_inspection_table_ids || [],
      finance: response.data?.finance_default_inspection_table_ids || []
    }
    roles.value = response.data?.roles || []
    permissions.value = response.data?.permissions || []
    rolePermissionOverrides.value = response.data?.role_permission_overrides || {}
    roleEffectivePermissions.value = response.data?.role_effective_permissions || {}
    roleInspectionTableScopeIds.value = response.data?.role_inspection_table_scope_ids || {}
    roleStationRegionScopeValues.value = response.data?.role_station_region_scope_values || {}
    if (rolePermissionDialog.visible) {
      loadRoleTemplatePermissions()
    }
    if (!form.id && !Object.keys(form.permissions || {}).length) {
      form.permissions = buildDefaultPermissions(form.role)
      if (hasRoleDefaultInspectionScope(form.role)) {
        form.inspection_table_scope_ids = createRoleInspectionScopeMap(form.role)
      }
    }
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
    setMessage('用户数据备份文件已生成，已包含数据库当前密码，请妥善保管。', 'success')
  } catch {
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

  const confirmed = window.confirm('导入后会按备份文件新增或更新用户、权限和当前密码；如果备份包含 root 且密码不同，导入完成后需要使用备份中的 root 密码重新登录。确定继续吗？')
  if (!confirmed) return

  try {
    importing.value = true
    setMessage('')
    const formData = new FormData()
    formData.append('user_id', currentUserId)
    formData.append('file', file)
    const response = await axios.post('/api/management/users/import', formData)
    if (response.data?.auth_invalidated) {
      const notice = response.data?.message || '用户数据导入完成。'
      window.alert(`${notice}\n\nroot 密码已按备份恢复，请使用备份文件中的 root 密码重新登录。`)
      clearAuthSession('用户备份已恢复 root 密码，请重新登录。')
      window.location.href = '/login'
      return
    }
    setMessage(response.data?.message || '用户数据导入完成。', 'success')
    resetForm({ keepMessage: true })
    await fetchUsers()
  } catch (error) {
    setMessage(error?.response?.data?.error || '用户数据导入失败。', 'error')
  } finally {
    importing.value = false
  }
}

const validateForm = () => {
  if (!form.username) return '请填写用户名。'
  if (!form.role) return '请选择角色。'
  if (form.role !== 'area_account' && !form.real_name) return '请填写用户姓名。'
  if (form.role === 'station_manager' && !form.station_id) return '站点账号必须选择所属站点。'
  if (form.role === 'area_account' && !areaAccountRegion.value) return '片区账号必须选择所属片区/归属地。'
  if (editorMode.value !== 'permissions') return ''
  if (
    form.role !== 'root' &&
    inspectionTables.value.length > 0 &&
    inspectionTableScopePermissionKeys.some((key) => (
      form.permissions?.[key] && !ensureInspectionScopeList(key).length
    ))
  ) {
    return '已启用检查表范围限制，请至少为对应页面选择一张检查表。'
  }
  if (
    form.role !== 'root' &&
    stationRegionScopePermissionKeys.some((key) => (
      form.permissions?.[key] && !ensureStationRegionScopeList(key).length
    ))
  ) {
    return '已启用片区范围限制，请至少为对应页面选择一个所属片区/归属地。'
  }
  return ''
}

const saveUser = async () => {
  formError.value = validateForm()
  if (formError.value) {
    setMessage(formError.value, 'error')
    return
  }

  try {
    saving.value = true
    const isCreating = !form.id
    const normalizedRealName = form.role === 'area_account'
      ? (form.real_name || areaAccountRegion.value || form.username)
      : form.real_name
    let response
    if (editorMode.value === 'permissions') {
      response = await axios.put(`/api/management/users/${form.id}/permissions`, {
        user_id: currentUserId,
        permission_overrides: { ...form.permission_overrides },
        inspection_table_scope_ids: Object.fromEntries(inspectionTableScopePermissionKeys.map(key => [key, scopeInherited[key] ? [] : [...ensureInspectionScopeList(key)]])),
        station_region_scope_values: Object.fromEntries(stationRegionScopePermissionKeys.map(key => [key, scopeInherited[key] ? [] : [...ensureStationRegionScopeList(key)]]))
      })
    } else {
      const payload = { user_id: currentUserId, username: form.username, role: form.role,
        real_name: normalizedRealName, phone: form.phone, station_id: form.station_id }
      if (form.role === 'area_account') payload.station_region_scope_values = Object.fromEntries(stationRegionScopePermissionKeys.map(key => [key, [areaAccountRegion.value]]))
      response = form.id ? await axios.put(`/api/management/users/${form.id}`, payload) : await axios.post('/api/management/users', payload)
    }
    setMessage(response.data?.message || '用户已保存。', 'success')
    editorOpen.value = false
    if (isCreating && response.data?.credentials?.[0]) {
      Object.assign(resetPasswordDialog, { visible: true, target: { username: form.username, real_name: form.real_name }, credential: response.data.credentials[0], error: '' })
    }
    await fetchUsers()
  } catch (error) {
    formError.value = error?.response?.data?.error || '用户保存失败。'
    setMessage(formError.value, 'error')
  } finally {
    saving.value = false
  }
}

const openPasswordReset = (user) => {
  if (!hasPermission || user.role === 'root' || resetPasswordDialog.loading) return
  Object.assign(resetPasswordDialog, { visible: true, target: { ...user }, credential: null, error: '' })
}

const closePasswordReset = () => {
  if (resetPasswordDialog.loading) return
  Object.assign(resetPasswordDialog, { visible: false, target: null, credential: null, error: '' })
}

const resetUserPassword = async () => {
  if (!hasPermission || !resetPasswordDialog.target || resetPasswordDialog.loading || resetPasswordDialog.credential) return
  resetPasswordDialog.loading = true
  resetPasswordDialog.error = ''
  try {
    const response = await axios.post(`/api/management/users/${resetPasswordDialog.target.id}/reset-password`, { user_id: currentUserId })
    resetPasswordDialog.credential = response.data.credentials?.[0] || null
    setMessage(response.data.message || '密码已重置。', 'success')
  } catch (error) {
    resetPasswordDialog.error = error?.response?.data?.error || '密码重置失败，请稍后重试。'
  } finally {
    resetPasswordDialog.loading = false
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
    if (form.id === user.id) resetForm({ keepMessage: true })
    await fetchUsers()
  } catch (error) {
    setMessage(error?.response?.data?.error || '用户删除失败。', 'error')
  } finally {
    deletingId.value = null
  }
}

watch(stationRegionFilter, () => {
  if (!form.station_id || !stationRegionFilter.value) return
  const stillVisible = filteredStations.value.some((station) => String(station.id) === String(form.station_id))
  if (!stillVisible) form.station_id = ''
})

watch(stationKeyword, () => {
  if (!form.station_id) return
  const stillVisible = filteredStations.value.some((station) => String(station.id) === String(form.station_id))
  if (!stillVisible) form.station_id = ''
})

onMounted(fetchUsers)

onBeforeUnmount(() => {
  userEditorDialog.value?.close()
  if (messageTimer) {
    clearTimeout(messageTimer)
    messageTimer = null
  }
})
</script>

<style scoped>
.user-editor-dialog, .user-editor-dialog * { box-sizing: border-box; }
.user-editor-dialog { width: min(720px, calc(100vw - 28px)); max-width: none; max-height: calc(100dvh - 28px); margin: auto; padding: 22px; border: 1px solid #dbe4ee; border-radius: 20px; overflow: auto; color: #0f172a; box-shadow: 0 28px 80px #0f172a40; }
.user-editor-dialog::backdrop { background: #0f172a80; backdrop-filter: blur(4px); }
.user-editor-dialog.permission-mode { width: min(1160px, calc(100vw - 28px)); height: min(880px, calc(100dvh - 28px)); overflow: hidden; }
.user-editor-dialog .editor-card { padding: 0; }
.user-editor-dialog .section-head { align-items: flex-start; }
.user-editor-dialog .basic-form { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.permission-mode .editor-card { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.permission-mode .editor-layout { flex: 1; min-height: 0; overflow: hidden; }
.permission-mode .permission-panel { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.permission-mode .permission-workspace { flex: 1; height: auto; min-height: 0; }
.permission-mode .section-head, .permission-mode .form-actions, .permission-mode .form-error { flex-shrink: 0; }
.permission-mode .form-actions { margin-top: 16px; }
.account-inheritance-note { grid-column: 1 / -1; margin: 0; padding: 12px; border-radius: 10px; background: #eff6ff; color: #3e6090; font-size: 12px; line-height: 1.8; }
.permission-mode .permission-section { grid-template-columns: 1fr; }
@media (max-width: 600px) { .user-editor-dialog { padding: 16px; } .user-editor-dialog .basic-form { grid-template-columns: 1fr; padding: 14px; } }
.scope-inheritance { display: flex; align-items: center; gap: 8px; padding: 12px 0; color: #2563eb; font-size: 12px; }

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
.form-actions {
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

.editing-heading,
.editing-target {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.editing-heading > span,
.editing-target > span {
  color: #64748b;
  font-size: 14px;
  font-weight: 900;
}

.editing-heading > strong,
.editing-target > strong {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 6px 14px;
  border-radius: 999px;
  background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.12);
  font-size: 15px;
  font-weight: 950;
}

.editor-card.editing {
  border-color: #bfdbfe;
  box-shadow: 0 18px 40px rgba(37, 99, 235, 0.12);
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

.station-picker-card {
  grid-column: 1 / -1;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid #bfdbfe;
  background:
    radial-gradient(circle at 92% 8%, rgba(37, 99, 235, 0.14), transparent 28%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(239, 246, 255, 0.92));
}

.station-picker-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.station-picker-head strong {
  display: block;
  color: #0f172a;
  font-size: 15px;
  font-weight: 900;
}

.station-picker-head p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.station-picker-head > span {
  flex: 0 0 auto;
  padding: 6px 10px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.station-picker-grid {
  display: grid;
  grid-template-columns: minmax(160px, 0.85fr) minmax(220px, 1fr) minmax(320px, 1.4fr);
  gap: 14px;
  align-items: end;
}

.station-picker-grid.single {
  grid-template-columns: minmax(240px, 420px);
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

.permission-panel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.permission-overview { flex-shrink: 0; padding: 7px 11px; border: 1px solid #bfdbfe; border-radius: 10px; background: #eff6ff; color: #1d4ed8; font-size: 12px; font-weight: 800; }
.permission-workspace { display: grid; grid-template-columns: 210px minmax(0, 1fr); grid-template-rows: minmax(0, 1fr); align-items: stretch; gap: 18px; height: min(68vh, 720px); min-height: 360px; overflow: hidden; overflow-anchor: none; }
.permission-groups.user-permission-groups { display: block; min-width: 0; min-height: 0; overflow: auto; overscroll-behavior: contain; overflow-anchor: none; scrollbar-gutter: stable; }
.user-permission-groups .permission-group { padding: 20px; }
.user-permission-groups .permission-group-title { margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid #e2e8f0; font-size: 16px; }
.user-permission-groups .permission-section { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 230px), 1fr)); gap: 10px; }
.user-permission-groups .permission-section-label { grid-column: 1 / -1; margin-bottom: 2px; }
.user-permission-groups .permission-item { min-width: 0; margin: 0; padding: 12px; border: 1px solid #e2e8f0; border-radius: 11px; background: #fff; cursor: pointer; }
.user-permission-groups .permission-item:has(input:checked) { border-color: #bfdbfe; background: #f5f9ff; }
.user-permission-groups .permission-item.disabled { cursor: not-allowed; }
.user-permission-groups .permission-item > span { min-width: 0; overflow-wrap: anywhere; }
.user-permission-groups .permission-item input { width: 16px; height: 16px; accent-color: #2563eb; }
.user-permission-groups .permission-section .permission-item:first-of-type { border-top: 1px solid #e2e8f0; }
.user-permission-groups .readonly-section { grid-template-columns: 1fr; }
.user-permission-groups .permission-item strong em { white-space: nowrap; }
.user-permission-groups .inspection-scope-grid { grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr)); }
.user-permission-groups .inspection-scope-item { min-width: 0; }

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
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
}

.permission-group-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 900;
}

.permission-group-title em {
  padding: 3px 8px;
  border-radius: 999px;
  background: #eef6ff;
  color: #2563eb;
  font-size: 11px;
  font-style: normal;
  font-weight: 900;
}

.permission-section + .permission-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #dbe6f2;
}

.permission-section-label {
  display: inline-flex;
  align-items: center;
  margin-bottom: 4px;
  color: #475569;
  font-size: 12px;
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

.permission-section .permission-item:first-of-type {
  border-top: 0;
}

.permission-item input {
  margin-top: 3px;
}

.permission-item.disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.permission-item-scope {
  border-radius: 12px;
}

.permission-item-action {
  padding-left: 8px;
  border-left: 3px solid #dbeafe;
}

.permission-item-readonly {
  margin-top: 6px;
  padding: 10px;
  border: 1px dashed #cbd5e1;
  border-radius: 14px;
  background: #f8fafc;
}

.permission-item strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
}

.permission-item strong em {
  margin-left: 7px;
  padding: 2px 7px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  font-size: 11px;
  font-style: normal;
  font-weight: 900;
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

.inspection-scope-panel {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #bfdbfe;
  border-radius: 18px;
  background:
    radial-gradient(circle at 95% 12%, rgba(37, 99, 235, 0.12), transparent 28%),
    linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
}

.inspection-scope-panel.disabled {
  border-color: #e2e8f0;
  background: #f8fafc;
}

.region-scope-panel {
  border-color: #bbf7d0;
  background:
    radial-gradient(circle at 95% 12%, rgba(22, 163, 74, 0.12), transparent 28%),
    linear-gradient(135deg, #ffffff 0%, #f7fef9 100%);
}

.inspection-scope-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}

.inspection-scope-head strong {
  display: block;
  color: #0f172a;
  font-size: 15px;
  font-weight: 950;
}

.inspection-scope-head p {
  margin: 5px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
}

.inspection-scope-head > span {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 900;
}

.inspection-scope-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.inspection-scope-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.inspection-scope-item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: flex-start;
  min-height: 76px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.inspection-scope-item:hover {
  border-color: #93c5fd;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.1);
  transform: translateY(-1px);
}

.inspection-scope-item.checked {
  border-color: #2563eb;
  background: #eff6ff;
}

.inspection-scope-item.disabled {
  cursor: not-allowed;
  opacity: 0.58;
  transform: none;
  box-shadow: none;
}

.inspection-scope-item input {
  margin-top: 4px;
}

.inspection-scope-item strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.45;
}

.inspection-scope-item small {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
}

.inspection-scope-item em {
  padding: 2px 7px;
  border-radius: 999px;
  background: #dcfce7;
  color: #15803d;
  font-style: normal;
  font-weight: 900;
}

.region-scope-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.region-scope-item {
  min-height: 64px;
}

.region-scope-item.checked {
  border-color: #16a34a;
  background: #f0fdf4;
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

.message-toast {
  position: fixed;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: min(calc(100vw - 32px), 440px);
  z-index: 1500;
  padding: 14px 16px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 900;
  line-height: 1.7;
  text-align: center;
  box-shadow: 0 18px 36px rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(10px);
  animation: toast-pulse 1.2s ease-in-out infinite;
}

.message-toast.error {
  border: 1px solid #fecaca;
  background: rgba(254, 242, 242, 0.98);
  color: #b91c1c;
}

.message-toast.success {
  border: 1px solid #bbf7d0;
  background: rgba(236, 253, 245, 0.98);
  color: #166534;
}

.message-toast.info {
  border: 1px solid #bfdbfe;
  background: rgba(239, 246, 255, 0.98);
  color: #1d4ed8;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, calc(-50% + 12px));
}

@keyframes toast-pulse {
  0%,
  100% {
    box-shadow: 0 18px 36px rgba(15, 23, 42, 0.16);
  }

  50% {
    box-shadow: 0 22px 44px rgba(37, 99, 235, 0.22);
  }
}

.form-error {
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.7;
}

.form-error {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #dc2626;
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

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(8px);
}

.role-permission-modal {
  display: flex;
  flex-direction: column;
  width: min(1440px, calc(100vw - 40px));
  max-height: min(92vh, 980px);
  padding: 24px;
  overflow: hidden;
}

.birthday-management-modal {
  display: flex;
  flex-direction: column;
  width: min(1100px, calc(100vw - 40px));
  max-height: min(90vh, 860px);
  padding: 24px;
  overflow: hidden;
}

.birthday-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  padding: 14px 16px;
  border: 1px solid #fed7aa;
  border-radius: 18px;
  background:
    radial-gradient(circle at 96% 0%, rgba(251, 191, 36, 0.16), transparent 30%),
    linear-gradient(135deg, #fff7ed 0%, #ffffff 100%);
}

.birthday-toolbar div {
  display: grid;
  gap: 4px;
}

.birthday-toolbar strong {
  color: #9a3412;
  font-size: 15px;
  font-weight: 950;
}

.birthday-toolbar span {
  color: #64748b;
  font-size: 13px;
}

.birthday-table-wrap {
  min-height: 0;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #fff;
}

.birthday-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

.birthday-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 13px 14px;
  background: #fff7ed;
  color: #9a3412;
  font-size: 13px;
  font-weight: 950;
  text-align: left;
  white-space: nowrap;
}

.birthday-table td {
  padding: 13px 14px;
  border-top: 1px solid #f1f5f9;
  color: #334155;
  font-size: 13px;
  vertical-align: middle;
}

.birthday-name-cell,
.birthday-user-match {
  display: grid;
  gap: 4px;
}

.birthday-name-cell strong,
.birthday-user-match strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 950;
}

.birthday-name-cell span,
.birthday-user-match span,
.birthday-unmatched {
  color: #64748b;
  font-size: 12px;
}

.birthday-unmatched {
  display: inline-flex;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
}

.birthday-select {
  width: 110px;
  height: 38px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 0 10px;
  background: #fff;
  color: #0f172a;
  font-weight: 800;
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
}

.modal-head h3 {
  margin: 0;
  color: #0f172a;
  font-size: 24px;
  font-weight: 950;
}

.modal-head p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.8;
}

.close-btn {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 22px;
  font-weight: 900;
  cursor: pointer;
}

.role-template-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 280px) 1fr;
  gap: 14px;
  align-items: stretch;
  margin-bottom: 16px;
  padding: 14px;
  border: 1px solid #dbeafe;
  border-radius: 18px;
  background: linear-gradient(135deg, #eff6ff 0%, #ffffff 100%);
}

.role-template-note {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
}

.role-template-note strong {
  color: #1d4ed8;
  font-size: 15px;
  font-weight: 950;
}

.role-template-note span {
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.role-template-groups {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  max-height: none;
  overflow: auto;
  padding: 4px 8px 4px 2px;
}

.role-template-groups .permission-group {
  padding: 18px;
  border-radius: 20px;
  background:
    radial-gradient(circle at 98% 0%, rgba(37, 99, 235, 0.08), transparent 24%),
    linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.role-template-groups .permission-group-title {
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 15px;
}

.role-template-groups .permission-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 230px), 1fr));
  gap: 10px;
  align-items: stretch;
}

.role-template-groups .permission-section + .permission-section {
  margin-top: 14px;
  padding-top: 14px;
}

.role-template-groups .permission-section-label {
  grid-column: 1 / -1;
  margin-bottom: 0;
}

.role-template-groups .permission-item {
  min-height: 74px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.86);
}

.role-template-groups .permission-section .permission-item:first-of-type {
  border-top: 1px solid #e2e8f0;
}

.role-template-groups .permission-item-action {
  padding-left: 12px;
  border-left: 4px solid #bfdbfe;
}

.role-template-groups .role-scope-panel {
  margin-top: 18px;
  padding: 18px;
}

.role-template-groups .inspection-scope-grid {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr));
  max-height: 300px;
  overflow: auto;
  padding: 2px 4px 2px 0;
}

.role-template-groups .region-scope-grid {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr));
  max-height: 220px;
}

.modal-actions {
  flex: 0 0 auto;
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #e2e8f0;
}

.role-template-workspace { flex: 1 1 auto; height: min(58vh, 650px); min-height: 180px; }
.role-template-toolbar, .role-permission-modal .modal-head { flex: 0 0 auto; }

@media (max-width: 1280px) {
  .permission-groups,
  .inspection-scope-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

}

@media (max-width: 980px) {
  .permission-panel-head { flex-direction: column; gap: 0; margin-bottom: 14px; }
  .permission-workspace { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); gap: 12px; }
  .user-permission-groups .permission-group { padding: 14px; }

  .basic-form,
  .permission-groups,
  .inspection-scope-grid,
  .station-picker-grid {
    grid-template-columns: 1fr;
  }

  .inspection-scope-head {
    flex-direction: column;
  }

  .station-picker-head {
    flex-direction: column;
  }

  .modal-backdrop {
    padding: 14px;
    align-items: flex-start;
  }

  .role-permission-modal {
    width: 100%;
    max-height: calc(100vh - 28px);
    padding: 18px;
  }

  .birthday-management-modal {
    width: 100%;
    max-height: calc(100vh - 28px);
    padding: 18px;
  }

  .birthday-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .birthday-toolbar .btn {
    width: 100%;
  }

  .birthday-table-wrap {
    max-height: 56vh;
  }

  .modal-head,
  .role-template-toolbar {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .modal-actions .btn {
    width: 100%;
  }

  .role-permission-modal { height: calc(100dvh - 28px); box-sizing: border-box; padding: 14px; }
  .role-permission-modal .modal-head { flex-direction: row; gap: 10px; margin-bottom: 10px; }
  .role-permission-modal .modal-head h3 { font-size: 18px; }
  .role-permission-modal .modal-head p { margin-top: 5px; font-size: 12px; line-height: 1.5; }
  .role-permission-modal .modal-head .section-kicker { display: none; }
  .role-permission-modal .close-btn { flex: 0 0 32px; width: 32px; height: 32px; }
  .role-template-toolbar { padding: 10px; margin-bottom: 10px; }
  .role-template-note { display: none; }
  .role-permission-modal .modal-actions { flex-wrap: nowrap; gap: 6px; margin-top: 10px; padding-top: 10px; }
  .role-permission-modal .modal-actions .btn { flex: 1; min-width: 0; width: auto; padding: 10px 6px; font-size: 12px; }
}
</style>
