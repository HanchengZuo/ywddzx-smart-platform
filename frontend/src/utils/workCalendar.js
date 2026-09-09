import axios from 'axios'
let pending
export function loadWorkCalendar() {
  if (!pending) pending = axios.get('/api/quality-work-calendar').then(({ data }) => data.days).catch(error => { pending = null; throw error })
  return pending
}
