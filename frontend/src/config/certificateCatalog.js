import { isAreaRole } from '../utils/roles.js'

export const certificatePages = [
  { path: '/certificates/register', title: '证照登记', icon: '登', description: '上传证照照片、有效期或登记无此证照，保留历次记录。' },
  { path: '/certificates/ledger', title: '证照台账', icon: '账', description: '按站点、片区和证照类型查询照片及登记历史。' },
  { path: '/certificates/reminders', title: '证照提醒', icon: '醒', description: '集中查看到期提醒、未读消息及各类证照覆盖情况。' },
]
export function canAccessCertificates(role, permissions = {}, path = '/certificates/ledger') {
  if (role === 'root' || role === 'station_manager' || isAreaRole(role)) return true
  return Boolean(permissions[path === '/certificates/register' ? 'register_all_certificates' : 'view_all_certificates'])
}
