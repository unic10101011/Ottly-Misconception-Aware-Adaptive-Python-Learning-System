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

test('deleting an account clears only that account drafts on this browser', async () => {
  const { saveCodeDraft, readCodeDraft, clearUserCodeDrafts } = await import('../src/components/codeDraft.mjs')
  const original = Object.getOwnPropertyDescriptor(global, 'localStorage')
  const entries = new Map()
  Object.defineProperty(global, 'localStorage', { configurable: true, value: {
    get length() { return entries.size },
    key: index => Array.from(entries.keys())[index] ?? null,
    getItem: key => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, value),
    removeItem: key => entries.delete(key),
  } })
  try {
    saveCodeDraft(1, 'level1', 'print(1)', '')
    saveCodeDraft(1, 'greeting-v1', 'print(2)', 'test')
    saveCodeDraft(2, 'level1', 'print(3)', '')
    localStorage.setItem('unrelated-setting', 'true')
    clearUserCodeDrafts(1)
    assert.equal(readCodeDraft(1, 'level1'), null)
    assert.equal(readCodeDraft(1, 'greeting-v1'), null)
    assert.deepEqual(readCodeDraft(2, 'level1'), { code: 'print(3)', stdin: '' })
    assert.equal(localStorage.getItem('unrelated-setting'), 'true')
  } finally {
    if (original) Object.defineProperty(global, 'localStorage', original)
    else delete global.localStorage
  }
})

test('level twelve removes the old untouched pass placeholder while preserving student code and input', async () => {
  const { readCodeDraft, saveCodeDraft } = await import('../src/components/codeDraft.mjs')
  const original = Object.getOwnPropertyDescriptor(global, 'localStorage')
  const entries = new Map()
  Object.defineProperty(global, 'localStorage', { configurable: true, value: {
    getItem: key => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value),
  } })
  try {
    const old = 'def count_at_least(scores, threshold):\n    # begin\n    pass\n    # end\n\nn = int(input())\n'
    saveCodeDraft(1, 'count-at-least-v1', old, '0\n60\n')
    assert.deepEqual(readCodeDraft(1, 'count-at-least-v1'), {
      code: old.replace('    pass\n', '    \n'), stdin: '0\n60\n',
    })
    const written = old.replace('    pass\n', '    count = 0\n    for score in scores:\n        pass\n    return count\n')
    saveCodeDraft(1, 'count-at-least-v1', written, 'my input')
    assert.deepEqual(readCodeDraft(1, 'count-at-least-v1'), { code: written, stdin: 'my input' })
    saveCodeDraft(1, 'practice-12-2-v1', old, '')
    assert.equal(readCodeDraft(1, 'practice-12-2-v1').code, old)
  } finally {
    if (original) Object.defineProperty(global, 'localStorage', original)
    else delete global.localStorage
  }
})
