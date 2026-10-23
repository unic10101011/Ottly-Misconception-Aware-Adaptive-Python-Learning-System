import React from 'react'

const statusLabels = {
  accepted: '全部测试通过',
  wrong_answer: '输出与预期不一致',
  execution_error: '代码执行出现错误',
  timeout: '代码执行超时',
}

function SubmissionFeedback({ result, showJudge = true, showAnalysis = true }) {
  const { judge, analysis } = result
  const content = analysis?.status === 'ready' ? analysis.content : null
  const requirementFailed = judge.cases.some(testCase => testCase.errors.some(error => error.type === 'REQUIREMENT_NOT_MET'))

  return (
    <section className="submission-feedback" aria-label={showJudge ? '提交结果' : '本次错因分析'} aria-live="polite">
      {showJudge && <>
      <h3 className={judge.passed ? 'judge-passed' : 'judge-failed'}>
        {requirementFailed ? '尚未满足本关任务要求' : statusLabels[judge.status] || '判题结果'}
      </h3>
      <p>测试通过：{judge.passed_cases} / {judge.total_cases}</p>
      {!!judge.failed_tests?.length && <p>未通过测试：{judge.failed_tests.join('、')}</p>}
      {judge.cases.map(testCase => (
        <div className="judge-case" key={testCase.case_id}>
          <strong>测试 {testCase.case_id} · {testCase.passed ? '通过' : '未通过'}</strong>
          {testCase.visibility === 'hidden' ? <p>隐藏测试仅展示通过状态。</p> : <div className="judge-output-grid">
            <div><span>预期输出</span><pre>{testCase.expected_output || '（无输出）'}</pre></div>
            <div><span>实际输出</span><pre>{testCase.output_available === false
              ? (testCase.errors.some(error => error.type === 'REQUIREMENT_NOT_MET') ? '未执行：请先满足本关任务要求' : '输出未采集（执行已终止）')
              : testCase.actual_output || '（无输出）'}</pre></div>
          </div>}
          {testCase.visibility !== 'hidden' && testCase.errors.map((error, index) => (
            <p className="judge-error" key={index}>
              {error.type}{error.line ? ` · 第 ${error.line} 行` : ''}：{error.message}
            </p>
          ))}
        </div>
      ))}
      </>}
      {showAnalysis && (judge.passed ? <p className="analysis-status">全部测试用例通过，本次未调用 AI。</p> : analysis?.status === 'preparing' ? (
        <p className="analysis-status" role="status">Ottly正在分析错因，判题结果已显示，你可以先对照测试检查代码。</p>
      ) : content ? (
        <div className="ai-feedback">
          <h4>{analysis.source === 'fixed' ? '基础错因分析' : 'AI 错因分析'}</h4>
          <p className="analysis-status">{analysis.source === 'fixed'
            ? '依据本次报错提供基础分析。'
            : 'AI 分析基于本次执行结果，仅供参考。'}</p>
          {analysis.source !== 'fixed' && analysis.personalization?.used &&
            <p className="analysis-status">本次分析参考了你的相关练习记录。</p>}
          <details className="analysis-details" open>
            <summary>查看疑似原因、分析依据与知识点</summary>
            <p><strong>疑似原因：</strong>{content.suspected_cause}</p>
            <p><strong>相关知识点：</strong>{content.knowledge_points.join('、')}</p>
            {!!content.knowledge_ids?.length && <p><strong>知识点编号：</strong>{content.knowledge_ids.join('、')}</p>}
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
        <p className="analysis-status" role="status">{analysis?.message || 'AI 分析暂不可用，判题结果已保留。请稍后重新提交。'}</p>
      ))}
    </section>
  )
}

export default SubmissionFeedback
