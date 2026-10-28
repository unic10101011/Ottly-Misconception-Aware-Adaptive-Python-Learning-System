const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const Module = require('node:module')
const { buildSync } = require('esbuild')
const { JSDOM } = require('jsdom')
const React = require('react')
const { act } = React
const { createRoot } = require('react-dom/client')

// Isolated DOM simulation. This does not replace real-browser/IME acceptance.
const dom = new JSDOM('<!doctype html><html><body></body></html>', { pretendToBeVisual: true })
for (const name of ['window', 'Window', 'document', 'MutationObserver', 'HTMLElement', 'Node', 'DOMRect']) global[name] = dom.window[name]
global.getComputedStyle = dom.window.getComputedStyle.bind(dom.window)
global.requestAnimationFrame = dom.window.requestAnimationFrame.bind(dom.window)
global.cancelAnimationFrame = dom.window.cancelAnimationFrame.bind(dom.window)
global.IS_REACT_ACT_ENVIRONMENT = true
dom.window.Range.prototype.getClientRects = () => []
dom.window.Range.prototype.getBoundingClientRect = () => new dom.window.DOMRect()

const filename = path.resolve(__dirname, '../src/components/PythonEditorView.jsx')
const compiled = buildSync({ entryPoints: [filename], bundle: true, platform: 'node', format: 'cjs',
  write: false, external: ['react'] }).outputFiles[0].text
const loaded = new Module(filename, module)
loaded.filename = filename
loaded.paths = Module._nodeModulePaths(path.dirname(filename))
loaded._compile(compiled, filename)
const Editor = loaded.exports.default
test.after(() => dom.window.close())

async function mount(props) {
  const container = document.body.appendChild(document.createElement('div'))
  const root = createRoot(container)
  const ref = React.createRef()
  const changes = []
  const base = { value: 'print(1)', documentId: 'student:problem', onChange: value => changes.push(value), ...props }
  const render = async more => { Object.assign(base, more); await act(async () => root.render(React.createElement(Editor, { ...base, ref }))) }
  await render()
  return { container, ref, changes, render, content: () => container.querySelector('.cm-content'),
    close: async () => { await act(async () => root.unmount()); container.remove() } }
}

test('the real component mounts highlighted Python, syncs external values and changes read-only state', async () => {
  const app = await mount({ value: 'if True:\n    print("你好", 12) # 注释' })
  try {
    assert.equal(app.container.querySelector('.py-keyword').textContent, 'if')
    assert.equal(app.container.querySelector('.py-string').textContent, '"你好"')
    assert.equal(app.container.querySelector('.py-comment').textContent, '# 注释')
    assert.equal(app.content().getAttribute('contenteditable'), 'true')
    await app.render({ value: 'print("外部恢复的草稿")', readOnly: true })
    assert.equal(app.content().textContent, 'print("外部恢复的草稿")')
    assert.equal(app.content().getAttribute('contenteditable'), 'false')
    assert.equal(app.content().getAttribute('aria-readonly'), 'true')
    assert.deepEqual(app.changes, [], 'external recovery must not clear judge feedback or resave a draft')
    await app.render({ readOnly: false })
    await act(async () => app.ref.current.focus())
    assert.equal(document.activeElement, app.content())
  } finally { await app.close() }
})

test('DOM edits notify the parent and keyboard undo/redo restore the text', async () => {
  const app = await mount()
  try {
    await act(async () => {
      app.ref.current.focus()
      const line = app.container.querySelector('.cm-line')
      line.textContent = 'print(2)'
      app.content().dispatchEvent(new dom.window.InputEvent('input', { bubbles: true, inputType: 'insertText', data: '2' }))
      await new Promise(resolve => setTimeout(resolve, 30))
    })
    assert.equal(app.changes.at(-1), 'print(2)')
    await app.render({ value: 'print(2)' })
    await act(async () => app.content().dispatchEvent(new dom.window.KeyboardEvent('keydown', {
      key: 'z', code: 'KeyZ', ctrlKey: true, bubbles: true, cancelable: true,
    })))
    assert.equal(app.content().textContent, 'print(1)')
    await act(async () => app.content().dispatchEvent(new dom.window.KeyboardEvent('keydown', {
      key: 'z', code: 'KeyZ', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true,
    })))
    assert.equal(app.content().textContent, 'print(2)')
  } finally { await app.close() }
})

test('switching account or problem creates a fresh editor and unmount removes its DOM', async () => {
  const app = await mount()
  try {
    const previous = app.content()
    await app.render({ documentId: 'another-student:another-problem', value: 'NEW_CODE' })
    assert.notEqual(app.content(), previous)
    assert.equal(previous.isConnected, false)
    assert.equal(app.content().textContent, 'NEW_CODE')
    await act(async () => app.content().dispatchEvent(new dom.window.KeyboardEvent('keydown', {
      key: 'z', code: 'KeyZ', ctrlKey: true, bubbles: true, cancelable: true,
    })))
    assert.equal(app.content().textContent, 'NEW_CODE')
    assert.equal(app.container.querySelectorAll('.cm-editor').length, 1)
  } finally { await app.close() }
})

test('the mounted editor handles Enter, Tab and Shift+Tab through its actual keymap', async () => {
  const app = await mount({ value: 'if True:' })
  const press = async (key, keyCode, extra = {}) => act(async () => {
    app.content().dispatchEvent(new dom.window.KeyboardEvent('keydown', {
      key, keyCode, bubbles: true, cancelable: true, ...extra,
    }))
  })
  try {
    await act(async () => app.ref.current.focus())
    await press('End', 35, { ctrlKey: true })
    await press('Enter', 13)
    assert.equal(app.changes.at(-1), 'if True:\n    ')
    await press('Tab', 9)
    assert.equal(app.changes.at(-1), 'if True:\n        ')
    await press('Tab', 9, { shiftKey: true })
    assert.equal(app.changes.at(-1), 'if True:\n    ')
  } finally { await app.close() }
})

test('composition input preserves Chinese text without duplicate characters', async () => {
  const app = await mount({ value: '' })
  try {
    await act(async () => {
      app.ref.current.focus()
      app.content().dispatchEvent(new dom.window.CompositionEvent('compositionstart', { bubbles: true }))
      app.container.querySelector('.cm-line').textContent = '# 小海獭'
      app.content().dispatchEvent(new dom.window.InputEvent('input', {
        bubbles: true, inputType: 'insertCompositionText', data: '小海獭', isComposing: true,
      }))
      app.content().dispatchEvent(new dom.window.CompositionEvent('compositionend', { bubbles: true, data: '小海獭' }))
      await new Promise(resolve => setTimeout(resolve, 40))
    })
    assert.equal(app.content().textContent, '# 小海獭')
    assert.equal(app.changes.at(-1), '# 小海獭')
  } finally { await app.close() }
})
