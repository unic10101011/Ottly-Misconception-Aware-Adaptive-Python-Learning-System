const test = require('node:test')
const assert = require('node:assert/strict')
const React = require('react')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const { transformSync } = require('esbuild')

function harness(file, overrides) {
  const states = []
  const refs = []
  const effects = []
  let cursor = 0
  let refCursor = 0
  let collect = true
  const hooks = { ...React, useEffect: effect => { if (collect) effects.push(effect) }, useRef: initial => {
    const index = refCursor++
    return refs[index] ||= { current: initial }
  },
    useState: initial => {
      const slot = cursor++
      if (!(slot in states)) states[slot] = typeof initial === 'function' ? initial() : initial
      return [states[slot], value => { states[slot] = typeof value === 'function' ? value(states[slot]) : value }]
    },
  }
  const filename = path.resolve(__dirname, file)
  const loaded = new Module(filename, module)
  loaded.filename = filename
  loaded.paths = Module._nodeModulePaths(path.dirname(filename))
  const nativeRequire = loaded.require.bind(loaded)
  loaded.require = id => id.endsWith('AiRetry.jsx') ? require('./load-ai-retry.cjs') : id === 'react' ? hooks : Object.hasOwn(overrides, id) ? overrides[id] : nativeRequire(id)
  loaded._compile(transformSync(fs.readFileSync(filename, 'utf8'), { loader: 'jsx', format: 'cjs' }).code, filename)
  const render = props => { cursor = 0; refCursor = 0; return loaded.exports.default(props) }
  render.mount = () => { collect = false; return effects.map(effect => effect()) }
  render.effects = effects
  return render
}
function find(tree, predicate) {
  if (!React.isValidElement(tree)) return null
  if (predicate(tree)) return tree
  return React.Children.toArray(tree.props.children).map(child => find(child, predicate)).find(Boolean)
}
const button = (tree, text) => find(tree, node => node.type === 'button' && node.props.children === text)

function hearPresetQuestion(render, props) {
  find(render(props), node => node.props.className === 'story-frame').props.onClick({ target: { closest: () => null } })
  assert.equal(find(render(props), node => node.type === 'input'), undefined, 'preset selection has no free question input')
  const group = find(render(props), node => node.props['aria-label'] === '想问的问题')
  React.Children.toArray(group.props.children)[0].props.onClick()
  for (let step = 0; step < 20; step++) {
    const tree = render(props)
    const next = button(tree, 'NEXT →')
    if (!next) return
    assert.equal(find(tree, node => node.type === 'input'), undefined, 'preset explanation has no free question input')
    next.props.onClick()
  }
  assert.fail('preset question should return to the question menu')
}

test('first-level tour precedes knowledge dialogue and can be replayed after completion', async () => {
  const Tour = () => null
  const Player = () => null
  const originalStorage = global.localStorage
  global.localStorage = { getItem: () => 'token' }
  let completed = false
  const overrides = { './StoryDialogue.jsx': Player, './BeginnerTour.jsx': Tour,
    '../codeApi.mjs': { getGuide: async () => ({ story: { id: 'level1' }, completed }) } }
  try {
    const props = { problemId: 'level1', beginner: true }
    const render = harness('../src/components/story/LessonIntro.jsx', overrides)
    render(props); render.mount(); await new Promise(resolve => setImmediate(resolve))
    let tree = render(props)
    assert.ok(find(tree, node => node.type === Tour))
    assert.equal(find(tree, node => node.type === Player), undefined)
    find(tree, node => node.type === Tour).props.onFinish()
    tree = render(props)
    assert.equal(find(tree, node => node.type === Tour), undefined)
    assert.equal(find(tree, node => node.type === Player).props.canSkip, false)
    completed = true
    const fresh = harness('../src/components/story/LessonIntro.jsx', overrides)
    fresh(props); fresh.mount(); await new Promise(resolve => setImmediate(resolve))
    assert.equal(find(fresh(props), node => node.type === Tour), undefined)
    find(fresh(props), node => node.props['aria-label'] === '重看第一关操作指引').props.onClick()
    assert.ok(find(fresh(props), node => node.type === Tour))
  } finally { if (originalStorage === undefined) delete global.localStorage; else global.localStorage = originalStorage }
})

test('tour advances every two seconds, supports pausing and cancels old timers', () => {
  const render = harness('../src/components/story/BeginnerTour.jsx', { './beginner-tour.css': {} })
  const originalTimeout = global.setTimeout, originalClear = global.clearTimeout
  let scheduled, cleared, finished = 0
  global.setTimeout = (callback, ms) => { scheduled = { callback, ms }; return scheduled }
  global.clearTimeout = timer => { cleared = timer }
  const props = { onFinish: () => finished++ }
  const timerEffect = () => render.effects.at(-2)()
  try {
    let tree = render(props)
    assert.match(find(tree, node => node.type === 'img').props.src, /peek.png$/)
    let cleanup = timerEffect()
    assert.equal(scheduled.ms, 1000)
    cleanup(); assert.equal(cleared, scheduled)
    scheduled.callback()
    tree = render(props)
    assert.equal(find(tree, node => node.props.role === 'status').props.children, '欢迎来到编程世界！')
    cleanup = timerEffect(); assert.equal(scheduled.ms, 2400)
    cleanup(); scheduled.callback()
    for (const text of ['这是代码编辑器，是你写程序的地方', '写完代码后，点击运行',
      '你的程序得出的结果会显示在这里', '系统会测试你编写的代码']) {
      tree = render(props)
      assert.equal(find(tree, node => node.props.role === 'status').props.children, text)
      cleanup = timerEffect(); assert.equal(scheduled.ms, 2000)
      cleanup(); scheduled.callback()
    }
    tree = render(props)
    assert.match(find(tree, node => node.props.role === 'status').props.children, /只有提交判题/)
    button(tree, '暂停播放').props.onClick()
    tree = render(props)
    assert.equal(timerEffect(), undefined)
    assert.ok(button(tree, '继续播放'))
    button(tree, '下一步 →').props.onClick()
    tree = render(props)
    assert.equal(finished, 0)
    button(tree, '开始知识点讲解 →').props.onClick()
    assert.equal(finished, 1)
  } finally { global.setTimeout = originalTimeout; global.clearTimeout = originalClear }
})

for (const passed of [false, true]) test(`first-submission encouragement explains the actual verdict (passed: ${passed})`, () => {
  const render = harness('../src/components/story/BeginnerTour.jsx', { './beginner-tour.css': {} })
  let finished = 0
  const props = { result: { judge: { passed } }, onFinish: () => finished++ }
  assert.equal(find(render(props), node => node.props.role === 'status').props.children, '恭喜你完成第一个代码的编写！')
  button(render(props), '下一步 →').props.onClick()
  assert.match(find(render(props), node => node.props.role === 'status').props.children, passed ? /全部测试通过/ : /还没有全部通过/)
  button(render(props), '下一步 →').props.onClick()
  assert.match(find(render(props), node => node.props.role === 'status').props.children, passed ? /前往下一关/ : /修改代码后/)
  button(render(props), '下一步 →').props.onClick()
  assert.equal(finished, 0)
  button(render(props), '我知道啦，继续探索！').props.onClick()
  assert.equal(finished, 1)
})

test('all twelve guides keep preset options and show input only after all preset explanations', async () => {
  const stories = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/app/data/guides/catalog.json'), 'utf8'))
  const engine = await import('../src/components/story/storyEngine.mjs')
  for (const source of Object.values(stories)) {
    for (const node of source.nodes) {
      const render = harness('../src/components/story/StoryDialogue.jsx', { './storyEngine.mjs': engine })
      assert.equal(find(render({ story: { ...source, start: node.id } }), item => item.type === 'input'), undefined)
    }
    const story = { ...source, start: source.nodes.find(node => node.type === 'choice').id }
    const props = { story, canSkip: false }
    const render = harness('../src/components/story/StoryDialogue.jsx', { './storyEngine.mjs': engine })
    hearPresetQuestion(render, props)
    assert.equal(find(render(props), node => node.type === 'input'), undefined)
    assert.ok(find(render(props), node => node.props['aria-label'] === '想问的问题'))
    assert.notEqual(find(render(props), node => node.props.className === 'story-sr').props.children, '还有想问的吗？也可以继续。')
    hearPresetQuestion(render, props)
    assert.ok(find(render(props), node => node.type === 'input'), source.problemId)
    assert.equal(find(render(props), node => node.props.className === 'story-sr').props.children, '还有想问的吗？也可以继续。')
  }
})

test('free questions reject blanks, show replies, retry errors and ignore late replies after continuing', async () => {
  const source = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/app/data/guides/catalog.json'), 'utf8')).level1
  const engine = await import('../src/components/story/storyEngine.mjs')
  const story = { ...source, start: source.nodes.find(node => node.type === 'choice').id }
  let resolve, reject, calls = 0
  const render = harness('../src/components/story/StoryDialogue.jsx', {
    './storyEngine.mjs': engine,
    '../codeApi.mjs': { askGuideQuestion: (pid, question, history, token) => {
      calls++; assert.equal(pid, 'level1'); assert.equal(token, 'test-token')
      return new Promise((yes, no) => { resolve = yes; reject = no })
    } },
  })
  const props = { story, canSkip: false }
  const reveal = () => find(render(props), node => node.props.className === 'story-frame').props.onClick({ target: { closest: () => null } })
  const input = () => find(render(props), node => node.type === 'input')
  const send = () => find(render(props), node => node.type === 'form').props.onSubmit({ preventDefault() {} })
  const originalStorage = global.localStorage
  global.localStorage = { getItem: () => 'test-token' }
  try {
    hearPresetQuestion(render, props)
    hearPresetQuestion(render, props)
    reveal()
    await send()
    assert.equal(calls, 0)
    input().props.onChange({ target: { value: '引号有什么作用？' } })
    const submit = find(render(props), node => node.type === 'form').props.onSubmit
    let pending = send()
    await submit({ preventDefault() {} })
    assert.equal(calls, 1, 'duplicate submits are blocked')
    assert.equal(input(), undefined, 'input is hidden while answering')
    assert.ok(find(render(props), node => node.props.className === 'story-stage story-stage-answer'))
    assert.equal(find(render(props), node => node.props.className === 'story-portrait'), undefined)
    reject(new Error('服务繁忙'))
    await pending
    assert.equal(input().props.value, '引号有什么作用？')
    assert.ok(find(render(props), node => node.props.role === 'alert'))
    pending = send()
    resolve({ answer: '引号用来标记字符串。' })
    await pending
    reveal()
    assert.equal(find(render(props), node => node.props.className === 'story-copy').props.children, '引号用来标记字符串。')
    assert.ok(find(render(props), node => node.props.className === 'story-stage story-stage-answer'), 'answer remains expanded until the reader is done')
    assert.equal(input(), undefined)
    button(render(props), '继续提问').props.onClick()
    reveal()
    assert.ok(find(render(props), node => node.props.className === 'story-portrait'))
    assert.ok(find(render(props), node => node.props.className === 'story-stage'))
    assert.equal(find(render(props), node => node.props.className === 'story-copy').props.children, '还有想问的吗？也可以继续。')
    assert.equal(input().props.value, '')
    input().props.onChange({ target: { value: '再举个例子' } })
    pending = send()
    assert.equal(button(render(props), '我明白了，继续').props.disabled, false)
    button(render(props), '我明白了，继续').props.onClick()
    resolve({ answer: '迟到的回答' })
    await pending
    reveal()
    assert.notEqual(find(render(props), node => node.props.className === 'story-copy').props.children, '迟到的回答')
    assert.equal(input(), undefined)
  } finally { if (originalStorage === undefined) delete global.localStorage; else global.localStorage = originalStorage }
})

test('quiz keeps all options visible during explanation, marks only the selected answer and locks further answers', async () => {
  const source = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/app/data/guides/catalog.json'), 'utf8')).level1
  const engine = await import('../src/components/story/storyEngine.mjs')
  for (const correct of [false, true]) {
    const story = { ...source, start: 'quiz-1' }
    const quiz = story.nodes.find(node => node.id === story.start)
    const chosen = quiz.options.find(option => (option.id === quiz.correct) === correct)
    const render = harness('../src/components/story/StoryDialogue.jsx', { './storyEngine.mjs': engine })
    const props = { story, canSkip: false }
    const reveal = tree => find(tree, node => node.props.className === 'story-frame').props.onClick({ target: { closest: () => null } })
    reveal(render(props))
    const pick = find(render(props), node => node.type === 'button' && find(node, child => child.type === 'span' && child.props.children === chosen.text))
    pick.props.onClick()
    let tree = render(props)
    let group = find(tree, node => node.props['aria-label'] === '知识小测选项')
    assert.ok(group, 'answers stay available for visual comparison during feedback')
    const options = React.Children.toArray(group.props.children)
    assert.equal(options.length, 3)
    assert.ok(options.every(option => option.props.disabled))
    assert.equal(options.filter(option => option.props.className.includes(correct ? 'is-correct' : 'is-incorrect')).length, 1)
    assert.equal(button(tree, '继续下一步'), undefined, 'wait for explanation before next action')
    reveal(tree)
    tree = render(props)
    assert.ok(button(tree, correct ? '继续下一步' : '重新选择'))
    if (!correct) {
      button(tree, '重新选择').props.onClick()
      group = find(render(props), node => node.props['aria-label'] === '知识小测选项')
      assert.ok(React.Children.toArray(group.props.children).every(option => !option.props.className.includes('is-incorrect')))
    }
  }
})

test('first NEXT reveals the current line; second advances; history and exit never finish the intro', async () => {
  const story = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/app/data/guides/catalog.json'), 'utf8')).level1
  const engine = await import('../src/components/story/storyEngine.mjs')
  const render = harness('../src/components/story/StoryDialogue.jsx', { './storyEngine.mjs': engine })
  let finishes = 0, exits = 0
  const props = { story, canSkip: false, onFinish: () => finishes++, onExit: () => exits++ }
  let tree = render(props)
  let escapePrevented = false
  find(tree, node => node.props.className === 'story-dialog').props.onKeyDown({ key: 'Escape', preventDefault: () => { escapePrevented = true } })
  assert.equal(escapePrevented, true, 'Escape is stopped before native dialog dismissal')
  assert.equal(button(tree, '跳过引导').props.disabled, true)
  button(tree, 'NEXT →').props.onClick()
  tree = render(props)
  assert.equal(find(tree, node => node.props.className === 'story-copy').props.children, story.nodes[0].text)
  button(tree, 'NEXT →').props.onClick()
  tree = render(props)
  assert.equal(find(tree, node => node.props.className === 'story-copy').props.children, '')
  button(tree, '历史对话').props.onClick()
  tree = render(props)
  const history = find(tree, node => typeof node.type === 'function')
  assert.ok(history.props.entries.length >= 1)
  assert.ok(history.props.entries.every(entry => !entry.text.includes('可能把它当成变量名')))
  assert.ok(history.props.entries[history.props.entries.length - 1].text.length < story.nodes[1].text.length,
    'the current history line never exposes text that has not been typed yet')
  const panel = history.type(history.props)
  const target = { getBoundingClientRect: () => ({ left: 20, right: 400, top: 20, bottom: 300 }) }
  const inside = { target, currentTarget: target, clientX: 40, clientY: 50 }
  let stopped = false
  const outside = { target, currentTarget: target, clientX: 500, clientY: 50, stopPropagation: () => { stopped = true } }
  panel.props.onPointerDown(inside)
  panel.props.onClick(inside)
  assert.ok(find(render(props), node => typeof node.type === 'function'), 'panel padding does not close history')
  panel.props.onPointerDown(inside)
  panel.props.onClick(outside)
  assert.ok(find(render(props), node => typeof node.type === 'function'), 'dragging from history to backdrop does not close it')
  panel.props.onPointerDown(outside)
  panel.props.onClick(outside)
  assert.equal(stopped, true, 'backdrop close never clicks through into the underlying story')
  assert.equal(find(render(props), node => typeof node.type === 'function'), undefined)
  assert.equal(find(render(props), node => node.props.className === 'story-copy').props.children, '', 'closing history does not advance or reveal the line')
  button(render(props), '返回学习地图').props.onClick()
  assert.equal(exits, 1)
  assert.equal(finishes, 0)
})

test('guide saves completion before entering code, retries failures and reads durable replay state', async () => {
  const level1Story = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/app/data/guides/catalog.json'), 'utf8')).level1
  const Player = () => null
  let saved = false, fail = true
  const overrides = { './StoryDialogue.jsx': Player, './BeginnerTour.jsx': () => null, '../codeApi.mjs': {
    getGuide: async () => ({ story: level1Story, completed: saved }),
    completeGuide: async (id, version, heard, answers) => {
      assert.equal(id, 'level1'); assert.deepEqual(answers, { q: 'a' })
      if (fail) throw new Error('offline')
      saved = true
    },
  } }
  const render = harness('../src/components/story/LessonIntro.jsx', overrides)
  const player = tree => find(tree, node => node.type === Player)
  const props = { problemId: 'level1' }
  const originalStorage = global.localStorage
  global.localStorage = { getItem: () => 'token' }
  try {
    render(props); render.mount(); await new Promise(resolve => setImmediate(resolve))
    assert.equal(player(render(props)).props.canSkip, false)
    player(render(props)).props.onSkip()
    assert.ok(player(render(props)))
    await player(render(props)).props.onFinish({ heard: ['quotes'], answers: { q: 'a' } })
    assert.ok(player(render(props)))
    assert.match(player(render(props)).props.saveError, /offline/)
    fail = false
    await player(render(props)).props.onFinish({ heard: ['quotes'], answers: { q: 'a' } })
    assert.equal(player(render(props)), undefined)
    const fresh = harness('../src/components/story/LessonIntro.jsx', overrides)
    fresh(props); fresh.mount(); await new Promise(resolve => setImmediate(resolve))
    assert.equal(player(fresh(props)), undefined)
    find(fresh(props), node => node.props['aria-label'] === '重温知识点引导').props.onClick()
    assert.equal(player(fresh(props)).props.canSkip, true)
  } finally { if (originalStorage === undefined) delete global.localStorage; else global.localStorage = originalStorage }
})
