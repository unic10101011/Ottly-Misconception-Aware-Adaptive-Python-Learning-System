const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { transformSync } = require('esbuild')
const fs = require('node:fs')
const Module = require('node:module')
const { pathToFileURL } = require('node:url')

function loadJsx(file, overrides = {}) {
  const filename = path.resolve(__dirname, file)
  const compiled = transformSync(fs.readFileSync(filename, 'utf8'), { loader: 'jsx', format: 'cjs', define: { 'import.meta.url': JSON.stringify(pathToFileURL(filename).href) } })
  const loaded = new Module(filename, module)
  loaded.filename = filename
  loaded.paths = Module._nodeModulePaths(path.dirname(filename))
  const nativeRequire = loaded.require.bind(loaded)
  loaded.require = id => Object.hasOwn(overrides, id) ? overrides[id] : nativeRequire(id)
  loaded._compile(compiled.code, filename)
  return loaded.exports.default
}

const failure = {
  problem_id: 'level2',
  judge: { status: 'wrong_answer', passed: false, passed_cases: 0, total_cases: 1, cases: [
    { case_id: 'stdout-1', passed: false, expected_output: '5050', actual_output: '100', errors: [], execution_time: 0.01 },
  ] },
  analysis: { status: 'ready', message: '', model: 'qwen2.5-coder:3b-instruct', content: {
    suspected_cause: 'Repeated replacement',
    evidence: [{ case_id: 'stdout-1', field: 'actual_output', quote: '100', explanation: 'Only the last value remains' }],
    knowledge_points: ['accumulation'],
    hints: { level1: 'HINT_ONE', level2: 'HINT_TWO', level3: 'HINT_THREE' },
  } },
}

test('submission sends current code and problem id with auth and preserves backend verdict', async () => {
  const { requestCode } = await import('../src/components/codeApi.mjs')
  const originalFetch = global.fetch
  global.fetch = async (url, options) => {
    assert.equal(url, '/api/v1/code/submit')
    assert.equal(options.headers.Authorization, 'Bearer token')
    assert.deepEqual(JSON.parse(options.body), { problem_id: 'level2', code: 'print(100)' })
    return new Response(JSON.stringify({ code: 200, data: failure }), { status: 200 })
  }
  try {
    const result = await requestCode('submit', { problem_id: 'level2', code: 'print(100)' }, 'token')
    assert.deepEqual(result, failure)
    assert.equal(result.judge.cases[0].actual_output, '100')
  } finally { global.fetch = originalFetch }
})

test('HTTP auth and invalid responses return readable errors instead of crashing on data', async () => {
  const { requestCode } = await import('../src/components/codeApi.mjs')
  const originalFetch = global.fetch
  try {
    global.fetch = async () => new Response(JSON.stringify({ detail: 'Expired' }), { status: 401 })
    await assert.rejects(requestCode('submit', {}, 'old'), /登录已过期/)
    global.fetch = async () => new Response('<html>Bad Gateway</html>', { status: 502 })
    await assert.rejects(requestCode('submit', {}, 'token'), /服务响应异常/)
    global.fetch = async () => { throw new TypeError('Failed to fetch') }
    await assert.rejects(requestCode('submit', {}, 'token'), /无法连接/)
  } finally { global.fetch = originalFetch }
})

test('hints start hidden and are revealed in order without showing later hints', () => {
  const Feedback = loadJsx('../src/components/SubmissionFeedback.jsx')
  const render = (visibleHintCount) => renderToStaticMarkup(React.createElement(Feedback, {
    result: failure, visibleHintCount, onRevealHint() {},
  }))
  const initial = render(0)
  assert.match(initial, /100/)
  assert.match(initial, /查看第 1 级提示/)
  assert.doesNotMatch(initial, /HINT_ONE|HINT_TWO|HINT_THREE/)
  assert.match(initial, /<details[^>]*>/)
  assert.doesNotMatch(initial, /<details[^>]*open/)
  const first = render(1)
  assert.match(first, /HINT_ONE/)
  assert.doesNotMatch(first, /HINT_TWO|HINT_THREE/)
  assert.match(first, /查看第 2 级提示/)
  const second = render(2)
  assert.match(second, /HINT_TWO/)
  assert.doesNotMatch(second, /HINT_THREE/)
  const third = render(3)
  assert.match(third, /HINT_THREE/)
  assert.doesNotMatch(third, /查看第 4 级提示/)
})

test('model outage keeps deterministic judge evidence visible and shows recovery guidance', () => {
  const Feedback = loadJsx('../src/components/SubmissionFeedback.jsx')
  const result = { ...failure, analysis: { status: 'unavailable', message: 'AI 暂时不可用，请稍后重新提交。', content: null } }
  const html = renderToStaticMarkup(React.createElement(Feedback, { result, visibleHintCount: 0 }))
  assert.match(html, /5050/)
  assert.match(html, /100/)
  assert.match(html, /AI 暂时不可用/)
  assert.doesNotMatch(html, /查看第 1 级提示/)
})


test('leaving the editor while an accepted submission is pending prevents late updates and navigation', async () => {
  const effects = []
  const updates = []
  const timers = []
  let completeRequest
  let successCount = 0
  const hooks = {
    ...React,
    useState: value => [value, next => updates.push(next)],
    useRef: value => ({ current: value }),
    useEffect: effect => effects.push(effect),
    useCallback: callback => callback,
  }
  const Editor = loadJsx('../src/components/CodeEditor.jsx', {
    react: hooks,
    'react-router-dom': { useNavigate: () => () => { successCount++ } },
    './SubmissionFeedback.jsx': { default: () => null },
    './codeApi.mjs': { requestCode: () => new Promise(resolve => { completeRequest = resolve }) },
  })
  const originalStorage = Object.getOwnPropertyDescriptor(global, 'localStorage')
  const originalSetTimeout = global.setTimeout
  const originalClearTimeout = global.clearTimeout
  Object.defineProperty(global, 'localStorage', { configurable: true, value: { getItem: () => 'test-token' } })
  global.setTimeout = callback => { timers.push(callback); return timers.length }
  global.clearTimeout = () => {}
  try {
    const tree = Editor({ initialCode: 'print(5050)', problemId: 'level2', title: 'test', onSuccess: () => { successCount++ } })
    const cleanups = effects.map(effect => effect()).filter(cleanup => typeof cleanup === 'function')
    const findSubmit = node => {
      if (!React.isValidElement(node)) return null
      if (node.props.className === 'btn-submit') return node
      return React.Children.toArray(node.props.children).map(findSubmit).find(Boolean)
    }
    const submit = findSubmit(tree)
    assert.ok(submit, 'the test must invoke the real submit button handler')
    const pendingSubmission = submit.props.onClick()
    assert.equal(typeof completeRequest, 'function')
    cleanups.forEach(cleanup => cleanup())
    updates.length = 0
    completeRequest({ judge: { passed: true } })
    await pendingSubmission
    assert.equal(updates.length, 0, 'unmounted editor must not update state')
    assert.equal(timers.length, 0, 'late success must not schedule navigation')
    assert.equal(successCount, 0)
  } finally {
    global.setTimeout = originalSetTimeout
    global.clearTimeout = originalClearTimeout
    if (originalStorage) Object.defineProperty(global, 'localStorage', originalStorage)
    else delete global.localStorage
  }
})

test('terminated execution distinguishes unavailable stdout from an empty output', () => {
  const Feedback = loadJsx('../src/components/SubmissionFeedback.jsx')
  const result = {
    ...failure,
    judge: { ...failure.judge, status: 'timeout', cases: [
      { ...failure.judge.cases[0], actual_output: '', output_available: false },
    ] },
    analysis: { status: 'unavailable', message: 'AI 暂不可用', content: null },
  }
  const html = renderToStaticMarkup(React.createElement(Feedback, { result, visibleHintCount: 0 }))
  assert.match(html, /输出未采集（执行已终止）/)
  assert.doesNotMatch(html, /（无输出）/)
})
