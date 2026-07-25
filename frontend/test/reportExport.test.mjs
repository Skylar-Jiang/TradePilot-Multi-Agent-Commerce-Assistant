import assert from 'node:assert/strict'
import test from 'node:test'

import { markdownDownloadFilename } from '../src/reportExport.ts'

test('creates a safe Markdown filename from a report id', () => {
  assert.equal(
    markdownDownloadFilename('04CB1EDF-863C-4172-91DE-AD0B9A131E82'),
    'tradepilot-report-04cb1edf-863c-4172-91de-ad0b9a131e82.md',
  )
})

test('uses a fallback Markdown filename when the report id is missing', () => {
  assert.equal(markdownDownloadFilename(''), 'tradepilot-report.md')
})
