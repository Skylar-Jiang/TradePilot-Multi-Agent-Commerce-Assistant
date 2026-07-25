export function markdownDownloadFilename(reportId: string): string {
  const safeReportId = reportId
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')

  return `tradepilot-report${safeReportId ? `-${safeReportId}` : ''}.md`
}

export function downloadMarkdownReport(markdown: string, reportId: string): void {
  const link = document.createElement('a')
  const url = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }))

  link.href = url
  link.download = markdownDownloadFilename(reportId)
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}
