<template>
  <div class="station-topics">
    <aside>
      <label
        >片区 / 单位<select v-model="unit">
          <option value="">全部片区</option>
          <option v-for="name in units" :key="name">{{ name }}</option>
        </select></label
      ><label
        >选择站点<select v-model="stationId">
          <option v-for="s in visibleStations" :key="s.station_id" :value="s.station_id">
            {{ s.station_name }} · {{ s.issue_count }}项
          </option>
        </select></label
      >
      <p>本站全部问题独立分类，每类一张代表照片，不受片区特性或高频选题限制。</p>
    </aside>
    <main v-if="station">
      <header>
        <h4>{{ station.station_name }}</h4>
        <span>{{ station.issue_count }}项问题 · {{ station.groups.length }}类</span>
      </header>
      <p v-if="!station.ready" class="pending">
        本站尚未完成 AI 分类，请重新生成报告；本面板读取、保存不调用 AI。
      </p>
      <article v-for="group in station.groups" :key="group.key" class="station-group">
        <label
          >类别名称<input
            :value="choice(group).name"
            :disabled="disabled"
            maxlength="80"
            :aria-label="`类别 ${group.name}`"
            @input="change(group, { name: $event.target.value })"
        /></label>
        <span
          >{{ group.issue_ids.length }}项 · 已选代表问题 #{{
            choice(group).representative_issue_id
          }}</span
        >
        <div class="station-evidence">
          <label
            v-for="issue in members(group)"
            :key="issue.issue_id"
            :class="{ chosen: choice(group).representative_issue_id === issue.issue_id }"
          >
            <div>
              <input
                type="radio"
                :name="group.key"
                :checked="choice(group).representative_issue_id === issue.issue_id"
                :disabled="
                  disabled || (!issue.issue_photo && members(group).some((i) => i.issue_photo))
                "
                :aria-label="`选问题 ${issue.issue_id} 为代表照片`"
                @change="change(group, { representative_issue_id: issue.issue_id })"
              /><strong>#{{ issue.issue_id }}</strong
              ><b v-if="choice(group).representative_issue_id === issue.issue_id">PPT代表</b>
            </div>
            <p>{{ issue.description }}</p>
            <button v-if="issue.issue_photo" type="button" @click.prevent="$emit('photo', issue)">
              <img
                :src="resolveImage(issue.issue_photo)"
                alt="问题照片"
                loading="lazy"
              />放大查看</button
            ><small v-else>无照片</small>
          </label>
        </div>
      </article>
    </main>
    <p v-else>当前范围没有站点问题数据。</p>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
const props = defineProps({
  stations: { type: Array, default: () => [] },
  issues: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
  resolveImage: { type: Function, required: true },
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue', 'photo'])
const unit = ref(''),
  stationId = ref(null)
const units = computed(() => [...new Set(props.stations.map((s) => s.management_unit))])
const visibleStations = computed(() =>
  props.stations.filter((s) => !unit.value || s.management_unit === unit.value),
)
const station = computed(() => visibleStations.value.find((s) => s.station_id === stationId.value))
watch(
  visibleStations,
  (rows) => {
    if (!rows.some((s) => s.station_id === stationId.value)) stationId.value = rows[0]?.station_id
  },
  { immediate: true },
)
const members = (g) => props.issues.filter((i) => g.issue_ids.includes(i.issue_id))
const choice = (g) =>
  props.modelValue[g.key] || { name: g.name, representative_issue_id: g.representative_issue_id }
function change(g, value) {
  emit('update:modelValue', { ...props.modelValue, [g.key]: { ...choice(g), ...value } })
}
</script>
<style scoped>
.station-topics {
  display: grid;
  grid-template-columns: 235px 1fr;
  min-height: 0;
  overflow: auto;
  background: #f5f8fb;
}
.station-topics aside {
  padding: 20px;
  background: #eaf1f6;
  border-right: 1px solid #cbdce8;
}
.station-topics main {
  padding: 22px;
  min-width: 0;
}
.station-topics header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
}
.station-topics h4 {
  margin: 0;
  font-size: 21px;
}
.station-topics label {
  display: grid;
  gap: 10px;
  font-size: 14px;
}
.station-topics aside label {
  margin-bottom: 20px;
}
.station-topics select,
.station-topics input:not([type='radio']) {
  padding: 11px;
  border: 1px solid #b9cddd;
  border-radius: 8px;
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
  font: inherit;
  color: #21455c;
}
.station-topics p {
  line-height: 1.8;
  white-space: pre-wrap;
}
.station-topics aside p,
.station-group > span {
  font-size: 13px;
  color: #587287;
}
.station-group {
  border: 1px solid #c5d9e7;
  border-radius: 13px;
  background: #fff;
  padding: 18px;
  margin-top: 18px;
}
.station-evidence {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 15px;
}
.station-evidence > label {
  border: 1px solid #d5e0e9;
  border-radius: 10px;
  padding: 12px;
  align-content: start;
}
.station-evidence .chosen {
  border-color: #267a91;
  background: #edf8f9;
}
.station-evidence img {
  height: 140px;
  width: 100%;
  object-fit: contain;
}
.station-evidence button {
  background: white;
  border: 1px solid #c5d8e5;
  border-radius: 8px;
  color: #216b85;
  padding: 6px;
  cursor: pointer;
}
.station-evidence b {
  color: #1e6c75;
  font-size: 12px;
  margin-left: 8px;
}
.pending {
  padding: 22px;
  border: 1px dashed #a8becd;
  border-radius: 12px;
  color: #526d80;
}
@media (max-width: 700px) {
  .station-topics {
    grid-template-columns: 1fr;
  }
  .station-topics aside {
    border-right: 0;
    border-bottom: 1px solid #cbdce8;
  }
  .station-topics aside label {
    margin: 0 0 10px;
  }
  .station-evidence {
    grid-template-columns: 1fr;
  }
  .station-topics main {
    padding: 15px;
  }
}
</style>
