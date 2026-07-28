import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const appSource = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')

test('makes the decision customer-service drawer use the shared floating resize controls', () => {
  assert.match(appSource, /customer-service-drawer customer-service-float/)
  assert.match(appSource, /ref=\{assistantFloatRef\}/)
  assert.match(appSource, /onPointerDown=\{handleAssistantFloatDragStart\}/)
  assert.match(appSource, /onPointerDown=\{handleAssistantFloatResizeStart\}/)
  assert.match(appSource, /openDecisionAssistant/)
})
