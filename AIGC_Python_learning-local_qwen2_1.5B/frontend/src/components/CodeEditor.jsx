import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

const API_URL = '/api/v1/code/run'

function CodeEditor({ initialCode, expectedOutput, onSuccess, title, children }) {
  const navigate = useNavigate()
  const [code, setCode] = useState(initialCode)
  const [output, setOutput] = useState('运行结果将显示在这里')
  const [outputType, setOutputType] = useState('hidden')
  const [running, setRunning] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [modal, setModal] = useState({ show: false, type: 'info', title: '', message: '' })
  const [lineCount, setLineCount] = useState(1)
  const [showConfetti, setShowConfetti] = useState(false)

  const textareaRef = useRef(null)
  const lineNumbersRef = useRef(null)
  const canvasRef = useRef(null)
  const animationRef = useRef(null)
  const particlesRef = useRef([])
  const cannonRef = useRef(null)
  const lastRunResultRef = useRef(null)

  // Update line numbers
  useEffect(() => {
    setLineCount(code.split('\n').length)
  }, [code])

  // Sync scroll
  const handleScroll = () => {
    if (lineNumbersRef.current && textareaRef.current) {
      lineNumbersRef.current.scrollTop = textareaRef.current.scrollTop
    }
  }

  // Tab key handler
  const handleKeyDown = (e) => {
    if (e.key === 'Tab') {
      e.preventDefault()
      const start = e.target.selectionStart
      const end = e.target.selectionEnd
      const newCode = code.substring(0, start) + '    ' + code.substring(end)
      setCode(newCode)
      setTimeout(() => {
        e.target.selectionStart = e.target.selectionEnd = start + 4
      }, 0)
    }
  }

  const runCode = async () => {
    if (!code.trim()) {
      setOutput('请输入代码')
      setOutputType('error')
      return
    }

    setRunning(true)
    setOutput('代码正在执行，请稍候...')
    setOutputType('info')

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, timeout: 10 }),
      })
      const result = await response.json()
      lastRunResultRef.current = result.data

      let display = ''
      if (result.data.output) {
        display += '📝 程序输出:\n' + result.data.output + '\n'
      }
      if (result.data.errors && result.data.errors.length > 0) {
        for (const err of result.data.errors) {
          display += '========================================\n'
          display += `⚠️ ${err.type}\n`
          if (err.line) display += `📍 第 ${err.line} 行\n`
          display += `❌ ${err.message}\n`
          if (err.suggestion) display += `\n💡 ${err.suggestion}\n`
          display += '========================================\n\n'
        }
      }
      if (result.data.execution_time !== undefined) {
        display += `⏱️ 执行时间: ${result.data.execution_time} 秒`
      }

      setOutput(display.trim())
      setOutputType(result.data.success ? 'success' : 'error')
    } catch (error) {
      setOutput('无法连接到服务器，请确保后端服务已启动')
      setOutputType('error')
    } finally {
      setRunning(false)
    }
  }

  const submitCode = async () => {
    if (!code.trim()) {
      setOutput('请先输入代码并运行')
      setOutputType('error')
      return
    }

    const lastResult = lastRunResultRef.current
    if (!lastResult || !lastResult.success) {
      setOutput('请先点击"运行"按钮验证代码')
      setOutputType('info')
      return
    }

    setSubmitting(true)
    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, timeout: 10 }),
      })
      const result = await response.json()

      if (result.data.success) {
        const actualOutput = (result.data.output || '').trim()
        if (actualOutput === expectedOutput.trim()) {
          setModal({
            show: true,
            type: 'success',
            title: '通过',
            message: '恭喜！代码运行结果正确！',
          })
          startConfetti()
          if (onSuccess) {
            setTimeout(() => onSuccess(), 3000)
          }
        } else {
          setModal({
            show: true,
            type: 'error',
            title: '未通过',
            message: `预期输出: "${expectedOutput}"\n实际输出: "${actualOutput}"`,
          })
        }
      } else {
        setModal({
          show: true,
          type: 'error',
          title: '执行错误',
          message: '代码执行有错误，请修改后重试',
        })
      }
    } catch (error) {
      setModal({
        show: true,
        type: 'error',
        title: '错误',
        message: '网络错误，请稍后重试',
      })
    } finally {
      setSubmitting(false)
    }
  }

  const closeModal = () => {
    setModal({ ...modal, show: false })
  }

  // Confetti animation
  const startConfetti = useCallback(() => {
    particlesRef.current = []
    setShowConfetti(true)

    const canvas = canvasRef.current
    if (!canvas) return
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
    const ctx = canvas.getContext('2d')

    cannonRef.current = {
      x: canvas.width / 2,
      y: canvas.height * 0.6,
      targetX: canvas.width / 2,
      targetY: canvas.height * 0.3,
      rotation: 0,
      smoke: [],
      phase: 'launching',
      startTime: performance.now(),
      flash: 0,
    }

    const colors = ['#FF4757', '#FFD700', '#4A90E2', '#2ECC71', '#9B59B6', '#FF69B4']

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      const now = performance.now()
      const elapsed = now - cannonRef.current.startTime
      const c = cannonRef.current

      if (elapsed < 500) {
        c.phase = 'launching'
        c.y += (c.targetY - c.y) * 0.02
        c.rotation = Math.sin(elapsed * 0.02) * 0.3
        if (Math.random() < 0.3) {
          c.smoke.push({
            x: c.x + (Math.random() - 0.5) * 20,
            y: c.y + 30,
            size: Math.random() * 15 + 10,
            alpha: 0.8,
            vx: (Math.random() - 0.5) * 2,
            vy: Math.random() * 2 + 1,
          })
        }
        c.smoke.forEach(s => { s.x += s.vx; s.y += s.vy; s.alpha -= 0.02; s.size *= 0.98 })
        c.smoke = c.smoke.filter(s => s.alpha > 0)

        // Draw cannon
        ctx.save()
        ctx.translate(c.x, c.y)
        ctx.rotate(c.rotation)
        ctx.fillStyle = '#FFD700'
        ctx.beginPath()
        ctx.moveTo(-10, 25)
        ctx.lineTo(-12, -15)
        ctx.lineTo(12, -15)
        ctx.lineTo(10, 25)
        ctx.closePath()
        ctx.fill()
        ctx.fillStyle = '#8B4513'
        ctx.beginPath()
        ctx.arc(0, 30, 6, 0, Math.PI * 2)
        ctx.fill()
        ctx.restore()

        // Draw smoke
        c.smoke.forEach(s => {
          ctx.fillStyle = `rgba(255,255,255,${s.alpha})`
          ctx.beginPath()
          ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2)
          ctx.fill()
        })
      } else if (elapsed < 1000) {
        if (c.phase === 'launching') {
          c.phase = 'explosion'
          c.y = c.targetY
          c.flash = 1
          for (let i = 0; i < 180; i++) {
            const angle = (Math.PI * 2 * i) / 180 + Math.random() * 0.5
            const speed = Math.random() * 8 + 4
            const color = colors[Math.floor(Math.random() * colors.length)]
            particlesRef.current.push({
              x: c.x,
              y: c.y,
              vx: Math.cos(angle) * speed,
              vy: Math.sin(angle) * speed - Math.random() * 3,
              size: Math.random() * 8 + 4,
              color,
              alpha: 1,
              gravity: 0.15,
            })
          }
        }
        c.flash *= 0.85

        if (c.flash > 0.1) {
          const g = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, 80)
          g.addColorStop(0, `rgba(255,255,255,${c.flash})`)
          g.addColorStop(0.5, `rgba(255,215,0,${c.flash * 0.5})`)
          g.addColorStop(1, 'rgba(255,215,0,0)')
          ctx.fillStyle = g
          ctx.beginPath()
          ctx.arc(c.x, c.y, 80, 0, Math.PI * 2)
          ctx.fill()
        }

        particlesRef.current.forEach(p => {
          p.vy += p.gravity
          p.x += p.vx
          p.y += p.vy
          p.vx *= 0.99
          const r = parseInt(p.color.slice(1, 3), 16)
          const g = parseInt(p.color.slice(3, 5), 16)
          const b = parseInt(p.color.slice(5, 7), 16)
          ctx.fillStyle = `rgba(${r},${g},${b},${p.alpha})`
          ctx.beginPath()
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
          ctx.fill()
        })
      } else if (elapsed < 2500) {
        particlesRef.current.forEach(p => {
          p.vy += p.gravity
          p.x += p.vx
          p.y += p.vy
          p.vx *= 0.99
          p.alpha = Math.max(0, 1 - (elapsed - 1000) / 1500)
          if (p.alpha <= 0) return
          const r = parseInt(p.color.slice(1, 3), 16)
          const g = parseInt(p.color.slice(3, 5), 16)
          const b = parseInt(p.color.slice(5, 7), 16)
          ctx.fillStyle = `rgba(${r},${g},${b},${p.alpha})`
          ctx.beginPath()
          ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
          ctx.fill()
        })
      } else {
        setShowConfetti(false)
        return
      }

      animationRef.current = requestAnimationFrame(animate)
    }

    animate()
  }, [])

  useEffect(() => {
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
    }
  }, [])

  return (
    <div className="level-detail-page">
      <div className="level-detail-card">
        <div className="problem-section">
          <h2>{title}</h2>
          <div className="steps-box">
            {children}
          </div>
        </div>

        <div className="code-section">
          <div className="code-header-bar">
            <span className="code-dot red"></span>
            <span className="code-dot yellow"></span>
            <span className="code-dot green"></span>
          </div>
          <div className="code-editor-box">
            <div className="code-line-numbers" ref={lineNumbersRef}>
              {Array.from({ length: Math.max(lineCount, 1) }, (_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>
            <textarea
              ref={textareaRef}
              className="code-textarea"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onScroll={handleScroll}
              onKeyDown={handleKeyDown}
              spellCheck={false}
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
            />
          </div>

          <div className={`output-box ${outputType}`}>
            {output}
          </div>

          <div className="code-buttons">
            <button className="btn-run" onClick={runCode} disabled={running}>
              {running ? '运行中...' : '运行'}
            </button>
            <button className="btn-submit" onClick={submitCode} disabled={submitting}>
              {submitting ? '提交中...' : '提交'}
            </button>
          </div>
        </div>

        <div className="otter-footer">
          <div className="speech-text">有问题可以来问我哦</div>
          <img
            className="otter-img"
            src={new URL('../pages/images/sea_otter.png', import.meta.url).href}
            alt="小海獭"
            onClick={() => navigate('/app/ai-chat')}
          />
        </div>
      </div>

      <div className={`result-modal-overlay ${modal.show ? 'show' : ''}`} onClick={closeModal}>
        <div className="result-modal" onClick={(e) => e.stopPropagation()}>
          <div className={`modal-icon ${modal.type}`}>
            {modal.type === 'success' ? '✓' : modal.type === 'error' ? '✕' : 'ℹ'}
          </div>
          <h3>{modal.title}</h3>
          <p>{modal.message}</p>
          <button className="btn-close-modal" onClick={closeModal}>关闭</button>
        </div>
      </div>

      {showConfetti && <canvas ref={canvasRef} className="confetti-canvas" />}
    </div>
  )
}

export default CodeEditor
