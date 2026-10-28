import { Annotation, Compartment, EditorState } from '@codemirror/state'
import { EditorView, drawSelection, highlightActiveLine, highlightActiveLineGutter, keymap, lineNumbers } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab, redo } from '@codemirror/commands'
import { HighlightStyle, bracketMatching, indentOnInput, indentUnit, syntaxHighlighting } from '@codemirror/language'
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { python } from '@codemirror/lang-python'
import { tags } from '@lezer/highlight'

export const externalCodeChange = Annotation.define()

export const pythonHighlightStyle = HighlightStyle.define([
  { tag: tags.keyword, class: 'py-keyword' },
  { tag: [tags.string, tags.special(tags.string)], class: 'py-string' },
  { tag: [tags.number, tags.bool, tags.null], class: 'py-number' },
  { tag: tags.comment, class: 'py-comment' },
  { tag: [tags.function(tags.variableName), tags.definition(tags.variableName)], class: 'py-function' },
  { tag: [tags.operator, tags.punctuation], class: 'py-punctuation' },
])

const theme = EditorView.theme({
  '&': { height: '100%', backgroundColor: '#233446', color: '#edf6fa', fontSize: '14px' },
  '&.cm-focused': { outline: '2px solid #6ab5db', outlineOffset: '-2px' },
  '.cm-scroller': { overflow: 'auto', fontFamily: 'Consolas, Monaco, monospace', lineHeight: '22px' },
  '.cm-content': { padding: '12px 0', minHeight: '100%', caretColor: '#fff' },
  '.cm-line': { padding: '0 12px' },
  '.cm-gutters': { backgroundColor: '#1c2c3c', color: '#b6c7d7', border: 'none' },
  '.cm-activeLineGutter, .cm-activeLine': { backgroundColor: '#2c4358' },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: '#fff' },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': { backgroundColor: '#405e7a' },
  '.cm-matchingBracket': { backgroundColor: '#41616b', outline: '1px solid #97d8db' },
  '.py-keyword': { color: '#d5b8ff' },
  '.py-string': { color: '#b5e5ab' },
  '.py-number': { color: '#ffc88d' },
  '.py-comment': { color: '#adbdcd', fontStyle: 'italic' },
  '.py-function': { color: '#97dbff' },
  '.py-punctuation': { color: '#e1e9f0' },
}, { dark: true })

export function readOnlyConfiguration(readOnly) {
  return [EditorState.readOnly.of(readOnly), EditorView.editable.of(!readOnly),
    EditorView.contentAttributes.of({ 'aria-readonly': String(readOnly), 'aria-busy': String(readOnly) })]
}

export function createPythonEditorState({ code = '', onChange = () => {}, readOnly = false,
  maxLength = 6000, readOnlyCompartment = new Compartment(), label = 'Python 代码编辑器' } = {}) {
  return EditorState.create({ doc: code, extensions: [
    python(), indentUnit.of('    '), EditorState.tabSize.of(4),
    lineNumbers(), highlightActiveLineGutter(), highlightActiveLine(), drawSelection(),
    history(), bracketMatching(), closeBrackets(), indentOnInput(),
    syntaxHighlighting(pythonHighlightStyle), theme,
    keymap.of([...closeBracketsKeymap, indentWithTab, { key: 'Mod-Shift-z', run: redo },
      ...defaultKeymap, ...historyKeymap]),
    readOnlyCompartment.of(readOnlyConfiguration(readOnly)),
    EditorView.contentAttributes.of({ 'aria-label': label, 'aria-multiline': 'true',
      role: 'textbox', tabindex: '0',
      'aria-description': 'Tab 缩进，Shift+Tab 减少缩进；按 Esc 后再按 Tab 可离开编辑器。',
      spellcheck: 'false', autocorrect: 'off', autocapitalize: 'off' }),
    EditorState.transactionFilter.of(transaction => {
      if (!transaction.docChanged || transaction.annotation(externalCodeChange)) return transaction
      return transaction.startState.readOnly || transaction.newDoc.length > maxLength ? [] : transaction
    }),
    EditorView.updateListener.of(update => {
      if (update.docChanged && update.transactions.some(transaction => transaction.docChanged
          && !transaction.annotation(externalCodeChange))) onChange(update.state.doc.toString())
    }),
  ] })
}
