import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import yunduo from './images/yunduo.png'
import xingxing from './images/xingxing.png'
import chathaita from './images/chathaita.png'
import { getLevels } from '../components/codeApi.mjs'

function generatePath(from, to, index) {
  const startX = from.x + 45
  const startY = from.y + 90
  const endX = to.x + 45
  const endY = to.y
  const midY = (startY + endY) / 2
  const bend = index % 2 === 0 ? 60 : -60
  return `M ${startX} ${startY} C ${startX + bend} ${midY}, ${endX + bend} ${midY}, ${endX} ${endY}`
}

function LevelSelection() {
  const navigate = useNavigate()
  const [levels, setLevels] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    getLevels(localStorage.getItem('access_token')).then(data => {
      if (!active) return
      setLevels(data.items.map((level, index) => ({ ...level,
        x: index % 2 ? 200 : 55, y: 100 + index * 160,
        color: level.status === 'completed' ? '#27c93f' : '#4A90E2',
        icon: !level.published ? '🔒' : ['🦦', '👋', '🛒', '🐚', '🏅', '⛵', '🚩'][index] || '📘',
      })))
    }).catch(error => {
      if (!active) return
      setError(error.message)
      if (error.status === 401) navigate('/auth')
    })
    return () => { active = false }
  }, [navigate])

  const handleCircleClick = (level) => {
    if (level.status === 'locked' || !level.published) return
    navigate(`/app/levels/${level.id}`)
  }

  const pathHeight = Math.max(700, 100 + levels.length * 160)

  return (
    <div className="level-page" style={{ minHeight: pathHeight + 40 }}>
      {error && <p role="alert">{error}</p>}
      {!error && levels.length === 0 && <p role="status">正在读取学习进度...</p>}
      <img src={xingxing} alt="星星" className="level-decoration"
        style={{ top: '2%', left: '3%', width: '50px', opacity: 0.6 }} />
      <img src={yunduo} alt="云朵" className="level-decoration"
        style={{ top: '3%', right: '5%', width: '70px', opacity: 0.6 }} />

      {/* Right-side otter - full body, ~1/3 page height */}
      <div className="otter-side"
        onClick={() => navigate('/app/ai-chat')}>
        <div className="otter-bubble">有问题问我哦</div>
        <img src={chathaita} alt="海獭" />
      </div>

      {/* Level circles container - centered */}
      <div className="level-path-container" style={{ height: pathHeight }}>
        <svg>
          {levels.slice(0, -1).map((level, i) => (
            <path
              key={i}
              d={generatePath(level, levels[i + 1], i)}
              fill="none"
              stroke={level.status === 'completed' ? '#27c93f' : level.status === 'current' ? '#4A90E2' : level.status === 'available' ? '#78afe4' : '#ccc'}
              strokeWidth="4"
              strokeDasharray={level.status === 'locked' ? '8,4' : 'none'}
              strokeLinecap="round"
              opacity="0.7"
            />
          ))}
        </svg>

        {levels.map((level) => (
          <div
            key={level.id}
            role="button" tabIndex={level.published && level.status !== 'locked' ? 0 : -1}
            aria-disabled={!level.published || level.status === 'locked'}
            onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); handleCircleClick(level) } }}
            className={`level-circle ${level.status}`}
            style={{ left: `${level.x}px`, top: `${level.y}px` }}
            onClick={() => handleCircleClick(level)}
          >
            {level.status === 'current' && <div className="current-arrow">▲</div>}
            {level.status === 'completed' && <div className="check-mark">✓</div>}
            <span className="level-icon">{level.icon}</span>
            <span className="level-name">{level.name}</span>
            <span className="level-label">
              {!level.published ? (level.status === 'current' ? '已解锁 · 待开放' : '待开放') : level.status === 'completed' ? '已通关' : level.status === 'current' ? '当前关卡' : '未解锁'}
            </span>
          </div>
        ))}
      </div>

      <div className="level-wave" />
    </div>
  )
}

export default LevelSelection
