<template>
  <div v-if="rows.length" class="region-table">
    <table>
      <thead>
        <tr>
          <th>片区 / 单位</th>
          <th>登记问题</th>
          <th>有问题站点</th>
          <th>在库问题</th>
          <th>待审核</th>
          <th>审核进度</th>
          <th>明细</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.region">
          <td>{{ row.region }}</td>
          <td>{{ row.registered }}</td>
          <td>{{ row.stations }}</td>
          <td>{{ row.live }}</td>
          <td>
            <span :class="{ pending: row.pending_audit }">{{ row.pending_audit }}</span>
          </td>
          <td>
            <div class="progress">
              <i
                :style="{ width: `${row.registered ? (row.reviewed / row.registered) * 100 : 0}%` }"
              ></i>
            </div>
            <small>{{
              row.registered ? `${((row.reviewed / row.registered) * 100).toFixed(1)}%` : '—'
            }}</small>
          </td>
          <td>
            <button :disabled="!row.registered" @click="$emit('open', row.region)">查看</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <p v-else class="empty">当前范围暂无片区数据</p>
</template>
<script setup>
defineProps({ rows: { type: Array, default: () => [] } })
defineEmits(['open'])
</script>
<style scoped>
.region-table {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  white-space: nowrap;
  text-align: left;
  font-size: 13px;
}
th {
  color: #6a7e94;
  font-size: 11px;
  font-weight: 600;
  background: #f4f8fb;
  padding: 12px 16px;
}
td {
  padding: 15px 16px;
  border-bottom: 1px solid #edf2f6;
  font-variant-numeric: tabular-nums;
}
td:first-child {
  font-weight: 650;
  color: #294663;
}
.progress {
  display: inline-block;
  vertical-align: middle;
  width: 65px;
  height: 5px;
  background: #e8f0f2;
  margin-right: 8px;
  border-radius: 4px;
  overflow: hidden;
}
.progress i {
  height: 100%;
  display: block;
  background: #198c7f;
}
small {
  font-size: 11px;
  color: #58748a;
}
.pending {
  color: #ae6424;
  font-weight: 700;
}
button {
  border: 0;
  background: #edf5fa;
  color: #147da5;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
}
button:disabled {
  opacity: 0.4;
  cursor: default;
}
button:focus-visible {
  outline: 2px solid #147da5;
}
.empty {
  text-align: center;
  padding: 25px;
  color: #64758b;
  font-size: 13px;
}
</style>
