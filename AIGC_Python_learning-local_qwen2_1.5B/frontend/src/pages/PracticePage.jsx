import React, { useEffect, useRef, useState } from 'react'
import { useNavigate, useOutletContext, useSearchParams } from 'react-router-dom'
import CodeEditor from '../components/CodeEditor.jsx'
import { getLesson, getPractice, getSolution } from '../components/codeApi.mjs'

export default function PracticePage() {
  const navigate = useNavigate()
  const { userId } = useOutletContext()
  const [params, setParams] = useSearchParams()
  const requestedLevel = Number(params.get('level_no'))
  const hasRequestedLevel = Number.isInteger(requestedLevel) && requestedLevel >= 1 && requestedLevel <= 12
  const [items, setItems] = useState([])
  const [lesson, setLesson] = useState(null)
  const [solution, setSolution] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(true)

  useEffect(() => {
    let active = true
    setBusy(true)
    getPractice(localStorage.getItem('access_token')).then(data => {
      if (!active) return
      setItems(data.items)
    }).catch(cause => {
      if (!active) return
      setError(cause.message)
      if (cause.status === 401) navigate('/auth')
    }).finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [navigate])

  const requestedId = params.get('problem_id')
  const activeItem = items.find(item => item.problem_id === requestedId && item.available
    && (!hasRequestedLevel || item.level_no === requestedLevel))
  const activeId = activeItem?.problem_id || null
  const levelNo = activeItem?.level_no
  const activeIdRef = useRef(activeId)
  activeIdRef.current = activeId
  const currentSolution = solution?.problem_id === activeId ? solution : null
  const embeddedTaskPrefix = `${lesson?.story}\n\n任务：`
  const task = lesson?.description.startsWith(embeddedTaskPrefix)
    ? lesson.description.slice(embeddedTaskPrefix.length)
    : lesson?.description

  useEffect(() => {
    if (!activeId) {
      setLesson(null)
      return
    }
    let active = true
    setLesson(null)
    setSolution(null)
    setError('')
    getLesson(activeId, localStorage.getItem('access_token')).then(data => {
      if (active) setLesson(data)
    }).catch(cause => {
      if (!active) return
      setError(cause.message)
      if (cause.status === 401) navigate('/auth')
    })
    return () => { active = false }
  }, [activeId, navigate])

  useEffect(() => {
    if (!activeId && !busy && hasRequestedLevel) {
      document.getElementById(`practice-level-${requestedLevel}`)?.scrollIntoView({ block: 'start' })
    }
  }, [activeId, busy, hasRequestedLevel, requestedLevel])

  const showSolution = async () => {
    const requestedId = activeId
    try {
      const answer = await getSolution(requestedId, localStorage.getItem('access_token'))
      if (activeIdRef.current === requestedId) setSolution(answer)
    } catch (cause) {
      if (activeIdRef.current === requestedId) setError(cause.message)
    }
  }

  return <div className="lesson-page practice-page">
    {activeId && <button type="button" className="btn-hint practice-back-button"
      onClick={() => setParams({ level_no: String(levelNo) })}>← 返回加练题库</button>}
    {busy && <p role="status">正在读取加练题库...</p>}
    {error && <p role="alert">{error}</p>}
    {!busy && requestedId && !activeId && <p role="alert">这道加练尚未解锁或不存在，请选择其他练习。</p>}
    {!activeId && items.length > 0 && <div className="practice-map" aria-label="加练题库">
      <div className="practice-map-legend" aria-label="通关状态说明">
        <span><i className="practice-legend-dot is-pending" aria-hidden="true" />蓝色：未通关</span>
        <span><i className="practice-legend-dot is-completed" aria-hidden="true" />绿色：已通关</span>
      </div>
      {Array.from({ length: 12 }, (_, index) => index + 1).map(number =>
        <section className="practice-map-level" id={`practice-level-${number}`} key={number}
          aria-labelledby={`practice-heading-${number}`}>
          <h2 id={`practice-heading-${number}`}>第 {number} 关</h2>
          <ol className="practice-map-questions">
            {items.filter(item => item.level_no === number).map((item, index) =>
              <li className="practice-map-question" key={item.problem_id}>
                <button type="button" className={`practice-circle ${item.completed ? 'is-completed' : 'is-pending'}`}
                  disabled={!item.available}
                  aria-label={`第 ${number} 关，练习 ${index + 1}，${item.completed ? '已通过' : item.available ? '未通过' : '完成前置关卡后解锁'}`}
                  onClick={() => { setError(''); setParams({ level_no: String(number), problem_id: item.problem_id }) }}>
                  <span aria-hidden="true">{!item.available
                    ? <svg viewBox="0 0 24 24" width="25" height="25" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="5" y="10" width="14" height="11" rx="3" /><path d="M8 10V7a4 4 0 0 1 8 0v3" />
                    </svg>
                    : item.completed ? '✓' : index + 1}</span>
                </button>
                <span className="practice-circle-caption">练习 {index + 1}</span>
              </li>)}
          </ol>
        </section>)}
    </div>}
    {activeId && !lesson && !error && <p role="status">正在加载题目...</p>}
    {lesson?.problem_id === activeId && <>
      <CodeEditor key={lesson.problem_id} userId={userId} initialCode={lesson.starter_code}
        problemId={lesson.problem_id} title={`加练 · ${lesson.title}`}
        acceptsInput={levelNo !== 1} persistentOutput allowReset sampleInput={lesson.examples[0]?.stdin || ''}
        teaching={lesson.teaching.map(item => <section className="lesson-teaching" key={item.title}>
          <h4>{item.title}</h4><p>{item.text}</p><pre>{item.example}</pre>
        </section>)}
        onAccepted={() => {
          setLesson(current => ({ ...current, completed: true }))
          setItems(current => current.map(item => item.problem_id === lesson.problem_id ? { ...item, completed: true } : item))
        }}>
        <div className="practice-statement">
          <section aria-label="题目"><h3>题目</h3><p>{lesson.story}</p></section>
          <section aria-label="任务"><h3>任务</h3><p>{task}</p></section>
        </div>
        <h3>样例</h3>
        {lesson.examples.map((example, index) => <div className="judge-output-grid" key={index}>
          <div><span>输入</span><pre>{example.stdin || '（无需输入）'}</pre></div>
          <div><span>输出</span><pre>{example.stdout || '（无输出）'}</pre></div>
        </div>)}
      </CodeEditor>
      {lesson.completed && <section className="lesson-complete" aria-label="加练完成">
        <h3>这道加练已通过</h3>
        {!currentSolution && <button type="button" className="btn-hint" onClick={showSolution}>查看参考解与解析</button>}
        {currentSolution && <><pre>{currentSolution.reference_solution}</pre><p>{currentSolution.solution_explanation}</p></>}
      </section>}
    </>}
  </div>
}
