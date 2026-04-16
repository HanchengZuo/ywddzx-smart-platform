<template>
  <div class="page-shell">
    <div class="page-header card-surface">
      <div>
        <div class="page-kicker">督导组培训</div>
        <h2>督导组内部培训系统</h2>
      </div>
    </div>

    <template v-if="hasPermission">
      <div class="stats-grid">
        <div v-for="stat in statCards" :key="stat.label" class="card-surface stat-card">
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-trend" :class="stat.trendClass">{{ stat.trend }}</div>
        </div>
      </div>

      <div class="content-grid">
        <div class="left-column">
          <div class="card-surface content-card section-card">
            <div class="section-head">
              <div>
                <div class="section-kicker">培训框架</div>
                <h3>督导组巡检培训任务总览</h3>
              </div>
              <button class="ghost-btn" type="button">新建培训</button>
            </div>

            <div class="task-list">
              <div v-for="task in trainingTasks" :key="task.title" class="task-card">
                <div class="task-top">
                  <div>
                    <div class="task-title">{{ task.title }}</div>
                    <div class="task-meta">{{ task.stationScope }} · 截止 {{ task.deadline }}</div>
                  </div>
                  <span class="status-tag" :class="task.statusClass">{{ task.status }}</span>
                </div>

                <div class="task-progress-row">
                  <div class="task-progress-text">完成进度 {{ task.progressText }}</div>
                  <div class="task-progress-bar">
                    <div class="task-progress-fill" :style="{ width: task.progress + '%' }"></div>
                  </div>
                </div>

                <div class="task-foot">
                  <span>{{ task.module }}</span>
                  <span>{{ task.pendingText }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="card-surface content-card section-card">
            <div class="section-head compact">
              <div>
                <div class="section-kicker">覆盖情况</div>
                <h3>巡检模块学习完成率示例</h3>
              </div>
              <button class="ghost-btn" type="button">查看全部</button>
            </div>

            <div class="rate-list">
              <div v-for="station in stationRates" :key="station.name" class="rate-row">
                <div class="rate-main">
                  <div class="rate-name">{{ station.name }}</div>
                  <div class="rate-desc">{{ station.finished }} / {{ station.total }} 人完成</div>
                </div>
                <div class="rate-bar-wrap">
                  <div class="rate-bar">
                    <div class="rate-bar-fill" :style="{ width: station.rate + '%' }"></div>
                  </div>
                </div>
                <div class="rate-value">{{ station.rate }}%</div>
              </div>
            </div>
          </div>
        </div>

        <div class="right-column">
          <div class="card-surface content-card section-card">
            <div class="section-head compact">
              <div>
                <div class="section-kicker">快捷入口</div>
                <h3>常用功能</h3>
              </div>
            </div>

            <div class="quick-grid">
              <button v-for="entry in quickEntries" :key="entry.title" class="quick-entry" type="button">
                <div class="quick-icon">{{ entry.icon }}</div>
                <div class="quick-title">{{ entry.title }}</div>
                <div class="quick-desc">{{ entry.desc }}</div>
              </button>
            </div>
          </div>

          <div class="card-surface content-card section-card">
            <div class="section-head compact">
              <div>
                <div class="section-kicker">提醒事项</div>
                <h3>待处理事项</h3>
              </div>
            </div>

            <div class="todo-list">
              <div v-for="todo in todoItems" :key="todo.title" class="todo-item">
                <div class="todo-badge" :class="todo.badgeClass"></div>
                <div class="todo-content">
                  <div class="todo-title">{{ todo.title }}</div>
                  <div class="todo-desc">{{ todo.desc }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="card-surface content-card section-card highlight-card">
            <div class="section-kicker highlight-kicker">样板说明</div>
            <h3>督导组巡检培训样板页面</h3>
            <p>
              当前页面按照督导中心巡检工作框架设计，培训内容以现场巡检、远程巡检及各类专项检查为主，主要服务于约 25 名督导组成员，后续可继续扩展接入培训任务下发、签到答题、学习留痕、完成率统计、培训档案与导出等功能。
            </p>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="card-surface content-card">
      <div class="permission-card">
        <div class="permission-icon">!</div>
        <div class="permission-title">无权限访问</div>
        <div class="permission-desc">当前账号无权访问培训系统，请使用督导组账号登录后操作。</div>
      </div>
    </div>
  </div>
</template>

<script setup>
const currentRole = localStorage.getItem('user_role') || ''
const hasPermission = currentRole === 'supervisor'

const statCards = [
  { label: '培训模块数', value: '8', trend: '现场 + 远程巡检', trendClass: 'neutral' },
  { label: '应参训人数', value: '25', trend: '督导组成员全覆盖', trendClass: 'neutral' },
  { label: '已完成学习', value: '19', trend: '完成率 76%', trendClass: 'up' },
  { label: '待补训人数', value: '6', trend: '需本周跟进', trendClass: 'down' }
]

const trainingTasks = [
  {
    title: '现场巡检—充电站安全检查培训',
    stationScope: '充电站巡检模块',
    deadline: '04-28',
    status: '进行中',
    statusClass: 'processing',
    progress: 80,
    progressText: '80%',
    module: '半年覆盖',
    pendingText: '对应充电站安全检查口径'
  },
  {
    title: '现场巡检—加油站财务与设备巡检培训',
    stationScope: '加油站现场巡检模块',
    deadline: '04-30',
    status: '进行中',
    statusClass: 'processing',
    progress: 64,
    progressText: '64%',
    module: '季度 / 年度覆盖',
    pendingText: '含财务巡检、设备巡检、计量磅房'
  },
  {
    title: '远程巡检—每月全覆盖项目学习',
    stationScope: '加油站远程巡检模块',
    deadline: '05-05',
    status: '待下发',
    statusClass: 'pending',
    progress: 28,
    progressText: '28%',
    module: '每月全覆盖',
    pendingText: '含加油站现场、安全检查、手工比对、油品接卸、加油机自校'
  }
]

const stationRates = [
  { name: '现场巡检模块', finished: 11, total: 14, rate: 79 },
  { name: '远程巡检模块', finished: 9, total: 11, rate: 82 },
  { name: '专项检查模块', finished: 7, total: 10, rate: 70 },
  { name: '问题口径学习模块', finished: 8, total: 12, rate: 67 }
]

const quickEntries = [
  { icon: '框', title: '培训框架', desc: '查看现场巡检、远程巡检模块结构' },
  { icon: '发', title: '培训下发', desc: '按巡检模块创建培训任务并分配成员' },
  { icon: '题', title: '答题管理', desc: '配置巡检规范与专项检查题库' },
  { icon: '档', title: '培训档案', desc: '查看个人培训记录与学习留痕' }
]

const todoItems = [
  {
    title: '现场巡检模块仍有 6 人未完成学习',
    desc: '建议本周内完成催办并跟进学习进度。',
    badgeClass: 'warning'
  },
  {
    title: '远程巡检培训任务尚未发布签到入口',
    desc: '发布后可供成员签到并自动留痕。',
    badgeClass: 'info'
  },
  {
    title: '专项检查测验通过率低于 70%',
    desc: '建议安排补训与再次测验。',
    badgeClass: 'danger'
  }
]
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.stat-card {
  padding: 22px 24px;
}

.stat-label {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 10px;
}

.stat-value {
  font-size: 34px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.1;
}

.stat-trend {
  margin-top: 10px;
  font-size: 13px;
  font-weight: 600;
}

.stat-trend.up {
  color: #15803d;
}

.stat-trend.down {
  color: #dc2626;
}

.stat-trend.neutral {
  color: #2563eb;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 1fr);
  gap: 20px;
}

.left-column,
.right-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-card {
  padding: 24px;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.section-head.compact {
  margin-bottom: 18px;
}

.section-kicker {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 10px;
}

.section-head h3,
.highlight-card h3 {
  margin: 0;
  font-size: 24px;
  color: #0f172a;
}

.ghost-btn {
  height: 38px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.task-card {
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #f8fafc;
  padding: 18px;
}

.task-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.task-title {
  font-size: 17px;
  font-weight: 800;
  color: #0f172a;
}

.task-meta,
.task-foot {
  margin-top: 6px;
  font-size: 13px;
  color: #64748b;
}

.task-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.status-tag.processing {
  background: #eff6ff;
  color: #1d4ed8;
}

.status-tag.pending {
  background: #fff7ed;
  color: #c2410c;
}

.task-progress-row {
  margin-top: 14px;
}

.task-progress-text {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 8px;
}

.task-progress-bar,
.rate-bar {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.task-progress-fill,
.rate-bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2563eb 0%, #60a5fa 100%);
}

.rate-list,
.todo-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.rate-row {
  display: grid;
  grid-template-columns: minmax(0, 180px) minmax(0, 1fr) 56px;
  gap: 14px;
  align-items: center;
}

.rate-name,
.quick-title,
.todo-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
}

.rate-desc,
.quick-desc,
.todo-desc,
.highlight-card p {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.8;
  color: #64748b;
}

.rate-value {
  text-align: right;
  font-size: 14px;
  font-weight: 800;
  color: #0f172a;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.quick-entry {
  padding: 18px 16px;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: #f8fafc;
  text-align: left;
  cursor: pointer;
}

.quick-icon {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  color: #2563eb;
  font-size: 18px;
  font-weight: 800;
  margin-bottom: 12px;
}

.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid #e2e8f0;
}

.todo-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.todo-badge {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  margin-top: 8px;
  flex-shrink: 0;
}

.todo-badge.warning {
  background: #f59e0b;
}

.todo-badge.info {
  background: #3b82f6;
}

.todo-badge.danger {
  background: #ef4444;
}

.highlight-card {
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
}

.highlight-kicker {
  background: #dbeafe;
}

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

.permission-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 8px;
}

.permission-desc {
  font-size: 14px;
  line-height: 1.8;
  color: #64748b;
  max-width: 520px;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .page-header {
    padding: 20px;
  }

  .page-header h2 {
    font-size: 28px;
  }

  .content-card,
  .section-card {
    padding: 20px;
  }

  .stats-grid,
  .quick-grid {
    grid-template-columns: 1fr;
  }

  .rate-row {
    grid-template-columns: 1fr;
  }

  .rate-value {
    text-align: left;
  }

  .section-head,
  .task-top,
  .task-foot {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>