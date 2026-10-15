import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import CodeEditor from '../components/CodeEditor.jsx'
import { getLesson, getSolution } from '../components/codeApi.mjs'

const PROBLEM_ID = 'greeting-v1'

function Level2() {
  const navigate = useNavigate()
  const [lesson, setLesson] = useState(null)
  const [error, setError] = useState('')
  const [completed, setCompleted] = useState(false)
  const [solution, setSolution] = useState(null)
  const [solutionError, setSolutionError] = useState('')
  const [solutionBusy, setSolutionBusy] = useState(false)

  useEffect(() => {
    let active = true
    getLesson(PROBLEM_ID, localStorage.getItem('access_token')).then(data => {
      if (!active) return
      setLesson(data)
      setCompleted(data.completed)
    }).catch(error => {
      if (!active) return
      setError(error.message)
      if (error.status === 401) navigate('/auth')
    })
    return () => { active = false }
  }, [navigate])

  const revealSolution = async () => {
    setSolutionBusy(true)
    setSolutionError('')
    try {
      setSolution(await getSolution(PROBLEM_ID, localStorage.getItem('access_token')))
    } catch (error) {
      setSolutionError(error.message)
    } finally {
      setSolutionBusy(false)
    }
  }

  return <div className="lesson-page">
    <button type="button" className="btn-hint" onClick={() => navigate('/app/levels')}>← 返回关卡选择</button>
    {error && <p role="alert">{error}</p>}
    {!lesson && !error && <p role="status">正在加载第 2 关...</p>}
    {lesson && <>
      <CodeEditor initialCode={lesson.starter_code} problemId={lesson.problem_id}
        title={`第 2 关 · ${lesson.title}`} acceptsInput sampleInput={lesson.examples[0].stdin}
        onAccepted={() => setCompleted(true)}>
        <h3>情境</h3><p>{lesson.story}</p>
        <details className="lesson-teaching" open>
          <summary>知识点讲解</summary>
          {lesson.teaching.map(item => <section key={item.title}>
            <h4>{item.title}</h4><p>{item.text}</p><pre>{item.example}</pre>
          </section>)}
        </details>
        <h3>任务</h3><p>{lesson.description}</p>
        <h3>样例</h3>
        {lesson.examples.map((example, index) => <div className="judge-output-grid" key={index}>
          <div><span>输入</span><pre>{example.stdin}</pre></div>
          <div><span>输出</span><pre>{example.stdout}</pre></div>
        </div>)}
      </CodeEditor>
      {completed && <section className="lesson-complete" aria-label="通关复盘">
        <h3>第 2 关已通过，进度已保存</h3>
        <p>第 3 关已解锁，内容待开放。你可以查看参考解，或回到学习记录复习。</p>
        {!solution && <button type="button" className="btn-hint" onClick={revealSolution} disabled={solutionBusy}>
          {solutionBusy ? '正在加载...' : '查看参考解与解析'}
        </button>}
        {solutionError && <p role="alert">{solutionError}</p>}
        {solution && <><pre>{solution.reference_solution}</pre><p>{solution.solution_explanation}</p></>}
        <button type="button" className="btn-hint" onClick={() => navigate('/app/history')}>查看学习记录</button>
      </section>}
    </>}
  </div>
}

export default Level2
