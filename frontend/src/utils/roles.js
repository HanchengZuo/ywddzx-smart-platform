export const SUPERVISOR_ROLES = Object.freeze(['supervisor_manager', 'supervisor'])
export const isSupervisorRole = (role) => SUPERVISOR_ROLES.includes(role)
export const SUPERVISOR_ROLE_LABELS = Object.freeze({ supervisor_manager: '督导组管理人员', supervisor: '督导组组员' })

export const AREA_SPECIALIST_DEPARTMENT_LABELS = Object.freeze({
  area_oil_gas: '油气事业部', area_non_oil: '非油事业部', area_safety: '质安部'
})
export const AREA_ROLE_LABELS = Object.freeze({
  area_account: '片区经理', area_oil_gas: '油气专员', area_non_oil: '非油专员', area_safety: '安全专员'
})
export const isAreaRole = role => Object.hasOwn(AREA_ROLE_LABELS, role)
export const isAreaSpecialist = role => Object.hasOwn(AREA_SPECIALIST_DEPARTMENT_LABELS, role)
