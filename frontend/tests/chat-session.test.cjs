const test = require('node:test')
const assert = require('node:assert/strict')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { transformSync } = require('esbuild')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')

const tick = () => new Promise(resolve => setImmediate(resolve))
const snapshot = (extra = {}) => ({ session_id: 'current', runtime_id: 'boot-one', context_full: false,
  pending: false, messages: [{ content: '原来的问题', isUser: true }, { content: '原来的回复', isUser: false }], ...extra })
const jsonResponse = data => new Response(JSON.stringify({ code: 200, data }), { status: 200 })
const find = (node, predicate) => !React.isValidElement(node) ? null : predicate(node) ? node
  : React.Children.toArray(node.props.children).map(child => find(child, predicate)).find(Boolean)

test('a failed reply retries in place once without duplicating the user question', async () => {
  let attempts = 0, finish
  const env = environment(async (url) => {
    if (url === '/api/v1/ai/chat') {
      attempts++
      if (attempts === 1) throw new TypeError('Failed to fetch')
      return new Promise(resolve => { finish = resolve })
    }
    return jsonResponse(snapshot({ messages: [] }))
  })
  const chat = mountChat()
  try {
    chat.render(); await tick()
    let tree = chat.render()
    find(tree, n => n.props.id === 'chat-question').props.onChange({ target: { value: '为什么需要等号？' } })
    tree = chat.render()
    await find(tree, n => n.type === 'form').props.onSubmit({ preventDefault() {} })
    tree = chat.render()
    const retry = find(tree, n => n.props.label === '重新生成这条回复')
    assert.ok(retry)
    const promise = retry.props.onRetry({ preventDefault() {} })
    retry.props.onRetry({ preventDefault() {} })
    await tick()
    assert.equal(attempts, 2)
    const html = renderToStaticMarkup(chat.render())
    assert.equal((html.match(/为什么需要等号？/g) || []).length, 1)
    finish(new Response('data: {"content":"解释"}\n\ndata: {"content":"[END]"}\n\n', { headers: { 'Content-Type': 'text/event-stream' } }))
    await promise
    const calls = env.calls.filter(c => c.url === '/api/v1/ai/chat')
    assert.equal(JSON.parse(calls[0].options.body).question, JSON.parse(calls[1].options.body).question)
  } finally { chat.unmount(); env.restore() }
})

function mountChat() {
  const values = [], refs = [], effects = []
  let stateIndex = 0, refIndex = 0, effectIndex = 0
  const pending = []
  const hooks = { ...React,
    useState: initial => {
      const slot = stateIndex++
      if (!(slot in values)) values[slot] = typeof initial === 'function' ? initial() : initial
      return [values[slot], next => { values[slot] = typeof next === 'function' ? next(values[slot]) : next }]
    },
    useRef: initial => refs[refIndex++] ||= { current: initial },
    useEffect: (effect, deps) => {
      const slot = effectIndex++
      if (!effects[slot] || deps.some((value, index) => value !== effects[slot].deps[index])) {
        pending.push(() => {
          effects[slot]?.cleanup?.()
          effects[slot] = { deps, cleanup: effect() }
        })
      }
    },
  }
  const filename = path.resolve(__dirname, '../src/pages/AIchat.jsx')
  const compiled = transformSync(fs.readFileSync(filename, 'utf8'), { loader: 'jsx', format: 'cjs' })
  const loaded = new Module(filename, module)
  loaded.filename = filename
  loaded.paths = Module._nodeModulePaths(path.dirname(filename))
  loaded.require = id => {
    if (id.endsWith('AiRetry.jsx')) return require('./load-ai-retry.cjs')
    if (id === 'react') return hooks
    if (id === 'react-router-dom') return { useNavigate: () => () => {} }
    if (id.endsWith('.png')) return 'test.png'
    if (id.endsWith('ChatContent.jsx')) return props => React.createElement('span', null, props.content)
    return require(id)
  }
  loaded._compile(compiled.code, filename)
  return {
    render() { stateIndex = 0; refIndex = 0; effectIndex = 0; const tree = loaded.exports.default(); pending.splice(0).forEach(run => run()); return tree },
    unmount() { effects.forEach(effect => effect?.cleanup?.()) },
  }
}

function environment(fetcher) {
  const originals = Object.fromEntries(['fetch', 'window', 'localStorage', 'setInterval', 'clearInterval'].map(key => [key, Object.getOwnPropertyDescriptor(global, key)]))
  const listeners = new Map(), timers = new Map(), calls = []
  Object.defineProperty(global, 'localStorage', { configurable: true, value: { getItem: () => 'student-token' } })
  global.window = { addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: (name, fn) => { if (listeners.get(name) === fn) listeners.delete(name) } }
  global.setInterval = fn => { const id = Symbol(); timers.set(id, fn); return id }
  global.clearInterval = id => timers.delete(id)
  global.fetch = async (url, options = {}) => {
    calls.push({ url, options })
    assert.equal(options.headers.Authorization, 'Bearer student-token')
    if (url === '/api/v1/ai/sessions') return jsonResponse({ sessions: [] })
    if (url.startsWith('/api/v1/ai/history')) return new Response(JSON.stringify({ code: 200, data: [], total: 0 }), { status: 200 })
    return fetcher(url, options)
  }
  return { calls, listeners, timers, restore() {
    for (const [key, descriptor] of Object.entries(originals)) {
      if (descriptor) Object.defineProperty(global, key, descriptor)
      else delete global[key]
    }
  } }
}

test('leaving and remounting chat restores the same saved conversation without creating another', async () => {
  const env = environment(async () => jsonResponse(snapshot()))
  try {
    for (let visit = 0; visit < 2; visit++) {
      const chat = mountChat()
      chat.render()
      await tick()
      const tree = chat.render()
      assert.match(renderToStaticMarkup(tree), /原来的问题|原来的回复/)
      assert.equal(find(tree, node => node.props.id === 'chat-session-select').props.value, 'current')
      chat.unmount()
    }
    assert.equal(env.calls.filter(call => call.url === '/api/v1/ai/session').length, 2)
    assert.ok(env.calls.every(call => call.options.method !== 'POST'))
  } finally { env.restore() }
})

test('returning while an answer is generating restores partial text and polls until saved', async () => {
  let pending = true
  const env = environment(async () => jsonResponse(snapshot({ pending,
    messages: [{ content: '正在问的问题', isUser: true }, { content: pending ? '半段回答' : '完整回答', isUser: false }] })))
  const chat = mountChat()
  try {
    chat.render(); await tick()
    let tree = chat.render()
    assert.match(renderToStaticMarkup(tree), /半段回答/)
    assert.equal(find(tree, node => node.props.id === 'chat-question').props.disabled, true)
    assert.equal(env.timers.size, 1)
    pending = false
    await [...env.timers.values()][0]()
    await tick()
    tree = chat.render()
    assert.match(renderToStaticMarkup(tree), /完整回答/)
    assert.equal(find(tree, node => node.props.id === 'chat-question').props.disabled, false)
    assert.equal(env.timers.size, 0)
  } finally { chat.unmount(); env.restore() }
})

test('backend restart on focus replaces active conversation and keeps the typed question', async () => {
  let restarted = false
  const env = environment(async () => jsonResponse(restarted ? snapshot({ runtime_id: 'boot-two', session_id: 'new', messages: [] }) : snapshot()))
  const chat = mountChat()
  try {
    chat.render(); await tick()
    let tree = chat.render()
    find(tree, node => node.props.id === 'chat-question').props.onChange({ target: { value: '尚未发送' } })
    restarted = true
    await env.listeners.get('focus')(); await tick()
    tree = chat.render()
    const html = renderToStaticMarkup(tree)
    assert.match(html, /项目已重启/)
    assert.doesNotMatch(html, /原来的问题|原来的回复/)
    assert.equal(find(tree, node => node.props.id === 'chat-question').props.value, '尚未发送')
  } finally { chat.unmount(); env.restore() }
})

test('full context disables sending and new conversation clears the old context', async () => {
  const env = environment(async (url, options) => {
    if (options.method === 'POST') {
      assert.deepEqual(JSON.parse(options.body), { session_id: null })
      return jsonResponse(snapshot({ session_id: 'new', messages: [] }))
    }
    return jsonResponse(snapshot({ context_full: true }))
  })
  const chat = mountChat()
  try {
    chat.render(); await tick()
    let tree = chat.render()
    assert.match(renderToStaticMarkup(tree), /上下文上限/)
    assert.equal(find(tree, node => node.props.id === 'chat-question').props.disabled, true)
    find(tree, node => node.type === 'button' && node.props.children === '新开一个对话').props.onClick()
    await tick()
    tree = chat.render()
    assert.doesNotMatch(renderToStaticMarkup(tree), /原来的问题|上下文上限/)
    assert.equal(find(tree, node => node.props.id === 'chat-question').props.disabled, false)
  } finally { chat.unmount(); env.restore() }
})

test('a rejected over-budget question remains editable after opening a new chat', async () => {
  const env = environment(async (url, options) => {
    if (url === '/api/v1/ai/chat') {
      assert.equal(JSON.parse(options.body).runtime_id, 'boot-one')
      return new Response(JSON.stringify({ detail: { code: 'CHAT_CONTEXT_FULL', message: '请新开对话' } }), { status: 409 })
    }
    return jsonResponse(snapshot())
  })
  const chat = mountChat()
  try {
    chat.render(); await tick()
    let tree = chat.render()
    find(tree, node => node.props.id === 'chat-question').props.onChange({ target: { value: '保留这条问题' } })
    tree = chat.render()
    await find(tree, node => node.type === 'form').props.onSubmit({ preventDefault() {} })
    tree = chat.render()
    assert.match(renderToStaticMarkup(tree), /上下文上限/)
    assert.equal(find(tree, node => node.props.id === 'chat-question').props.value, '保留这条问题')
    find(tree, node => node.type === 'button' && node.props.children === '新开一个对话').props.onClick()
    await tick()
    tree = chat.render()
    assert.equal(find(tree, node => node.props.id === 'chat-question').props.value, '保留这条问题')
    assert.equal(find(tree, node => node.props.id === 'chat-question').props.disabled, false)
  } finally { chat.unmount(); env.restore() }
})

test('leaving during an SSE reply keeps the request alive and returning restores its completed answer', async () => {
  let controller, completed = false
  const env = environment(async (url, options) => {
    if (url === '/api/v1/ai/chat') {
      assert.equal(JSON.parse(options.body).session_id, 'current')
      return new Response(new ReadableStream({ start(value) { controller = value } }), {
        status: 200, headers: { 'Content-Type': 'text/event-stream' },
      })
    }
    return jsonResponse(snapshot(completed ? { messages: [{ content: '新问题', isUser: true }, { content: '完整中文回复', isUser: false }] } : {}))
  })
  const first = mountChat()
  let second
  try {
    first.render(); await tick()
    let tree = first.render()
    find(tree, node => node.props.id === 'chat-question').props.onChange({ target: { value: '新问题' } })
    tree = first.render()
    const sending = find(tree, node => node.type === 'form').props.onSubmit({ preventDefault() {} })
    await tick()
    first.unmount()
    const bytes = new TextEncoder().encode('data: {"content":"完整中文回复","session_id":"current"}\n\ndata: {"content":"[END]","session_id":"current"}\n\n')
    controller.enqueue(bytes.slice(0, 20))
    controller.enqueue(bytes.slice(20))
    completed = true
    controller.close()
    await sending
    second = mountChat()
    second.render(); await tick()
    assert.match(renderToStaticMarkup(second.render()), /新问题|完整中文回复/)
  } finally { second?.unmount(); env.restore() }
})
