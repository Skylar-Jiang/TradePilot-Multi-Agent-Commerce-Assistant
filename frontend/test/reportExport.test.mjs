import assert from 'node:assert/strict'
import test from 'node:test'

import { buildPrintableReportDocument, markdownDownloadFilename } from '../src/reportExport.ts'

test('creates a safe Markdown filename from a report id', () => {
  assert.equal(
    markdownDownloadFilename('04CB1EDF-863C-4172-91DE-AD0B9A131E82'),
    'tradepilot-report-04cb1edf-863c-4172-91de-ad0b9a131e82.md',
  )
})

test('uses a fallback Markdown filename when the report id is missing', () => {
  assert.equal(markdownDownloadFilename(''), 'tradepilot-report.md')
})

test('builds a standalone printable document containing only report content', () => {
  const document = buildPrintableReportDocument({
    title: '宠物饮水机上市分析报告',
    reportId: 'report-123',
    version: 2,
    contentHtml: '<h1>结论</h1><p>正文内容</p>',
  })

  assert.match(document, /<title>宠物饮水机上市分析报告<\/title>/)
  assert.match(document, /报告编号：report-123 · V2/)
  assert.match(document, /<article><h1>结论<\/h1><p>正文内容<\/p><\/article>/)
  assert.doesNotMatch(document, /sidebar|main-content|history-workbench/)
})
