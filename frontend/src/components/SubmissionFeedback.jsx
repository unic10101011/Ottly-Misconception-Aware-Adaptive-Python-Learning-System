import React, { useState } from 'react'
import AiRetry from './AiRetry.jsx'

const statusLabels = {
  accepted: '全部测试通过',
  wrong_answer: '输出与预期不一致',
  execution_error: '代码执行出现错误',
  timeout: '代码执行超时',
}

function GuidanceFeedback({ guidance }) {
  const [selected, setSelected] = useState(null)
  const [answered, setAnswered] = useState(false)
  const question = guidance.question
  return <div className="ai-feedback ai-guidance">
    <p><strong>思考提示：</strong>{guidance.hint}</p>
    <p><strong>相关知识点：</strong>{guidance.knowledge_points.join('、')}</p>
    {question && <div className="guidance-question">
      <fieldset>
        <legend>{question.prompt}</legend>
        {question.options.map((option, index) => <label key={index}>
          <input type="radio" name="guidance-answer" value={index} checked={selected === index}
            onChange={() => { setSelected(index); setAnswered(false) }} />
          <span>{String.fromCharCode(65 + index)}. {option}</span>
        </label>)}
      </fieldset>
      <button type="button" className="btn-hint" disabled={selected === null}
        onClick={() => setAnswered(true)}>提交选项</button>
      {answered && <p role="status">
        <strong>{selected === question.correct_index ? '回答正确。' : '再想一想。'}</strong>
        {question.explanation}
      </p>}
    </div>}
  </div>
}

function SubmissionFeedback({ result, showJudge = true, showAnalysis = true, onRetry }) {
  const { judge, analysis } = result
  const content = analysis?.status === 'ready' ? analysis.content : null
  const guidance = analysis?.status === 'ready' && analysis.feedback_kind === 'guidance' ? analysis.guidance : null
  const isPartial = !judge.passed && judge.passed_cases > 0 && judge.passed_cases < judge.total_cases
  const hiddenCases = judge.cases.filter(testCase => testCase.visibility === 'hidden')
  const requirementFailed = judge.cases.some(testCase => testCase.errors.some(error => error.type === 'REQUIREMENT_NOT_MET'))

  return (
    <section className="submission-feedback" aria-label={showJudge ? '提交结果' : guidance ? '本次思考提示' : '本次错因分析'} aria-live="polite">
      {showJudge && <>
      <h3 className={judge.passed ? 'judge-passed' : 'judge-failed'}>
        {requirementFailed ? '尚未满足本关任务要求' : statusLabels[judge.status] || '判题结果'}
      </h3>
      <p>测试通过：{judge.passed_cases} / {judge.total_cases}</p>
      {!!judge.failed_tests?.length && <p>未通过测试：{judge.failed_tests.join('、')}</p>}
      {judge.cases.filter(testCase => testCase.visibility !== 'hidden').map(testCase => (
        <div className="judge-case" key={testCase.case_id}>
          <strong>测试 {testCase.case_id} · {testCase.passed ? '通过' : '未通过'}</strong>
          <div className="judge-output-grid">
            <div><span>预期输出</span><pre>{testCase.expected_output || '（无输出）'}</pre></div>
            <div><span>实际输出</span><pre>{testCase.output_available === false
              ? (testCase.errors.some(error => error.type === 'REQUIREMENT_NOT_MET') ? '未执行：请先满足本关任务要求' : '输出未采集（执行已终止）')
              : testCase.actual_output || '（无输出）'}</pre></div>
          </div>
          {testCase.errors.map((error, index) => (
            <p className="judge-error" key={index}>
              {error.type}{error.line ? ` · 第 ${error.line} 行` : ''}：{error.message}
            </p>
          ))}
        </div>
      ))}
      {hiddenCases.length > 0 && <ul className="hidden-test-grid" aria-label="隐藏测试结果">
        {hiddenCases.map((testCase, index) => <li key={testCase.case_id}
          className={`hidden-test-tile ${testCase.passed ? 'is-passed' : 'is-failed'}`}
          aria-label={`隐藏测试 ${index + 1}（${testCase.case_id}）：${testCase.passed ? '通过' : '未通过'}`}>
          <strong>测试 {index + 1}</strong>
          <span>{testCase.passed ? '通过' : '未通过'}</span>
        </li>)}
      </ul>}
      </>}
      {showAnalysis && (judge.passed ? <p className="analysis-status">全部测试用例通过。</p> : analysis?.status === 'preparing' ? (
        <p className="analysis-status" role="status">{isPartial ? 'Ottly正在准备思考提示，判题结果已显示。' : 'Ottly正在分析错因，判题结果已显示，你可以先对照测试检查代码。'}</p>
      ) : guidance ? (
        <GuidanceFeedback key={result.submission_id || guidance.question?.prompt || guidance.hint} guidance={guidance} />
      ) : content ? (
        <div className="ai-feedback">
          <p><strong>{analysis.source === 'fixed' ? '基础说明：' : '疑似原因：'}</strong>{content.suspected_cause}</p>
          <p><strong>相关知识点：</strong>{content.knowledge_points.join('、')}</p>
          {content.evidence.map((item, index) => (
            <div className="analysis-evidence" key={index}>
              <strong>依据：{item.case_id} · {item.field === 'actual_output' ? '实际输出' : '错误信息'}</strong>
              <pre>{item.quote || '（无输出）'}</pre>
              <p>{item.explanation}</p>
            </div>
          ))}
        </div>
      ) : (
        <AiRetry status={analysis?.status} message={analysis?.message || 'AI 分析暂不可用，判题结果已保留。'} onRetry={onRetry} />
      ))}
    </section>
  )
}

export default SubmissionFeedback
