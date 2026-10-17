export const routingKey = (config) => JSON.stringify([
  config.default_model,
  Object.entries(config.overrides || {})
    .sort(([a], [b]) => a.localeCompare(b))
])

export const groupAiScenes = (scenarios, keyword = '') => {
  const groups = new Map()
  for (const scene of scenarios) {
    if (keyword && !`${scene.group}${scene.name}${scene.description}`.includes(keyword)) continue
    if (!groups.has(scene.group)) groups.set(scene.group, [])
    groups.get(scene.group).push(scene)
  }
  return [...groups].map(([name, items]) => ({ name, items }))
}
