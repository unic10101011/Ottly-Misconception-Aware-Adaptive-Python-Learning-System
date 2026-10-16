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

test('snapshot metadata distinguishes known values from unavailable historical values', () => {
  const Metadata = loadJsx('../src/components/ProblemMetadata.jsx')
  const current = renderToStaticMarkup(React.createElement(Metadata, {
    version: 2, difficulty: 3, knowledgeIds: ['K02'], knowledgeNames: { K02: '变量与输入' },
  }))
  assert.match(current, /版本 2/)
  assert.match(current, /综合/)
  assert.match(current, /变量与输入/)
  const old = renderToStaticMarkup(React.createElement(Metadata, { version: null, difficulty: null, knowledgeIds: [] }))
  assert.match(old, /历史版本未提供/)
  assert.match(old, /历史记录未提供/)
  assert.doesNotMatch(old, /基础|版本 1/)
})

test('contract failure IDs and mapped knowledge IDs render alongside existing explanations', () => {
  const Feedback = loadJsx('../src/components/SubmissionFeedback.jsx')
  const result = { ...failure,
    judge: { ...failure.judge, failed_tests: ['stdout-1'] },
    analysis: { ...failure.analysis, content: { ...failure.analysis.content, knowledge_ids: ['K08'] } },
  }
  const html = renderToStaticMarkup(React.createElement(Feedback, { result, visibleHintCount: 3 }))
  assert.match(html, /未通过测试：stdout-1/)
  assert.match(html, /K08/)
  assert.match(html, /accumulation/)
})

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

test('history requests use the current account token and record hint level', async () => {
  const { getLearningHistory, saveHintView } = await import('../src/components/codeApi.mjs')
  const originalFetch = global.fetch
  const requests = []
  global.fetch = async (url, options) => {
    requests.push({ url, options })
    assert.equal(options.headers.Authorization, 'Bearer student-token')
    if (options.method === 'GET') {
      return new Response(JSON.stringify({ code: 200, data: { items: [], total: 0 } }), { status: 200 })
    }
    return new Response(JSON.stringify({ code: 200, data: { submission_id: 17, hints_viewed_max: 2 } }), { status: 200 })
  }
  try {
    assert.deepEqual(await getLearningHistory(true, 20, 0, 'student-token'), { items: [], total: 0 })
    assert.deepEqual(await saveHintView(17, 2, 'student-token'), { submission_id: 17, hints_viewed_max: 2 })
    assert.match(requests[0].url, /code\/submissions\?failed_only=true&limit=20&offset=0$/)
    assert.equal(requests[0].options.method, 'GET')
    assert.equal(requests[1].url, '/api/v1/code/submissions/17/hints')
    assert.equal(requests[1].options.method, 'PATCH')
    assert.deepEqual(JSON.parse(requests[1].options.body), { level: 2 })
  } finally { global.fetch = originalFetch }
})

test('history requests can be aborted and report a timeout', async () => {
  const { getLearningHistory } = await import('../src/components/codeApi.mjs')
  const originalFetch = global.fetch
  global.fetch = async (url, options) => {
    assert.ok(options.signal, 'history fetch must have an abort signal')
    const error = new Error('aborted')
    error.name = 'AbortError'
    throw error
  }
  try {
    await assert.rejects(getLearningHistory(true, 20, 0, 'token'), /请求超时/)
  } finally { global.fetch = originalFetch }
})

test('review submission carries its source and mistake questions load with auth', async () => {
  const { requestCode, getMistakeQuestions, getLearningHistory } = await import('../src/components/codeApi.mjs')
  const originalFetch = global.fetch
  const calls = []
  global.fetch = async (url, options) => {
    calls.push({ url, options })
    assert.equal(options.headers.Authorization, 'Bearer student-token')
    if (url.endsWith('/code/submit')) {
      assert.equal(options.headers['X-Review-Source-Id'], '23')
      return new Response(JSON.stringify({ code: 200, data: failure }), { status: 200 })
    }
    return new Response(JSON.stringify({ code: 200, data: { items: [], total: 0 } }), { status: 200 })
  }
  try {
    await requestCode('submit', { problem_id: 'level2', code: 'print(100)' }, 'student-token', { reviewSourceId: 23 })
    await getMistakeQuestions('student-token')
    await getLearningHistory(false, 20, 0, 'student-token', 'level2')
    assert.equal(calls[1].url, '/api/v1/code/mistakes')
    assert.match(calls[2].url, /problem_id=level2/)
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
  assert.doesNotMatch(initial, /<details|Repeated replacement|Only the last value remains/)
  const first = render(1)
  assert.match(first, /HINT_ONE/)
  assert.doesNotMatch(first, /HINT_TWO|HINT_THREE/)
  assert.match(first, /查看第 2 级提示/)
  const second = render(2)
  assert.match(second, /HINT_TWO/)
  assert.doesNotMatch(second, /HINT_THREE/)
  assert.doesNotMatch(second, /Repeated replacement|Only the last value remains/)
  const third = render(3)
  assert.match(third, /HINT_THREE/)
  assert.match(third, /Repeated replacement/)
  assert.match(third, /<details[^>]*>/)
  assert.doesNotMatch(third, /<details[^>]*open/)
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

test('reviewed fallback tells the student why the wording changed', () => {
  const Feedback = loadJsx('../src/components/SubmissionFeedback.jsx')
  const result = { ...failure, analysis: { ...failure.analysis, message: '原提示未通过分层检查，已采用保守教学提示。' } }
  const html = renderToStaticMarkup(React.createElement(Feedback, { result, visibleHintCount: 0 }))
  assert.match(html, /保守教学提示/)
  assert.doesNotMatch(html, /HINT_ONE/)
})

test('hint button waits for saved view and shows a sync error', () => {
  const Feedback = loadJsx('../src/components/SubmissionFeedback.jsx')
  const html = renderToStaticMarkup(React.createElement(Feedback, {
    result: failure, visibleHintCount: 1, hintBusy: true, hintError: '提示查看记录暂未保存',
  }))
  assert.match(html, /提示查看记录暂未保存/)
  assert.match(html, /<button[^>]*disabled/)
  assert.doesNotMatch(html, /HINT_TWO/)
})


test('leaving the editor while an accepted submission is pending prevents late updates and navigation', async () => {
  const effects = []
  const updates = []
  const timers = []
  let completeRequest
  let successCount = 0
  const hooks = {
    ...React,
    useState: value => [typeof value === 'function' ? value() : value, next => updates.push(next)],
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

test('private cases never render outputs or errors and fixed hints are labelled honestly', () => {
  const Feedback = loadJsx('../src/components/SubmissionFeedback.jsx')
  const result = { ...failure,
    judge: { ...failure.judge, cases: [{ ...failure.judge.cases[0], visibility: 'hidden',
      expected_output: 'PRIVATE_EXPECTED', actual_output: 'PRIVATE_ACTUAL',
      errors: [{ type: 'Error', message: 'PRIVATE_ERROR' }] }] },
    analysis: { ...failure.analysis, source: 'fixed', message: '本关已审核的基础提示。' },
  }
  const html = renderToStaticMarkup(React.createElement(Feedback, { result, visibleHintCount: 1 }))
  assert.doesNotMatch(html, /PRIVATE_EXPECTED|PRIVATE_ACTUAL|PRIVATE_ERROR|AI 学习提示/)
  assert.match(html, /隐藏测试仅展示通过状态/)
  assert.match(html, /本关基础提示/)
  assert.match(html, /HINT_ONE/)
})

test('input lesson sends run input but submission uses only the server problem id and current code', async () => {
  const effects = []
  const calls = []
  const hooks = { ...React,
    useState: value => [typeof value === 'function' ? value() : value, () => {}], useRef: value => ({ current: value }),
    useEffect: effect => effects.push(effect), useCallback: callback => callback,
  }
  const Editor = loadJsx('../src/components/CodeEditor.jsx', {
    react: hooks, 'react-router-dom': { useNavigate: () => () => {} },
    './SubmissionFeedback.jsx': { default: () => null },
    './codeApi.mjs': { requestCode: async (action, payload) => {
      calls.push({ action, payload })
      return action === 'run' ? { success: true, output: 'Hello, Sea Otter!\n', errors: [] } : failure
    } },
  })
  const originalStorage = Object.getOwnPropertyDescriptor(global, 'localStorage')
  Object.defineProperty(global, 'localStorage', { configurable: true, value: { getItem: () => 'token' } })
  try {
    const code = 'name = input()\nprint("Hello,", name + "!")'
    const tree = Editor({ initialCode: code, problemId: 'greeting-v1', acceptsInput: true, sampleInput: 'Sea Otter\n' })
    const cleanups = effects.map(effect => effect()).filter(fn => typeof fn === 'function')
    const find = (node, predicate) => {
      if (!React.isValidElement(node)) return null
      if (predicate(node)) return node
      return React.Children.toArray(node.props.children).map(child => find(child, predicate)).find(Boolean)
    }
    assert.equal(find(tree, node => node.props.id === 'lesson-stdin').props.value, 'Sea Otter\n')
    await find(tree, node => node.props.className === 'btn-run').props.onClick()
    await find(tree, node => node.props.className === 'btn-submit').props.onClick()
    assert.deepEqual(calls, [
      { action: 'run', payload: { code, timeout: 3, stdin: 'Sea Otter\n' } },
      { action: 'submit', payload: { problem_id: 'greeting-v1', code } },
    ])
    cleanups.forEach(fn => fn())
  } finally {
    if (originalStorage) Object.defineProperty(global, 'localStorage', originalStorage)
    else delete global.localStorage
  }
})
test('analysis request uses the owning token and a model sized timeout', async () => {
  const { requestAnalysis } = await import('../src/components/codeApi.mjs')
  const originalFetch = global.fetch
  const originalSetTimeout = global.setTimeout
  let timeoutMs = 0
  global.setTimeout = (callback, ms) => { timeoutMs = ms; return originalSetTimeout(callback, ms) }
  global.fetch = async (url, options) => {
    assert.equal(url, '/api/v1/code/submissions/17/analysis')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers.Authorization, 'Bearer owner-token')
    return new Response(JSON.stringify({ code: 200, data: { analysis: { status: 'ready' } } }), { status: 200 })
  }
  try {
    assert.equal((await requestAnalysis(17, 'owner-token')).analysis.status, 'ready')
    assert.ok(timeoutMs >= 90000, 'the browser must wait through the model deadline')
  } finally {
    global.fetch = originalFetch
    global.setTimeout = originalSetTimeout
  }
})

test('pending analysis renders real judge evidence before hints arrive', () => {
  const Feedback = loadJsx('../src/components/SubmissionFeedback.jsx')
  const result = { ...failure, analysis: { status: 'preparing', message: '正在准备提示', content: null } }
  const html = renderToStaticMarkup(React.createElement(Feedback, { result, visibleHintCount: 0 }))
  assert.match(html, /5050/)
  assert.match(html, /100/)
  assert.match(html, /正在准备提示/)
  assert.doesNotMatch(html, /查看第 1 级提示|HINT_ONE/)
})
test('editor shows the judge before analysis resolves and keeps the verdict', async () => {
  const effects = []
  const updates = []
  let finishAnalysis
  const prepared = { ...failure, submission_id: 71, analysis: { status: 'preparing', message: '正在准备提示', content: null } }
  const hooks = {
    ...React,
    useState: value => [typeof value === 'function' ? value() : value, next => updates.push(next)],
    useRef: value => ({ current: value }),
    useEffect: effect => effects.push(effect),
    useCallback: callback => callback,
  }
  const Editor = loadJsx('../src/components/CodeEditor.jsx', {
    react: hooks,
    'react-router-dom': { useNavigate: () => () => {} },
    './SubmissionFeedback.jsx': { default: () => null },
    './codeApi.mjs': {
      requestCode: async () => prepared,
      requestAnalysis: () => new Promise(resolve => { finishAnalysis = resolve }),
    },
  })
  const originalStorage = Object.getOwnPropertyDescriptor(global, 'localStorage')
  Object.defineProperty(global, 'localStorage', { configurable: true, value: { getItem: () => 'owner-token' } })
  try {
    const tree = Editor({ initialCode: 'print(100)', problemId: 'level2', title: 'test' })
    const cleanups = effects.map(effect => effect()).filter(fn => typeof fn === 'function')
    const find = node => {
      if (!React.isValidElement(node)) return null
      if (node.props.className === 'btn-submit') return node
      return React.Children.toArray(node.props.children).map(find).find(Boolean)
    }
    await find(tree).props.onClick()
    assert.equal(typeof finishAnalysis, 'function')
    assert.ok(updates.includes(prepared), 'first render update must contain the real judge')
    assert.equal(prepared.judge.status, 'wrong_answer')
    finishAnalysis({ analysis: failure.analysis, timings: { judge_ms: 12, model_load_ms: 5, hint_generation_ms: 30 } })
    await Promise.resolve()
    await Promise.resolve()
    const completed = updates.find(value => value?.analysis?.status === 'ready' && value?.submission_id === 71)
    assert.ok(completed, 'later update should contain the hints')
    assert.deepEqual(completed.judge, prepared.judge)
    cleanups.forEach(fn => fn())
  } finally {
    if (originalStorage) Object.defineProperty(global, 'localStorage', originalStorage)
    else delete global.localStorage
  }
})
test('review submission also shows the judge before its hint request finishes', async () => {
  const effects = []
  const updates = []
  let finishAnalysis
  const question = { problem_id: 'level2', first_wrong_submission_id: 5,
    last_wrong_code: 'print(100)', title: '求和', description: '求和', source: '系统关卡' }
  const states = [[question], {}, 'level2', 'practice', false, '', 'print(100)', '', false, false,
    null, null, 0, null, {}, [], 0, 0, 0, 0, false, '', '']
  let stateIndex = 0
  const hooks = {
    ...React,
    useState: () => {
      const index = stateIndex++
      return [states[index], next => updates.push({ index, next })]
    },
    useRef: value => ({ current: value }),
    useEffect: effect => effects.push(effect),
  }
  const History = loadJsx('../src/pages/LearningHistory.jsx', {
    react: hooks,
    'react-router-dom': { useNavigate: () => () => {} },
    '../components/ProblemMetadata.jsx': () => null,
    '../components/SubmissionFeedback.jsx': { default: () => null },
    '../components/codeApi.mjs': {
      requestCode: async () => prepared,
      requestAnalysis: () => new Promise(resolve => { finishAnalysis = resolve }),
    },
  })
  const prepared = { ...failure, submission_id: 72,
    analysis: { status: 'preparing', message: '正在准备提示', content: null } }
  const originalStorage = Object.getOwnPropertyDescriptor(global, 'localStorage')
  Object.defineProperty(global, 'localStorage', { configurable: true, value: { getItem: () => 'owner-token' } })
  try {
    const tree = History()
    const cleanup = effects[0]()
    effects[3]()
    const find = node => {
      if (!React.isValidElement(node)) return null
      if (node.props.className === 'mistake-primary-button') return node
      return React.Children.toArray(node.props.children).map(find).find(Boolean)
    }
    await find(tree).props.onClick()
    assert.ok(updates.some(update => update.index === 11 && update.next === prepared))
    assert.equal(typeof finishAnalysis, 'function')
    finishAnalysis({ analysis: failure.analysis, timings: { judge_ms: 12 } })
    await Promise.resolve()
    await Promise.resolve()
    assert.ok(updates.some(update => update.index === 11 && update.next?.analysis?.status === 'ready'))
    cleanup()
  } finally {
    if (originalStorage) Object.defineProperty(global, 'localStorage', originalStorage)
    else delete global.localStorage
  }
})
test('opening an unfinished history entry resumes only that analysis', async () => {
  const effects = []
  const updates = []
  let finishAnalysis
  const item = { id: 81, code: 'print(100)', judge: failure.judge,
    analysis: { status: 'preparing', message: '正在准备提示' },
    hints_viewed_max: 0, passed: false, created_at: '2026-10-16T00:00:00Z' }
  const question = { problem_id: 'level2', first_wrong_submission_id: 5,
    last_wrong_code: 'print(100)', title: '求和', description: '求和', source: '系统关卡',
    first_wrong_at: '2026-10-16T00:00:00Z', latest_suspected_cause: null,
    review_count: 0, review_rate_percent: null, recent_review_passed: 0,
    recent_review_total: 0, related_questions: [] }
  const states = [[question], {}, 'level2', 'insight', false, '', 'print(100)', '', false, false,
    null, null, 0, null, {}, [item], 1, 0, 0, 0, false, '', '']
  let stateIndex = 0
  const hooks = {
    ...React,
    useState: () => { const index = stateIndex++; return [states[index], next => updates.push({ index, next })] },
    useRef: value => ({ current: value }),
    useEffect: effect => effects.push(effect),
  }
  const History = loadJsx('../src/pages/LearningHistory.jsx', {
    react: hooks,
    'react-router-dom': { useNavigate: () => () => {} },
    '../components/ProblemMetadata.jsx': () => null,
    '../components/SubmissionFeedback.jsx': () => null,
    '../components/codeApi.mjs': {
      requestAnalysis: async id => { assert.equal(id, 81); return new Promise(resolve => { finishAnalysis = resolve }) },
    },
  })
  const originalStorage = Object.getOwnPropertyDescriptor(global, 'localStorage')
  Object.defineProperty(global, 'localStorage', { configurable: true, value: { getItem: () => 'owner-token' } })
  try {
    const tree = History()
    const cleanup = effects[0]()
    const find = node => {
      if (!React.isValidElement(node)) return null
      if (node.props.className === 'mistake-history-item') return node
      return React.Children.toArray(node.props.children).map(find).find(Boolean)
    }
    find(tree).props.onToggle({ currentTarget: { open: true } })
    assert.equal(typeof finishAnalysis, 'function')
    finishAnalysis({ analysis: failure.analysis })
    await new Promise(resolve => setImmediate(resolve))
    const changed = updates.find(update => update.index === 15 && typeof update.next === 'function')
    assert.equal(changed.next([item])[0].analysis.status, 'ready')
    cleanup()
  } finally {
    if (originalStorage) Object.defineProperty(global, 'localStorage', originalStorage)
    else delete global.localStorage
  }
})
