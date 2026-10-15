import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import SubmissionFeedback from './SubmissionFeedback.jsx'
import { requestCode, saveHintView } from './codeApi.mjs'
import { readCodeDraft, saveCodeDraft } from './codeDraft.mjs'

function CodeEditor({ initialCode, problemId, userId, onSuccess, onAccepted, title, children, acceptsInput = false, sampleInput = '' }) {
  const navigate = useNavigate()
  const [code, setCode] = useState(() => readCodeDraft(userId, problemId)?.code ?? initialCode)
  const [stdin, setStdin] = useState(() => readCodeDraft(userId, problemId)?.stdin ?? sampleInput)
  const [draftError, setDraftError] = useState('')
  const [runOutput, setRunOutput] = useState(null)
  const [output, setOutput] = useState('运行结果将显示在这里')
  const [outputType, setOutputType] = useState('hidden')
  const [running, setRunning] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submission, setSubmission] = useState(null)
  const [visibleHintCount, setVisibleHintCount] = useState(0)
  const [hintBusy, setHintBusy] = useState(false)
  const [hintError, setHintError] = useState('')
  const [authRequired, setAuthRequired] = useState(false)
  const [modal, setModal] = useState({ show: false, type: 'info', title: '', message: '' })
  const [lineCount, setLineCount] = useState(1)
  const [showConfetti, setShowConfetti] = useState(false)

  const textareaRef = useRef(null)
  const lineNumbersRef = useRef(null)
  const canvasRef = useRef(null)
  const animationRef = useRef(null)
  const particlesRef = useRef([])
  const cannonRef = useRef(null)
  const busyRef = useRef(false)
  const hintBusyRef = useRef(false)
  const submissionRef = useRef(null)
  const mountedRef = useRef(false)
  const successTimerRef = useRef(null)
  const busy = running || submitting || hintBusy

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

  const updateCode = (value) => {
    if (busyRef.current || hintBusyRef.current) return
    setCode(value)
    persistDraft(value, stdin)
    setRunOutput(null)
    setSubmission(null)
    submissionRef.current = null
    setVisibleHintCount(0)
    setHintError('')
    setOutputType('hidden')
    clearTimeout(successTimerRef.current)
  }

  const persistDraft = (nextCode, nextInput) => {
    const saved = saveCodeDraft(userId, problemId, nextCode, nextInput)
    setDraftError(saved ? '' : '草稿未能保存到此浏览器，请先复制代码备份。')
  }

  const updateInput = (value) => {
    if (busyRef.current || hintBusyRef.current) return
    setStdin(value)
    persistDraft(code, value)
    setOutputType('hidden')
    setRunOutput(null)
  }

  // Tab key handler
  const handleKeyDown = (e) => {
    if (busyRef.current || hintBusyRef.current) return
    if (e.key === 'Tab') {
      e.preventDefault()
      const start = e.target.selectionStart
      const end = e.target.selectionEnd
      const newCode = code.substring(0, start) + '    ' + code.substring(end)
      if (newCode.length > 6000) return
      updateCode(newCode)
      setTimeout(() => {
        e.target.selectionStart = e.target.selectionEnd = start + 4
      }, 0)
    }
  }

  const showRequestError = (error) => {
    setOutput(error.message || '请求失败，请稍后重试。')
    setOutputType('error')
    setAuthRequired(error.status === 401)
  }

  const runCode = async () => {
    if (busyRef.current || hintBusyRef.current) return
    const showRunOutput = (text, type) => {
      if (acceptsInput) {
        setRunOutput({ text, type })
        setOutputType('hidden')
      } else {
        setOutput(text)
        setOutputType(type)
      }
    }
    if (!code.trim()) {
      showRunOutput('请输入代码', 'error')
      return
    }

    busyRef.current = true
    setRunning(true)
    setAuthRequired(false)
    showRunOutput('代码正在执行，请稍候...', 'info')
    clearTimeout(successTimerRef.current)

    try {
      const result = await requestCode('run', { code, timeout: 3, ...(acceptsInput ? { stdin } : {}) }, localStorage.getItem('access_token'))
      if (!mountedRef.current) return
      let display = ''
      if (result.output) {
        display += '程序输出:\n' + result.output + '\n'
      } else if (result.output_available === false) {
        display += '输出未采集（执行已终止）。\n'
      } else if (result.success) {
        display += '程序运行结束，没有输出。\n'
      }
      if (result.errors && result.errors.length > 0) {
        for (const err of result.errors) {
          display += '========================================\n'
          display += `⚠️ ${err.type}\n`
          if (err.line) display += `📍 第 ${err.line} 行\n`
          display += `❌ ${err.message}\n`
          if (err.suggestion) display += `\n💡 ${err.suggestion}\n`
          display += '========================================\n\n'
        }
      }
      if (result.execution_time !== undefined) {
        display += `执行时间: ${result.execution_time} 秒`
      }
      showRunOutput(display.trim() || '程序运行结束，没有输出。', result.success ? 'success' : 'error')
    } catch (error) {
      if (mountedRef.current) {
        showRunOutput(error.message || '请求失败，请稍后重试。', 'error')
        setAuthRequired(error.status === 401)
      }
    } finally {
      busyRef.current = false
      if (mountedRef.current) setRunning(false)
    }
  }

  const submitCode = async () => {
    if (busyRef.current || hintBusyRef.current) return
    if (!code.trim()) {
      setOutput('请先输入代码')
      setOutputType('error')
      return
    }

    busyRef.current = true
    setSubmitting(true)
    setAuthRequired(false)
    setSubmission(null)
    submissionRef.current = null
    setVisibleHintCount(0)
    setHintError('')
    setModal(current => ({ ...current, show: false }))
    clearTimeout(successTimerRef.current)
    setOutput('正在运行测试用例；若未通过，将准备学习提示，请稍候...')
    setOutputType('info')
    try {
      const result = await requestCode('submit', { problem_id: problemId, code }, localStorage.getItem('access_token'))
      if (!mountedRef.current) return
      submissionRef.current = result
      setSubmission(result)
      setOutputType('hidden')
      if (result.judge.passed) {
        onAccepted?.(result)
        setModal({ show: true, type: 'success', title: '通过', message: '恭喜！全部测试用例通过！' })
        startConfetti()
        if (onSuccess) successTimerRef.current = setTimeout(() => {
          if (mountedRef.current) onSuccess()
        }, 3000)
      }
    } catch (error) {
      if (mountedRef.current) showRequestError(error)
    } finally {
      busyRef.current = false
      if (mountedRef.current) setSubmitting(false)
    }
  }

  const revealHint = async () => {
    const current = submissionRef.current
    if (hintBusyRef.current || !current?.submission_id || visibleHintCount >= 3) return
    hintBusyRef.current = true
    setHintBusy(true)
    setHintError('')
    try {
      const saved = await saveHintView(current.submission_id, visibleHintCount + 1, localStorage.getItem('access_token'))
      if (mountedRef.current && submissionRef.current === current) {
        setVisibleHintCount(saved.hints_viewed_max)
      }
    } catch (error) {
      if (mountedRef.current && submissionRef.current === current) {
        setHintError(`提示查看记录暂未保存：${error.message} 请重试。`)
      }
    } finally {
      hintBusyRef.current = false
      if (mountedRef.current) setHintBusy(false)
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
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
      clearTimeout(successTimerRef.current)
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
              placeholder="在这里输入 Python 代码..."
              value={code}
              onChange={(e) => updateCode(e.target.value)}
              aria-label="Python 代码编辑器"
              readOnly={busy}
              aria-busy={busy}
              maxLength={6000}
              wrap="off"
              onScroll={handleScroll}
              onKeyDown={handleKeyDown}
              spellCheck={false}
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
            />
          </div>

          <p className="draft-status" role="status">
            {draftError || '代码和运行输入自动保存在当前浏览器，按账号和题目分别保留。'}
          </p>

          {acceptsInput && <div className="lesson-input">
            <label htmlFor="lesson-stdin">运行输入（每次 input 读取一行）</label>
            <textarea id="lesson-stdin" value={stdin} maxLength={8000} readOnly={busy}
              onChange={event => updateInput(event.target.value)} rows={3} />
            <button type="button" className="btn-hint" disabled={busy}
              onClick={() => updateInput(sampleInput)}>填入样例输入</button>
            <p>运行只使用这里的输入；提交会由后端检查全部正式测试。</p>
          </div>}

          {acceptsInput && <section className="lesson-output" aria-labelledby="lesson-output-title">
            <h4 id="lesson-output-title">运行输出</h4>
            <div className={`output-box ${runOutput?.type || 'info'}`} role="status" aria-live="polite">
              {runOutput?.text || '点击“运行”后，这里会显示程序输出或错误信息。'}
            </div>
          </section>}

          <div className={`output-box ${outputType}`} role="status">
            {output}
          </div>

          {authRequired && <button type="button" className="btn-hint" onClick={() => navigate('/auth')}>重新登录</button>}

          <div className="code-buttons">
            <button className="btn-run" onClick={runCode} disabled={busy}>
              {running ? '运行中...' : '运行'}
            </button>
            <button className="btn-submit" onClick={submitCode} disabled={busy}>
              {submitting ? '提交中...' : '提交判题'}
            </button>
          </div>
          <p className="code-action-note">“运行”只检查代码执行结果；“提交判题”会测试题目要求，失败后才记入错题本。</p>
          {submission && (
            <SubmissionFeedback
              result={submission}
              visibleHintCount={visibleHintCount}
              onRevealHint={revealHint}
              hintBusy={hintBusy}
              hintError={hintError}
            />
          )}
          {submission && !submission.judge.passed && (
            <button type="button" className="btn-hint" onClick={() => navigate('/app/history')}>
              查看这道题的错题记录
            </button>
          )}
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
