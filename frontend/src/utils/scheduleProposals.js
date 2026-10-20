// Keep the server's station assignments/token untouched; group only the presentation.
export function groupScheduleProposals(assignments = []) {
  const groups = new Map()
  for (const assignment of assignments) {
    const key = `${assignment.mode}:${assignment.person.id}`
    if (!groups.has(key)) groups.set(key, { ...assignment, key, stations: [] })
    const group = groups.get(key)
    group.stations.push(assignment)
    group.after = assignment.after
  }
  return [...groups.values()]
}
