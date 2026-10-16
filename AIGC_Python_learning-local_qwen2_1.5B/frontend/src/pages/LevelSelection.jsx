import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import yunduo from './images/yunduo.png'
import xingxing from './images/xingxing.png'
import chathaita from './images/chathaita.png'
import { getLevels } from '../components/codeApi.mjs'

function LevelSelection() {
  const navigate = useNavigate()
  const [levels, setLevels] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getLevels(localStorage.getItem('access_token')).then(data => {
      if (active) setLevels(data.items)
    }).catch(error => {
      if (!active) return
      setError(error.message)
      if (error.status === 401) navigate('/auth')
    })
    return () => { active = false }
  }, [navigate])

  const openLevel = level => {
    if (level.status === 'locked' || !level.published) return
    navigate('/app/levels/' + level.id)
  }

  const publishedCount = levels.filter(level => level.published).length
  const completedCount = levels.filter(level => level.published && level.status === 'completed').length
  const nextLevel = levels.find(level => level.published && level.status !== 'locked' && level.status !== 'completed')
  const progress = publishedCount ? Math.round(completedCount / publishedCount * 100) : 0

  return (
    <div className="level-page">
      <img src={xingxing} alt="" className="level-decoration level-star" />
      <img src={yunduo} alt="" className="level-decoration level-cloud" />
      <header className="level-intro">
        <div>
          <span className="level-eyebrow">OTTLY · 学习地图</span>
          <h1>和小海獭继续探索 Python</h1>
          <p>沿着海岸一步步前进，完成练习后解锁下一站。</p>
        </div>
        {nextLevel && <button type="button" className="level-continue" onClick={() => openLevel(nextLevel)}>
          继续学习 · {nextLevel.name} <span aria-hidden="true">→</span>
        </button>}
      </header>

      {error && <p className="level-load-error" role="alert">{error}</p>}
      {!error && levels.length === 0 && <p className="level-loading" role="status">正在读取学习进度...</p>}

      {levels.length > 0 && <div className="level-content">
        <section className="level-map-card" aria-labelledby="level-map-heading">
          <div className="level-map-heading">
            <div><span className="level-eyebrow">你的学习旅程</span><h2 id="level-map-heading">闯关路线</h2></div>
            <span className="level-progress-text">已完成 {completedCount} / {publishedCount} 关</span>
          </div>
          <div className="level-progress-track" role="progressbar" aria-label="已开放关卡完成进度" aria-valuenow={completedCount} aria-valuemin="0" aria-valuemax={publishedCount || 1}>
            <span style={{ width: progress + '%' }} />
          </div>
          <ol className="level-map">
            {levels.map((level, index) => {
              const disabled = !level.published || level.status === 'locked'
              const statusText = !level.published ? '待开放' : level.status === 'completed' ? '已通关' : level.status === 'current' ? '当前关卡' : level.status === 'available' ? '可以挑战' : '尚未解锁'
              return <li key={level.id} className={'level-step ' + level.status + (disabled ? ' is-disabled' : '')}>
                <button type="button" className="level-step-button" disabled={disabled} onClick={() => openLevel(level)}
                  aria-label={'第 ' + (index + 1) + ' 关，' + level.name + '，' + statusText}>
                  <span className="level-step-number">{String(index + 1).padStart(2, '0')}</span>
                  <span className="level-step-copy"><strong>{level.name}</strong><small>{statusText}</small></span>
                  <span className="level-step-arrow" aria-hidden="true">{disabled ? '·' : '→'}</span>
                </button>
              </li>
            })}
          </ol>
        </section>
        <aside className="level-guide">
          <img src={chathaita} alt="小海獭" />
          <div><span className="level-eyebrow">小海獭在线</span><h2>卡住了？一起想办法。</h2>
            <p>遇到难题时，可以随时和我聊聊思路。</p></div>
          <button type="button" onClick={() => navigate('/app/ai-chat')}>向小海獭提问 <span aria-hidden="true">→</span></button>
        </aside>
      </div>}
      <div className="level-wave" aria-hidden="true" />
    </div>
  )
}

export default LevelSelection
