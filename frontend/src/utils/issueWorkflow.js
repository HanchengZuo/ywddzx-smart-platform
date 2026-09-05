export const isUnableRectification = value => ['站经无法整改', '站级无法整改', '站经理无法整改'].includes(value)
export const isReviewReturned = value => ['整改不通过', '驳回站级无法整改'].includes(value)
export const reviewOptionsFor = result => isUnableRectification(result)
  ? ['通过站级无法整改', '驳回站级无法整改']
  : ['整改通过', '整改不通过']
export const reviewRequiresPhoto = result => result === '整改通过'

export const rectificationDraftFor = (item, resolvePhoto = path => path) => {
  const returned = isReviewReturned(item.review_result)
  return {
    rectificationResult: returned ? '' : isUnableRectification(item.rectification_result) ? '站经无法整改' : item.rectification_result === '已整改' ? '已整改' : '',
    rectificationNote: returned ? '' : item.rectification_note || '',
    rectificationPhotoFile: null,
    rectificationPhotoPreview: !returned && item.rectification_photo ? resolvePhoto(item.rectification_photo) : ''
  }
}
