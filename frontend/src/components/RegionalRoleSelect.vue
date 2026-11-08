<template>
  <div class="regional-role-select">
    <label>
      <span>{{ label }}</span>
      <select :value="parentValue" :disabled="disabled" @change="changeParent($event.target.value)">
        <option value="">{{ placeholder }}</option>
        <template v-for="role in parentOptions" :key="role.value">
          <option :value="role.value">{{ role.label }}</option>
        </template>
      </select>
    </label>
    <label v-if="parentValue === AREA_ROLE_FAMILY" class="regional-role-child">
      <span>片区子角色</span>
      <select :value="isAreaRole(modelValue) ? modelValue : ''" :disabled="disabled"
        @change="choose($event.target.value || (allowAreaGroup ? AREA_ROLE_FAMILY : ''))">
        <option value="">{{ allowAreaGroup ? '全部片区子角色' : '请选择片区子角色' }}</option>
        <option v-for="role in children" :key="role.value" :value="role.value">{{ role.label }}</option>
      </select>
    </label>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { AREA_ROLE_FAMILY, isAreaRole, regionalRoleOptions } from '../utils/roles.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  roles: { type: Array, default: () => [] },
  label: { type: String, default: '角色' },
  placeholder: { type: String, default: '请选择角色' },
  allowAreaGroup: Boolean,
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue', 'change'])
const browsingArea = ref(false)
const children = computed(() => props.roles.filter(role => isAreaRole(role.value)))
const parentOptions = computed(() => regionalRoleOptions(props.roles))
const parentValue = computed(() => isAreaRole(props.modelValue) || props.modelValue === AREA_ROLE_FAMILY || browsingArea.value
  ? AREA_ROLE_FAMILY : props.modelValue)
watch(() => props.modelValue, (value) => {
  if (value || props.allowAreaGroup) browsingArea.value = isAreaRole(value) || value === AREA_ROLE_FAMILY
})

function choose(value) {
  if (value === props.modelValue) return
  emit('update:modelValue', value)
  emit('change', value)
}
function changeParent(value) {
  browsingArea.value = value === AREA_ROLE_FAMILY
  choose(browsingArea.value && !props.allowAreaGroup ? '' : value)
}
</script>

<style scoped>
.regional-role-select { display: grid; gap: 8px; min-width: 0; }
label { display: grid; gap: 6px; min-width: 0; color: #475569; font-size: 12px; font-weight: 700; }
select { width: 100%; min-width: 0; min-height: 38px; padding: 0 10px; border: 1px solid #cbd8e5; border-radius: 8px; background: #fff; color: #172033; font: inherit; }
select:focus-visible { outline: 2px solid #2563a8; outline-offset: 2px; }
.regional-role-child { border-inline-start: 2px solid #87b1cd; padding-inline-start: 10px; color: #224f6c; }
</style>
