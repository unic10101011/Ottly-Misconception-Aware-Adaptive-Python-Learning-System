import React from 'react'

const statusLabels = {
  accepted: '全部测试通过',
  wrong_answer: '输出与预期不一致',
  execution_error: '代码执行出现错误',
  timeout: '代码执行超时',
}
const hintLabels = ['观察方向', '定位原因', '修改思路']

function SubmissionFeedback({ result, visibleHintCount, onRevealHint }) {
  const { judge, analysis } = result
  const content = analysis.status === 'ready' ? analysis.content : null

  return (
    <section className="submission-feedback" aria-label="提交结果" aria-live="polite">
      <h3 className={judge.passed ? 'judge-passed' : 'judge-failed'}>
        {statusLabels[judge.status] || '判题结果'}
      </h3>
      <p>测试通过：{judge.passed_cases} / {judge.total_cases}</p>
      {judge.cases.map(testCase => (
        <div className="judge-case" key={testCase.case_id}>
          <strong>测试 {testCase.case_id} · {testCase.passed ? '通过' : '未通过'}</strong>
          <div className="judge-output-grid">
            <div><span>预期输出</span><pre>{testCase.expected_output || '（无输出）'}</pre></div>
            <div><span>实际输出</span><pre>{testCase.output_available === false ? '输出未采集（执行已终止）' : testCase.actual_output || '（无输出）'}</pre></div>
          </div>
          {testCase.errors.map((error, index) => (
            <p className="judge-error" key={index}>
              {error.type}{error.line ? ` · 第 ${error.line} 行` : ''}：{error.message}
            </p>
          ))}
        </div>
      ))}
      {judge.passed ? <p className="analysis-status">全部测试用例通过，本次未调用 AI。</p> : content ? (
        <div className="ai-feedback">
          <h4>AI 学习提示</h4>
          <p className="analysis-status">先尝试自己修改；需要帮助时，逐级查看提示。AI 分析是基于本次测试的推测。</p>
          <div className="progressive-hints">
            {hintLabels.slice(0, visibleHintCount).map((label, index) => (
              <article className="hint-card" key={label}>
                <strong>第 {index + 1} 级 · {label}</strong>
                <p>{content.hints[`level${index + 1}`]}</p>
              </article>
            ))}
            {visibleHintCount < 3 && (
              <button type="button" className="btn-hint" onClick={onRevealHint}>
                查看第 {visibleHintCount + 1} 级提示
              </button>
            )}
          </div>
          <details className="analysis-details">
            <summary>查看疑似原因、分析依据与知识点</summary>
            <p><strong>疑似原因：</strong>{content.suspected_cause}</p>
            <p><strong>相关知识点：</strong>{content.knowledge_points.join('、')}</p>
            {content.evidence.map((item, index) => (
              <div className="analysis-evidence" key={index}>
                <strong>依据：{item.case_id} · {item.field === 'actual_output' ? '实际输出' : '错误信息'}</strong>
                <pre>{item.quote || '（无输出）'}</pre>
                <p>{item.explanation}</p>
              </div>
            ))}
          </details>
        </div>
      ) : (
        <p className="analysis-status" role="status">{analysis.message || 'AI 分析暂不可用，判题结果已保留。请稍后重新提交。'}</p>
      )}
    </section>
  )
}

export default SubmissionFeedback
