const test = require('node:test')
const assert = require('node:assert/strict')

test('drafts survive new reads and remain isolated by account and problem version', async () => {
  const { readCodeDraft, saveCodeDraft } = await import('../src/components/codeDraft.mjs')
  const original = Object.getOwnPropertyDescriptor(global, 'localStorage')
  const entries = new Map()
  Object.defineProperty(global, 'localStorage', { configurable: true, value: {
    getItem: key => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, value),
  } })
  try {
    assert.equal(readCodeDraft(1, 'greeting-v1'), null)
    assert.equal(saveCodeDraft(1, 'greeting-v1', 'name = input()\nprint(name)', '海獭\n'), true)
    assert.deepEqual(readCodeDraft(1, 'greeting-v1'), { code: 'name = input()\nprint(name)', stdin: '海獭\n' })
    assert.equal(readCodeDraft(2, 'greeting-v1'), null)
    assert.equal(readCodeDraft(1, 'greeting-v2'), null)
    saveCodeDraft(1, 'greeting-v1', '', '')
    assert.deepEqual(readCodeDraft(1, 'greeting-v1'), { code: '', stdin: '' })
    assert.equal(saveCodeDraft(null, 'greeting-v1', 'secret', ''), false)
    assert.equal(readCodeDraft(null, 'greeting-v1'), null)
    entries.set('ottly:code-draft:v1:1:greeting-v1', 'broken json')
    assert.equal(readCodeDraft(1, 'greeting-v1'), null)
    entries.set('ottly:code-draft:v1:1:greeting-v1', '{"code":123,"stdin":""}')
    assert.equal(readCodeDraft(1, 'greeting-v1'), null)
    global.localStorage.setItem = () => { throw new Error('storage full') }
    assert.equal(saveCodeDraft(1, 'greeting-v1', 'print(1)', ''), false)
    global.localStorage.getItem = () => { throw new Error('storage blocked') }
    assert.equal(readCodeDraft(1, 'greeting-v1'), null)
  } finally {
    if (original) Object.defineProperty(global, 'localStorage', original)
    else delete global.localStorage
  }
})
