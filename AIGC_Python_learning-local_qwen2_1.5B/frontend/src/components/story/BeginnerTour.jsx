import React, { useEffect, useRef, useState } from 'react'
import './beginner-tour.css'

const assets = '/beginner-assets/'
const introSteps = [
  { pose: 'peek', text: '', duration: 1000 },
  { pose: 'welcome', text: '欢迎来到编程世界！', duration: 2400 },
  { target: 'editor', text: '这是代码编辑器，是你写程序的地方', duration: 2000 },
  { target: 'run', text: '写完代码后，点击运行', duration: 2000 },
  { target: 'output', text: '你的程序得出的结果会显示在这里', duration: 2000 },
  { target: 'submit', text: '系统会测试你编写的代码', duration: 2000 },
  { target: 'submit', text: '只有提交判题，系统才能判断你的程序是对还是错哦。', duration: 4000 },
  { pose: 'welcome', text: '接下来，让我们一起认识第一关的知识点，再动手写出你的第一个程序吧！' },
]

export default function BeginnerTour({ onFinish, result }) {
  const steps = result ? [
    { pose: 'welcome', text: '恭喜你完成第一个代码的编写！' },
    { text: result.judge.passed
      ? '全部测试通过啦！你已经完成了“编写 → 运行 → 提交判题”的完整过程，第一关的进度也保存好了。'
      : '第一次提交就是很棒的开始！这次还没有全部通过，先看看判题反馈，对照题目要求和实际输出找找线索。' },
    { text: result.judge.passed
      ? '你可以查看参考解与解析，回顾这道题的写法；也可以练习本关知识点，或者点击“前往下一关”继续冒险。'
      : '如果出现“查看错因分析”或“查看思考提示”，点开就能和我一起找原因。修改代码后，先运行看看，再提交判题。' },
    { text: '想复习时，可以点击上方的“重温知识”；遇到问题，也可以点击页面下方的“问问小海獭”。每一次尝试，都会让你更熟练！' },
  ] : introSteps
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const [rect, setRect] = useState(null)
  const ref = useRef(null)
  const step = steps[index]

  useEffect(() => {
    const dialog = ref.current
    const focus = document.activeElement
    dialog.showModal()
    return () => { dialog.close(); if (focus?.isConnected) focus.focus() }
  }, [])

  useEffect(() => {
    if (!step.duration || paused) return
    const timer = setTimeout(() => setIndex(value => value + 1), step.duration)
    return () => clearTimeout(timer)
  }, [index, paused, step.duration])

  useEffect(() => {
    const target = step.target && document.querySelector(`[data-beginner-target="${step.target}"]`)
    if (!target) { setRect(null); return }
    // Keep the real control visible through the spotlight, even in a stacked mobile layout.
    target.scrollIntoView({ block: 'center', behavior: 'instant' })
    const measure = () => {
      let bounds = target.getBoundingClientRect()
      if (bounds.top < 100 || bounds.bottom > window.innerHeight - 16) {
        target.scrollIntoView({ block: 'center', behavior: 'instant' })
        bounds = target.getBoundingClientRect()
      }
      setRect({ left: bounds.left - 6, top: bounds.top - 6, width: bounds.width + 12, height: bounds.height + 12 })
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(target)
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
    }
  }, [step.target])

  const pointing = Boolean(step.target && rect)
  const flipped = pointing && rect.left < 220
  const smallScreen = pointing && window.innerWidth <= 720
  const actorStyle = pointing ? {
    left: flipped ? Math.min(window.innerWidth - 130, rect.left + rect.width + 12) : Math.max(0, rect.left - 155),
    top: Math.max(100, Math.min(window.innerHeight - (smallScreen ? 115 : 165), rect.top + rect.height / 2 - (smallScreen ? 20 : 65))),
  } : undefined
  const bubbleStyle = pointing ? {
    left: Math.max(16, Math.min(window.innerWidth - Math.min(380, window.innerWidth - 32) - 16, rect.left)),
    ...(rect.top > window.innerHeight / 2
      ? { top: 'auto', bottom: window.innerHeight - rect.top + 24 }
      : { top: Math.min(window.innerHeight - 200, rect.top + rect.height + 24), bottom: 'auto' }),
  } : undefined

  return <dialog ref={ref} className={`beginner-tour ${pointing ? 'is-pointing' : ''} ${step.pose === 'peek' ? 'is-peeking' : ''}`}
    aria-label={result ? '首次提交指引' : '第一关新手指引'} onCancel={event => { event.preventDefault(); setPaused(true) }}>
    {pointing && <div className="beginner-spotlight" style={rect} aria-hidden="true" />}
    <div className="beginner-controls">
      <span>{result ? '第一次编程，完成！' : '跟着 Ottly 认识编程工作台'}</span>
      {!result && <button type="button" onClick={() => setPaused(value => !value)}>{paused ? '继续播放' : '暂停播放'}</button>}
      <button type="button" onClick={onFinish}>{result ? '返回代码' : '进入知识点讲解'}</button>
    </div>
    <div className={`beginner-actor ${pointing ? 'is-small' : ''} ${flipped ? 'is-flipped' : ''}`} style={actorStyle} aria-hidden="true">
      <img src={`${assets}${step.pose === 'peek' ? 'peek.png' : pointing ? 'point.png' : 'welcome.png'}`} alt="" />
    </div>
    {step.text && <section className="beginner-bubble" style={bubbleStyle}>
      <strong>Ottly <small>你的小海獭伙伴</small></strong>
      <p role="status" aria-live="polite" aria-atomic="true">{step.text}</p>
      <footer><span>{result ? index + 1 : Math.max(1, index)} / {result ? steps.length : steps.length - 1}</span>
        <button type="button" onClick={() => index === steps.length - 1 ? onFinish() : setIndex(value => value + 1)}>
          {index === steps.length - 1 ? result ? '我知道啦，继续探索！' : '开始知识点讲解 →' : '下一步 →'}
        </button>
      </footer>
    </section>}
  </dialog>
}
