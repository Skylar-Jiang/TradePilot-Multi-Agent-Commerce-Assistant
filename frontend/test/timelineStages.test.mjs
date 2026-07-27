import assert from 'node:assert/strict'
import test from 'node:test'

import { summarizeTimelineStage } from '../src/timelineStages.ts'

const stage = (status, duration_ms) => ({ status, duration_ms })

test('maps the statistics workflow node to its persisted statistics stage', () => {
  const summary = summarizeTimelineStage(
    'statistics_provider',
    new Map([['statistics', stage('succeeded', 11700)]]),
  )

  assert.deepEqual(summary, { status: 'succeeded', duration_ms: 11700 })
})

test('combines the persisted peer preparation stages for the product and RAG node', () => {
  const summary = summarizeTimelineStage(
    'product_normalizer',
    new Map([
      ['image_understanding', stage('succeeded', 120)],
      ['peer_matching', stage('succeeded', 840)],
      ['rag_preparation', stage('succeeded', 360)],
    ]),
  )

  assert.deepEqual(summary, { status: 'succeeded', duration_ms: 1320 })
})

test('maps report persistence to the persisted report export stage', () => {
  const summary = summarizeTimelineStage(
    'persist_and_export',
    new Map([['report_export', stage('succeeded', 250)]]),
  )

  assert.deepEqual(summary, { status: 'succeeded', duration_ms: 250 })
})
