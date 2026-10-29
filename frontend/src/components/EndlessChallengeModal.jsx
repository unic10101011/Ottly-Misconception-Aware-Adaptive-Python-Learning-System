import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { startEndlessChallenge } from './codeApi.mjs'
import AiRetry from './AiRetry.jsx'

export default function EndlessChallengeModal({ onClose }) {
  const navigate = useNavigate()
  const dialogRef = useRef(null)
  const firstChoiceRef = useRef(null)
  const requestRef = useRef(null)
  const lastMode = useRef('ottly')
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const previousFocus = document.activeElement
    const dialog = dialogRef.current
    dialog.showModal()
    firstChoiceRef.current.focus()
    return () => {
      requestRef.current?.abort()
      dialog.close()
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [])

  const choose = async mode => {
    if (requestRef.current) return
    lastMode.current = mode
    const controller = new AbortController()
    requestRef.current = controller
    setBusy(true)
    setError('')
    setProgress(mode === 'catalog' ? '正在从题库中抽题…' : '正在生成候选题…')
    try {
      const result = await startEndlessChallenge(mode, localStorage.getItem('access_token'), {
        signal: controller.signal,
        onProgress: data => { if (!controller.signal.aborted) setProgress(data.message) },
      })
      if (!controller.signal.aborted) {
        navigate('/app/endless?problem_id=' + encodeURIComponent(result.problem_id))
        onClose()
      }
    } catch (cause) {
      if (!controller.signal.aborted) {
        setError(cause.message)
        if (cause.status === 401) navigate('/auth')
      }
    } finally {
      if (!controller.signal.aborted) {
        requestRef.current = null
        setBusy(false)
        setProgress('')
      }
    }
  }

  return <dialog ref={dialogRef} className="endless-modal" aria-labelledby="endless-title"
    onCancel={event => { event.preventDefault(); onClose() }}>
    <button type="button" className="practice-recommendation-skip" aria-label="关闭无尽挑战" onClick={onClose}>×</button>
    <h2 id="endless-title">开启无尽挑战</h2>
    <div className="endless-choices" aria-busy={busy}>
      <button ref={firstChoiceRef} type="button" className="endless-choice" disabled={busy} onClick={() => choose('catalog')}>
        <strong>从题库中抽题</strong>
        <span>从已有题库中选择一道题。</span>
      </button>
      <button type="button" className="endless-choice" disabled={busy} onClick={() => choose('ottly')}>
        <strong>让 Ottly 出题</strong>
        <span>根据你的错题和学习情况，生成一道新的挑战。</span>
      </button>
    </div>
    {progress && <p className="endless-progress" role="status">{progress}</p>}
    {error && <AiRetry message={error} pending={busy} onRetry={() => choose(lastMode.current)} label="重新准备挑战题目" />}
  </dialog>
}
