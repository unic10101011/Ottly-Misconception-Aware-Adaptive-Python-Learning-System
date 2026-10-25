const test = require('node:test')
const assert = require('node:assert/strict')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { transformSync } = require('esbuild')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')

function load(file, overrides) {
  const filename = path.resolve(__dirname, file)
  const compiled = transformSync(fs.readFileSync(filename, 'utf8'), { loader: 'jsx', format: 'cjs' })
  const loaded = new Module(filename, module)
  loaded.filename = filename
  loaded.paths = Module._nodeModulePaths(path.dirname(filename))
  loaded.require = id => Object.hasOwn(overrides, id) ? overrides[id]
    : id.endsWith('.png') ? 'test.png' : require(id)
  loaded._compile(compiled.code, filename)
  return loaded.exports.default
}

function find(node, predicate) {
  if (!React.isValidElement(node)) return null
  return predicate(node) ? node : React.Children.toArray(node.props.children)
    .map(child => find(child, predicate)).find(Boolean)
}

function hooks(values = []) {
  const refs = []
  let stateIndex = 0, refIndex = 0
  return { react: { ...React, useEffect: () => {},
    useState: initial => {
      const slot = stateIndex++
      if (!(slot in values)) values[slot] = initial
      return [values[slot], next => { values[slot] = typeof next === 'function' ? next(values[slot]) : next }]
    },
    useRef: initial => refs[refIndex++] ||= { current: initial },
  }, render(Component, props) { stateIndex = 0; refIndex = 0; return Component(props) } }
}

test('thirteenth stop unlocks only after all twelve lessons and does not change main progress', () => {
  for (const complete of [false, true]) {
    const levels = Array.from({ length: 12 }, (_, index) => ({ id: index + 1, name: `第${index + 1}关`,
      published: true, status: !complete && index === 11 ? 'current' : 'completed' }))
    const harness = hooks([levels, '', false])
    const Page = load('../src/pages/LevelSelection.jsx', {
      react: harness.react, 'react-router-dom': { useNavigate: () => () => assert.fail('opens a modal, not a level') },
      '../components/codeApi.mjs': {}, '../components/EndlessChallengeModal.jsx': () => React.createElement('dialog'),
    })
    let tree = harness.render(Page)
    assert.equal((renderToStaticMarkup(tree).match(/class="level-circle /g) || []).length, 13)
    assert.match(renderToStaticMarkup(tree), new RegExp(`已完成 ${complete ? 12 : 11} / 12 关`))
    const stop = find(tree, node => node.props['aria-label']?.startsWith('无尽挑战，'))
    assert.equal(stop.props.disabled, !complete)
    if (complete) {
      stop.props.onClick()
      tree = harness.render(Page)
      assert.ok(find(tree, node => typeof node.type === 'function'))
    }
  }
})

test('modal uses the exact requested copy, locks choices while preparing, and opens the shared page', async () => {
  const harness = hooks()
  const navigations = []
  let finish, notify, closeCount = 0
  const Modal = load('../src/components/EndlessChallengeModal.jsx', {
    react: harness.react, 'react-router-dom': { useNavigate: () => url => navigations.push(url) },
    './codeApi.mjs': { startEndlessChallenge: (mode, token, options) => {
      assert.equal(mode, 'ottly'); assert.equal(token, 'student-token')
      notify = options.onProgress
      return new Promise(resolve => { finish = resolve })
    } },
  })
  const storage = Object.getOwnPropertyDescriptor(global, 'localStorage')
  Object.defineProperty(global, 'localStorage', { configurable: true, value: { getItem: () => 'student-token' } })
  try {
    let tree = harness.render(Modal, { onClose: () => closeCount++ })
    const html = renderToStaticMarkup(tree)
    for (const copy of ['开启无尽挑战', '从题库中抽题', '从已有题库中选择一道题。',
      '让 Ottly 出题', '根据你的错题和学习情况，生成一道新的挑战。']) assert.ok(html.includes(copy))
    const pending = find(tree, node => node.type === 'button' && node.props.children?.[0]?.props?.children === '让 Ottly 出题').props.onClick()
    tree = harness.render(Modal, { onClose: () => closeCount++ })
    assert.equal(find(tree, node => node.props.className === 'endless-choice').props.disabled, true)
    notify({ stage: 'reviewing', message: '正在检查边界及题意一致性…' })
    assert.match(renderToStaticMarkup(harness.render(Modal, { onClose: () => closeCount++ })), /正在检查边界及题意一致性/)
    finish({ stage: 'ready', problem_id: 'endless-demo-v1' })
    await pending
    assert.deepEqual(navigations, ['/app/endless?problem_id=endless-demo-v1'])
    assert.equal(closeCount, 1)
  } finally {
    if (storage) Object.defineProperty(global, 'localStorage', storage)
    else delete global.localStorage
  }
})

test('endless questions render through the existing practice editor without a catalog lookup', () => {
  const lesson = { problem_id: 'endless-demo-v1', title: '新挑战', story: 'STORY', description: 'TASK',
    examples: [{ stdin: '2\n', stdout: '3\n' }], teaching: [], starter_code: '# code', completed: false }
  const harness = hooks([[], lesson, null, '', false, false])
  let editor
  const Page = load('../src/pages/PracticePage.jsx', {
    react: harness.react, 'react-router-dom': { useNavigate: () => () => {},
      useOutletContext: () => ({ userId: 7 }),
      useSearchParams: () => [new URLSearchParams('problem_id=endless-demo-v1'), () => {}] },
    '../components/codeApi.mjs': {}, '../components/EndlessChallengeModal.jsx': () => null,
    '../components/CodeEditor.jsx': props => { editor = props; return React.createElement('div', null, props.children) },
  })
  const html = renderToStaticMarkup(harness.render(Page, { endless: true }))
  assert.match(html, /题目.*STORY.*任务.*TASK.*样例/s)
  assert.doesNotMatch(html, /尚未解锁或不存在|practice-map/)
  assert.equal(editor.problemId, lesson.problem_id)
  assert.equal(editor.userId, 7)
  assert.equal(editor.acceptsInput, true)
  editor.onAccepted()
  assert.match(renderToStaticMarkup(harness.render(Page, { endless: true })), /这道挑战已通过/)
})

test('endless API decodes split Unicode progress and waits for the final verified problem', async () => {
  const { startEndlessChallenge } = await import('../src/components/codeApi.mjs')
  const original = global.fetch
  const progress = []
  try {
    global.fetch = async (url, options) => {
      assert.equal(url, '/api/v1/code/endless')
      assert.equal(options.headers.Authorization, 'Bearer token')
      assert.deepEqual(JSON.parse(options.body), { mode: 'ottly' })
      const encoded = new TextEncoder().encode([
        { stage: 'generating', message: '正在生成候选题…' },
        { stage: 'ready', problem_id: 'endless-demo-v1' },
      ].map(data => JSON.stringify({ code: 200, data })).join('\n'))
      return new Response(new ReadableStream({ start(controller) {
        for (let index = 0; index < encoded.length; index += 7) controller.enqueue(encoded.slice(index, index + 7))
        controller.close()
      } }), { headers: { 'Content-Type': 'application/x-ndjson' } })
    }
    const result = await startEndlessChallenge('ottly', 'token', { onProgress: item => progress.push(item) })
    assert.equal(result.problem_id, 'endless-demo-v1')
    assert.equal(progress[0].message, '正在生成候选题…')
  } finally { global.fetch = original }
})

test('catalog response works, while failed and interrupted generation never opens a question', async () => {
  const { startEndlessChallenge } = await import('../src/components/codeApi.mjs')
  const original = global.fetch
  try {
    global.fetch = async () => new Response(JSON.stringify({ code: 200, data: { stage: 'ready', problem_id: 'practice-demo-v1' } }))
    assert.equal((await startEndlessChallenge('catalog', 'token')).problem_id, 'practice-demo-v1')
    for (const [data, message] of [
      [{ stage: 'error', message: '本次题目未通过验证' }, /未通过验证/],
      [{ stage: 'executing', message: '测试中' }, /尚未完成/],
    ]) {
      global.fetch = async () => new Response(JSON.stringify({ code: 200, data }) + '\n',
        { headers: { 'Content-Type': 'application/x-ndjson' } })
      await assert.rejects(startEndlessChallenge('ottly', 'token'), message)
    }
    global.fetch = async () => new Response(JSON.stringify({ detail: '完成全部 12 关后解锁无尽挑战。' }), { status: 403 })
    await assert.rejects(startEndlessChallenge('catalog', 'token'), /完成全部 12 关/)
  } finally { global.fetch = original }
})

test('catalog places endless after lesson twelve, never under a numbered lesson, and preserves its return location', () => {
  const generated = { problem_id: 'endless-saved-v1', kind: 'endless', level_no: 8,
    title: '已生成的题目', available: true, completed: false }
  const values = [[{ problem_id: 'practice-12-v1', level_no: 12, available: true }, generated],
    null, null, '', false, false]
  const harness = hooks(values)
  let params = new URLSearchParams()
  const Page = load('../src/pages/PracticePage.jsx', {
    react: harness.react, 'react-router-dom': { useNavigate: () => () => {},
      useOutletContext: () => ({ userId: 7 }),
      useSearchParams: () => [params, next => { params = new URLSearchParams(next) }] },
    '../components/codeApi.mjs': {}, '../components/EndlessChallengeModal.jsx': () => null,
    '../components/CodeEditor.jsx': props => React.createElement('div', null, props.children),
  })
  let tree = harness.render(Page)
  const html = renderToStaticMarkup(tree)
  assert.ok(html.indexOf('id="practice-level-12"') < html.indexOf('id="practice-endless"'))
  const levelEight = find(tree, node => node.props.id === 'practice-level-8')
  assert.doesNotMatch(renderToStaticMarkup(levelEight), /已生成的题目/)
  const circle = find(tree, node => node.props['aria-label']?.startsWith('无尽模式，练习 1，'))
  circle.props.onClick()
  assert.equal(params.get('category'), 'endless')
  assert.equal(params.get('problem_id'), generated.problem_id)
  assert.equal(params.has('level_no'), false)
  tree = harness.render(Page)
  find(tree, node => node.props['aria-label'] === '返回加练题库').props.onClick()
  assert.equal(params.get('category'), 'endless')
  assert.equal(params.has('problem_id'), false)
  values[0] = [values[0][0]]
  assert.match(renderToStaticMarkup(harness.render(Page)), /还没有生成的题目/)
})
