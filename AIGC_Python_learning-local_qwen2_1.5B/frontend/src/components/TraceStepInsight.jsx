import React, { useEffect, useRef, useState } from 'react'
import { requestTraceExplanation } from './codeApi.mjs'

export default function TraceStepInsight({ trace, index }) {
  const [answers, setAnswers] = useState({})
  const [errors, setErrors] = useState({})
  const [pending, setPending] = useState(null)
  const busy = useRef(false)
  const generation = useRef(0)
  useEffect(() => {
    generation.current++
    return () => { generation.current++ }
  }, [])
  const step = trace.steps?.[index]
  const answer = answers[index]
  const preview = answer ? (answer.match(/^[\s\S]*?[。！？]/)?.[0] || answer).slice(0, 140) : ''
  const explain = async () => {
    if (busy.current || answers[index] || !trace.trace_id || !step) return
    const current = generation.current
    busy.current = true
    setPending(index)
    setErrors(value => ({ ...value, [index]: '' }))
    try {
      const result = await requestTraceExplanation(trace.trace_id, index, localStorage.getItem('access_token'))
      if (generation.current === current) setAnswers(value => ({ ...value, [index]: result.answer }))
    } catch (error) {
      if (generation.current === current) setErrors(value => ({ ...value, [index]: error.message }))
    } finally {
      if (generation.current === current) { busy.current = false; setPending(null) }
    }
  }
  return <section className="trace-step-insight" aria-label="Ottly步骤解释">
    <header><strong>Ottly</strong></header>
    <button type="button" className="trace-explain-button" disabled={!step || !trace.trace_id || pending !== null || Boolean(answers[index])} onClick={explain}>
      <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="m12 3 2.7 6.3L21 12l-6.3 2.7L12 21l-2.7-6.3L3 12l6.3-2.7L12 3Z" /></svg>
      {answers[index] ? '已解释这一步' : pending === index ? 'Ottly 正在想…' : pending !== null ? '正在解释另一步，可继续回放' : '请 Ottly 解释这一步'}
    </button>
    {!trace.trace_id && step && <small>请在正式题目页重新打开回放，再向 Ottly 提问。</small>}
    {answer && <div className="trace-ai-answer" role="status"><p className="trace-ai-preview">{preview}</p>{answer.length > preview.length && <details key={index}><summary>展开完整解释</summary><p>{answer}</p></details>}</div>}
    {errors[index] && <p className="trace-ai-error" role="alert">{errors[index]}</p>}
    {pending !== null && !answers[index] && <small>解释不会阻止你切换步骤，最多等待约25秒。</small>}
  </section>
}

