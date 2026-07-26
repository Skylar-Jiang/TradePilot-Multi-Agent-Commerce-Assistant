import assert from 'node:assert/strict'
import test from 'node:test'

import { clampAssistantFloatPosition, initialAssistantFloatPosition } from '../src/assistantFloat.ts'

test('opens the assistant aligned to the right without a delayed position jump', () => {
  assert.deepEqual(
    initialAssistantFloatPosition({ viewportWidth: 1200, viewportHeight: 900, panelWidth: 430, panelHeight: 560 }),
    { x: 738, y: 112 },
  )
})

test('keeps the assistant within the visible upper portion while dragging', () => {
  assert.deepEqual(
    clampAssistantFloatPosition({
      x: 1000,
      y: 800,
      viewportWidth: 1200,
      viewportHeight: 1000,
      panelWidth: 430,
      panelHeight: 500,
    }),
    { x: 746, y: 450 },
  )
})

test('prevents the assistant from being dragged above or past the left edge', () => {
  assert.deepEqual(
    clampAssistantFloatPosition({
      x: -100,
      y: -80,
      viewportWidth: 1200,
      viewportHeight: 900,
      panelWidth: 430,
      panelHeight: 500,
    }),
    { x: 24, y: 96 },
  )
})
