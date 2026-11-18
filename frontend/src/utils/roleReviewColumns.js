export const roleReviewGroups = [
  { key: 'area', label: '片区' }, { key: 'department', label: '非油事业部' }, { key: 'field', label: '盛大' },
]
export const roleReviewColumns = roleReviewGroups.flatMap(group => [
  { suffix: 'result', title: '结果', width: 160 }, { suffix: 'note', title: '说明', width: 240 },
  { suffix: 'reviewer', title: '人员', width: 200 }, { suffix: 'at', title: '时间', width: 160 },
  { suffix: 'photo', title: '照片', width: 128, photo: true },
].map(field => ({ ...field, key: `${group.key}_review_${field.suffix}`,
  label: `${group.label}问题复核${field.title}`, group: `${group.label}复核` })))
