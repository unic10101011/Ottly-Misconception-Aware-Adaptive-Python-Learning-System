const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

async function editor(code = '', options = {}) {
  const filename = path.resolve(__dirname, '../src/components/pythonEditor.mjs')
  assert.ok(fs.existsSync(filename), '共享 Python 编辑器配置尚未实现')
  const { createPythonEditorState } = await import('../src/components/pythonEditor.mjs')
  const state = createPythonEditorState({ code, ...options })
  const target = { state, dispatch: transaction => {
    target.state = transaction.state || target.state.update(transaction).state
  } }
  return target
}

test('Python blocks indent four spaces on Enter and retain the current indentation', async () => {
  const { insertNewlineAndIndent } = await import('@codemirror/commands')
  for (const line of ['if True:', 'for i in range(3):', 'def greet(name):']) {
    const target = await editor(line)
    target.state = target.state.update({ selection: { anchor: line.length } }).state
    assert.equal(insertNewlineAndIndent(target), true)
    assert.equal(target.state.doc.toString(), line + '\n    ')
  }
  const code = 'if True:\n    print(1)'
  const target = await editor(code)
  target.state = target.state.update({ selection: { anchor: code.length } }).state
  insertNewlineAndIndent(target)
  assert.equal(target.state.doc.toString(), code + '\n    ')
})

test('Tab and Shift+Tab indent and unindent all selected lines', async () => {
  const { indentMore, indentLess } = await import('@codemirror/commands')
  const target = await editor('print(1)\nprint(2)')
  target.state = target.state.update({ selection: { anchor: 0, head: target.state.doc.length } }).state
  assert.equal(indentMore(target), true)
  assert.equal(target.state.doc.toString(), '    print(1)\n    print(2)')
  assert.equal(indentLess(target), true)
  assert.equal(target.state.doc.toString(), 'print(1)\nprint(2)')
})

test('brackets and quotes pair, skip existing closing symbols and delete together', async () => {
  const { insertBracket, deleteBracketPair } = await import('@codemirror/autocomplete')
  for (const [opening, closing] of [['(', ')'], ['[', ']'], ['{', '}'], ['"', '"'], ["'", "'"]]) {
    const target = await editor()
    const inserted = insertBracket(target.state, opening)
    assert.ok(inserted, opening)
    target.dispatch(inserted)
    assert.equal(target.state.doc.toString(), opening + closing)
    assert.equal(target.state.selection.main.head, 1)
    const skipped = insertBracket(target.state, closing)
    assert.ok(skipped, closing)
    assert.equal(skipped.state.doc.toString(), opening + closing)
    assert.equal(skipped.state.selection.main.head, 2)
    assert.equal(deleteBracketPair(target), true)
    assert.equal(target.state.doc.toString(), '')
  }
})

test('Python syntax receives distinct keyword, string, number and comment highlights', async () => {
  const { syntaxTree } = await import('@codemirror/language')
  const { highlightTree } = await import('@lezer/highlight')
  const { pythonHighlightStyle } = await import('../src/components/pythonEditor.mjs')
  const target = await editor('if True:\n    print("你好", 12) # 注释')
  const spans = []
  highlightTree(syntaxTree(target.state), pythonHighlightStyle, (from, to, classes) => {
    spans.push({ text: target.state.sliceDoc(from, to), classes })
  })
  for (const [text, token] of [['if', 'py-keyword'], ['"你好"', 'py-string'], ['12', 'py-number'], ['# 注释', 'py-comment']]) {
    assert.ok(spans.some(span => span.text === text && span.classes.includes(token)), text)
  }
})

test('read-only and length limits reject user edits without truncating the document', async () => {
  const locked = await editor('print(1)', { readOnly: true })
  locked.dispatch({ changes: { from: 0, insert: 'x' } })
  assert.equal(locked.state.doc.toString(), 'print(1)')
  const target = await editor('x'.repeat(5999))
  target.dispatch({ changes: { from: 5999, insert: 'y' } })
  assert.equal(target.state.doc.length, 6000)
  target.dispatch({ changes: { from: 6000, insert: 'z' } })
  assert.equal(target.state.doc.length, 6000)
  target.dispatch({ changes: { from: 0, to: 6000, insert: '新的代码' } })
  assert.equal(target.state.doc.toString(), '新的代码')
})

test('undo and redo restore edits while new documents start with independent history', async () => {
  const { undo, redo } = await import('@codemirror/commands')
  const target = await editor('print(1)')
  target.dispatch({ changes: { from: 6, to: 7, insert: '2' } })
  assert.equal(target.state.doc.toString(), 'print(2)')
  assert.equal(undo(target), true)
  assert.equal(target.state.doc.toString(), 'print(1)')
  assert.equal(redo(target), true)
  assert.equal(target.state.doc.toString(), 'print(2)')
  const other = await editor('OTHER_ACCOUNT_OR_PROBLEM')
  assert.equal(undo(other), false)
  assert.equal(other.state.doc.toString(), 'OTHER_ACCOUNT_OR_PROBLEM')
})
