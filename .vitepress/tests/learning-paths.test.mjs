import assert from 'node:assert/strict'
import test from 'node:test'
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
