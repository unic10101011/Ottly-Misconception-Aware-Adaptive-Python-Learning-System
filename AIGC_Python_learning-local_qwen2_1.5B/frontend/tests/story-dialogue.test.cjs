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
  loaded.require = id => id === 'react' ? hooks : Object.hasOwn(overrides, id) ? overrides[id] : nativeRequire(id)
  loaded._compile(transformSync(fs.readFileSync(filename, 'utf8'), { loader: 'jsx', format: 'cjs' }).code, filename)
  const render = props => { cursor = 0; refCursor = 0; return loaded.exports.default(props) }
  render.mount = () => { collect = false; return effects.map(effect => effect()) }
  return render
}
function find(tree, predicate) {
  if (!React.isValidElement(tree)) return null
  if (predicate(tree)) return tree
  return React.Children.toArray(tree.props.children).map(child => find(child, predicate)).find(Boolean)
}
const button = (tree, text) => find(tree, node => node.type === 'button' && node.props.children === text)

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
  const overrides = { './StoryDialogue.jsx': Player, '../codeApi.mjs': {
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
