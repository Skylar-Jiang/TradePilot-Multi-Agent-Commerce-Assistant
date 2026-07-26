import assert from 'node:assert/strict'
import test from 'node:test'

import {
  clampAssistantFloatPosition,
  draggedAssistantFloatPosition,
  initialAssistantFloatPosition,
  resizedAssistantFloatSize,
} from '../src/assistantFloat.ts'

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

test('preserves the pointer grab point while dragging in viewport coordinates', () => {
  assert.deepEqual(
    draggedAssistantFloatPosition({
      pointerX: 708,
      pointerY: 362,
      grabOffsetX: 300,
      grabOffsetY: 40,
      viewportWidth: 1200,
      viewportHeight: 900,
      panelWidth: 430,
      panelHeight: 500,
    }),
    { x: 408, y: 322 },
  )
})

test('resizes within the remaining viewport without changing the panel origin', () => {
  assert.deepEqual(
    resizedAssistantFloatSize({
      pointerX: 920,
      pointerY: 780,
      startPointerX: 500,
      startPointerY: 400,
      startWidth: 430,
      startHeight: 520,
      panelX: 280,
      panelY: 112,
      viewportWidth: 1000,
      viewportHeight: 900,
    }),
    { width: 696, height: 764 },
  )
})

test('keeps the resize result usable when the pointer moves above the minimum size', () => {
  assert.deepEqual(
    resizedAssistantFloatSize({
      pointerX: 40,
      pointerY: 80,
      startPointerX: 500,
      startPointerY: 400,
      startWidth: 430,
      startHeight: 520,
      panelX: 280,
      panelY: 112,
      viewportWidth: 1200,
      viewportHeight: 900,
    }),
    { width: 340, height: 420 },
  )
})
