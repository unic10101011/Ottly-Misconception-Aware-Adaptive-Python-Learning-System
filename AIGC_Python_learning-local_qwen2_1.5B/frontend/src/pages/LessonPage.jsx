import React, { useEffect, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router-dom'
import CodeEditor from '../components/CodeEditor.jsx'
import { getLevels, getLesson, getSolution } from '../components/codeApi.mjs'

export default function LessonPage({ levelNo: fixedLevelNo }) {
  const navigate = useNavigate()
  const { levelId } = useParams()
  const { userId } = useOutletContext()
  const levelNo = fixedLevelNo ?? Number(levelId)
  // A separate mounted lesson prevents requests or editor state from crossing levels.
  return <Lesson key={`${userId}:${levelNo}`} levelNo={levelNo} userId={userId} navigate={navigate} />
}

function Lesson({ levelNo, userId, navigate }) {
  const [lesson, setLesson] = useState(null)
  const [next, setNext] = useState(null)
  const [error, setError] = useState('')
  const [completed, setCompleted] = useState(false)
  const [solution, setSolution] = useState(null)
  const [solutionError, setSolutionError] = useState('')
  const [solutionBusy, setSolutionBusy] = useState(false)

  useEffect(() => {
    let active = true
    const token = localStorage.getItem('access_token')
    async function load() {
      try {
        const levels = await getLevels(token)
        const slot = levels.items.find(item => item.id === levelNo)
        if (!slot?.published || !slot.problem_id) throw new Error('本关内容尚未开放。')
        const data = await getLesson(slot.problem_id, token)
        if (!active) return
        setNext(levels.items.find(item => item.id === levelNo + 1) || null)
        setLesson(data)
        setCompleted(data.completed)
      } catch (error) {
        if (!active) return
        setError(error.message)
        if (error.status === 401) navigate('/auth')
      }
    }
    load()
    return () => { active = false }
  }, [levelNo, navigate])

  const revealSolution = async () => {
    setSolutionBusy(true)
    setSolutionError('')
    try {
      setSolution(await getSolution(lesson.problem_id, localStorage.getItem('access_token')))
    } catch (error) {
      setSolutionError(error.message)
    } finally {
      setSolutionBusy(false)
    }
  }

  return <div className="lesson-page">
    <button type="button" className="btn-hint" onClick={() => navigate('/app/levels')}>← 返回关卡选择</button>
    {error && <p role="alert">{error}</p>}
    {!lesson && !error && <p role="status">正在加载第 {levelNo} 关...</p>}
    {lesson && <>
      <CodeEditor userId={userId} initialCode={lesson.starter_code} problemId={lesson.problem_id}
        title={`第 ${levelNo} 关 · ${lesson.title}`} acceptsInput={levelNo !== 1} persistentOutput
        sampleInput={lesson.examples[0]?.stdin || ''} onAccepted={() => setCompleted(true)}>
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
          <div><span>输入</span><pre>{example.stdin || '（无需输入）'}</pre></div>
          <div><span>输出</span><pre>{example.stdout || '（无输出，不打印空行）'}</pre></div>
        </div>)}
      </CodeEditor>
      {completed && <section className="lesson-complete" aria-label="通关复盘">
        <h3>第 {levelNo} 关已通过，进度已保存</h3>
        {next && <p>{next.published ? `可以继续挑战第 ${next.id} 关：${next.name}。` : `第 ${next.id} 关内容待开放。`}</p>}
        {!next && levelNo === 12 && <p>恭喜完成全部 12 关！可以查看参考详解，或到学习记录复习。</p>}
        {!solution && <button type="button" className="btn-hint" onClick={revealSolution} disabled={solutionBusy}>
          {solutionBusy ? '正在加载...' : '查看参考解与解析'}
        </button>}
        {solutionError && <p role="alert">{solutionError}</p>}
        {solution && <><pre>{solution.reference_solution}</pre><p style={{ whiteSpace: 'pre-wrap' }}>{solution.solution_explanation}</p></>}
        {next?.published && <button type="button" className="btn-hint" onClick={() => navigate(`/app/levels/${next.id}`)}>进入第 {next.id} 关</button>}
        <button type="button" className="btn-hint" onClick={() => navigate('/app/history')}>查看学习记录</button>
      </section>}
    </>}
  </div>
}
