import React from 'react'
import { useNavigate } from 'react-router-dom'
import CodeEditor from '../components/CodeEditor.jsx'

function Level2() {
  const navigate = useNavigate()

  const handleSuccess = () => {
    navigate('/app/levels')
  }

  return (
    <div className="lesson-page">
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
        initialCode=""
        problemId="level2"
        onSuccess={handleSuccess}
        title="for循环练习"
      >
        <p style={{ fontWeight: 600, marginBottom: 8 }}>步骤:</p>
        <p>1. 使用 <code>for</code> 循环计算1到100的和</p>
        <p>2. 使用 <code>print()</code> 函数输出计算结果</p>
        <div className="expected-output">
          题目目标输出：<code>5050</code>
        </div>
      </CodeEditor>
    </div>
  )
}

export default Level2
