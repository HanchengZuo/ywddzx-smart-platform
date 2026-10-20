// Preview moves are local only. The server validates these choices again on confirmation.
export function movePreviewStudent(preview, people, studentId, leaderId) {
  const assignments = preview.groups.flatMap((group) => group.members)
  const student = assignments.find((p) => p.id === studentId && p.position === '大学生')
  const eligible = people.find((p) => p.id === studentId && p.available === true)
  if (!student || !eligible) throw new Error('只能移动今日有空且已参与预览的大学生。')
  const leader = assignments.find(
    (p) =>
      p.id === leaderId &&
      p.position === '管理人员' &&
      p.mode === 'offline' &&
      p.leader_id === p.id,
  )
  if (leaderId !== null && !leader) throw new Error('请选择预览中的外勤带队组或内勤视频组。')
  const mode = leader ? 'offline' : 'online'
  if (
    (eligible.station_modes || []).some((m) => m !== mode) ||
    (eligible.actual_modes || []).some((m) => m.mode !== mode)
  )
    throw new Error('该学生已有另一种站点派工或巡检实绩，不能调整到此组。')
  const groups = new Map(preview.groups.map((group) => [group.name, { ...group, members: [] }]))
  for (const person of assignments) {
    const member =
      person.id === studentId
        ? {
            ...person,
            mode,
            leader_id: leaderId,
            group_name: leader ? leader.group_name : '内勤视频组',
          }
        : { ...person }
    if (!groups.has(member.group_name))
      groups.set(member.group_name, {
        name: member.group_name,
        mode: member.mode,
        leader_id: member.leader_id,
        members: [],
      })
    groups.get(member.group_name).members.push(member)
  }
  for (const group of groups.values())
    group.members.sort(
      (a, b) => Number(b.position === '管理人员') - Number(a.position === '管理人员'),
    )
  return {
    ...preview,
    groups: [...groups.values()],
    student_leaders: { ...preview.student_leaders, [studentId]: leaderId },
  }
}
