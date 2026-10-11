import React from 'react'
import { useNavigate } from 'react-router-dom'
import CodeEditor from '../components/CodeEditor.jsx'

function Level1() {
  const navigate = useNavigate()

  const handleSuccess = () => {
    navigate('/app/levels')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <button
        onClick={() => navigate('/app/levels')}
        style={{
          alignSelf: 'flex-start',
          background: 'none',
          border: '1px solid #ddd',
          borderRadius: '8px',
          padding: '6px 16px',
          cursor: 'pointer',
          fontSize: '14px',
          color: '#666',
          marginBottom: '8px',
        }}
      >
        ← 返回关卡选择
      </button>
      <CodeEditor
        initialCode={"print('Hello, World!')"}
        expectedOutput="Hello, World!"
        onSuccess={handleSuccess}
        title="初识小海獭"
      >
        <p style={{ fontWeight: 600, marginBottom: 8 }}>步骤:</p>
        <p>1. 使用 <code>print()</code> 函数输出 "Hello, World!"</p>
        <p style={{ fontSize: 13, opacity: 0.8, marginTop: 8 }}>
          💡 提示：<code>print()</code> 是 Python 中最常用的输出函数
        </p>
      </CodeEditor>
    </div>
  )
}

export default Level1
