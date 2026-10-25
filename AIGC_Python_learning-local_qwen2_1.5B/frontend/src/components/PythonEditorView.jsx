import React, { forwardRef, useImperativeHandle, useLayoutEffect, useRef } from 'react'
import { Compartment, Transaction } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { createPythonEditorState, externalCodeChange, readOnlyConfiguration } from './pythonEditor.mjs'

const PythonEditor = forwardRef(function PythonEditor({ value, onChange, readOnly = false,
  label = 'Python 代码编辑器', documentId, maxLength = 6000, className = '', height = '100%' }, ref) {
  const hostRef = useRef(null)
  const viewRef = useRef(null)
  const compartmentRef = useRef(new Compartment())
  const latest = useRef({ value, onChange, readOnly })
  latest.current = { value, onChange, readOnly }

  useImperativeHandle(ref, () => ({ focus: () => viewRef.current?.focus() }), [])

  useLayoutEffect(() => {
    const view = new EditorView({ parent: hostRef.current, state: createPythonEditorState({
      code: latest.current.value, readOnly: latest.current.readOnly, label, maxLength,
      readOnlyCompartment: compartmentRef.current,
      onChange: nextValue => latest.current.onChange(nextValue),
    }) })
    viewRef.current = view
    return () => { viewRef.current = null; view.destroy() }
  }, [documentId, label, maxLength])

  useLayoutEffect(() => {
    const view = viewRef.current
    if (view && value !== view.state.doc.toString()) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value },
        annotations: [externalCodeChange.of(true), Transaction.addToHistory.of(false)] })
    }
  }, [value])

  useLayoutEffect(() => {
    viewRef.current?.dispatch({ effects: compartmentRef.current.reconfigure(readOnlyConfiguration(readOnly)) })
  }, [readOnly])

  return <div className={`python-editor ${className}`} style={{ height, width: '100%', minWidth: 0,
    display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRadius: 'inherit' }}>
    <div ref={hostRef} style={{ flex: 1, minHeight: 0 }} />
    <div style={{ padding: '5px 10px', background: '#1c2c3c', color: '#bdcedc', fontSize: 12,
      lineHeight: 1.5 }}>Tab 缩进 · Shift+Tab 减少缩进 · Esc 后按 Tab 离开编辑器</div>
  </div>
})

export default PythonEditor
