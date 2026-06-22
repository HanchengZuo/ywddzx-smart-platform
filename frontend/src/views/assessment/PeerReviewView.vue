<template>
  <div class="peer-review-page">
    <section class="review-hero">
      <div>
        <div class="page-kicker">考核系统</div>
        <h2>成员互评</h2>
        <p>通过任务模板发起成员互评，普通人员可参与填写并查看自己的历史评价记录。</p>
      </div>
      <div class="hero-actions">
        <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchDashboard">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
        <button v-if="canManage" class="btn btn-primary" type="button" @click="openTemplateDialog()">
          新建互评模板
        </button>
      </div>
    </section>

    <div v-if="message.text" :class="['message-toast', message.type]">{{ message.text }}</div>
    <div v-if="error" class="message-card error">{{ error }}</div>

    <section class="overview-grid">
      <article v-for="card in overviewCards" :key="card.label" class="overview-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.desc }}</small>
      </article>
    </section>

    <div v-if="loading" class="state-card">
      <div class="state-orb loading"></div>
      <h3>正在读取成员互评数据</h3>
      <p>系统正在加载任务、模板、填写进度和评价记录。</p>
    </div>

    <template v-else>
      <section class="task-section">
        <div class="section-title">
          <div>
            <span>任务中心</span>
            <h3>互评任务</h3>
          </div>
          <em>{{ tasks.length }} 个任务</em>
        </div>

        <div v-if="tasks.length" class="task-grid">
          <article v-for="task in paginatedTasks" :key="task.id" class="task-card">
            <div class="task-card-head">
              <div>
                <div class="task-status-row">
                  <span :class="['status-pill', task.status]">{{ task.status === 'active' ? '进行中' : '已关闭' }}</span>
                  <span v-if="task.deadline_at" class="deadline-pill">截止 {{ task.deadline_at }}</span>
                </div>
                <h4>{{ task.title }}</h4>
                <p>{{ task.description || '暂无任务说明。' }}</p>
              </div>
              <label v-if="canManage" class="task-status-switch" :class="{ active: task.status === 'active' }">
                <input type="checkbox" :checked="task.status === 'active'"
                  @change="updateTaskStatus(task, $event.target.checked ? 'active' : 'closed')" />
                <span></span>
                <em>{{ task.status === 'active' ? '开启' : '关闭' }}</em>
              </label>
              <button v-if="canManage" class="task-delete-btn" type="button" @click="deleteTask(task)">删除</button>
            </div>

            <div class="progress-block">
              <div class="progress-head">
                <strong>完成进度</strong>
                <span>{{ task.progress.completed_count }} / {{ task.progress.participant_count }}</span>
              </div>
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: `${taskProgressPercent(task)}%` }"></div>
              </div>
              <div v-if="task.progress.completed_participants.length || task.progress.pending_participants?.length" class="progress-people-board">
                <div v-if="task.progress.completed_participants.length" class="progress-people-row">
                  <em>已完成</em>
                  <div class="chip-list">
                    <span v-for="person in task.progress.completed_participants" :key="person.id" class="person-chip done">
                      {{ person.display_name }}
                    </span>
                  </div>
                </div>
                <div v-if="task.progress.pending_participants?.length" class="progress-people-row">
                  <em>未完成</em>
                  <div class="chip-list pending-chip-list">
                    <span v-for="person in task.progress.pending_participants" :key="person.id" class="person-chip pending">
                      {{ person.display_name }}
                    </span>
                  </div>
                </div>
              </div>
              <p v-else class="muted-text">该任务未开启填写人员完成进度展示。</p>
            </div>

            <div class="task-meta-grid">
              <div>
                <span>填写人员</span>
                <strong>{{ task.participants.length }} 人</strong>
              </div>
              <div>
                <span>被评人</span>
                <strong>{{ task.reviewees.length }} 人</strong>
              </div>
              <div>
                <span>评价项目</span>
                <strong>{{ task.items.length }} 项</strong>
              </div>
            </div>

            <div class="reviewee-panel">
              <div class="mini-title">我需要填写</div>
              <div v-if="task.my_pending_reviewees.length && task.can_submit" class="reviewee-list">
                <button v-for="reviewee in task.my_pending_reviewees" :key="reviewee.id" class="reviewee-btn"
                  type="button" @click="openResponseDialog(task, reviewee)">
                  <span>{{ reviewee.display_name }}</span>
                  <em>去评价</em>
                </button>
              </div>
              <div v-else-if="task.my_pending_reviewees.length" class="finished-tip">
                仍有 {{ task.my_pending_reviewees.length }} 个对象未评价，但任务已关闭或超过截止时间。
              </div>
              <div v-else class="finished-tip">当前账号没有待填写对象。</div>
            </div>

            <div v-if="task.responses.length" class="response-panel">
              <div class="mini-title">{{ canManage ? '评价明细' : '我的评价记录' }}</div>
              <div class="response-list">
                <div v-for="response in task.responses" :key="response.id" class="response-card">
                  <div class="response-head">
                    <strong>{{ response.reviewee_name }}</strong>
                    <span>
                      <template v-if="canManage">填写人：{{ response.reviewer_name }}</template>
                      <template v-else>我的评价</template>
                      ｜ {{ response.updated_at || response.submitted_at }}
                    </span>
                  </div>
                  <div class="answer-grid">
                    <div v-for="item in response.items" :key="`${response.id}-${item.task_item_id}`" class="answer-item">
                      <span>{{ item.title }}</span>
                      <strong v-if="item.item_type === 'score'">{{ item.score_value }} / {{ item.max_score }}</strong>
                      <p v-else>{{ item.text_value }}</p>
                    </div>
                  </div>
                  <button v-if="response.reviewer_id === currentUser.id && task.status === 'active'" class="btn btn-secondary btn-sm"
                    type="button" @click="openResponseDialog(task, getPersonById(task.reviewees, response.reviewee_id))">
                    修改我的评价
                  </button>
                </div>
              </div>
            </div>
          </article>
        </div>

        <div v-if="tasks.length" class="pagination-bar card-surface">
          <div class="pagination-summary">共 {{ tasks.length }} 个互评任务</div>
          <div class="pagination-controls">
            <div class="pagination-size-control">
              <label>每页显示</label>
              <select v-model.number="pageSize">
                <option :value="5">5</option>
                <option :value="10">10</option>
                <option :value="20">20</option>
                <option :value="50">50</option>
              </select>
            </div>
            <div class="pagination-nav-row">
              <button class="btn btn-secondary pagination-btn" :disabled="page <= 1" @click="goToPage(1)">首页</button>
              <button class="btn btn-secondary pagination-btn" :disabled="page <= 1" @click="prevPage">上一页</button>
            </div>
            <div class="pagination-page-list" aria-label="成员互评页码">
              <template v-for="item in visiblePageItems" :key="item.key">
                <span v-if="item.type === 'ellipsis'" class="pagination-ellipsis">...</span>
                <button v-else class="pagination-page-btn" :class="{ active: item.value === page }" type="button"
                  @click="goToPage(item.value)">
                  {{ item.value }}
                </button>
              </template>
            </div>
            <div class="pagination-nav-row">
              <button class="btn btn-secondary pagination-btn" :disabled="page >= totalPage" @click="nextPage">下一页</button>
              <button class="btn btn-secondary pagination-btn" :disabled="page >= totalPage" @click="goToPage(totalPage)">末页</button>
            </div>
            <div class="pagination-jump">
              <span>跳至</span>
              <input v-model="pageJumpInput" type="number" min="1" :max="totalPage" :placeholder="`1-${totalPage}`"
                @keyup.enter="jumpToInputPage" />
              <button class="btn btn-primary pagination-jump-btn" type="button" @click="jumpToInputPage">跳转</button>
            </div>
          </div>
        </div>

        <div v-else class="empty-card">
          <div class="state-orb"></div>
          <h3>暂无成员互评任务</h3>
          <p>{{ canManage ? '可以先新建模板，再发起一次互评任务。' : '当前账号暂未被安排参与成员互评。' }}</p>
        </div>
      </section>

      <section v-if="canManage" class="template-section">
        <div class="section-title">
          <div>
            <span>模板管理</span>
            <h3>成员互评任务模板</h3>
          </div>
          <em>{{ templates.length }} 个模板</em>
        </div>

        <div v-if="templates.length" class="template-grid">
          <article v-for="template in templates" :key="template.id" class="template-card">
            <div>
              <h4>{{ template.title }}</h4>
              <p>{{ template.description || '暂无简介说明。' }}</p>
            </div>
            <div class="template-stats">
              <span>{{ template.participant_ids.length }} 名填写人员</span>
              <span>{{ template.reviewee_ids.length }} 名被评人</span>
              <span>{{ template.items.length }} 个评价项目</span>
            </div>
            <div class="template-actions">
              <button class="btn btn-primary btn-sm" type="button" @click="openLaunchDialog(template)">发起任务</button>
              <button class="btn btn-secondary btn-sm" type="button" @click="openTemplateDialog(template)">编辑模板</button>
              <button class="btn btn-danger btn-sm" type="button" @click="deleteTemplate(template)">删除模板</button>
            </div>
          </article>
        </div>

        <div v-else class="empty-card compact">
          <h3>还没有互评模板</h3>
          <p>模板可以复用，适合把固定评价项目先沉淀下来。</p>
        </div>
      </section>
    </template>

    <div v-if="templateDialog.visible" class="modal-backdrop">
      <form class="dialog-card template-dialog" @submit.prevent="saveTemplate">
        <div class="dialog-head">
          <div>
            <span>任务模板</span>
            <h3>{{ templateForm.id ? '编辑成员互评模板' : '新建成员互评模板' }}</h3>
          </div>
          <button type="button" class="close-btn" @click="closeTemplateDialog">×</button>
        </div>

        <div class="dialog-grid">
          <label class="form-field">
            <span>标题</span>
            <input v-model.trim="templateForm.title" type="text" placeholder="例如：二季度督导组成员互评" />
          </label>
          <label class="form-field">
            <span>默认截止时间</span>
            <input v-model="templateForm.default_deadline_at" type="datetime-local" />
          </label>
          <label class="form-field wide">
            <span>简介说明</span>
            <textarea v-model.trim="templateForm.description" rows="3" placeholder="说明本次互评目标和填写要求"></textarea>
          </label>
        </div>

        <div class="switch-row">
          <label><input v-model="templateForm.show_participation" type="checkbox" /> 展示填写人员完成进度</label>
        </div>

        <div class="selector-layout">
          <div class="selector-card">
            <div class="selector-title">
              <span>填写人员</span>
              <em>已选 {{ templateForm.participant_ids.length }} 人</em>
            </div>
            <div class="role-tabs">
              <button v-for="group in peopleGroups" :key="`p-tab-${group.role}`" type="button"
                :class="{ active: rolePickerState.templateParticipants === group.role }"
                @click="rolePickerState.templateParticipants = group.role">
                {{ group.label }}
                <em>{{ selectedCount(templateForm.participant_ids, group.people) }}/{{ group.people.length }}</em>
              </button>
            </div>
            <div v-if="getActiveGroup(rolePickerState.templateParticipants)" class="role-picker-panel">
              <div class="role-picker-head">
                <strong>{{ getActiveGroup(rolePickerState.templateParticipants).label }}</strong>
                <span>{{ selectedCount(templateForm.participant_ids, getActiveGroup(rolePickerState.templateParticipants).people) }} / {{ getActiveGroup(rolePickerState.templateParticipants).people.length }}</span>
                <button type="button" @click="togglePeopleGroup(templateForm, 'participant_ids', getActiveGroup(rolePickerState.templateParticipants).people, true)">全选本组</button>
                <button type="button" @click="togglePeopleGroup(templateForm, 'participant_ids', getActiveGroup(rolePickerState.templateParticipants).people, false)">清空本组</button>
              </div>
              <div class="people-picker">
                <label v-for="person in getActiveGroup(rolePickerState.templateParticipants).people" :key="`p-${person.id}`"
                  :class="{ checked: templateForm.participant_ids.includes(person.id) }">
                  <input v-model="templateForm.participant_ids" type="checkbox" :value="person.id" />
                  <span>{{ person.display_name }}</span>
                  <small>{{ person.username }}</small>
                </label>
              </div>
            </div>
            <div v-else class="role-empty-tip">请先点击上方角色标签，再选择填写人员。</div>
          </div>
          <div class="selector-card">
            <div class="selector-title">
              <span>被评人</span>
              <em>已选 {{ templateForm.reviewee_ids.length }} 人</em>
            </div>
            <div class="role-tabs">
              <button v-for="group in peopleGroups" :key="`r-tab-${group.role}`" type="button"
                :class="{ active: rolePickerState.templateReviewees === group.role }"
                @click="rolePickerState.templateReviewees = group.role">
                {{ group.label }}
                <em>{{ selectedCount(templateForm.reviewee_ids, group.people) }}/{{ group.people.length }}</em>
              </button>
            </div>
            <div v-if="getActiveGroup(rolePickerState.templateReviewees)" class="role-picker-panel">
              <div class="role-picker-head">
                <strong>{{ getActiveGroup(rolePickerState.templateReviewees).label }}</strong>
                <span>{{ selectedCount(templateForm.reviewee_ids, getActiveGroup(rolePickerState.templateReviewees).people) }} / {{ getActiveGroup(rolePickerState.templateReviewees).people.length }}</span>
                <button type="button" @click="togglePeopleGroup(templateForm, 'reviewee_ids', getActiveGroup(rolePickerState.templateReviewees).people, true)">全选本组</button>
                <button type="button" @click="togglePeopleGroup(templateForm, 'reviewee_ids', getActiveGroup(rolePickerState.templateReviewees).people, false)">清空本组</button>
              </div>
              <div class="people-picker">
                <label v-for="person in getActiveGroup(rolePickerState.templateReviewees).people" :key="`r-${person.id}`"
                  :class="{ checked: templateForm.reviewee_ids.includes(person.id) }">
                  <input v-model="templateForm.reviewee_ids" type="checkbox" :value="person.id" />
                  <span>{{ person.display_name }}</span>
                  <small>{{ person.username }}</small>
                </label>
              </div>
            </div>
            <div v-else class="role-empty-tip">请先点击上方角色标签，再选择被评人。</div>
          </div>
        </div>

        <div class="items-editor">
          <div class="selector-title">
            <span>评价项目</span>
            <button class="btn btn-secondary btn-sm" type="button" @click="addTemplateItem">新增项目</button>
          </div>
          <div v-for="(item, index) in templateForm.items" :key="item.local_id" class="item-editor-row">
            <select v-model="item.item_type">
              <option value="score">星级评分</option>
              <option value="text">文本问题</option>
            </select>
            <input v-model.trim="item.title" type="text" placeholder="评价项目或问题" />
            <input v-if="item.item_type === 'score'" v-model.number="item.max_score" type="number" min="1" max="10" />
            <input v-else class="score-placeholder" type="text" value="文本回答" disabled />
            <input v-model.trim="item.description" type="text" placeholder="补充说明，可不填" />
            <button class="btn btn-danger btn-sm" type="button" @click="removeTemplateItem(index)">删除</button>
          </div>
        </div>

        <div v-if="templateDialog.error" class="form-error">{{ templateDialog.error }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" type="button" @click="closeTemplateDialog">取消</button>
          <button class="btn btn-primary" type="submit" :disabled="templateDialog.saving">
            {{ templateDialog.saving ? '保存中...' : '保存模板' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="launchDialog.visible" class="modal-backdrop">
      <form class="dialog-card launch-dialog" @submit.prevent="launchTask">
        <div class="dialog-head">
          <div>
            <span>发起任务</span>
            <h3>发起成员互评任务</h3>
          </div>
          <button type="button" class="close-btn" @click="closeLaunchDialog">×</button>
        </div>

        <div class="dialog-grid">
          <label class="form-field">
            <span>任务标题</span>
            <input v-model.trim="launchForm.title" type="text" />
          </label>
          <label class="form-field">
            <span>截止时间</span>
            <input v-model="launchForm.deadline_at" type="datetime-local" />
          </label>
          <label class="form-field wide">
            <span>任务说明</span>
            <textarea v-model.trim="launchForm.description" rows="3"></textarea>
          </label>
        </div>
        <div class="switch-row">
          <label><input v-model="launchForm.show_participation" type="checkbox" /> 展示填写人员完成进度</label>
        </div>
        <div class="selector-layout">
          <div class="selector-card">
            <div class="selector-title">
              <span>填写人员</span>
              <em>已选 {{ launchForm.participant_ids.length }} 人</em>
            </div>
            <div class="role-tabs">
              <button v-for="group in peopleGroups" :key="`lp-tab-${group.role}`" type="button"
                :class="{ active: rolePickerState.launchParticipants === group.role }"
                @click="rolePickerState.launchParticipants = group.role">
                {{ group.label }}
                <em>{{ selectedCount(launchForm.participant_ids, group.people) }}/{{ group.people.length }}</em>
              </button>
            </div>
            <div v-if="getActiveGroup(rolePickerState.launchParticipants)" class="role-picker-panel">
              <div class="role-picker-head">
                <strong>{{ getActiveGroup(rolePickerState.launchParticipants).label }}</strong>
                <span>{{ selectedCount(launchForm.participant_ids, getActiveGroup(rolePickerState.launchParticipants).people) }} / {{ getActiveGroup(rolePickerState.launchParticipants).people.length }}</span>
                <button type="button" @click="togglePeopleGroup(launchForm, 'participant_ids', getActiveGroup(rolePickerState.launchParticipants).people, true)">全选本组</button>
                <button type="button" @click="togglePeopleGroup(launchForm, 'participant_ids', getActiveGroup(rolePickerState.launchParticipants).people, false)">清空本组</button>
              </div>
              <div class="people-picker">
                <label v-for="person in getActiveGroup(rolePickerState.launchParticipants).people" :key="`lp-${person.id}`"
                  :class="{ checked: launchForm.participant_ids.includes(person.id) }">
                  <input v-model="launchForm.participant_ids" type="checkbox" :value="person.id" />
                  <span>{{ person.display_name }}</span>
                  <small>{{ person.username }}</small>
                </label>
              </div>
            </div>
            <div v-else class="role-empty-tip">请先点击上方角色标签，再选择填写人员。</div>
          </div>
          <div class="selector-card">
            <div class="selector-title">
              <span>被评人</span>
              <em>已选 {{ launchForm.reviewee_ids.length }} 人</em>
            </div>
            <div class="role-tabs">
              <button v-for="group in peopleGroups" :key="`lr-tab-${group.role}`" type="button"
                :class="{ active: rolePickerState.launchReviewees === group.role }"
                @click="rolePickerState.launchReviewees = group.role">
                {{ group.label }}
                <em>{{ selectedCount(launchForm.reviewee_ids, group.people) }}/{{ group.people.length }}</em>
              </button>
            </div>
            <div v-if="getActiveGroup(rolePickerState.launchReviewees)" class="role-picker-panel">
              <div class="role-picker-head">
                <strong>{{ getActiveGroup(rolePickerState.launchReviewees).label }}</strong>
                <span>{{ selectedCount(launchForm.reviewee_ids, getActiveGroup(rolePickerState.launchReviewees).people) }} / {{ getActiveGroup(rolePickerState.launchReviewees).people.length }}</span>
                <button type="button" @click="togglePeopleGroup(launchForm, 'reviewee_ids', getActiveGroup(rolePickerState.launchReviewees).people, true)">全选本组</button>
                <button type="button" @click="togglePeopleGroup(launchForm, 'reviewee_ids', getActiveGroup(rolePickerState.launchReviewees).people, false)">清空本组</button>
              </div>
              <div class="people-picker">
                <label v-for="person in getActiveGroup(rolePickerState.launchReviewees).people" :key="`lr-${person.id}`"
                  :class="{ checked: launchForm.reviewee_ids.includes(person.id) }">
                  <input v-model="launchForm.reviewee_ids" type="checkbox" :value="person.id" />
                  <span>{{ person.display_name }}</span>
                  <small>{{ person.username }}</small>
                </label>
              </div>
            </div>
            <div v-else class="role-empty-tip">请先点击上方角色标签，再选择被评人。</div>
          </div>
        </div>
        <div v-if="launchDialog.error" class="form-error">{{ launchDialog.error }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" type="button" @click="closeLaunchDialog">取消</button>
          <button class="btn btn-primary" type="submit" :disabled="launchDialog.saving">
            {{ launchDialog.saving ? '发起中...' : '发起任务' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="responseDialog.visible" class="modal-backdrop">
      <form class="dialog-card response-dialog" @submit.prevent="submitResponse">
        <div class="dialog-head">
          <div>
            <span>填写评价</span>
            <h3>评价 {{ responseDialog.reviewee?.display_name }}</h3>
            <p>{{ responseDialog.task?.title }}｜填写人：{{ currentUser.display_name || currentUser.real_name || currentUser.username }}</p>
          </div>
          <button type="button" class="close-btn" @click="closeResponseDialog">×</button>
        </div>

        <div class="response-form-list">
          <div v-for="item in responseDialog.task?.items || []" :key="item.id" class="response-form-item">
            <div>
              <strong>{{ item.title }}</strong>
              <p v-if="item.description">{{ item.description }}</p>
            </div>
            <div v-if="item.item_type === 'score'" class="star-row">
              <button v-for="score in Number(item.max_score || 5)" :key="score" type="button"
                :class="{ active: getAnswer(item.id).score_value >= score }" @click="setScore(item.id, score)">
                ★
              </button>
              <span>{{ getAnswer(item.id).score_value || 0 }} / {{ item.max_score || 5 }}</span>
            </div>
            <textarea v-else v-model.trim="getAnswer(item.id).text_value" rows="4" placeholder="请输入评价内容"></textarea>
          </div>
        </div>

        <div v-if="responseDialog.error" class="form-error">{{ responseDialog.error }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary" type="button" @click="closeResponseDialog">取消</button>
          <button class="btn btn-primary" type="submit" :disabled="responseDialog.saving">
            {{ responseDialog.saving ? '提交中...' : '提交评价' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onMounted, reactive, ref, watch } from 'vue'

const loading = ref(false)
const error = ref('')
const canManage = ref(false)
const people = ref([])
const templates = ref([])
const tasks = ref([])
const currentUser = reactive({ id: null, username: '', real_name: '', display_name: '' })
const message = reactive({ text: '', type: 'info' })
const page = ref(1)
const pageSize = ref(5)
const pageJumpInput = ref('')
let messageTimer = null
const rolePickerState = reactive({
  templateParticipants: '',
  templateReviewees: '',
  launchParticipants: '',
  launchReviewees: ''
})

const roleLabelMap = {
  supervisor: '督导组账号',
  quality_safety: '质安部账号',
  development_plan: '发展计划部账号',
  oil_gas: '油气事业部账号',
  area_account: '片区账号',
  station_manager: '站点账号'
}
const roleOrder = ['supervisor', 'quality_safety', 'development_plan', 'oil_gas', 'area_account', 'station_manager']

const emptyTemplateForm = () => ({
  id: null,
  title: '',
  description: '',
  default_deadline_at: '',
  show_participation: true,
  participant_ids: [],
  reviewee_ids: [],
  items: [
    { local_id: Date.now(), item_type: 'score', title: '工作配合度', description: '', max_score: 5 }
  ]
})

const templateForm = reactive(emptyTemplateForm())
const templateDialog = reactive({ visible: false, saving: false, error: '' })
const launchForm = reactive({
  template_id: null,
  title: '',
  description: '',
  deadline_at: '',
  show_participation: true,
  participant_ids: [],
  reviewee_ids: []
})
const launchDialog = reactive({ visible: false, saving: false, error: '' })
const responseDialog = reactive({
  visible: false,
  saving: false,
  error: '',
  task: null,
  reviewee: null,
  answers: []
})

const overviewCards = computed(() => {
  const activeTasks = tasks.value.filter((task) => task.status === 'active')
  const pendingCount = tasks.value.reduce((sum, task) => sum + (task.my_pending_reviewees?.length || 0), 0)
  const responseCount = tasks.value.reduce((sum, task) => sum + (task.responses?.length || 0), 0)
  return [
    { label: '进行中任务', value: activeTasks.length, desc: '当前仍可填写的互评任务' },
    { label: '待我填写', value: pendingCount, desc: '需要当前账号继续完成的评价' },
    { label: canManage.value ? '评价明细' : '我的记录', value: responseCount, desc: canManage.value ? '当前可查看的全部评价' : '我已经提交的评价' }
  ]
})

const peopleGroups = computed(() => {
  const groups = new Map()
  people.value.forEach((person) => {
    const role = person.role || 'other'
    if (!groups.has(role)) {
      groups.set(role, {
        role,
        label: roleLabelMap[role] || '其他账号',
        people: []
      })
    }
    groups.get(role).people.push(person)
  })
  return [...groups.values()].sort((a, b) => {
    const indexA = roleOrder.includes(a.role) ? roleOrder.indexOf(a.role) : 99
    const indexB = roleOrder.includes(b.role) ? roleOrder.indexOf(b.role) : 99
    return indexA - indexB || a.label.localeCompare(b.label, 'zh-Hans-CN')
  })
})

const totalPage = computed(() => Math.max(1, Math.ceil(tasks.value.length / pageSize.value)))

const paginatedTasks = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return tasks.value.slice(start, start + pageSize.value)
})

const visiblePageItems = computed(() => {
  const total = totalPage.value
  const current = page.value

  if (total <= 7) {
    return Array.from({ length: total }, (_item, index) => {
      const value = index + 1
      return { type: 'page', value, key: `page-${value}` }
    })
  }

  const pages = new Set([1, total, current, current - 1, current + 1])
  if (current <= 3) {
    pages.add(2)
    pages.add(3)
    pages.add(4)
  }
  if (current >= total - 2) {
    pages.add(total - 1)
    pages.add(total - 2)
    pages.add(total - 3)
  }

  const sortedPages = [...pages]
    .filter((value) => value >= 1 && value <= total)
    .sort((a, b) => a - b)

  const result = []
  sortedPages.forEach((value, index) => {
    const previous = sortedPages[index - 1]
    if (index > 0 && value - previous > 1) {
      result.push({ type: 'ellipsis', key: `ellipsis-${previous}-${value}` })
    }
    result.push({ type: 'page', value, key: `page-${value}` })
  })

  return result
})

const setMessage = (text, type = 'info') => {
  if (messageTimer) window.clearTimeout(messageTimer)
  message.text = text
  message.type = type
  if (!text) return
  messageTimer = window.setTimeout(() => {
    message.text = ''
  }, 2600)
}

const taskProgressPercent = (task) => {
  const total = Number(task.progress?.participant_count || 0)
  if (!total) return 0
  return Math.min(100, Math.round((Number(task.progress?.completed_count || 0) / total) * 100))
}

const getPersonById = (list, id) => list.find((item) => String(item.id) === String(id)) || { id, display_name: `用户${id}` }

const getActiveGroup = (role) => peopleGroups.value.find((group) => group.role === role) || null

const selectedCount = (selectedIds, groupPeople) => {
  const selectedSet = new Set((selectedIds || []).map((id) => Number(id)))
  return groupPeople.filter((person) => selectedSet.has(Number(person.id))).length
}

const togglePeopleGroup = (form, field, groupPeople, checked) => {
  const current = new Set((form[field] || []).map((id) => Number(id)))
  groupPeople.forEach((person) => {
    const personId = Number(person.id)
    if (checked) {
      current.add(personId)
    } else {
      current.delete(personId)
    }
  })
  form[field] = [...current]
}

const goToPage = (targetPage) => {
  const normalizedPage = Number.parseInt(targetPage, 10)
  if (!Number.isFinite(normalizedPage)) return
  page.value = Math.min(Math.max(normalizedPage, 1), totalPage.value)
}

const prevPage = () => {
  goToPage(page.value - 1)
}

const nextPage = () => {
  goToPage(page.value + 1)
}

const jumpToInputPage = () => {
  goToPage(pageJumpInput.value)
  pageJumpInput.value = ''
}

const fetchDashboard = async () => {
  try {
    loading.value = true
    error.value = ''
    const response = await axios.get('/api/assessment/peer-reviews', { params: { _ts: Date.now() } })
    canManage.value = Boolean(response.data?.can_manage)
    people.value = response.data?.people || []
    templates.value = response.data?.templates || []
    tasks.value = response.data?.tasks || []
    Object.assign(currentUser, response.data?.current_user || {})
  } catch (err) {
    error.value = err?.response?.data?.error || '成员互评数据加载失败。'
  } finally {
    loading.value = false
  }
}

const resetTemplateForm = () => {
  Object.assign(templateForm, emptyTemplateForm())
}

const resetRolePickerState = (prefix) => {
  if (prefix === 'template') {
    rolePickerState.templateParticipants = ''
    rolePickerState.templateReviewees = ''
  }
  if (prefix === 'launch') {
    rolePickerState.launchParticipants = ''
    rolePickerState.launchReviewees = ''
  }
}

const openTemplateDialog = (template = null) => {
  resetTemplateForm()
  resetRolePickerState('template')
  if (template) {
    Object.assign(templateForm, {
      id: template.id,
      title: template.title || '',
      description: template.description || '',
      default_deadline_at: template.default_deadline_at || '',
      show_participation: Boolean(template.show_participation),
      participant_ids: [...(template.participant_ids || [])],
      reviewee_ids: [...(template.reviewee_ids || [])],
      items: (template.items || []).map((item) => ({
        ...item,
        local_id: `${item.id}-${Date.now()}`
      }))
    })
  }
  templateDialog.error = ''
  templateDialog.visible = true
}

const closeTemplateDialog = () => {
  if (templateDialog.saving) return
  templateDialog.visible = false
}

const addTemplateItem = () => {
  templateForm.items.push({
    local_id: `${Date.now()}-${Math.random()}`,
    item_type: 'score',
    title: '',
    description: '',
    max_score: 5
  })
}

const removeTemplateItem = (index) => {
  if (templateForm.items.length <= 1) {
    templateDialog.error = '至少保留一个评价项目。'
    return
  }
  templateForm.items.splice(index, 1)
}

const validateTemplateForm = () => {
  if (!templateForm.title) return '请填写模板标题。'
  if (!templateForm.participant_ids.length) return '请选择填写人员。'
  if (!templateForm.reviewee_ids.length) return '请选择被评人。'
  if (!templateForm.items.some((item) => item.title)) return '请至少填写一个评价项目。'
  return ''
}

const saveTemplate = async () => {
  const validation = validateTemplateForm()
  if (validation) {
    templateDialog.error = validation
    return
  }
  try {
    templateDialog.saving = true
    templateDialog.error = ''
    const payload = {
      ...templateForm,
      show_reviewer: Boolean(templateForm.show_participation),
      items: templateForm.items.map((item) => ({ ...item }))
    }
    const response = templateForm.id
      ? await axios.put(`/api/assessment/peer-reviews/templates/${templateForm.id}`, payload)
      : await axios.post('/api/assessment/peer-reviews/templates', payload)
    setMessage(response.data?.message || '模板已保存。', 'success')
    templateDialog.visible = false
    await fetchDashboard()
  } catch (err) {
    templateDialog.error = err?.response?.data?.error || '模板保存失败。'
  } finally {
    templateDialog.saving = false
  }
}

const deleteTemplate = async (template) => {
  if (!window.confirm(`确定删除模板【${template.title}】吗？已发起的历史互评任务不会被删除。`)) return
  try {
    const response = await axios.delete(`/api/assessment/peer-reviews/templates/${template.id}`)
    setMessage(response.data?.message || '模板已删除。', 'success')
    await fetchDashboard()
  } catch (err) {
    setMessage(err?.response?.data?.error || '模板删除失败。', 'error')
  }
}

const openLaunchDialog = (template) => {
  const base = template || templates.value[0]
  if (!base) {
    setMessage('请先创建一个互评模板。', 'error')
    return
  }
  launchForm.template_id = base?.id
  launchForm.title = base?.title || ''
  launchForm.description = base?.description || ''
  launchForm.deadline_at = base?.default_deadline_at || ''
  launchForm.show_participation = Boolean(base?.show_participation ?? true)
  launchForm.participant_ids = [...(base?.participant_ids || [])]
  launchForm.reviewee_ids = [...(base?.reviewee_ids || [])]
  resetRolePickerState('launch')
  launchDialog.error = ''
  launchDialog.visible = true
}

const closeLaunchDialog = () => {
  if (launchDialog.saving) return
  launchDialog.visible = false
}

const launchTask = async () => {
  if (!launchForm.title) {
    launchDialog.error = '请填写任务标题。'
    return
  }
  if (!launchForm.participant_ids.length || !launchForm.reviewee_ids.length) {
    launchDialog.error = '请配置填写人员和被评人。'
    return
  }
  try {
    launchDialog.saving = true
    launchDialog.error = ''
    const response = await axios.post('/api/assessment/peer-reviews/tasks', {
      ...launchForm,
      show_reviewer: Boolean(launchForm.show_participation)
    })
    setMessage(response.data?.message || '任务已发起。', 'success')
    launchDialog.visible = false
    await fetchDashboard()
  } catch (err) {
    launchDialog.error = err?.response?.data?.error || '任务发起失败。'
  } finally {
    launchDialog.saving = false
  }
}

const updateTaskStatus = async (task, status) => {
  try {
    const response = await axios.put(`/api/assessment/peer-reviews/tasks/${task.id}/status`, { status })
    setMessage(response.data?.message || '任务状态已更新。', 'success')
    await fetchDashboard()
  } catch (err) {
    setMessage(err?.response?.data?.error || '任务状态更新失败。', 'error')
  }
}

const deleteTask = async (task) => {
  if (!window.confirm(`确定删除互评任务【${task.title}】吗？该任务下已提交的评价记录也会一起删除。`)) return
  try {
    const response = await axios.delete(`/api/assessment/peer-reviews/tasks/${task.id}`)
    setMessage(response.data?.message || '任务已删除。', 'success')
    await fetchDashboard()
    window.dispatchEvent(new Event('peer-review-pending-refresh'))
  } catch (err) {
    setMessage(err?.response?.data?.error || '任务删除失败。', 'error')
  }
}

const openResponseDialog = (task, reviewee) => {
  if (!reviewee?.id) return
  responseDialog.task = task
  responseDialog.reviewee = reviewee
  const existing = (task.responses || []).find((response) => (
    String(response.reviewer_id) === String(currentUser.id) &&
    String(response.reviewee_id) === String(reviewee.id)
  ))
  responseDialog.answers = (task.items || []).map((item) => {
    const oldAnswer = existing?.items?.find((answer) => String(answer.task_item_id) === String(item.id))
    return {
      task_item_id: item.id,
      item_type: item.item_type,
      score_value: oldAnswer?.score_value || 0,
      text_value: oldAnswer?.text_value || ''
    }
  })
  responseDialog.error = ''
  responseDialog.visible = true
}

const closeResponseDialog = () => {
  if (responseDialog.saving) return
  responseDialog.visible = false
}

const getAnswer = (taskItemId) => {
  let answer = responseDialog.answers.find((item) => String(item.task_item_id) === String(taskItemId))
  if (!answer) {
    answer = { task_item_id: taskItemId, item_type: 'score', score_value: 0, text_value: '' }
    responseDialog.answers.push(answer)
  }
  return answer
}

const setScore = (taskItemId, score) => {
  getAnswer(taskItemId).score_value = score
}

const submitResponse = async () => {
  try {
    responseDialog.saving = true
    responseDialog.error = ''
    const response = await axios.post('/api/assessment/peer-reviews/responses', {
      task_id: responseDialog.task?.id,
      reviewee_id: responseDialog.reviewee?.id,
      answers: responseDialog.answers
    })
    setMessage(response.data?.message || '评价已提交。', 'success')
    responseDialog.visible = false
    await fetchDashboard()
    window.dispatchEvent(new Event('peer-review-pending-refresh'))
  } catch (err) {
    responseDialog.error = err?.response?.data?.error || '评价提交失败。'
  } finally {
    responseDialog.saving = false
  }
}

watch([tasks, pageSize], () => {
  if (page.value > totalPage.value) page.value = totalPage.value
})

onMounted(fetchDashboard)
</script>

<style scoped>
.peer-review-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.review-hero,
.filter-card,
.task-card,
.template-card,
.empty-card,
.state-card,
.message-card,
.overview-card {
  border: 1px solid #dbe4ee;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
}

.review-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 28px;
  background:
    radial-gradient(circle at 88% 10%, rgba(20, 184, 166, 0.16), transparent 30%),
    linear-gradient(135deg, #f8fffb 0%, #ffffff 58%, #eef7ff 100%);
}

.page-kicker,
.section-title span,
.dialog-head span {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 900;
}

.review-hero h2 {
  margin: 14px 0 8px;
  color: #0f172a;
  font-size: 34px;
}

.review-hero p,
.task-card p,
.template-card p,
.muted-text,
.finished-tip {
  color: #64748b;
  line-height: 1.7;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.btn {
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid #d7e0ea;
  border-radius: 12px;
  background: #fff;
  color: #334155;
  font-weight: 900;
  cursor: pointer;
}

.btn-sm {
  min-height: 32px;
  padding: 0 10px;
  font-size: 12px;
}

.btn-primary {
  border-color: #0f766e;
  background: #0f766e;
  color: #fff;
}

.btn-secondary {
  background: #f8fafc;
}

.btn-danger {
  border-color: #fecaca;
  color: #dc2626;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.overview-card {
  padding: 18px;
}

.overview-card span,
.task-meta-grid span,
.answer-item span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.overview-card strong {
  display: block;
  margin: 8px 0 4px;
  color: #0f172a;
  font-size: 30px;
}

.overview-card small {
  color: #64748b;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin: 8px 0 14px;
}

.section-title h3 {
  margin: 8px 0 0;
  color: #0f172a;
  font-size: 24px;
}

.section-title em {
  font-style: normal;
  color: #64748b;
  font-weight: 900;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 16px;
}

.task-card,
.template-card {
  padding: 20px;
}

.task-card-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 16px;
  align-items: flex-start;
}

.task-status-row,
.template-stats,
.template-actions,
.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.task-card h4,
.template-card h4 {
  margin: 12px 0 8px;
  color: #0f172a;
  font-size: 20px;
}

.status-pill,
.deadline-pill,
.person-chip,
.template-stats span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 900;
}

.status-pill.active {
  background: #dcfce7;
  color: #15803d;
}

.status-pill.closed {
  background: #e2e8f0;
  color: #475569;
}

.deadline-pill {
  background: #fff7ed;
  color: #c2410c;
}

.progress-block,
.reviewee-panel,
.response-panel {
  margin-top: 14px;
  padding: 14px;
  border-radius: 18px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.progress-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #0f172a;
  font-weight: 900;
}

.progress-track {
  height: 10px;
  margin: 10px 0;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0f766e, #22c55e);
}

.person-chip.done {
  background: #ecfdf5;
  color: #047857;
}

.person-chip.pending {
  background: #fff7ed;
  color: #c2410c;
}

.progress-people-board {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

.progress-people-row {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 10px;
  align-items: flex-start;
}

.progress-people-row em {
  padding-top: 5px;
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  font-weight: 950;
}

.pending-chip-list {
  opacity: 0.95;
}

.task-status-switch {
  display: inline-grid;
  grid-template-columns: 44px auto;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  font-weight: 950;
  cursor: pointer;
  white-space: nowrap;
}

.task-status-switch input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.task-status-switch span {
  position: relative;
  width: 44px;
  height: 24px;
  border-radius: 999px;
  background: #cbd5e1;
  transition: background 0.18s ease;
}

.task-status-switch span::after {
  content: "";
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 3px 10px rgba(15, 23, 42, 0.22);
  transition: transform 0.18s ease;
}

.task-status-switch.active {
  border-color: #99f6e4;
  background: #f0fdfa;
  color: #0f766e;
}

.task-status-switch.active span {
  background: #0f766e;
}

.task-status-switch.active span::after {
  transform: translateX(20px);
}

.task-delete-btn {
  height: 42px;
  padding: 0 12px;
  border: 1px solid #fecaca;
  border-radius: 999px;
  background: #fff7f7;
  color: #dc2626;
  font-size: 12px;
  font-weight: 950;
  cursor: pointer;
}

.task-delete-btn:hover {
  background: #fee2e2;
}

.task-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.task-meta-grid div,
.answer-item {
  padding: 12px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.task-meta-grid strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
}

.mini-title,
.selector-title {
  margin-bottom: 10px;
  color: #0f172a;
  font-weight: 950;
}

.reviewee-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
}

.reviewee-btn {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #99f6e4;
  border-radius: 14px;
  background: #f0fdfa;
  color: #0f766e;
  font-weight: 900;
  cursor: pointer;
}

.reviewee-btn em {
  font-style: normal;
  color: #0f766e;
}

.response-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.response-card {
  padding: 12px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.response-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.response-head span {
  color: #64748b;
  font-size: 12px;
}

.answer-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.answer-item strong,
.answer-item p {
  display: block;
  margin: 6px 0 0;
  color: #0f172a;
}

.template-section {
  margin-top: 4px;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 14px;
}

.template-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.empty-card,
.state-card,
.message-card {
  padding: 28px;
  text-align: center;
}

.empty-card.compact {
  padding: 20px;
}

.message-card.error,
.form-error {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #dc2626;
}

.message-toast {
  position: fixed;
  z-index: 1500;
  left: 50%;
  top: 22px;
  transform: translateX(-50%);
  padding: 12px 18px;
  border-radius: 999px;
  background: #0f172a;
  color: #fff;
  font-weight: 900;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.2);
}

.message-toast.success {
  background: #047857;
}

.message-toast.error {
  background: #dc2626;
}

.state-orb {
  width: 48px;
  height: 48px;
  margin: 0 auto 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, #99f6e4, #dbeafe);
}

.state-orb.loading {
  animation: pulse 1.4s ease-in-out infinite;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 22px;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(8px);
}

.dialog-card {
  width: min(1280px, calc(100vw - 44px));
  max-height: calc(100vh - 44px);
  overflow: auto;
  padding: 24px;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.22);
}

.response-dialog {
  width: min(760px, calc(100vw - 44px));
}

.dialog-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.dialog-head h3 {
  margin: 10px 0 4px;
  color: #0f172a;
  font-size: 24px;
}

.dialog-head p {
  margin: 0;
  color: #64748b;
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

.dialog-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-field.wide {
  grid-column: 1 / -1;
}

.form-field span {
  color: #334155;
  font-size: 13px;
  font-weight: 900;
}

.form-field input,
.form-field textarea,
.item-editor-row input,
.item-editor-row select {
  width: 100%;
  border: 1px solid #d7e0ea;
  border-radius: 12px;
  padding: 10px 12px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
}

.switch-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 14px 0;
  padding: 12px;
  border-radius: 16px;
  background: #f8fafc;
}

.switch-row label {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  color: #334155;
  font-weight: 900;
}

.selector-layout {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 14px;
}

.selector-card,
.items-editor {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #f8fafc;
}

.people-picker {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
}

.people-picker label {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  padding: 9px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  color: #334155;
  font-weight: 800;
}

.people-picker label small {
  grid-column: 2;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 800;
}

.people-picker label.checked {
  border-color: #0f766e;
  background: #f0fdfa;
  color: #0f766e;
}

.items-editor {
  margin-top: 14px;
}

.items-editor .selector-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.selector-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.selector-title em {
  color: #64748b;
  font-size: 12px;
  font-style: normal;
  font-weight: 900;
}

.role-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.role-tabs button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 11px;
  border: 1px solid #dbe4ee;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  font-size: 12px;
  font-weight: 950;
  cursor: pointer;
}

.role-tabs button em {
  color: #94a3b8;
  font-size: 11px;
  font-style: normal;
}

.role-tabs button.active {
  border-color: #0f766e;
  background: #f0fdfa;
  color: #0f766e;
}

.role-tabs button.active em {
  color: #0f766e;
}

.role-picker-panel,
.role-empty-tip {
  min-height: 238px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
}

.role-empty-tip {
  display: grid;
  place-items: center;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 900;
  text-align: center;
}

.role-picker-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}

.role-picker-head strong {
  color: #0f172a;
  font-size: 14px;
}

.role-picker-head span {
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.role-picker-head button {
  height: 28px;
  padding: 0 9px;
  border: 1px solid #dbe4ee;
  border-radius: 999px;
  background: #f8fafc;
  color: #0f766e;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}

.item-editor-row {
  display: grid;
  grid-template-columns: 132px minmax(220px, 1.15fr) 104px minmax(220px, 1fr) 72px;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
}

.score-placeholder {
  color: #94a3b8 !important;
  background: #f1f5f9 !important;
}

.response-form-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.response-form-item {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.response-form-item strong {
  color: #0f172a;
}

.response-form-item p {
  color: #64748b;
  margin: 5px 0 0;
}

.star-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.star-row button {
  border: 0;
  background: transparent;
  color: #cbd5e1;
  font-size: 28px;
  cursor: pointer;
}

.star-row button.active {
  color: #f59e0b;
}

.star-row span {
  margin-left: 8px;
  color: #475569;
  font-weight: 900;
}

.response-form-item textarea {
  width: 100%;
  margin-top: 12px;
  border: 1px solid #d7e0ea;
  border-radius: 14px;
  padding: 12px;
}

.form-error {
  margin-top: 14px;
  padding: 12px;
  border-radius: 14px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #e2e8f0;
}

.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 20px;
}

.pagination-summary {
  color: #475569;
  font-size: 14px;
  font-weight: 950;
}

.pagination-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.pagination-size-control,
.pagination-nav-row,
.pagination-page-list,
.pagination-jump {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.pagination-size-control label,
.pagination-jump span {
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
  white-space: nowrap;
}

.pagination-controls select,
.pagination-jump input {
  height: 40px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0 10px;
  background: #fff;
  color: #0f172a;
  font-size: 14px;
}

.pagination-jump input {
  width: 78px;
  text-align: center;
}

.pagination-btn,
.pagination-jump-btn {
  min-width: 72px;
}

.pagination-page-list {
  padding: 4px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
}

.pagination-page-btn {
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #475569;
  font-size: 13px;
  font-weight: 900;
  cursor: pointer;
  transition: all 0.18s ease;
}

.pagination-page-btn:hover {
  background: #e0edff;
  color: #1d4ed8;
}

.pagination-page-btn.active {
  background: #2563eb;
  color: #fff;
  box-shadow: 0 8px 16px rgba(37, 99, 235, 0.22);
}

.pagination-ellipsis {
  min-width: 28px;
  color: #94a3b8;
  font-weight: 900;
  line-height: 34px;
  text-align: center;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.75; }
  50% { transform: scale(1.08); opacity: 1; }
}

@media (max-width: 900px) {
  .review-hero,
  .section-title,
  .response-head {
    flex-direction: column;
  }

  .review-hero {
    padding: 20px;
  }

  .review-hero h2 {
    font-size: 28px;
  }

  .overview-grid,
  .task-meta-grid,
  .dialog-grid,
  .selector-layout {
    grid-template-columns: 1fr;
  }

  .task-card {
    padding: 16px;
  }

  .task-card-head {
    grid-template-columns: 1fr;
  }

  .task-status-switch,
  .task-delete-btn {
    justify-self: flex-start;
  }

  .progress-people-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .item-editor-row {
    grid-template-columns: 1fr;
  }

  .task-grid {
    grid-template-columns: 1fr;
  }

  .modal-backdrop {
    align-items: flex-end;
    padding: 10px;
  }

  .dialog-card {
    width: 100%;
    max-height: calc(100vh - 20px);
    padding: 18px;
    border-radius: 22px;
  }

  .dialog-head {
    align-items: flex-start;
  }

  .role-picker-head {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .role-picker-head button {
    min-width: 58px;
  }

  .people-picker {
    grid-template-columns: 1fr;
  }

  .pagination-bar {
    align-items: stretch;
  }

  .pagination-controls {
    justify-content: flex-start;
    width: 100%;
  }

  .pagination-page-list {
    max-width: 100%;
    overflow-x: auto;
    justify-content: flex-start;
  }

  .pagination-page-btn {
    flex: 0 0 auto;
  }
}
</style>
