const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const React = require('react')
const { transformSync } = require('esbuild')

function setup() {
  const states = [], refs = [], effects = []
  let cursor = 0, refCursor = 0, requests = 0, finishRequest
  const bodies = []
  const hooks = { ...React, useState: initial => {
    const slot = cursor++
    if (!(slot in states)) states[slot] = typeof initial === 'function' ? initial() : initial
    return [states[slot], value => { states[slot] = typeof value === 'function' ? value(states[slot]) : value }]
  }, useRef: initial => refs[refCursor++] ||= { current: initial }, useEffect: effect => effects.push(effect) }
  const filename = path.resolve(__dirname, '../src/components/ExecutionReplay.jsx')
  const loaded = new Module(filename, module)
  loaded.filename = filename; loaded.paths = Module._nodeModulePaths(path.dirname(filename))
  const nativeRequire = loaded.require.bind(loaded)
  loaded.require = id => id === 'react' ? hooks : id === './codeApi.mjs'
    ? { requestExecutionTrace: async body => { requests++; bodies.push(body); return new Promise(resolve => { finishRequest = resolve }) } }
      : ['./TraceVisuals.jsx', './TraceStepInsight.jsx', './TraceAction.jsx'].includes(id) ? () => null : nativeRequire(id)
  loaded._compile(transformSync(fs.readFileSync(filename, 'utf8'), { loader: 'jsx', format: 'cjs' }).code, filename)
  return { render: (name, props) => { cursor = 0; refCursor = 0; effects.length = 0; return loaded.exports[name](props) },
    effects, bodies, requests: () => requests, finish: data => finishRequest(data) }
}
function find(tree, predicate) {
  if (!React.isValidElement(tree)) return null
  if (predicate(tree)) return tree
  return React.Children.toArray(tree.props.children).map(child => find(child, predicate)).find(Boolean)
}
const button = (tree, name) => find(tree, node => node.type === 'button' && node.props.children === name)
const trace = { code: 'total = 0\ntotal = 1\nprint(total)', stdin: '3\n', code_source: 'draft',
  test_case_label: '演示 n=3', trace_status: 'completed', truncated: false, steps: [
    { step: 1, event: 'line', line: 2, scope_id: 'module', variables: { total: '0' }, stdout: '' },
    { step: 2, event: 'line', line: 3, scope_id: 'module', variables: { total: '1' }, stdout: '' },
    { step: 3, event: 'end', line: null, scope_id: 'module', variables: { total: '1' }, stdout: '1\n' },
  ] }

test('next/previous/restart read saved snapshots without executing code or calling AI', () => {
  const app = setup(), props = { trace }
  let tree = app.render('TracePlayer', props)
  assert.equal(button(tree, '上一步').props.disabled, true)
  assert.equal(find(tree, node => node.props['aria-label'] === '当前步骤输出').props.children, '（当前尚无输出）')
  button(tree, '下一步').props.onClick()
  tree = app.render('TracePlayer', props)
  assert.ok(find(tree, node => node.props.className === 'trace-variable-old' && node.props.children === '0'))
  button(tree, '下一步').props.onClick()
  tree = app.render('TracePlayer', props)
  assert.equal(find(tree, node => node.props['aria-label'] === '当前步骤输出').props.children, '1\n')
  assert.equal(button(tree, '下一步').props.disabled, true)
  button(tree, '上一步').props.onClick()
  tree = app.render('TracePlayer', props)
  assert.equal(find(tree, node => node.props['aria-label'] === '当前步骤输出').props.children, '（当前尚无输出）')
  button(tree, '重新开始').props.onClick()
  assert.equal(button(app.render('TracePlayer', props), '上一步').props.disabled, true)
  assert.equal(app.requests(), 0)
})

test('empty syntax and limited traces have truthful status and valid controls', () => {
  for (const status of ['syntax_error', 'unsupported', 'truncated']) {
    const app = setup()
    const tree = app.render('TracePlayer', { trace: { ...trace, steps: [], trace_status: status,
      exception: { type: 'SyntaxError', message: '缺少冒号', line: 1 }, truncated: status === 'truncated' } })
    assert.equal(button(tree, '下一步').props.disabled, true)
    assert.equal(button(tree, '上一步').props.disabled, true)
    assert.ok(find(tree, node => node.props.className === 'trace-status'))
    assert.equal(app.requests(), 0)
  }
})

test('returning to the caller does not repeat output produced in a function', () => {
  const app = setup()
  const props = { trace: { ...trace, steps: [
    { step: 1, event: 'line', line: 1, scope_id: 'module', variables: {}, stdout: '' },
    { step: 2, event: 'return', line: 2, scope_id: 'call-1', function: 'f', variables: {}, stdout: '1\n' },
    { step: 3, event: 'line', line: 3, scope_id: 'module', variables: { a: '2' }, stdout: '1\n' },
  ] } }
  let tree = app.render('TracePlayer', props)
  button(tree, '下一步').props.onClick()
  tree = app.render('TracePlayer', props)
  button(tree, '下一步').props.onClick()
  tree = app.render('TracePlayer', props)
  assert.equal(find(tree, node => node.type === 'small' && node.props.children === '本步有新输出'), undefined)
})

test('closing the dialog restores focus and ignores a late trace response', async () => {
  const app = setup()
  const oldDocument = global.document, oldStorage = global.localStorage
  let focused = false, closed = false
  global.document = { activeElement: { isConnected: true, focus: () => { focused = true } }, body: { style: { overflow: 'auto' } } }
  global.localStorage = { getItem: () => 'test-token' }
  try {
    const props = { code: trace.code, problemId: 'shell-total-v1', onClose: () => {} }
    const tree = app.render('default', props)
    tree.ref.current = { showModal() {}, close() { closed = true } }
    const cleanup = app.effects[0]()
    assert.equal(app.requests(), 1)
    assert.equal(document.body.style.overflow, 'hidden')
    cleanup()
    app.finish(trace)
    await new Promise(resolve => setImmediate(resolve))
    const after = app.render('default', props)
    assert.ok(!find(after, node => node.type.name === 'TracePlayer'))
    assert.equal(document.body.style.overflow, 'auto')
    assert.ok(closed && focused)
  } finally {
    global.document = oldDocument
    global.localStorage = oldStorage
  }
})

test('first four replay dialogs use the lesson title and preserve multiline or name input', () => {
  const cases = [
    ['level1', '第 1 关 · 初识小海獭', '', false],
    ['greeting-v1', '第 2 关 · 打招呼', ' Li Ming ', true],
    ['shell-shop-v1', '第 3 关 · 贝壳小商店', '4\n3\n20\n', true],
    ['shell-groups-v1', '第 4 关 · 贝壳分组', '17\n5\n', true],
  ]
  const oldStorage = global.localStorage, oldDocument = global.document
  global.localStorage = { getItem: () => 'test-token' }
  try {
    for (const [problemId, title, initialInput, hasInput] of cases) {
      const app = setup()
      const tree = app.render('default', { code: 'print(1)', problemId, initialInput, onClose() {} })
      assert.ok(find(tree, node => node.type === 'small' && node.props.children === title))
      assert.equal(Boolean(find(tree, node => node.type === 'textarea')), hasInput)
      global.document = { activeElement: null, body: { style: { overflow: '' } } }
      tree.ref.current = { showModal() {}, close() {} }
      const cleanup = app.effects[0]()
      assert.equal(app.bodies[0].stdin, initialInput)
      assert.equal(app.bodies[0].problem_id, problemId)
      cleanup()
    }
  } finally { global.localStorage = oldStorage; global.document = oldDocument }
})

test('all twelve formal lessons have replay configuration and practice has no entry', async () => {
  const { executionReplayLessons } = await import('../src/components/executionReplayConfig.mjs')
  assert.equal(Object.keys(executionReplayLessons).length, 12)
  assert.equal(executionReplayLessons['count-at-least-v1'].defaultInput, '4\n60\n59\n60\n80\n100\n')
  assert.equal(executionReplayLessons['practice-12-2-v1'], undefined)
})

test('function playback identifies the local scope, call stack and actual return', () => {
  const app = setup()
  const props = { trace: { ...trace, code: 'def f(x):\n    return x + 1\nprint(f(2))', steps: [
    { event: 'call', line: 1, function: 'f', scope_id: 'call-1', variables: { x: '2' }, call_stack: [{ function: '<module>', scope_id: 'module' }, { function: 'f', scope_id: 'call-1' }] },
    { event: 'return', line: 2, function: 'f', scope_id: 'call-1', variables: { x: '2' }, return_value: '3', call_stack: [{ function: '<module>', scope_id: 'module' }, { function: 'f', scope_id: 'call-1' }] },
  ] } }
  let tree = app.render('TracePlayer', props)
  assert.match(find(tree, node => node.props.className === 'trace-step-label').props.children, /进入函数 f/)
  assert.ok(find(tree, node => node.props['aria-label'] === '调用栈'))
  button(tree, '下一步').props.onClick()
  tree = app.render('TracePlayer', props)
  assert.match(find(tree, node => node.props.className === 'trace-step-label').props.children, /函数 f 返回 3/)
})

test('code version selection appears only when a saved submission is available', () => {
  const props = { code: 'print(1)', problemId: 'greeting-v1', onClose() {} }
  let tree = setup().render('default', props)
  assert.ok(!find(tree, node => node.type === 'select'))
  tree = setup().render('default', { ...props, submissionId: 42 })
  const selector = find(tree, node => node.type === 'select')
  assert.ok(selector)
  assert.equal(React.Children.count(selector.props.children), 2)
})

test('input settings are collapsed by default and rerun is an explicit adjustment', () => {
  const tree = setup().render('default', { code: 'name = input()', problemId: 'greeting-v1', onClose() {} })
  const settings = find(tree, node => node.type === 'details' && node.props.className === 'trace-options')
  assert.ok(settings && !settings.props.open)
  assert.ok(find(settings, node => node.type === 'button' && node.props.type === 'submit'))
  assert.ok(!button(tree, '生成回放'))
})
