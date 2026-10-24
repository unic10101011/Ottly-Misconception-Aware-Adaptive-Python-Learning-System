import React, { useEffect, useRef, useState } from 'react'
import { createStoryState, currentStoryNode, stepStory } from './storyEngine.mjs'

function useModal(ref) {
  useEffect(() => {
    const dialog = ref.current
    const previousFocus = document.activeElement
    const previousOverflow = document.body.style.overflow
    const preventCancel = event => event.preventDefault()
    dialog.addEventListener('cancel', preventCancel)
    dialog.showModal()
    document.body.style.overflow = 'hidden'
    return () => {
      dialog.close()
      dialog.removeEventListener('cancel', preventCancel)
      document.body.style.overflow = previousOverflow
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [ref])
}

function StoryHistory({ entries, onClose }) {
  const ref = useRef(null)
  const pointerStartedOutside = useRef(false)
  const outsidePanel = event => {
    if (event.target !== event.currentTarget) return false
    const bounds = event.currentTarget.getBoundingClientRect()
    return event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom
  }
  useModal(ref)
  return <dialog ref={ref} className="story-history" aria-labelledby="story-history-title"
    onPointerDown={event => { pointerStartedOutside.current = outsidePanel(event) }}
    onClick={event => {
      if (pointerStartedOutside.current && outsidePanel(event)) {
        event.stopPropagation()
        onClose()
      }
      pointerStartedOutside.current = false
    }}
    onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); onClose() } }}
    onCancel={event => { event.preventDefault(); onClose() }}>
    <header><h2 id="story-history-title">历史对话</h2><button type="button" onClick={onClose} autoFocus>返回对话</button></header>
    <ol>{entries.map((entry, index) => <li key={index} className={entry.speaker === '我' ? 'story-history-self' : ''}>
      <strong>{entry.speaker}</strong><p>{entry.text || '（正在播放）'}</p>
    </li>)}</ol>
  </dialog>
}

export default function StoryDialogue({ story, canSkip, onFinish, onSkip, onExit, saving = false, saveError = '' }) {
  const ref = useRef(null)
  useModal(ref)
  const [state, setState] = useState(() => createStoryState(story))
  const [progress, setProgress] = useState({ nodeId: null, count: 0 })
  const [historyOpen, setHistoryOpen] = useState(false)
  const node = currentStoryNode(story, state)
  const text = state.history[state.history.length - 1].text
  const textKey = `${node.id}:${state.history.length}`
  const count = progress.nodeId === textKey ? progress.count : 0
  const revealed = count >= text.length

  useEffect(() => {
    if (historyOpen) return
    if (node.type === 'choice' || (node.type === 'quiz' && !state.feedback) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setProgress({ nodeId: textKey, count: text.length })
      return
    }
    if (revealed) return
    const timer = window.setInterval(() => setProgress(previous => ({
      nodeId: textKey,
      count: Math.min(text.length, (previous.nodeId === textKey ? previous.count : 0) + 1),
    })), 40)
    return () => window.clearInterval(timer)
  }, [textKey, node.type, text, historyOpen, revealed, state.feedback])

  const act = action => {
    if (!historyOpen && revealed) setState(previous => stepStory(story, previous, action))
  }
  const advance = () => {
    if (historyOpen) return
    if (!revealed) setProgress({ nodeId: textKey, count: text.length })
    else if (node.type === 'line') act({ type: 'next' })
  }
  const finish = () => {
    if (!revealed || historyOpen || saving) return
    const completed = stepStory(story, state, { type: 'finish' })
    if (completed.complete) onFinish(completed)
  }
  const entries = state.history.map((entry, index) => index === state.history.length - 1
    ? { ...entry, text: text.slice(0, count) } : entry)

  return <dialog ref={ref} className="story-dialog" aria-labelledby="story-title"
    onKeyDown={event => { if (event.key === 'Escape' && !historyOpen) event.preventDefault() }}
    onCancel={event => event.preventDefault()}>
    <div className="story-toolbar">
      <div><button type="button" onClick={() => setHistoryOpen(true)}>历史对话</button>
        <button type="button" onClick={onExit}>返回学习地图</button></div>
      <div className="story-skip"><button type="button" disabled={!canSkip} onClick={() => { if (canSkip) onSkip() }}>跳过引导</button>
        {!canSkip && <span>首次引导，请先听完</span>}</div>
    </div>
    {(node.type === 'choice' || node.type === 'quiz') && <div className={`story-floating-options${state.feedback ? ' has-feedback' : ''}`} role="group"
      aria-label={node.type === 'quiz' ? '知识小测选项' : '想问的问题'}>
      {node.options.filter(option => node.type !== 'choice' || !state.heard.includes(option.id)).map(option => <button type="button"
        className={`story-option-strip${state.feedback?.optionId === option.id ? state.feedback.correct ? ' is-correct' : ' is-incorrect' : ''}`}
        key={option.id} disabled={!revealed || historyOpen || Boolean(state.feedback)}
        onClick={() => act({ type: node.type === 'quiz' ? 'answer' : 'choose', optionId: option.id })}>
        <span className="story-option-dots" aria-hidden="true">▪ ▪ ▪</span>
        <span>{option.text}</span>
        {state.feedback?.optionId === option.id && <small className="story-option-verdict">{state.feedback.correct ? '✓ 回答正确' : '✕ 再想一想'}</small>}
        <span className="story-option-corners" aria-hidden="true"><i /><i /></span>
      </button>)}
    </div>}
    <section className="story-stage">
      <img className="story-portrait" src="/story-assets/ottly-portrait-transparent.png" alt="小海獭 Ottly" />
      <div className="story-frame-shadow" aria-hidden="true" />
      <div className="story-frame" onClick={event => { if (!event.target.closest('button, a')) advance() }}>
        <div className="story-corner-squares" aria-hidden="true"><i /><i /></div>
        <div className="story-nameplate">Ottly</div>
        <div className="story-heading"><span id="story-title">第 {story.levelNo || 1} 关 · {story.title}</span><span>{story.knowledge}</span></div>
        <div className="story-content">
          <p className="story-copy" aria-hidden="true">{text.slice(0, count)}</p>
          <p className="story-sr" aria-live="polite" aria-atomic="true">{text}</p>
          {saveError && <p role="alert" className="story-save-error">{saveError}</p>}
        </div>
        <footer className="story-footer">
          {node.type === 'choice' ? <><span>{state.heard.length ? '也可以再问一次，或继续挑战。' : '完整听完一个回答，就能继续。'}</span>
            <button type="button" disabled={!revealed || state.heard.length < story.requiredQuestions}
              onClick={() => act({ type: 'continue' })}>我明白了，继续</button></>
            : node.type === 'quiz' ? <><span>{state.feedback ? state.feedback.correct ? '答对啦！理解之后再继续。' : '再想一想，可以重新选择。' : '选择屏幕中间的一项。'}</span>
              {state.feedback && (revealed ? state.feedback.correct
                ? <button type="button" onClick={() => act({ type: 'quiz-next' })}>继续下一步</button>
                : <div className="story-feedback-actions"><button type="button" onClick={() => act({ type: 'review' })}>再听这段讲解</button>
                  <button type="button" onClick={() => act({ type: 'retry' })}>重新选择</button></div>
                : <button type="button" onClick={advance}>显示整句</button>)}</>
            : node.type === 'end' && revealed ? <><span>轮到你来试一试了。</span><button type="button" disabled={saving} onClick={finish}>{saving ? '正在保存引导…' : '开始本关挑战'}</button></>
              : <><span>{revealed ? '点击对话框或 NEXT 继续' : '点击对话框或 NEXT 显示整句'}</span><button type="button" onClick={advance} autoFocus>NEXT →</button></>}
        </footer>
        <div className="story-pixels" aria-hidden="true"><i /><i /><i /><i /></div>
      </div>
    </section>
    {historyOpen && <StoryHistory entries={entries} onClose={() => setHistoryOpen(false)} />}
  </dialog>
}
