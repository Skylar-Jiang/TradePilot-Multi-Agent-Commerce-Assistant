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

type PrintableReport = {
  title: string
  reportId: string
  version?: number
  contentHtml: string
}

const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (character) => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
})[character] ?? character)

export function buildPrintableReportDocument({ title, reportId, version, contentHtml }: PrintableReport): string {
  const versionLabel = version ? ` · V${version}` : ''

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(title)}</title>
  <style>
    @page { margin: 16mm; }
    * { box-sizing: border-box; }
    body { margin: 0; color: #18222d; background: #fff; font: 14px/1.8 "Noto Sans SC", "Microsoft YaHei", sans-serif; }
    header { margin-bottom: 28px; padding-bottom: 16px; border-bottom: 1px solid #d8dee8; }
    h1 { margin: 0 0 8px; font: 600 28px/1.3 "Noto Serif SC", "Microsoft YaHei", serif; }
    header p { margin: 0; color: #617085; font-size: 11px; }
    article h1, article h2, article h3 { color: #18222d; font-family: "Noto Serif SC", "Microsoft YaHei", serif; line-height: 1.4; }
    article h1 { margin-top: 0; font-size: 26px; }
    article h2 { margin-top: 28px; padding-bottom: 7px; border-bottom: 1px solid #d8dee8; font-size: 20px; }
    article h3 { margin-top: 22px; font-size: 16px; }
    p, li { font-size: 14px; }
    a { color: #1757b8; }
    code { padding: 2px 4px; border-radius: 3px; color: #1d4e89; background: #eef3f9; }
    pre { overflow: auto; padding: 12px; color: #f2f6fb; background: #142235; white-space: pre-wrap; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { padding: 8px; border: 1px solid #d8dee8; text-align: left; vertical-align: top; }
    th { background: #f2f5f9; }
  </style>
</head>
<body>
  <header><h1>${escapeHtml(title)}</h1><p>报告编号：${escapeHtml(reportId)}${versionLabel}</p></header>
  <article>${contentHtml}</article>
</body>
</html>`
}

export function printReportDocument(report: PrintableReport): void {
  const printWindow = window.open('', '_blank', 'width=960,height=760')
  if (!printWindow) return

  printWindow.document.write(buildPrintableReportDocument(report))
  printWindow.document.close()
  printWindow.setTimeout(() => {
    printWindow.focus()
    printWindow.print()
  }, 0)
}
