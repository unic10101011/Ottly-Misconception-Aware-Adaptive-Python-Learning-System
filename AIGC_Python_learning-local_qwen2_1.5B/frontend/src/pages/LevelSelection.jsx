import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import yunduo from './images/yunduo.png'
import xingxing from './images/xingxing.png'
import chathaita from './images/chathaita.png'
import { getLevels } from '../components/codeApi.mjs'
import EndlessChallengeModal from '../components/EndlessChallengeModal.jsx'

const ROUTE_START = 82
const ROUTE_STEP = 150
const ROUTE_X = [112, 288]
const levelIconFiles = [null,
  '第一关.png', '第二关.png', '第三关.png', '第四关.png', '第五关.png', '第六关.png',
  '第七关.png', '第八关.png', '第九关.png', '第十关.png', '第十一关.png', '第十二关.png',
]

function routeCurve(from, to) {
  const middleY = (from.y + to.y) / 2
  return `M ${from.x} ${from.y} C ${from.x} ${middleY}, ${to.x} ${middleY}, ${to.x} ${to.y}`
}

function LevelSelection() {
  const navigate = useNavigate()
  const [levels, setLevels] = useState([])
  const [error, setError] = useState('')
  const [showEndless, setShowEndless] = useState(false)

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
  const endlessUnlocked = levels.length === 12 && levels.every(level => level.published && level.status === 'completed')
  const mapStops = [...levels, { id: 'endless', name: '无尽挑战', published: true,
    status: endlessUnlocked ? 'available' : 'locked' }]
  const routePoints = mapStops.map((level, index) => ({
    ...level,
    x: ROUTE_X[index % 2],
    y: ROUTE_START + index * ROUTE_STEP,
  }))
  const routeHeight = Math.max(220, ROUTE_START * 2 + (mapStops.length - 1) * ROUTE_STEP)

  return (
    <div className="level-page">
      <img src={xingxing} alt="" className="level-decoration level-star" />
      <img src={yunduo} alt="" className="level-decoration level-cloud" />
      {nextLevel && <header className="level-intro">
        <button type="button" className="level-continue" onClick={() => openLevel(nextLevel)}>
          继续学习 · {nextLevel.name} <span aria-hidden="true">→</span>
        </button>
      </header>}

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
          <div className="level-path-container" style={{ height: routeHeight }}>
            <svg viewBox={`0 0 400 ${routeHeight}`} preserveAspectRatio="none" aria-hidden="true">
              {routePoints.slice(0, -1).map((level, index) => (
                <path key={level.id} d={routeCurve(level, routePoints[index + 1])}
                  className={'level-route-line ' + level.status} />
              ))}
            </svg>
            <ol className="level-route-stops">
            {routePoints.map((level, index) => {
              const disabled = !level.published || level.status === 'locked'
              const iconFile = level.id !== 'endless' && (level.status === 'completed' ? 'bingo.png' : levelIconFiles[level.id])
              const statusText = !level.published ? '待开放' : level.status === 'completed' ? '已通关' : level.status === 'current' ? '当前关卡' : level.status === 'available' ? '可以挑战' : '尚未解锁'
              return <li key={level.id} className="level-route-stop"
                style={{ left: `${level.x / 4}%`, top: level.y }}>
                <button type="button" className={'level-circle ' + level.status + (iconFile ? ' has-image' : '')} disabled={disabled}
                  onClick={() => level.id === 'endless' ? setShowEndless(true) : openLevel(level)}
                  aria-current={level.status === 'current' ? 'step' : undefined}
                  aria-label={level.id === 'endless' ? '无尽挑战，' + (endlessUnlocked ? '可以挑战' : '完成全部 12 关后解锁')
                    : '第 ' + (index + 1) + ' 关，' + level.name + '，' + statusText}>
                  {level.status === 'current' && <span className="current-arrow" aria-hidden="true">▲</span>}
                  {level.status === 'completed' && <span className="check-mark" aria-hidden="true">✓</span>}
                  {iconFile ? <img className="level-map-image" src={`/level-icons/${iconFile}`} alt="" draggable={false} decoding="async" />
                    : <span className="level-icon" aria-hidden="true">{disabled ? '🔒' : '∞'}</span>}
                  {iconFile && disabled && <span className="check-mark" aria-hidden="true">🔒</span>}
                  <span className="level-name">{level.name}</span>
                  <span className="level-label">{statusText}</span>
                </button>
              </li>
            })}
            </ol>
          </div>
        </section>
      </div>}
      <div className="level-otter-summon">
        <button type="button" className="otter-help" onClick={() => navigate('/app/ai-chat')}>
          <img src={chathaita} alt="" />
          <span>有问题？<strong>召唤小海獭 →</strong></span>
        </button>
      </div>
      <div className="level-wave" aria-hidden="true" />
      {showEndless && <EndlessChallengeModal onClose={() => setShowEndless(false)} />}
    </div>
  )
}

export default LevelSelection
