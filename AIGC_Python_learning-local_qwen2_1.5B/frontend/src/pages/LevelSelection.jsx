import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import yunduo from './images/yunduo.png'
import xingxing from './images/xingxing.png'
import chathaita from './images/chathaita.png'

const levels = [
  { id: 1, name: '初识小海獭', icon: '🦦', x: 55, y: 100 },
  { id: 2, name: 'for循环', icon: '🔄', x: 200, y: 260 },
  { id: 3, name: '???', icon: '🔒', x: 55, y: 420 },
  { id: 4, name: '???', icon: '🔒', x: 200, y: 580 },
]

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
  const [passedIds, setPassedIds] = useState(null)
  const [loadError, setLoadError] = useState('')

  const loadProgress = () => {
    setLoadError('')
    fetch('/api/v1/code/progress', {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
    }).then(async response => {
      if (!response.ok) throw new Error('学习进度加载失败')
      const result = await response.json()
      setPassedIds(new Set(result.data.passed_problem_ids))
    }).catch(error => setLoadError(error.message))
  }

  useEffect(() => { loadProgress() }, [])

  const visibleLevels = levels.map(level => ({
    ...level,
    status: level.id === 1
      ? (passedIds?.has('level1') ? 'completed' : 'current')
      : level.id === 2
        ? (passedIds?.has('level2') ? 'completed' : passedIds?.has('level1') ? 'current' : 'available')
        : 'locked',
  }))

  const handleCircleClick = (level) => {
    if (passedIds === null || level.status === 'locked') return
    navigate(`/app/levels/${level.id}`)
  }

  return (
    <div className="level-page">
      <img src={xingxing} alt="星星" className="level-decoration"
        style={{ top: '2%', left: '3%', width: '50px', opacity: 0.6 }} />
      <img src={yunduo} alt="云朵" className="level-decoration"
        style={{ top: '3%', right: '5%', width: '70px', opacity: 0.6 }} />

      {loadError && <div className="level-load-error" role="alert">{loadError} <button type="button" onClick={loadProgress}>重试</button></div>}
      {passedIds === null && !loadError && <div className="level-load-error">正在加载学习进度...</div>}

      {/* Right-side otter - full body, ~1/3 page height */}
      <div className="otter-side"
        onClick={() => navigate('/app/ai-chat')}>
        <div className="otter-bubble">有问题问我哦</div>
        <img src={chathaita} alt="海獭" />
      </div>

      {/* Level circles container - centered */}
      <div className="level-path-container">
        <svg>
          {visibleLevels.slice(0, -1).map((level, i) => (
            <path
              key={i}
              d={generatePath(level, visibleLevels[i + 1], i)}
              fill="none"
              stroke={level.status === 'completed' ? '#27c93f' : level.status === 'current' ? '#4A90E2' : level.status === 'available' ? '#78afe4' : '#ccc'}
              strokeWidth="4"
              strokeDasharray={level.status === 'locked' ? '8,4' : 'none'}
              strokeLinecap="round"
              opacity="0.7"
            />
          ))}
        </svg>

        {visibleLevels.map((level) => (
          <div
            key={level.id}
            className={`level-circle ${level.status}`}
            style={{ left: `${level.x}px`, top: `${level.y}px` }}
            onClick={() => handleCircleClick(level)}
          >
            {level.status === 'current' && <div className="current-arrow">▲</div>}
            {level.status === 'completed' && <div className="check-mark">✓</div>}
            <span className="level-icon">{level.icon}</span>
            <span className="level-name">{level.name}</span>
            <span className="level-label">
              {level.status === 'completed' ? '已通关' : level.status === 'current' ? '当前关卡' : level.status === 'available' ? '可学习' : '未解锁'}
            </span>
          </div>
        ))}
      </div>

      <div className="level-wave" />
    </div>
  )
}

export default LevelSelection
