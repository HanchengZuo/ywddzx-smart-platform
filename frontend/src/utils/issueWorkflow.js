export const isUnableRectification = value => ['站经无法整改', '站级无法整改', '站经理无法整改'].includes(value)
export const isReviewReturned = value => ['整改不通过', '驳回站级无法整改'].includes(value)
export const reviewOptionsFor = result => isUnableRectification(result)
  ? ['通过站级无法整改', '驳回站级无法整改']
  : ['整改通过', '整改不通过']
export const reviewRequiresPhoto = result => result === '整改通过'

export const rectificationReturnKind = item => item?.appeal_rejected ? 'appeal' : isReviewReturned(item?.review_result) ? 'review' : ''

export const rectificationReturnNotices = items => {
  const counts = { appeal: 0, review: 0 }
  for (const item of items) {
    const kind = rectificationReturnKind(item)
    if (kind) counts[kind]++
  }
  return [
    {
      kind: 'appeal', count: counts.appeal, label: '申诉驳回提醒',
      title: `有 ${counts.appeal} 条问题申诉未通过，需要继续整改`,
      description: '片区或质安部未通过申诉，问题已返回待整改。请查看对应的申诉驳回原因和问题流转记录，按要求提交整改；同一问题不能再次发起申诉。'
    },
    {
      kind: 'review', count: counts.review, label: '复核退回提醒',
      title: `有 ${counts.review} 条问题复核未通过，需要重新整改`,
      description: '督导组未通过上一轮整改或站级无法整改申请的复核。请先查看复核退回原因和问题流转记录，再重新提交整改。'
    }
  ].filter(notice => notice.count > 0)
}

export const rectificationDraftFor = (item, resolvePhoto = path => path) => {
  const returned = Boolean(rectificationReturnKind(item))
  return {
    rectificationResult: returned ? '' : isUnableRectification(item.rectification_result) ? '站经无法整改' : item.rectification_result === '已整改' ? '已整改' : '',
    rectificationNote: returned ? '' : item.rectification_note || '',
    rectificationPhotoFile: null,
    rectificationPhotoPreview: !returned && item.rectification_photo ? resolvePhoto(item.rectification_photo) : ''
  }
}
