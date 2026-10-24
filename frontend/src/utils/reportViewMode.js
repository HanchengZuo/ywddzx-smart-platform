export const REPORT_VIEW_MODE_KEY = 'report-studio-display-mode'

export function readReportViewMode(storage) {
  try {
    return (storage ?? globalThis.localStorage)?.getItem(REPORT_VIEW_MODE_KEY) === 'html'
      ? 'html'
      : 'ppt'
  } catch {
    return 'ppt'
  }
}

export function saveReportViewMode(mode, storage) {
  try {
    const target = storage ?? globalThis.localStorage
    target?.setItem(REPORT_VIEW_MODE_KEY, mode === 'html' ? 'html' : 'ppt')
  } catch {
    // Reading reports must still work when browser storage is unavailable.
  }
}
