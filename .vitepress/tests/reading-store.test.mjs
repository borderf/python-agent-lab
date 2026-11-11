import assert from 'node:assert/strict'
import test from 'node:test'
import { readProgress, saveProgress, storageKey } from '../theme/reading-store.mjs'
import { learningPaths } from '../learning-paths.mjs'

function storage(value) {
  return { value, getItem() { return this.value }, setItem(key, next) { assert.equal(key, storageKey); this.value = next } }
}

test('invalid or unavailable storage keeps the reading page usable', () => {
  assert.equal(readProgress(storage('{')).font, 17)
  assert.equal(readProgress({ getItem() { throw Error('denied') } }).last, null)
  assert.equal(saveProgress({ setItem() { throw Error('quota') } }, {}), false)
})

test('resume accepts a lesson in this site and validates its position', () => {
  const last = { path: '/docs/python-book/01-认识执行过程、对象与控制流.html', title: '第一章', scroll: 1200 }
  const local = storage(null)
  assert.ok(saveProgress(local, { version: 1, last, font: 19, pathId: 'agent', read: [last.path, last.path] }))
  assert.deepEqual(readProgress(local), { version: 1, last, font: 19, pathId: 'agent', read: [last.path] })
  for (const path of ['https://example.com', '//example.com', '/docs/../secret.html', '/docs/page.html?target=other']) {
    local.value = JSON.stringify({ version: 1, last: { ...last, path }, read: [path] })
    assert.equal(readProgress(local).last, null)
    assert.deepEqual(readProgress(local).read, [])
  }
})

test('the project route goes from retrieval to evaluation and DocPilot', () => {
  const steps = learningPaths.find(item => item.id === 'application').steps
  const index = steps.findIndex(step => step.link.includes('/21-'))
  assert.ok(steps[index + 1].link.includes('/22-'))
  assert.ok(steps[index + 2].link.includes('/23-'))
  const agent = learningPaths.find(item => item.id === 'agent').steps
  const docpilot = agent.findIndex(step => step.link.includes('/23-'))
  assert.ok(agent[docpilot + 1].link.includes('/24-'))
  for (const id of ['architecture', 'product']) {
    const route = learningPaths.find(item => item.id === id)
    assert.equal(route.steps.length, 14)
    assert.ok(route.steps[0].link.includes('/01-'))
    assert.ok(route.steps.at(-1).link.includes('/14-'))
    assert.equal(readProgress(storage(JSON.stringify({version: 1, pathId: id}))).pathId, id)
  }
})
