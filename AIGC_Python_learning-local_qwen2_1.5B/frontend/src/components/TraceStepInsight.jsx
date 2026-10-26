import React, { useEffect, useRef, useState } from 'react'
import { requestTraceExplanation } from './codeApi.mjs'

export default function TraceStepInsight({ trace, index, previous }) {
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
  const changed = Object.entries(step?.variables || {}).filter(([name, value]) => previous?.variables?.[name] !== value)
  const short = value => String(value).length > 80 ? String(value).slice(0, 80) + '…' : String(value)
  const summary = changed.length ? changed.slice(0, 2).map(([name, value]) =>
    `${name}：${short(previous?.variables?.[name] ?? '未定义')} → ${short(value)}`).join('；')
    : '这一刻没有变量变化，可以问问这行代码的作用。'
  const hints = { input: '输入已保存到变量。这个读取动作本身不会新增打印输出。',
    add: '先相加，再把结果保存到变量。对照原值和新值看看。', concat: '文字按顺序连接，再保存到变量。',
    replace: '新值替换了原值；这次没有把原值一起相加。', assign: '这个值已经保存到变量。',
    print: '结果已送到输出。退回一步，可以对比打印前的状态。', loop: '进入新一轮循环，留意本轮变量。',
    call: '进入函数后，右侧显示这次调用自己的变量。', return: '函数把这个值交回调用它的地方。',
    exception: '操作在这里中断了，可以对照高亮行和异常信息检查。' }
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
    <header><strong>Ottly</strong><span>按需解释当前步骤</span></header>
    <p className="trace-change-summary">{step ? hints[step.action?.kind] || summary : '当前没有可解释的执行步骤。'}</p>
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

