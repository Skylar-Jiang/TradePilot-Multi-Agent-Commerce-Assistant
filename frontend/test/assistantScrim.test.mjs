import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const stylesheet = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8')

test('keeps the report visible behind the customer-service assistant', () => {
  const scrimRules = stylesheet.match(/\.assistant-scrim\s*\{[^}]*\}/g) || []

  assert.ok(scrimRules.length > 0)
  assert.ok(scrimRules.every((rule) => !rule.includes('backdrop-filter')))
  assert.ok(scrimRules.every((rule) => rule.includes('background: transparent')))
})
