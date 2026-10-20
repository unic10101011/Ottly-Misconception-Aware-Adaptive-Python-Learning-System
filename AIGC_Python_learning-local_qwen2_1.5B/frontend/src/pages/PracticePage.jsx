import React, { useEffect, useRef, useState } from 'react'
import { useNavigate, useOutletContext, useSearchParams } from 'react-router-dom'
import CodeEditor from '../components/CodeEditor.jsx'
import { getLesson, getPractice, getSolution } from '../components/codeApi.mjs'

export default function PracticePage() {
  const navigate = useNavigate()
  const { userId } = useOutletContext()
  const [params, setParams] = useSearchParams()
  const requestedLevel = Number(params.get('level_no'))
  const levelNo = Number.isInteger(requestedLevel) && requestedLevel >= 1 && requestedLevel <= 12 ? requestedLevel : 1
  const [items, setItems] = useState([])
  const [selectedId, setSelectedId] = useState(null)
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

  const visible = items.filter(item => item.level_no === levelNo)
  const activeId = visible.some(item => item.problem_id === selectedId && item.available) ? selectedId : null
  const activeIdRef = useRef(activeId)
  activeIdRef.current = activeId
  const currentSolution = solution?.problem_id === activeId ? solution : null

  useEffect(() => {
    if (!visible.some(item => item.problem_id === selectedId && item.available)) {
      setSelectedId(visible.find(item => item.available)?.problem_id || null)
    }
  }, [levelNo, items, selectedId])

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
    <h1>针对性加练</h1>
    <p>每关三题，选择想巩固的知识点。加练结果会保存，但不会改变主线关卡进度。</p>
    <label className="practice-level-label" htmlFor="practice-level">选择关卡</label>
    <select id="practice-level" value={levelNo} onChange={event => { setSelectedId(null); setError(''); setParams({ level_no: event.target.value }) }}>
      {Array.from({ length: 12 }, (_, index) => <option key={index + 1} value={index + 1}>第 {index + 1} 关</option>)}
    </select>
    {busy && <p role="status">正在读取加练题库...</p>}
    {error && <p role="alert">{error}</p>}
    <div className="practice-list" aria-label={`第 ${levelNo} 关加练题`}>
      {visible.map(item => <button type="button" key={item.problem_id}
        className="practice-item" disabled={!item.available}
        aria-pressed={activeId === item.problem_id}
        onClick={() => setSelectedId(item.problem_id)}>
        <strong>{item.title}</strong>
        <span>{item.practice_focus}</span>
        <small>{item.completed ? '已完成' : item.available ? '可练习' : '完成前置关卡后解锁'}</small>
      </button>)}
    </div>
    {activeId && !lesson && !error && <p role="status">正在加载题目...</p>}
    {lesson?.problem_id === activeId && <>
      <CodeEditor key={lesson.problem_id} userId={userId} initialCode={lesson.starter_code}
        problemId={lesson.problem_id} title={`加练 · ${lesson.title}`}
        acceptsInput={levelNo !== 1} persistentOutput sampleInput={lesson.examples[0]?.stdin || ''}
        onAccepted={() => {
          setLesson(current => ({ ...current, completed: true }))
          setItems(current => current.map(item => item.problem_id === lesson.problem_id ? { ...item, completed: true } : item))
        }}>
        <h3>任务</h3><p>{lesson.description}</p>
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
