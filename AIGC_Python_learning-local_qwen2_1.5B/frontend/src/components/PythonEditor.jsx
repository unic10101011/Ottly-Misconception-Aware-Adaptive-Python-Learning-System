import React, { forwardRef, lazy, Suspense } from 'react'

const Editor = lazy(() => import('./PythonEditorView.jsx'))

export default forwardRef(function PythonEditor(props, ref) {
  return <Suspense fallback={<div role="status" style={{ height: props.height ?? '100%', width: '100%',
    minHeight: 200, display: 'grid', placeItems: 'center', background: '#233446', color: '#edf6fa' }}>
    正在准备代码编辑器…
  </div>}>
    <Editor {...props} ref={ref} />
  </Suspense>
})
