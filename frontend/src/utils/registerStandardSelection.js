export const MAX_SELECTED_STANDARDS = 100
export const standardCode = standard => String(standard?.internal_standard_id || standard?.standard_id || '').trim()
export const isStandardSelected = (ids, standard) => ids.includes(standardCode(standard))
export const toggleStandardId = (ids, standard) => {
  const id = standardCode(standard)
  if (!id) return [...ids]
  if (ids.includes(id)) return ids.filter(value => value !== id)
  if (ids.length >= MAX_SELECTED_STANDARDS) throw new Error(`一次最多选择${MAX_SELECTED_STANDARDS}条规范。`)
  return [...ids, id]
}
export const buildRegistrationSelections = standards => standards.map(standard => standard.internal_standard_id
  ? { internal_standard_id: standardCode(standard) }
  : { standard_id: standardCode(standard), inspection_table_id: String(standard.inspection_table_id || '') })
export const registrationIssueCount = standards => new Set(standards.flatMap(standard => standard.internal_standard_id
  ? (standard.linked_externals || []).map(link => String(link.external_standard_id))
  : [standardCode(standard)])).size
export const restoreStandardIds = (form, catalog) => {
  const ids = Array.isArray(form?.standardIds) ? form.standardIds : form?.standardId ? [form.standardId] : []
  const available = new Set(catalog.map(standardCode))
  return [...new Set(ids.map(id => String(id).trim()).filter(id => available.has(id)))].slice(0, MAX_SELECTED_STANDARDS)
}
