import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import MisconceptionOverview from '../components/MisconceptionOverview.jsx'
import StatusStamp from '../components/StatusStamp.jsx'
import { groupMistakes, mistakeDetailUrl, mistakeOverviewUrl } from '../components/mistakeGrouping.mjs'
import { getMistakeQuestions, getKnowledge, getMisconceptions } from '../components/codeApi.mjs'

const difficultyLabels = { 1: '基础', 2: '巩固', 3: '综合' }

export default function LearningHistory() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [questions, setQuestions] = useState([])
  const [knowledgeNames, setKnowledgeNames] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [misconceptions, setMisconceptions] = useState([])
  const [misconceptionLoading, setMisconceptionLoading] = useState(true)
  const [misconceptionError, setMisconceptionError] = useState('')

  useEffect(() => {
    let active = true
    const token = localStorage.getItem('access_token')
    getMistakeQuestions(token).then(data => {
      if (active) setQuestions(data.items)
    }).catch(cause => {
      if (!active) return
      setError(cause.message)
      if (cause.status === 401) navigate('/auth')
    }).finally(() => { if (active) setLoading(false) })
    getKnowledge(token).then(data => {
      if (active) setKnowledgeNames(Object.fromEntries(data.items.map(item => [item.knowledge_id, item.name])))
    }).catch(() => {})
    getMisconceptions(token).then(data => {
      if (active) setMisconceptions(data.items)
    }).catch(cause => {
      if (active) setMisconceptionError(cause.message)
    }).finally(() => { if (active) setMisconceptionLoading(false) })
    return () => { active = false }
  }, [navigate])

  const groups = groupMistakes(questions, knowledgeNames)
  const activeGroup = params.get('knowledge') || 'all'
  const visibleGroups = activeGroup === 'all' ? groups : groups.filter(group => group.id === activeGroup)

  return <div className="mistake-page mistake-overview">
    <header className="mistake-page-header">
      <h1>我的错题</h1>
      <span className="mistake-total"><strong>{questions.length}</strong>道题待回顾</span>
    </header>
    {loading && <p role="status">正在整理你的错题...</p>}
    {error && <p className="mistake-alert" role="alert">{error}</p>}
    {!loading && !error && questions.length === 0 && <div className="mistake-empty">
      <h2>你的复习小站，还在等第一道题</h2>
      <p>提交中遇到的错题会留在这里，随时回来再试一次。</p>
      <Link to="/app/levels">去学习地图 →</Link>
    </div>}

    {questions.length > 0 && <>
      <nav className="mistake-knowledge-nav" aria-label="按知识点查看错题">
        <Link to="/app/history" aria-current={activeGroup === 'all' ? 'page' : undefined}>全部知识点<span>{questions.length}</span></Link>
        {groups.map(group => <Link key={group.id} to={mistakeOverviewUrl(group.id)}
          aria-current={activeGroup === group.id ? 'page' : undefined}>{group.name}<span>{group.questions.length}</span></Link>)}
      </nav>
      {!visibleGroups.length && <div className="mistake-empty">
        <p>这个知识点下暂时没有错题。</p><Link to="/app/history">查看全部知识点</Link>
      </div>}
      <div className={`mistake-groups ${activeGroup !== 'all' ? 'is-filtered' : ''}`}>
      {visibleGroups.map(group => <section className="mistake-knowledge-group" key={group.id}
        id={`knowledge-${group.id}`} aria-labelledby={`heading-${group.id}`}>
        <div className="mistake-group-heading"><h2 id={`heading-${group.id}`}>{group.name}</h2>
          <span>{group.questions.length} 道题</span></div>
        <div className="mistake-card-grid">
          {group.questions.map(question => <Link className="mistake-question-card" key={question.problem_id}
            to={mistakeDetailUrl(question.problem_id, group.id)}>
            <div className="mistake-card-copy"><small>{difficultyLabels[question.difficulty] || '难度待补充'}</small>
              <h3>{question.title}</h3></div>
            <div className="mistake-card-stamp"><StatusStamp passed={question.latest_passed} /></div>
            <div className="mistake-card-footer"><span>最近提交 · {question.latest_passed === true ? '已通过' : question.latest_passed === false ? '未通过' : '待尝试'}</span><strong>进入复习 <span aria-hidden="true">↗</span></strong></div>
          </Link>)}
        </div>
      </section>)}
      </div>
    </>}

    <details className="mistake-misconception-fold">
      <summary>查看疑似误区记录</summary>
      <MisconceptionOverview items={misconceptions} loading={misconceptionLoading} error={misconceptionError} />
    </details>
  </div>
}
