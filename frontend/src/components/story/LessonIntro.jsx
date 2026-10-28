import React, { useEffect, useRef, useState } from 'react'
import StoryDialogue from './StoryDialogue.jsx'
import BeginnerTour from './BeginnerTour.jsx'
import { getGuide, completeGuide } from '../codeApi.mjs'

export default function LessonIntro({ problemId, onExit, onReady, beginner = false }) {
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [tourOpen, setTourOpen] = useState(false)
  const active = useRef(false)
  const savingRef = useRef(false)
  useEffect(() => {
    let current = true
    active.current = true
    setError('')
    getGuide(problemId, localStorage.getItem('access_token')).then(result => {
      if (!current) return
      setData(result)
      setTourOpen(beginner && !result.completed)
      setOpen(!result.completed)
      onReady?.(result.completed)
    }).catch(error => { if (current) setError(error.message) })
    return () => { current = false; active.current = false }
  }, [problemId, attempt, onReady, beginner])
  const finish = async state => {
    if (savingRef.current) return
    savingRef.current = true
    setSaving(true)
    setError('')
    try {
      await completeGuide(problemId, data.story.id, state.heard, state.answers, localStorage.getItem('access_token'))
      if (!active.current) return
      setData(previous => ({ ...previous, completed: true }))
      setOpen(false)
      onReady?.(true)
    } catch (error) {
      if (active.current) setError(`引导完成记录未保存：${error.message} 请重试。`)
    } finally {
      savingRef.current = false
      if (active.current) setSaving(false)
    }
  }
  return <>
    <button type="button" className="lesson-tool-icon" title="重温知识" aria-label="重温知识点引导"
      disabled={!data} onClick={() => { setError(''); setOpen(true) }}>
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M4 4h16v12H9l-5 4V4Z" /><path d="M8 8h8M8 12h5" />
      </svg>
    </button>
    {beginner && <button type="button" className="lesson-tool-icon" title="重看操作指引" aria-label="重看第一关操作指引"
      disabled={!data} onClick={() => setTourOpen(true)}>
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <circle cx="12" cy="12" r="9" /><path d="m10 8 6 4-6 4V8Z" />
      </svg>
    </button>}
    {!data && <div className="guide-load-status" role={error ? 'alert' : 'status'}>{error || '正在加载知识引导…'}
      {error && <button type="button" onClick={() => setAttempt(value => value + 1)}>重试加载引导</button>}</div>}
    {data && tourOpen && <BeginnerTour onFinish={() => { setTourOpen(false); setOpen(true) }} />}
    {data && open && !tourOpen && <StoryDialogue story={data.story} canSkip={data.completed} onExit={onExit}
      saving={saving} saveError={error} onFinish={finish} onSkip={() => { if (data.completed) setOpen(false) }} />}
  </>
}
