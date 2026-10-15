import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import SubmissionFeedback from '../components/SubmissionFeedback.jsx'
import { getLearningHistory, getMistakeQuestions, requestCode, saveHintView } from '../components/codeApi.mjs'

const HISTORY_PAGE_SIZE = 10
const formatDate = value => new Date(value).toLocaleString('zh-CN')

function LearningHistory() {
  const navigate = useNavigate()
  const [questions, setQuestions] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [tab, setTab] = useState('practice')
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [code, setCode] = useState('')
  const [running, setRunning] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [runResult, setRunResult] = useState(null)
  const [submission, setSubmission] = useState(null)
  const [visibleHintCount, setVisibleHintCount] = useState(0)
  const [savingHintId, setSavingHintId] = useState(null)
  const [hintErrors, setHintErrors] = useState({})
  const [history, setHistory] = useState([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyOffset, setHistoryOffset] = useState(0)
  const [summaryReload, setSummaryReload] = useState(0)
  const [historyReload, setHistoryReload] = useState(0)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [actionError, setActionError] = useState('')
  const selectedRef = useRef(null)
  const busy = running || submitting || savingHintId !== null
  const selected = questions.find(item => item.problem_id === selectedId)

  useEffect(() => {
    let active = true
    const load = () => {
      setLoading(true)
      setListError('')
      getMistakeQuestions(localStorage.getItem('access_token')).then(data => {
        if (!active) return
        setQuestions(data.items)
        setSelectedId(current => current || data.items[0]?.problem_id || null)
      }).catch(error => {
        if (!active) return
        setListError(error.message)
        if (error.status === 401) navigate('/auth')
      }).finally(() => { if (active) setLoading(false) })
    }
    load()
    return () => { active = false }
  }, [navigate, summaryReload])

  useEffect(() => {
    selectedRef.current = selectedId
    if (!selectedId) return
    const question = questions.find(item => item.problem_id === selectedId)
    if (question) setCode(question.last_wrong_code)
    setRunResult(null)
    setSubmission(null)
    setVisibleHintCount(0)
    setActionError('')
  }, [selectedId])

  useEffect(() => {
    if (!selectedId) return
    let active = true
    setHistoryLoading(true)
    setHistoryError('')
    getLearningHistory(false, HISTORY_PAGE_SIZE, historyOffset,
      localStorage.getItem('access_token'), selectedId).then(data => {
      if (!active) return
      setHistory(data.items)
      setHistoryTotal(data.total)
    }).catch(error => {
      if (!active) return
      setHistoryError(error.message)
      if (error.status === 401) navigate('/auth')
    }).finally(() => { if (active) setHistoryLoading(false) })
    return () => { active = false }
  }, [selectedId, historyOffset, historyReload, navigate])

  const chooseQuestion = problemId => {
    if (busy) return
    selectedRef.current = problemId
    setSelectedId(problemId)
    setHistoryOffset(0)
    setTab('practice')
  }

  const editCode = value => {
    if (busy) return
    setCode(value)
    setRunResult(null)
    setSubmission(null)
    setVisibleHintCount(0)
    setActionError('')
  }

  const runCode = async () => {
    if (busy || !code.trim()) return
    setRunning(true)
    setActionError('')
    try {
      const result = await requestCode('run', { code, timeout: 3 }, localStorage.getItem('access_token'))
      setRunResult(result)
    } catch (error) {
      setActionError(error.message)
      if (error.status === 401) navigate('/auth')
    } finally {
      setRunning(false)
    }
  }

  const submitReview = async () => {
    if (busy || !code.trim() || !selected) return
    const problemId = selected.problem_id
    setSubmitting(true)
    setActionError('')
    setSubmission(null)
    setVisibleHintCount(0)
    try {
      const result = await requestCode('submit', { problem_id: problemId, code },
        localStorage.getItem('access_token'), { reviewSourceId: selected.first_wrong_submission_id })
      if (selectedRef.current !== problemId) return
      setSubmission(result)
      setHistoryOffset(0)
      setSummaryReload(value => value + 1)
      setHistoryReload(value => value + 1)
    } catch (error) {
      setActionError(error.message)
      if (error.status === 401) navigate('/auth')
    } finally {
      setSubmitting(false)
    }
  }

  const revealHint = async (item, currentResult = false) => {
    if (savingHintId !== null) return
    const id = currentResult ? submission?.submission_id : item.id
    const level = (currentResult ? visibleHintCount : item.hints_viewed_max) + 1
    if (!id || level > 3) return
    setSavingHintId(id)
    setHintErrors(current => ({ ...current, [id]: '' }))
    try {
      const saved = await saveHintView(id, level, localStorage.getItem('access_token'))
      if (currentResult) setVisibleHintCount(saved.hints_viewed_max)
      setHistory(current => current.map(row => row.id === id
        ? { ...row, hints_viewed_max: saved.hints_viewed_max } : row))
    } catch (error) {
      setHintErrors(current => ({ ...current, [id]: `提示查看记录暂未保存：${error.message} 请重试。` }))
      if (error.status === 401) navigate('/auth')
    } finally {
      setSavingHintId(null)
    }
  }

  return (
    <main className="mistake-page">
      <header className="mistake-page-header">
        <div><span className="mistake-eyebrow">个人学习记录</span><h1>我的错题</h1>
          <p>选择一道题重新练习，也可以查看它的复习轨迹。</p></div>
        <span className="mistake-count">{questions.length} 道错题</span>
      </header>

      {loading && <p role="status">正在加载错题...</p>}
      {listError && <p className="mistake-alert" role="alert">{listError}</p>}
      {!loading && !listError && questions.length === 0 &&
        <div className="mistake-empty">还没有错题记录。完成关卡提交后，错题会出现在这里。</div>}

      {questions.length > 0 && <>
        <nav className="mistake-question-list" aria-label="选择错题">
          {questions.map(question => <button key={question.problem_id} type="button"
            className={`mistake-question-chip ${question.problem_id === selectedId ? 'active' : ''}`}
            aria-current={question.problem_id === selectedId ? 'true' : undefined}
            disabled={busy} onClick={() => chooseQuestion(question.problem_id)}>
            <span>{question.title}</span><small>{question.latest_passed ? '最近已通过' : '待复习'}</small>
          </button>)}
        </nav>

        {selected && <section className="mistake-workbench">
          <div className="mistake-workbench-heading">
            <div><span className="mistake-eyebrow">{selected.source}</span><h2>{selected.title}</h2></div>
            <span className={`mistake-status ${selected.latest_passed ? 'is-passed' : ''}`}>
              {selected.latest_passed ? '最近已通过' : '继续巩固'}</span>
          </div>
          <div className="mistake-tabs" role="tablist" aria-label="错题页面">
            <button type="button" role="tab" aria-selected={tab === 'practice'}
              className={tab === 'practice' ? 'active' : ''} onClick={() => setTab('practice')}>重新做题</button>
            <button type="button" role="tab" aria-selected={tab === 'insight'}
              className={tab === 'insight' ? 'active' : ''} onClick={() => setTab('insight')}>我的情况</button>
          </div>

          {tab === 'practice' && <div className="mistake-practice-grid" role="tabpanel">
            <div className="mistake-problem-pane">
              <span className="mistake-pane-label">题目</span>
              <p>{selected.description}</p>
              <button type="button" className="mistake-text-link" onClick={() => setTab('insight')}>
                查看这道题的个人详情 →</button>
            </div>
            <div className="mistake-code-pane">
              <div className="mistake-code-title"><span>Python 代码</span><small>已填入最近一次错误代码</small></div>
              <textarea aria-label="复习代码编辑器" className="mistake-code-input" spellCheck={false}
                value={code} readOnly={busy} maxLength={6000} onChange={event => editCode(event.target.value)} />
              <div className="mistake-actions">
                <button type="button" className="mistake-secondary-button" disabled={busy || !code.trim()}
                  onClick={runCode}>{running ? '运行中...' : '运行代码'}</button>
                <button type="button" className="mistake-primary-button" disabled={busy || !code.trim()}
                  onClick={submitReview}>{submitting ? '判题与分析中...' : '提交并记录复习'}</button>
              </div>
              {actionError && <p className="mistake-alert" role="alert">{actionError}</p>}
              {runResult && <div className="mistake-run-result" role="status"><strong>运行结果</strong>
                <pre>{runResult.output || '（无输出）'}</pre>
                {runResult.errors?.map((error, index) =>
                  <p key={index}>{error.type}：{error.message}</p>)}</div>}
              {submission && <SubmissionFeedback result={submission} visibleHintCount={visibleHintCount}
                onRevealHint={() => revealHint(null, true)}
                hintBusy={savingHintId === submission.submission_id}
                hintError={hintErrors[submission.submission_id] || ''} />}
            </div>
          </div>}

          {tab === 'insight' && <div className="mistake-insight" role="tabpanel">
            <div className="mistake-metrics">
              <div><span>首次出错</span><strong>{formatDate(selected.first_wrong_at)}</strong></div>
              <div><span>题目来源</span><strong>{selected.source}</strong></div>
              <div><span>复习提交</span><strong>{selected.review_count} 次</strong></div>
              <div><span>最近复习表现</span><strong>{selected.review_rate_percent === null
                ? '样本较少' : `${selected.review_rate_percent}%`}</strong>
                <small>{selected.recent_review_passed} / {selected.recent_review_total} 次通过</small></div>
            </div>
            <div className="mistake-insight-grid">
              <article className="mistake-info-card">
                <h3>最近一次疑似错因</h3>
                <p>{selected.latest_suspected_cause || '暂无可靠的 AI 错因分析，可查看下方真实判题记录。'}</p>
                <small>AI 推测仅供复习参考，正确与否以判题结果为准。</small>
              </article>
              <article className="mistake-info-card">
                <h3>同类加练</h3>
                {selected.related_questions.length ? selected.related_questions.map(question =>
                  <a key={question.problem_id} href={question.url}>{question.title}</a>)
                  : <p>暂无已验证的同类题，先巩固这道题。</p>}
              </article>
            </div>
            <div className="mistake-history-heading"><h3>提交与复习记录</h3>
              <span>共 {historyTotal} 次提交，错误与通过记录都会保留</span></div>
            {historyLoading && <p role="status">正在加载记录...</p>}
            {historyError && <p className="mistake-alert" role="alert">{historyError}</p>}
            {!historyLoading && !historyError && history.map(item =>
              <details className="mistake-history-item" key={item.id}>
                <summary><span className={item.passed ? 'judge-passed' : 'judge-failed'}>
                  {item.passed ? '通过' : '未通过'}</span><strong>{formatDate(item.created_at)}</strong>
                  <small>{item.judge.passed_cases} / {item.judge.total_cases} 个测试通过</small></summary>
                <div className="mistake-history-body"><strong>当时提交的代码</strong><pre>{item.code}</pre>
                  <SubmissionFeedback result={{ judge: item.judge, analysis: item.analysis }}
                    visibleHintCount={item.hints_viewed_max} onRevealHint={() => revealHint(item)}
                    hintBusy={savingHintId === item.id} hintError={hintErrors[item.id] || ''} />
                </div>
              </details>)}
            {historyTotal > HISTORY_PAGE_SIZE && <div className="mistake-pagination">
              <button type="button" disabled={historyOffset === 0} onClick={() => setHistoryOffset(value => value - HISTORY_PAGE_SIZE)}>上一页</button>
              <span>{Math.floor(historyOffset / HISTORY_PAGE_SIZE) + 1} / {Math.ceil(historyTotal / HISTORY_PAGE_SIZE)}</span>
              <button type="button" disabled={historyOffset + HISTORY_PAGE_SIZE >= historyTotal}
                onClick={() => setHistoryOffset(value => value + HISTORY_PAGE_SIZE)}>下一页</button>
            </div>}
          </div>}
        </section>}
      </>}
    </main>
  )
}

export default LearningHistory
