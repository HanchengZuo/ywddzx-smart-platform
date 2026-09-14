export const getRegisterStandardLabel = (standard) =>
  `${standard?.standard_id || ''}｜${standard?.inspection_table_name || '未关联外部检查表'}`

export const getRegisterStandardPreview = (standard) => {
  // An empty visible-field projection must never fall back to hidden full details.
  return String(standard?.register_display_text || '').replace(/\\n/g, '\n').trim() || '未设置登记展示字段'
}
