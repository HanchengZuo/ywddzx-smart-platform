import { ref } from 'vue'

const routes = {
  cockpit: '/operations/overview',
  map: '/inspection/station-map',
}

// Tab-local state: other windows and other fullscreen pages retain their idle limits.
export const activePresentation = ref('')
export const setPresentationMode = (kind, active) => {
  if (!routes[kind]) return
  if (active) activePresentation.value = kind
  else if (activePresentation.value === kind) activePresentation.value = ''
}
export const presentationKindForRoute = (path, kind) => (routes[kind] === path ? kind : '')
export const needsPresentationRenewal = (kind, secondsRemaining) =>
  Boolean(routes[kind]) && secondsRemaining > 0 && secondsRemaining <= 30 * 60
