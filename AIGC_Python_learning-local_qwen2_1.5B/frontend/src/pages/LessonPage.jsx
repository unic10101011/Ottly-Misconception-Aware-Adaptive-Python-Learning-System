import React, { useEffect, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router-dom'
import CodeEditor from '../components/CodeEditor.jsx'
import LessonIntro from '../components/story/LessonIntro.jsx'
import { getLevels, getLesson, getSolution } from '../components/codeApi.mjs'

const lessonIllustrations = [null,
  '第一关.png', '第二关.png', '第三关.png', '第四关.png', '第五关.png',
  '第六关.jpg', '第七关.png', '第八关.png', '第九关.png', '第十关.png', '第十一关.png',
]

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
  const [guideReady, setGuideReady] = useState(false)

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

  const completionPanel = completed && <section className="lesson-complete" aria-label="通关复盘">
    <h3>第 {levelNo} 关已通过，进度已保存</h3>
    {next && <p>{next.published ? `可以继续挑战第 ${next.id} 关：${next.name}。` : `第 ${next.id} 关内容待开放。`}</p>}
    {!next && levelNo === 12 && <p>恭喜完成全部 12 关！可以查看参考详解，或到学习记录复习。</p>}
    {!solution && <button type="button" className="btn-hint" onClick={revealSolution} disabled={solutionBusy}>
      {solutionBusy ? '正在加载...' : '查看参考解与解析'}
    </button>}
    {solutionError && <p role="alert">{solutionError}</p>}
    {solution && <><pre>{solution.reference_solution}</pre><p style={{ whiteSpace: 'pre-wrap' }}>{solution.solution_explanation}</p></>}
    <button type="button" className="btn-hint" onClick={() => navigate('/app/history')}>查看学习记录</button>
  </section>

  return <div className="lesson-page">
    <div className="lesson-tools" aria-label="关卡工具">
      <button type="button" className="lesson-tool-icon" title="返回关卡" aria-label="返回关卡选择" onClick={() => navigate('/app/levels')}>
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m14 5-7 7 7 7M7 12h14" /></svg>
      </button>
      {lesson && <LessonIntro problemId={lesson.problem_id} onReady={setGuideReady} onExit={() => navigate('/app/levels')} />}
    </div>
    {error && <p role="alert">{error}</p>}
    {!lesson && !error && <p role="status">正在加载第 {levelNo} 关...</p>}
    {lesson && <div inert={guideReady ? undefined : ''}>
      <CodeEditor userId={userId} initialCode={lesson.starter_code} problemId={lesson.problem_id}
        allowReset resetMode="clear"
        title={`第 ${levelNo} 关 · ${lesson.title}`} acceptsInput={levelNo !== 1} persistentOutput
        sampleInput={lesson.examples[0]?.stdin || ''} onAccepted={() => setCompleted(true)}
        teaching={lesson.teaching.map(item => <section className="lesson-teaching" key={item.title}>
          <h4>{item.title}</h4><p>{item.text}</p><pre>{item.example}</pre>
        </section>)}
        nextAction={completed && next?.published ? () => navigate(`/app/levels/${next.id}`) : undefined}
        completionPanel={completionPanel}>
        <h3>情境</h3><p>{lesson.story}</p>
        {lessonIllustrations[levelNo] && <figure className="lesson-illustration">
          <img src={`/lesson-illustrations/${lessonIllustrations[levelNo]}`}
            alt={`第 ${levelNo} 关 · ${lesson.title}的情境插图`} loading="lazy" decoding="async" />
        </figure>}
        <h3>任务</h3><p>{lesson.description}</p>
        <h3>样例</h3>
        {lesson.examples.map((example, index) => <div className="judge-output-grid" key={index}>
          <div><span>输入</span><pre>{example.stdin || '（无需输入）'}</pre></div>
          <div><span>输出</span><pre>{example.stdout || '（无输出，不打印空行）'}</pre></div>
        </div>)}
      </CodeEditor>
      {completed && <button type="button" className="btn-hint" onClick={() => navigate(`/app/practice?level_no=${levelNo}`)}>
        练习第 {levelNo} 关知识点
      </button>}
    </div>}
  </div>
}
