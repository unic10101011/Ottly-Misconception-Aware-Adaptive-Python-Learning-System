import React from 'react'
import { useNavigate } from 'react-router-dom'
import CodeEditor from '../components/CodeEditor.jsx'

function Level2() {
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
        initialCode={`sum = 0
for i in range(1, 101)
    sum = i
print(sum)`}
        expectedOutput="5050"
        onSuccess={handleSuccess}
        title="for循环练习"
      >
        <p style={{ fontWeight: 600, marginBottom: 8 }}>步骤:</p>
        <p>1. 使用 <code>for</code> 循环计算1到100的和</p>
        <p>2. 使用 <code>print()</code> 函数输出计算结果</p>
        <div className="error-hint">
          ⚠️ 错误提示：当前代码有两处错误：① range后缺少冒号 ② sum+=中缺少加号
        </div>
        <div className="expected-output">
          ✓ 预期输出：<code>5050</code>
        </div>
      </CodeEditor>
    </div>
  )
}

export default Level2
