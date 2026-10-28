// Preview moves are local only. The server validates these choices again on confirmation.
export function fieldDriverCount(group, people) {
  return (group.members || []).filter((person) =>
    (people || []).some((p) => p.id === person.id && p.has_driving_permit === true),
  ).length
}

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
  if ((eligible.execution_modes || (eligible.actual_modes || []).map(m => m.mode)).some(m => m !== mode))
    throw new Error('该学生已在对应任务站点产生巡检实绩，不能调整到此组。')
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

export function currentTeamDraft(context) {
  return {
    ...context,
    groups: context.groups.map((group) => ({
      ...group,
      members: group.members.map((p) => ({ ...p })),
    })),
    source: 'current',
    token: context.current_token,
    moves: [],
    unassigned_people: (context.unassigned_people || []).map((p) => ({ ...p })),
  }
}

export function movePreviewMember(preview, people, personId, leaderId) {
  let assignments = preview.groups.flatMap((group) => group.members)
  const eligible = new Map(people.filter((p) => p.available === true).map((p) => [p.id, p]))
  let person = assignments.find((p) => p.id === personId)
  if (!person && preview.unassigned_people?.some((p) => p.id === personId)) {
    const free = eligible.get(personId)
    if (free && !free.station_modes?.length) {
      person = {
        id: free.id,
        display_name: free.display_name,
        position: free.position,
        has_driving_permit: free.has_driving_permit === true,
        mode: 'unassigned',
        leader_id: null,
      }
      assignments = [...assignments, person]
    }
  }
  if (!person || !eligible.has(personId)) throw new Error('只能调整今日有空且已参与方案的人员。')
  const source = preview.groups.find((g) => g.members.some((p) => p.id === personId))
  const target = preview.groups.find((g) => g.mode === 'offline' && g.leader_id === leaderId)
  if (person.dispatch_locked || source?.dispatch_locked || target?.dispatch_locked)
    throw new Error(
      person.lock_reason ||
        source?.lock_reason ||
        target?.lock_reason ||
        '相关组或视频人员派工后已有对应任务的巡检实绩，不能调整。',
    )
  const manager = person.position === '管理人员'
  if (manager && leaderId !== null && leaderId !== person.id)
    throw new Error('一个外勤组只能有一位管理人员；可移至内勤视频组或独立带队。')
  if (!manager && leaderId !== null && !target)
    throw new Error('请选择已有外勤带队组或内勤视频组。')
  const mode = leaderId === null ? 'online' : 'offline'
  if (person.mode === mode && person.leader_id === leaderId) return preview
  const members = assignments.map((p) => {
    if (
      p.id !== personId &&
      !(manager && person.mode === 'offline' && p.mode === 'offline' && p.leader_id === personId)
    )
      return { ...p }
    const chosenMode = p.id === personId ? mode : 'online'
    const info = eligible.get(p.id)
    if (
      !info ||
      p.dispatch_locked
    )
      throw new Error('相关组员的档期或派工已变化，请重新载入。')
    if ((info.execution_modes || (info.actual_modes || []).map(m => m.mode)).some(m => m !== chosenMode))
      throw new Error('相关人员已有另一种巡检实绩，不能调整到此组。')
    return {
      ...p,
      mode: chosenMode,
      leader_id: p.id === personId ? leaderId : null,
      group_name:
        chosenMode === 'online'
          ? '内勤视频组'
          : manager
            ? `外勤${person.display_name}组`
            : target.name,
    }
  })
  const groups = new Map(preview.groups.map((g) => [g.name, { ...g, members: [] }]))
  for (const p of members) {
    if (!groups.has(p.group_name))
      groups.set(p.group_name, {
        name: p.group_name,
        mode: p.mode,
        leader_id: p.leader_id,
        members: [],
      })
    groups.get(p.group_name).members.push(p)
  }
  return {
    ...preview,
    groups: [...groups.values()]
      .filter((g) => g.mode === 'online' || g.members.some((p) => p.id === g.leader_id))
      .map((g) => ({
        ...g,
        members: g.members.sort(
          (a, b) => Number(b.position === '管理人员') - Number(a.position === '管理人员'),
        ),
      })),
    moves: [...(preview.moves || []), { person_id: personId, leader_id: leaderId }],
    unassigned_people: (preview.unassigned_people || []).filter((p) => p.id !== personId),
  }
}
