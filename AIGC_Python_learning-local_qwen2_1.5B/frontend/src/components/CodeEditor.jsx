import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import SubmissionFeedback from './SubmissionFeedback.jsx'
import PracticeRecommendationModal from './PracticeRecommendationModal.jsx'
import { requestCode, requestAnalysis, requestPracticeRecommendation } from './codeApi.mjs'
import { readCodeDraft, saveCodeDraft } from './codeDraft.mjs'

function CodeEditor({ initialCode, problemId, userId, onSuccess, onAccepted, onSubmitted, title, children, teaching, completionPanel, nextAction, acceptsInput = false, persistentOutput = acceptsInput, sampleInput = '', allowReset = false, resetMode = 'template' }) {
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
  const [authRequired, setAuthRequired] = useState(false)
  const [modal, setModal] = useState({ show: false, type: 'info', title: '', message: '' })
  const [lineCount, setLineCount] = useState(1)
  const [showConfetti, setShowConfetti] = useState(false)
  const [contentTab, setContentTab] = useState('task')
  const [recommendation, setRecommendation] = useState(null)
  const [recommendationPending, setRecommendationPending] = useState(false)

  const textareaRef = useRef(null)
  const lineNumbersRef = useRef(null)
  const canvasRef = useRef(null)
  const animationRef = useRef(null)
  const particlesRef = useRef([])
  const cannonRef = useRef(null)
  const busyRef = useRef(false)
  const submissionRef = useRef(null)
  const mountedRef = useRef(false)
  const successTimerRef = useRef(null)
  const busy = running || submitting
  const diagnosisReady = submission && !submission.judge.passed && submission.analysis?.status === 'ready'
    && (submission.analysis.content || submission.analysis.guidance)
  const isPartialFailure = submission && !submission.judge.passed && submission.judge.passed_cases > 0
    && submission.judge.passed_cases < submission.judge.total_cases
  const analysisPending = submission && !submission.judge.passed && submission.analysis?.status === 'preparing'

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
    if (busyRef.current) return
    setCode(value)
    setRecommendation(null)
    setRecommendationPending(false)
    persistDraft(value, stdin)
    setRunOutput(null)
    setSubmission(null)
    submissionRef.current = null
    setOutputType('hidden')
    clearTimeout(successTimerRef.current)
  }

  const persistDraft = (nextCode, nextInput) => {
    const saved = saveCodeDraft(userId, problemId, nextCode, nextInput)
    setDraftError(saved ? '' : '草稿未能保存到此浏览器，请先复制代码备份。')
  }

  const updateInput = (value) => {
    if (busyRef.current) return
    setStdin(value)
    persistDraft(code, value)
    setOutputType('hidden')
    setRunOutput(null)
    if (submissionRef.current?.origin === 'run') {
      setSubmission(null)
      submissionRef.current = null
    }
  }

  // Tab key handler
  const handleKeyDown = (e) => {
    if (busyRef.current) return
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
    if (busyRef.current) return
    const showRunOutput = (text, type) => {
      if (persistentOutput) {
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
    setRecommendation(null)
    setRecommendationPending(false)
    setAuthRequired(false)
    setSubmission(null)
    submissionRef.current = null
    showRunOutput('正在运行代码；若出现错误，将继续生成 AI 分析，请稍候...', 'info')
    clearTimeout(successTimerRef.current)

    let executionResult = null
    const displayExecution = result => {
      executionResult = result
      if (!result.success && result.analysis && result.judge) {
        const feedback = { origin: 'run', judge: result.judge, analysis: result.analysis }
        submissionRef.current = feedback
        setSubmission(feedback)
      }
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
    }
    try {
      const result = await requestCode('run', { code, timeout: 3, ...(problemId ? { problem_id: problemId } : {}), ...(acceptsInput ? { stdin } : {}) }, localStorage.getItem('access_token'), {
        onExecution: result => { if (mountedRef.current) displayExecution(result) },
      })
      if (!mountedRef.current) return
      displayExecution(result)
    } catch (error) {
      if (mountedRef.current) {
        if (executionResult) {
          const feedback = { origin: 'run', judge: executionResult.judge, analysis: {
            status: 'unavailable', message: `AI 分析暂不可用：${error.message} 运行结果已保留。`, content: null,
          } }
          submissionRef.current = feedback
          setSubmission(feedback)
        } else showRunOutput(error.message || '请求失败，请稍后重试。', 'error')
        setAuthRequired(error.status === 401)
      }
    } finally {
      busyRef.current = false
      if (mountedRef.current) setRunning(false)
    }
  }

  const submitCode = async () => {
    if (busyRef.current) return
    if (!code.trim()) {
      setOutput('请先输入代码')
      setOutputType('error')
      return
    }

    busyRef.current = true
    setSubmitting(true)
    setRecommendation(null)
    setRecommendationPending(false)
    setAuthRequired(false)
    setSubmission(null)
    submissionRef.current = null
    setModal(current => ({ ...current, show: false }))
    clearTimeout(successTimerRef.current)
    setOutput('正在运行测试用例...')
    setOutputType('info')
    try {
      const result = await requestCode('submit', { problem_id: problemId, code }, localStorage.getItem('access_token'))
      if (!mountedRef.current) return
      submissionRef.current = result
      setSubmission(result)
      setOutputType('hidden')
      const submissionGuided = onSubmitted?.(result) === true
      if (result.analysis?.status === 'preparing') {
        requestAnalysis(result.submission_id, localStorage.getItem('access_token'))
          .then(data => {
            if (!mountedRef.current || submissionRef.current !== result) return
            const updated = { ...result, analysis: data.analysis, timings: data.timings }
            submissionRef.current = updated
            setSubmission(updated)
          })
          .catch(error => {
            if (!mountedRef.current || submissionRef.current !== result) return
            const updated = { ...result, analysis: {
              status: 'unavailable', message: `${result.analysis.feedback_kind === 'guidance' ? '思考提示' : '错因分析'}暂时无法生成：${error.message} 判题结果已保留。`, content: null,
            } }
            submissionRef.current = updated
            setSubmission(updated)
          })
      }
      if (result.judge.passed) {
        onAccepted?.(result)
        startConfetti()
        if (!submissionGuided && result.practice_recommendation_eligible) {
          setRecommendationPending(true)
          requestPracticeRecommendation(result.submission_id, localStorage.getItem('access_token')).then(data => {
            if (!mountedRef.current || submissionRef.current !== result) return
            setRecommendationPending(false)
            if (data.status === 'ready' && data.recommendation) setRecommendation(data.recommendation)
            else setModal({ show: true, type: 'success', title: '通过', message: '恭喜！全部测试用例通过！' })
          }).catch(() => {
            if (!mountedRef.current || submissionRef.current !== result) return
            setRecommendationPending(false)
            setModal({ show: true, type: 'success', title: '通过', message: '恭喜！全部测试用例通过！' })
          })
        } else if (!submissionGuided) setModal({ show: true, type: 'success', title: '通过', message: '恭喜！全部测试用例通过！' })
        if (onSuccess && !submissionGuided && !result.practice_recommendation_eligible) successTimerRef.current = setTimeout(() => {
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
      <div className="ottly-notification" role="status" aria-live="polite">
        {diagnosisReady && <details className="ottly-diagnosis" key={submission.submission_id}>
          <summary className="ottly-diagnosis-trigger">
            <img src={new URL('../pages/images/ottly-message.png', import.meta.url).href} alt="" />
            <span><strong>{isPartialFailure ? '查看思考提示' : '查看错因分析'}</strong><small>Ottly有话要说！</small></span>
          </summary>
          <div className="ottly-diagnosis-chat" onKeyDown={event => {
            if (event.key === 'Escape') {
              const details = event.currentTarget.closest('details')
              details.open = false
              details.querySelector('summary').focus()
            }
          }}>
            <div className="ottly-message-heading">
              <img src={new URL('../pages/images/ottly-message.png', import.meta.url).href} alt="Ottly头像" />
              <div><strong>Ottly</strong><small>{isPartialFailure ? '已经通过了一部分，来想一想下一步。' : '来看看这次测试，我发现了这些线索。'}</small></div>
              <button type="button" aria-label={isPartialFailure ? '收起思考提示' : '收起错因分析'} onClick={event => {
                const details = event.currentTarget.closest('details')
                details.open = false
                details.querySelector('summary').focus()
              }}>×</button>
            </div>
            <SubmissionFeedback result={submission} showJudge={false} />
          </div>
        </details>}
      </div>
      <div className="level-detail-card">
        <div className="problem-section">
          <h2>{title}</h2>
          <div className="problem-tabs" role="tablist" aria-label="学习内容">
            <button id="problem-task-tab" type="button" role="tab"
              aria-selected={contentTab === 'task'} aria-controls="problem-content-panel"
              className={contentTab === 'task' ? 'active' : ''}
              onClick={() => setContentTab('task')}>题目要求</button>
            <button id="problem-teaching-tab" type="button" role="tab"
              aria-selected={contentTab === 'teaching'} aria-controls="problem-content-panel"
              className={contentTab === 'teaching' ? 'active' : ''}
              onClick={() => setContentTab('teaching')}>知识点讲解</button>
          </div>
          <div className="steps-box" id="problem-content-panel" role="tabpanel"
            aria-labelledby={contentTab === 'task' ? 'problem-task-tab' : 'problem-teaching-tab'}
            tabIndex={0}>
            {contentTab === 'task' ? children : teaching}
          </div>
        </div>

        <div className="code-section" id="code-workspace">
          <div className="code-header-bar">
            <span className="code-dot red"></span>
            <span className="code-dot yellow"></span>
            <span className="code-dot green"></span>
            <span className="code-file-label">main.py</span>
            {allowReset && <button type="button" className="code-reset-button"
              aria-label={resetMode === 'clear' ? '清空当前代码' : '清除代码痕迹，恢复初始代码'}
              title={resetMode === 'clear' ? '清空当前代码' : '清除代码痕迹，恢复初始代码'}
              disabled={busy} onClick={() => {
                if (resetMode === 'clear' && !window.confirm('确定清空当前代码吗？')) return
                updateCode(resetMode === 'clear' && problemId !== 'count-at-least-v1' ? '' : initialCode)
                textareaRef.current?.focus()
              }}>
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
                strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v6m4-6v6" />
              </svg>
            </button>}
          </div>
          <div className="code-editor-box" data-beginner-target="editor">
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

          {draftError && <p className="draft-status" role="status">{draftError}</p>}

          {acceptsInput && <div className="lesson-input">
            <label htmlFor="lesson-stdin">运行输入（每次 input 读取一行）</label>
            <textarea id="lesson-stdin" value={stdin} maxLength={8000} readOnly={busy}
              onChange={event => updateInput(event.target.value)} rows={3} />
            <button type="button" className="btn-hint" disabled={busy}
              onClick={() => updateInput(sampleInput)}>填入样例输入</button>
          </div>}

          {persistentOutput && <section className="lesson-output" data-beginner-target="output" aria-labelledby="lesson-output-title">
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
            <button className="btn-run" data-beginner-target="run" onClick={runCode} disabled={busy}>
              {running ? '运行中...' : '运行'}
            </button>
            <button className="btn-submit" data-beginner-target="submit" onClick={submitCode} disabled={busy}>
              {submitting ? '提交中...' : '提交判题'}
            </button>
            {nextAction && <button type="button" className="btn-next-level" onClick={nextAction} disabled={busy}>前往下一关 →</button>}
            {analysisPending && <span className="ottly-analysis-pending" role="status"><span aria-hidden="true" />{isPartialFailure ? 'Ottly正在准备思考提示' : 'Ottly正在分析错因'}</span>}
            {recommendationPending && <span className="ottly-analysis-pending" role="status"><span aria-hidden="true" />Ottly正在挑选加练题</span>}
          </div>
          {submission && (
            <SubmissionFeedback
              result={submission}
              showJudge={submission.origin !== 'run'}
              showAnalysis={!diagnosisReady}
            />
          )}
          {completionPanel}
          {submission && submission.origin !== 'run' && !submission.judge.passed && (
            <button type="button" className="btn-hint" onClick={() => navigate('/app/history')}>
              查看这道题的错题记录
            </button>
          )}
        </div>

      </div>

      <div className="otter-footer">
        <button type="button" className="otter-help" onClick={() => navigate('/app/ai-chat')}>
          <img src={new URL('../pages/images/sea_otter.png', import.meta.url).href} alt="" />
          <span>有问题？<strong>问问小海獭 →</strong></span>
        </button>
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

      {recommendation && <PracticeRecommendationModal recommendation={recommendation}
        onSkip={() => setRecommendation(null)}
        onPractice={() => {
          setRecommendation(null)
          navigate(`/app/practice?level_no=${recommendation.level_no}&problem_id=${encodeURIComponent(recommendation.problem_id)}`)
        }} />}
      {showConfetti && <canvas ref={canvasRef} className="confetti-canvas" />}
    </div>
  )
}

export default CodeEditor
