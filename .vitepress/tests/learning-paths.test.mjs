import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { learningPaths } from '../learning-paths.mjs'

const numbers = id => learningPaths.find(route => route.id === id).steps
  .map(step => Number(step.link.match(/\/(\d\d)-/)[1]))

test('application route completes evaluation and DocPilot before career chapters', () => {
  assert.deepEqual(numbers('application'), [...Array.from({ length: 23 }, (_, i) => i + 1), 29, 30])
})

test('agent route learns tool calling and persistent state before ProcureAgent', () => {
  assert.deepEqual(numbers('agent'), [...Array.from({ length: 26 }, (_, i) => i + 1), 29, 30])
  assert.equal(numbers('agent').includes(27), false)
  assert.equal(numbers('agent').includes(28), false)
})

test('every route resolves complete chapters for its book', () => {
  const expected = { python: 12, application: 25, agent: 28, architecture: 14, product: 14, typescript: 18, 'ai-foundations': 9 }
  for (const [id, count] of Object.entries(expected)) {
    const route = learningPaths.find(item => item.id === id)
    assert.equal(route.steps.length, count, id)
    assert.ok(route.steps.every(step => step && step.title && /^\/docs\/[\w-]+\/\d\d-.+\.html$/.test(step.link)), id)
    assert.ok(route.steps.every(step => existsSync(fileURLToPath(new URL(`../../${step.link.slice(1).replace(/\.html$/, '.md')}`, import.meta.url)))), `${id}: every chapter exists`)
    assert.equal(new Set(route.steps.map(step => step.link)).size, count, id)
  }
})
