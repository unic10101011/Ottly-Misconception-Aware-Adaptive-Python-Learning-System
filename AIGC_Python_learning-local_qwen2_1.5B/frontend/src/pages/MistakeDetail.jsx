import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import SubmissionFeedback from '../components/SubmissionFeedback.jsx'
import ProblemMetadata from '../components/ProblemMetadata.jsx'
import StatusStamp from '../components/StatusStamp.jsx'
import { knowledgeName, questionKnowledgeIds, mistakeOverviewUrl } from '../components/mistakeGrouping.mjs'
import { getLearningHistory, getMistakeQuestions, getKnowledge, requestAnalysis, requestCode } from '../components/codeApi.mjs'

const HISTORY_PAGE_SIZE = 10
const formatDate = value => new Date(value).toLocaleString('zh-CN')

function MistakeDetail() {
  const { problemId: selectedId } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [questions, setQuestions] = useState([])
  const [knowledgeNames, setKnowledgeNames] = useState({})
  const [tab, setTab] = useState('practice')
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [code, setCode] = useState('')
  const [stdin, setStdin] = useState('')
  const [running, setRunning] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [runResult, setRunResult] = useState(null)
  const [submission, setSubmission] = useState(null)
  const [history, setHistory] = useState([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyOffset, setHistoryOffset] = useState(0)
  const [summaryReload, setSummaryReload] = useState(0)
  const [historyReload, setHistoryReload] = useState(0)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [actionError, setActionError] = useState('')
  const selectedRef = useRef(null)
  const latestSubmissionRef = useRef(null)
  const pendingHistoryRef = useRef(new Set())
  const mountedRef = useRef(false)
  const initializedProblemRef = useRef(null)
  const busy = running || submitting
  const selected = questions.find(item => item.problem_id === selectedId)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    let active = true
    getKnowledge(localStorage.getItem('access_token')).then(data => {
      if (active) setKnowledgeNames(Object.fromEntries(data.items.map(item => [item.knowledge_id, item.name])))
    }).catch(() => {}) // IDs still identify the snapshot if the dictionary is unavailable.
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    const load = () => {
      setLoading(true)
      setListError('')
      getMistakeQuestions(localStorage.getItem('access_token')).then(data => {
        if (!active) return
        setQuestions(data.items)
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
    if (!selected || initializedProblemRef.current === selectedId) return
    initializedProblemRef.current = selectedId
    setCode(selected.last_wrong_code)
    setRunResult(null)
    setSubmission(null)
    latestSubmissionRef.current = null
    setActionError('')
    setStdin('')
  }, [selectedId, selected])

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

  const editCode = value => {
    if (busy) return
    setCode(value)
    setRunResult(null)
    setSubmission(null)
    latestSubmissionRef.current = null
    setActionError('')
  }

  const runCode = async () => {
    if (busy || !code.trim()) return
    const problemId = selectedId
    setRunning(true)
    setActionError('')
    setRunResult(null)
    setSubmission(null)
    latestSubmissionRef.current = null
    try {
      const result = await requestCode('run', { code, timeout: 3, stdin, problem_id: problemId }, localStorage.getItem('access_token'))
      if (!mountedRef.current || selectedRef.current !== problemId) return
      setRunResult(result)
    } catch (error) {
      if (!mountedRef.current) return
      setActionError(error.message)
      if (error.status === 401) navigate('/auth')
    } finally {
      if (mountedRef.current) setRunning(false)
    }
  }

  const submitReview = async () => {
    if (busy || !code.trim() || !selected) return
    const problemId = selected.problem_id
    setSubmitting(true)
    setRunResult(null)
    setActionError('')
    setSubmission(null)
    latestSubmissionRef.current = null
    try {
      const result = await requestCode('submit', { problem_id: problemId, code },
        localStorage.getItem('access_token'), { reviewSourceId: selected.first_wrong_submission_id })
      if (!mountedRef.current || selectedRef.current !== problemId) return
      latestSubmissionRef.current = result.submission_id
      setSubmission(result)
      setQuestions(current => current.map(question => question.problem_id === problemId
        ? { ...question, latest_passed: result.judge.passed } : question))
      if (result.analysis?.status === 'preparing') {
        pendingHistoryRef.current.add(result.submission_id)
        requestAnalysis(result.submission_id, localStorage.getItem('access_token'))
          .then(data => {
            if (!mountedRef.current || latestSubmissionRef.current !== result.submission_id) return
            setSubmission({ ...result, analysis: data.analysis, timings: data.timings })
            setHistoryReload(value => value + 1)
            setSummaryReload(value => value + 1)
          })
          .catch(error => {
            if (!mountedRef.current || latestSubmissionRef.current !== result.submission_id) return
            setSubmission({ ...result, analysis: { status: 'unavailable',
              message: `错因分析暂时无法生成：${error.message} 判题结果已保留。`, content: null } })
          })
          .finally(() => pendingHistoryRef.current.delete(result.submission_id))
      }
      setHistoryOffset(0)
      setSummaryReload(value => value + 1)
      setHistoryReload(value => value + 1)
    } catch (error) {
      if (!mountedRef.current) return
      setActionError(error.message)
      if (error.status === 401) navigate('/auth')
    } finally {
      if (mountedRef.current) setSubmitting(false)
    }
  }

  const prepareHistoryAnalysis = item => {
    if (item.analysis?.status !== 'preparing' || pendingHistoryRef.current.has(item.id)) return
    pendingHistoryRef.current.add(item.id)
    requestAnalysis(item.id, localStorage.getItem('access_token'))
      .then(data => {
        if (!mountedRef.current) return
        setHistory(current => current.map(row => row.id === item.id
          ? { ...row, analysis: data.analysis } : row))
        setSummaryReload(value => value + 1)
      })
      .catch(error => {
        if (!mountedRef.current) return
        setHistory(current => current.map(row => row.id === item.id
          ? { ...row, analysis: { status: 'unavailable',
            message: `错因分析暂时无法生成：${error.message} 判题结果已保留。`, content: null } } : row))
      })
      .finally(() => pendingHistoryRef.current.delete(item.id))
  }

  const ids = selected ? questionKnowledgeIds(selected) : []
  const groupId = ids.includes(params.get('knowledge')) ? params.get('knowledge') : ids[0]
  const groupName = knowledgeName(groupId, knowledgeNames)
  const latestPassed = submission?.judge?.passed ?? selected?.latest_passed

  return (
    <div className="mistake-page mistake-detail">
      <nav className="mistake-breadcrumb" aria-label="面包屑">
        <Link to="/app/history">我的错题</Link>
        {selected && <><span aria-hidden="true">/</span>
          <Link to={mistakeOverviewUrl(groupId)}>{groupName}</Link>
          <span aria-hidden="true">/</span><span aria-current="page">{selected.title}</span></>}
      </nav>
      {loading && <p role="status">正在加载错题...</p>}
      {listError && <p className="mistake-alert" role="alert">{listError}</p>}
      {!loading && !listError && !selected && <div className="mistake-empty">
        <h1>暂时找不到这道错题</h1><p>这道题可能尚无错题记录，或不属于当前账号。</p>
        <Link to="/app/history">返回我的错题</Link>
      </div>}
        {selected && <section className="mistake-workbench">
          <div className="mistake-workbench-heading">
            <div><span className="mistake-eyebrow">{selected.source} · 复习这一题</span><h1>{selected.title}</h1></div>
            <div className="mistake-detail-stamp"><StatusStamp passed={latestPassed} /><small>最近提交：{latestPassed === true ? '已通过' : latestPassed === false ? '未通过' : '待尝试'}</small></div>
          </div>
          <ProblemMetadata version={selected.version} difficulty={selected.difficulty}
            knowledgeIds={selected.knowledge_ids} knowledgeNames={knowledgeNames} />
          <div className="mistake-tabs" role="tablist" aria-label="错题页面">
            <button type="button" role="tab" id="review-practice-tab" aria-controls="review-practice-panel" aria-selected={tab === 'practice'}
              className={tab === 'practice' ? 'active' : ''} onClick={() => setTab('practice')}>重新做题</button>
            <button type="button" role="tab" id="review-insight-tab" aria-controls="review-insight-panel" aria-selected={tab === 'insight'}
              className={tab === 'insight' ? 'active' : ''} onClick={() => setTab('insight')}>我的情况</button>
          </div>

          {tab === 'practice' && <div className="mistake-practice-grid" role="tabpanel" id="review-practice-panel" aria-labelledby="review-practice-tab">
            <div className="mistake-problem-pane">
              <span className="mistake-pane-label">题目</span>
              <p>{selected.description}</p>
              <button type="button" className="mistake-text-link" onClick={() => setTab('insight')}>
                查看这道题的个人详情 →</button>
            </div>
            <div className="mistake-code-pane">
              <div className="mistake-code-title"><span>Python 代码</span></div>
              <textarea aria-label="复习代码编辑器" className="mistake-code-input" spellCheck={false}
                value={code} readOnly={busy} maxLength={6000} onChange={event => editCode(event.target.value)} />
              <div className="lesson-input">
                <label htmlFor="review-stdin">运行输入（每次 input 读取一行）</label>
                <textarea id="review-stdin" value={stdin} readOnly={busy} maxLength={8000} rows={3}
                  onChange={event => { setStdin(event.target.value); setRunResult(null) }} />
              </div>
              <div className="mistake-actions">
                <button type="button" className="mistake-secondary-button" disabled={busy || !code.trim()}
                  onClick={runCode}>{running ? '运行中...' : '运行代码'}</button>
                <button type="button" className="mistake-primary-button" disabled={busy || !code.trim()}
                  onClick={submitReview}>{submitting ? '正在判题...' : '提交并记录复习'}</button>
              </div>
              {running && <p role="status">正在运行代码；若出现错误，将继续生成 AI 分析，请稍候...</p>}
              {actionError && <p className="mistake-alert" role="alert">{actionError}</p>}
              {runResult && <div className="mistake-run-result" role="status"><strong>运行结果</strong>
                <pre>{runResult.output || '（无输出）'}</pre>
                {runResult.errors?.map((error, index) =>
                  <p key={index}>{error.type}：{error.message}</p>)}</div>}
              {runResult?.analysis && <SubmissionFeedback
                result={{ judge: runResult.judge, analysis: runResult.analysis }} showJudge={false} />}
              {submission && <SubmissionFeedback result={submission} />}
            </div>
          </div>}

          {tab === 'insight' && <div className="mistake-insight" role="tabpanel" id="review-insight-panel" aria-labelledby="review-insight-tab">
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
                <h3>根据 AI 知识点推荐</h3>
                {selected.related_questions?.length ? selected.related_questions.map(question =>
                  <a className="mistake-practice-link" key={question.problem_id} href={question.url}>
                    <strong>{question.title}</strong><span>{question.practice_focus}</span>
                    {question.completed && <small>已练过，可再次练习</small>}
                  </a>)
                  : <p>暂无可直接练习的推荐题；AI 分析可能还没有可靠知识点，或对应加练尚未解锁。</p>}
              </article>
            </div>
            <div className="mistake-history-heading"><h3>提交与复习记录</h3>
              <span>共 {historyTotal} 次提交，错误与通过记录都会保留</span></div>
            {historyLoading && <p role="status">正在加载记录...</p>}
            {historyError && <p className="mistake-alert" role="alert">{historyError}</p>}
            {!historyLoading && !historyError && history.map(item =>
              <details className="mistake-history-item" key={item.id}
                onToggle={event => { if (event.currentTarget.open) prepareHistoryAnalysis(item) }}>
                <summary><span className={item.passed ? 'judge-passed' : 'judge-failed'}>
                  {item.passed ? '通过' : '未通过'}</span><strong>{formatDate(item.created_at)}</strong>
                  <small>{item.judge.passed_cases} / {item.judge.total_cases} 个测试通过</small></summary>
                <div className="mistake-history-body"><strong>当时提交的代码</strong><pre>{item.code}</pre>
                  <ProblemMetadata version={item.version} difficulty={item.difficulty}
                    knowledgeIds={item.knowledge_ids} knowledgeNames={knowledgeNames} />
                  {!item.passed && <p>错误分类：{item.error_type || '历史记录未提供'}</p>}
                  <SubmissionFeedback result={{ judge: item.judge, analysis: item.analysis }} />
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
    </div>
  )
}

export default MistakeDetail
