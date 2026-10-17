export const SUPERVISOR_ROLES = Object.freeze(['supervisor_manager', 'supervisor'])
export const isSupervisorRole = (role) => SUPERVISOR_ROLES.includes(role)
export const SUPERVISOR_ROLE_LABELS = Object.freeze({ supervisor_manager: '督导组管理人员', supervisor: '督导组组员' })
