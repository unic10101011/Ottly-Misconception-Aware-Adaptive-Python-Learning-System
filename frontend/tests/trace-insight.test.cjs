const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { transformSync } = require('esbuild')

function setup(file) {
  const states = [], refs = [], effects = [], calls = []
  let cursor = 0, refCursor = 0, resolve, reject
  const hooks = { ...React, useState(initial) {
    const slot = cursor++
    if (!(slot in states)) states[slot] = typeof initial === 'function' ? initial() : initial
    return [states[slot], value => { states[slot] = typeof value === 'function' ? value(states[slot]) : value }]
  }, useRef(initial) { return refs[refCursor++] ||= { current: initial } }, useEffect(effect) { effects.push(effect) } }
  const filename = path.resolve(__dirname, '../src/components/' + file)
  const loaded = new Module(filename, module)
  loaded.filename = filename; loaded.paths = Module._nodeModulePaths(path.dirname(filename))
  const nativeRequire = loaded.require.bind(loaded)
  loaded.require = id => id === 'react' ? hooks : id === './codeApi.mjs' ? {
    requestTraceExplanation: (...args) => { calls.push(args); return new Promise((yes, no) => { resolve = yes; reject = no }) },
  } : nativeRequire(id)
  loaded._compile(transformSync(fs.readFileSync(filename, 'utf8'), { loader: 'jsx', format: 'cjs' }).code, filename)
  return { render(props) { cursor = 0; refCursor = 0; effects.length = 0; return loaded.exports.default(props) }, effects, calls,
    resolve: value => resolve(value), reject: value => reject(value) }
}
function find(tree, predicate) {
  if (!React.isValidElement(tree)) return null
  if (predicate(tree)) return tree
  return React.Children.toArray(tree.props.children).map(child => find(child, predicate)).find(Boolean)
}
const ask = tree => find(tree, node => node.type === 'button')
const replay = { trace_id: 'owned-trace', code: 'total = i\nprint(total)', steps: [
  { variables: { total: '1' }, scope_id: 'module' }, { variables: { total: '2' }, scope_id: 'module' },
] }

test('number boxes use actual old/new values and list cells preserve indices and snapshots', () => {
  const app = setup('TraceVisuals.jsx')
  const numeric = app.render({ trace: { problem_id: 'shell-total-v1', code: 'total = i' },
    previous: { event: 'line', line: 1, visual_values: { total: { kind: 'number', text: '1' } } },
    step: { visual_values: { total: { kind: 'number', text: '2' } } } })
  assert.match(renderToStaticMarkup(numeric), /total：1 → 2/)
  assert.doesNotMatch(renderToStaticMarkup(numeric), /1 \+ 2|累加成功/)
  const before = { visual_values: { values: { kind: 'list', items: ['2'] } } }
  const list = app.render({ trace: { problem_id: 'temperature-max-v1', code: 'print(values[0])' }, previous: before,
    step: { visual_values: { values: { kind: 'list', items: ['2', '9'] } }, list_accesses: [{ name: 'values', index: 0, mode: 'read' }] } })
  const html = renderToStaticMarkup(list)
  assert.match(html, /即将读取下标 0|即将<!-- -->读取/)
  assert.equal(find(list, n => n.type === 'li' && n.props.className.includes('is-accessed')).props.children[1].props.children, '2')
  assert.ok(find(list, n => n.type === 'li' && n.props.className.includes('is-new')))
  assert.deepEqual(before.visual_values.values.items, ['2'])
})

test('AI runs only on click, caches by step and never puts a late answer under another step', async () => {
  const oldStorage = global.localStorage
  global.localStorage = { getItem: () => 'owner-token' }
  try {
    const app = setup('TraceStepInsight.jsx')
    let tree = app.render({ trace: replay, index: 0 })
    const cleanup = app.effects[0]()
    assert.equal(app.calls.length, 0)
    const pending = ask(tree).props.onClick()
    ask(tree).props.onClick()
    assert.deepEqual(app.calls, [['owned-trace', 0, 'owner-token']])
    tree = app.render({ trace: replay, index: 1, previous: replay.steps[0] })
    assert.equal(ask(tree).props.disabled, true)
    app.resolve({ answer: '只解释第一步' }); await pending
    assert.doesNotMatch(renderToStaticMarkup(app.render({ trace: replay, index: 1 })), /只解释第一步/)
    tree = app.render({ trace: replay, index: 0 })
    assert.match(renderToStaticMarkup(tree), /只解释第一步/)
    await ask(tree).props.onClick()
    assert.equal(app.calls.length, 1)
    cleanup()
  } finally { global.localStorage = oldStorage }
})

test('long AI explanations show a short preview and collapsed details', async () => {
  global.localStorage = { getItem: () => 'owner-token' }
  const app = setup('TraceStepInsight.jsx')
  let tree = app.render({ trace: replay, index: 0 })
  app.effects[0]()
  const pending = ask(tree).props.onClick()
  app.resolve({ answer: '先观察本轮变量。后面这段是补充讲解，需要时再阅读。' })
  await pending
  tree = app.render({ trace: replay, index: 0 })
  const details = find(tree, node => node.type === 'details')
  assert.ok(details)
  assert.notEqual(details.props.open, true)
  assert.ok(find(tree, node => node.props.className === 'trace-ai-preview' && node.props.children === '先观察本轮变量。'))
})

test('AI failures can retry and a reply after closing is discarded', async () => {
  const oldStorage = global.localStorage
  global.localStorage = { getItem: () => 'owner-token' }
  try {
    const app = setup('TraceStepInsight.jsx')
    let tree = app.render({ trace: replay, index: 0 })
    const cleanup = app.effects[0]()
    let pending = ask(tree).props.onClick()
    app.reject(new Error('解释超时')); await pending
    tree = app.render({ trace: replay, index: 0 })
    assert.match(renderToStaticMarkup(tree), /解释超时/)
    pending = ask(tree).props.onClick()
    cleanup()
    app.resolve({ answer: '不应显示的迟到解答' }); await pending
    assert.doesNotMatch(renderToStaticMarkup(app.render({ trace: replay, index: 0 })), /不应显示的迟到解答/)
  } finally { global.localStorage = oldStorage }
})
