<template>
  <div class="unit-evidence">
    <div class="mobile-path">
      <label
        >片区 / 单位<select v-model="unit">
          <option v-for="item in units" :key="item.unit_name" :value="item.unit_name">
            {{ item.unit_name }}
          </option>
        </select></label
      >
      <label
        >检查类别<select v-model="category">
          <option v-for="item in categories" :key="item.name" :value="item.name">
            {{ item.name }} · {{ item.count }} 项
          </option>
        </select></label
      >
    </div>
    <nav aria-label="片区单位">
      <div class="nav-heading">
        <span>01</span>
        <h4>片区 / 单位</h4>
        <small>{{ units.length }} 个单位</small>
      </div>
      <div class="nav-list">
        <button
          v-for="item in units"
          :key="item.unit_name"
          :class="{ active: unit === item.unit_name }"
          @click="unit = item.unit_name"
        >
          {{ item.unit_name
          }}<small>{{ item.categories.reduce((n, c) => n + c.count, 0) }} 项问题</small>
        </button>
        <p v-if="!units.length">当前范围暂无问题。</p>
      </div>
    </nav>
    <nav aria-label="检查类别">
      <div class="nav-heading">
        <span>02</span>
        <h4>检查类别</h4>
        <small>{{ categories.length }} 个类别</small>
      </div>
      <div class="nav-list">
        <button
          v-for="item in categories"
          :key="item.name"
          :class="{ active: category === item.name }"
          @click="category = item.name"
        >
          {{ item.name }}<small>{{ item.count }} 项 · {{ item.groups.length }} 个环节</small>
        </button>
      </div>
      <p class="nav-note">现场按新版“项目”或旧版“考察类别区域”，视频按“检查类别”；相同类别合并统计。</p>
    </nav>
    <main>
      <header>
        <div>
          <span>03 / 环节证据</span>
          <h4>{{ unit }} · {{ category }}</h4>
        </div>
        <b>{{ activeCategory?.count || 0 }} 项</b>
      </header>
      <p class="notice">
        数字及涉及站点由真实数据统计。AI只概括实际表现并选择照片；人工调整保存后，重新生成报告生效。
      </p>
      <div class="evidence-list">
        <article v-for="group in activeCategory?.groups || []" :key="group.key">
          <button
            class="group-heading"
            :aria-expanded="stage === group.key"
            @click="stage = stage === group.key ? '' : group.key"
          >
            <span
              ><b>{{ group.stage }}</b
              ><small
                >{{ group.count }} 项 ·
                {{ group.modes.map((m) => (m === 'video' ? '视频' : '现场')).join(' / ') }}</small
              ></span
            >
            <span
              >{{ ready(group) ? '已准备' : '待准备AI概括 / 选图' }}
              {{ stage === group.key ? '−' : '+' }}</span
            >
          </button>
          <div v-if="stage === group.key" class="group-content">
            <p>涉及站点：{{ group.station_names.join('、') }}</p>
            <label
              >环节问题表现概括<textarea
                :value="value(group).summary"
                maxlength="160"
                :disabled="disabled"
                rows="3"
                placeholder="尚未准备，请点击上方AI准备按钮；也可人工填写。"
                @input="edit(group, { summary: $event.target.value })"
              />
            </label>
            <p class="notice">PPT代表照片：每个环节选择1张，点击图片可放大查看。</p>
            <div class="problems">
              <article
                v-for="issue in groupIssues(group)"
                :key="issue.issue_id"
                :class="{ picked: value(group).photo_ids.includes(issue.issue_id) }"
              >
                <button class="photo" :disabled="!issue.issue_photo" @click="$emit('photo', issue)">
                  <img
                    v-if="issue.issue_photo"
                    :src="resolveImage(issue.issue_photo)"
                    :alt="`问题 #${issue.issue_id}`"
                    loading="lazy"
                  /><span v-else>暂无照片</span>
                </button>
                <div>
                  <b>#{{ issue.issue_id }} · {{ issue.station_name }}</b>
                  <p>{{ issue.description }}</p>
                </div>
                <button
                  :disabled="disabled || !issue.issue_photo"
                  :aria-pressed="value(group).photo_ids.includes(issue.issue_id)"
                  @click="
                    edit(group, {
                      photo_ids: [issue.issue_id],
                    })
                  "
                >
                  {{
                    value(group).photo_ids.includes(issue.issue_id) ? '已选入PPT' : '选为代表照片'
                  }}
                </button>
              </article>
            </div>
          </div>
        </article>
        <p v-if="!activeCategory" class="empty">请选择片区与检查类别，查看问题依据。</p>
      </div>
    </main>
  </div>
</template>
<script setup>
import { ref, computed, watch } from 'vue'
const props = defineProps({
  units: { type: Array, default: () => [] },
  issues: Array,
  overrides: Object,
  resolveImage: Function,
  disabled: Boolean,
})
const emit = defineEmits(['edit', 'photo'])
const unit = ref(''),
  category = ref(''),
  stage = ref('')
const categories = computed(
  () => props.units.find((u) => u.unit_name === unit.value)?.categories || [],
)
const activeCategory = computed(() => categories.value.find((c) => c.name === category.value))
watch(
  () => props.units,
  () => {
    if (!props.units.some((u) => u.unit_name === unit.value))
      unit.value = props.units[0]?.unit_name || ''
  },
  { immediate: true },
)
watch(
  categories,
  () => {
    if (!categories.value.some((c) => c.name === category.value))
      category.value = categories.value[0]?.name || ''
  },
  { immediate: true },
)
watch(
  activeCategory,
  () => {
    if (!activeCategory.value?.groups.some((g) => g.key === stage.value))
      stage.value = activeCategory.value?.groups[0]?.key || ''
  },
  { immediate: true },
)
const value = (group) => ({
  summary: group.summary,
  photo_ids: group.photo_ids,
  ...props.overrides?.[group.key],
})
const groupIssues = (group) =>
  (props.issues || []).filter((i) => group.issue_ids.includes(i.issue_id))
const ready = (group) =>
  Boolean(value(group).summary) &&
  (value(group).photo_ids.length > 0 || !groupIssues(group).some((i) => i.issue_photo))
function edit(group, patch) {
  if (props.disabled) return
  const changed = { ...props.overrides?.[group.key], ...patch }
  if (changed.summary === '') delete changed.summary
  emit('edit', group.key, changed)
}
</script>
<style scoped>
.unit-evidence {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 185px 220px minmax(0, 1fr);
  height: 100%;
  min-height: 0;
  color: #29465d;
}
nav {
  box-sizing: border-box;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #edf4f9;
  border-right: 1px solid #cbdce8;
}
.nav-heading {
  padding: 20px 16px 16px;
  border-bottom: 1px solid #d2e0e9;
  background: #e4eef5;
  flex-shrink: 0;
}
.nav-heading > span {
  color: #377c96;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
}
.nav-heading h4 {
  margin: 7px 0;
}
.nav-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  scrollbar-width: thin;
}
.nav-note {
  flex-shrink: 0;
  margin: 0;
  padding: 14px;
  border-top: 1px solid #d2e0e9;
  background: #e4eef5;
}
.mobile-path {
  display: none;
}
h4 {
  margin: 0 0 15px;
  font-size: 16px;
}
nav button {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  padding: 11px;
  margin-bottom: 6px;
  color: #29465d;
  font: inherit;
  cursor: pointer;
}
nav button.active {
  background: #195c7b;
  color: white;
  box-shadow: 0 3px 10px #16455d20;
}
small {
  display: block;
  font-size: 12px;
  margin-top: 6px;
  opacity: 0.8;
}
nav p,
.notice {
  font-size: 13px;
  line-height: 1.7;
  color: #597487;
}
main {
  padding: 22px;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
}
.evidence-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 2px 8px 18px 0;
  scrollbar-width: thin;
}
.empty {
  padding: 40px 12px;
  text-align: center;
  color: #718495;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 2px solid #d8e5ed;
}
header span {
  font-size: 12px;
  color: #237b94;
}
header h4 {
  margin-top: 8px;
}
.evidence-list > article {
  border: 1px solid #cbdce8;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 15px;
}
.group-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 15px;
  text-align: left;
  border: 0;
  background: #eef5fa;
  color: #184861;
  font: inherit;
  cursor: pointer;
}
.group-heading > span:last-child {
  font-size: 12px;
}
.group-content {
  padding: 15px;
}
p {
  overflow-wrap: anywhere;
  line-height: 1.65;
}
label {
  display: grid;
  gap: 9px;
  font-size: 14px;
  font-weight: 600;
}
textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 12px;
  font: inherit;
  font-weight: 400;
  color: #233f55;
  border: 1px solid #b8d0df;
  border-radius: 8px;
  resize: vertical;
}
.problems > article {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid #dce6ed;
}
.problems p {
  font-size: 14px;
  margin: 7px 0;
}
.picked {
  background: #e9f6f3;
}
.problems button {
  border: 1px solid #bdd2df;
  padding: 8px;
  border-radius: 8px;
  background: white;
  color: #216780;
  cursor: pointer;
}
.problems button[aria-pressed='true'] {
  background: #176b61;
  color: white;
}
.photo img {
  width: 90px;
  height: 80px;
  display: block;
  object-fit: contain;
}
.photo {
  padding: 0 !important;
}
.photo span {
  font-size: 12px;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
@media (max-width: 900px) {
  .unit-evidence {
    display: flex;
    flex-direction: column;
  }
  main {
    flex: 1;
    padding: 16px;
  }
  nav {
    display: none;
  }
  .mobile-path {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    padding: 14px 16px;
    flex-shrink: 0;
    border-bottom: 1px solid #d2e0e9;
    background: #e4eef5;
  }
  .mobile-path label {
    font-size: 12px;
    color: #3a6079;
    gap: 7px;
  }
  .mobile-path select {
    width: 100%;
    min-width: 0;
    padding: 10px 6px;
    background: white;
    color: #214f6a;
    border: 1px solid #b9cedd;
    border-radius: 8px;
    font: inherit;
    font-size: 13px;
  }
}
@media (max-width: 600px) {
  nav {
    padding: 12px;
  }
  nav button {
    display: inline-block;
    width: auto;
    margin: 3px;
  }
  nav small {
    display: inline;
    margin-left: 6px;
  }
  nav p {
    margin: 8px 0;
  }
  main {
    padding: 12px;
  }
  .problems > article {
    grid-template-columns: 78px minmax(0, 1fr);
  }
  .problems > article > button:last-child {
    grid-column: 2;
    justify-self: start;
  }
  .photo img {
    width: 76px;
  }
}
</style>
