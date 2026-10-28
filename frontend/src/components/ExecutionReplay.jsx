import React, { useEffect, useRef, useState } from 'react'
import { requestExecutionTrace } from './codeApi.mjs'
import { executionReplayLessons } from './executionReplayConfig.mjs'
import TraceVisuals from './TraceVisuals.jsx'
import TraceStepInsight from './TraceStepInsight.jsx'
import TraceAction from './TraceAction.jsx'

const statusText = {
  completed: '回放就绪', runtime_error: '运行时出错，已停在异常处', syntax_error: '语法错误，无法执行回放',
  truncated: '执行被限制，轨迹不完整', timeout: '执行超时，轨迹不完整',
  unsupported: '这段代码超出首版回放范围', unavailable: '回放执行器暂不可用',
}
const reasonText = { step_limit: '达到300步上限', output_limit: '输出达到上限', range_limit: '循环范围过大',
  integer_limit: '整数过大', text_limit: '字符串超过2000字符上限', variable_limit: '变量过多', trace_size_limit: '轨迹数据达到上限',
  list_limit: '列表超过100项上限', call_depth_limit: '函数调用超过16层上限',
  wall_time_limit: '达到时间上限', worker_limit: '执行进程被限制或停止' }
const lessonNumbers = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二']

export function TracePlayer({ trace, showContext = true }) {
  const [index, setIndex] = useState(0)
  const activeLine = useRef(null)
  useEffect(() => { activeLine.current?.scrollIntoView({ block: 'nearest' }) }, [index])
  const steps = trace.steps || []
  const step = steps[index]
  const previous = steps.slice(0, index).reverse().find(item => item.scope_id === step?.scope_id)
  const previousInTime = steps[index - 1]
  const variables = step?.variables || {}
  const line = step?.line ?? (step?.event === 'end' ? step.action?.line : trace.trace_status === 'syntax_error' ? trace.exception?.line : null)
  const position = step?.event === 'line' ? `即将执行第 ${line} 行`
    : step?.event === 'end' ? '程序已结束 · 以下为执行结束后的状态'
      : step?.event === 'call' ? `进入函数 ${step.function}`
        : step?.event === 'return' ? `函数 ${step.function} 返回 ${step.return_value ?? 'None'}`
      : step?.event === 'exception' ? `第 ${line} 行发生异常` : '没有可播放的执行步骤'
  const sourceTitle = trace.code_source === 'submission' ? `提交代码 #${trace.submission_id}`
    : trace.code_source === 'demo' ? '示例代码' : '当前代码'
  return <div className="trace-player">
    <div className="trace-summary"><span className="trace-status">{statusText[trace.trace_status] || '回放状态未知'}</span><strong>当前步骤 {steps.length ? index + 1 : 0} / {steps.length}</strong>
      <div className="trace-step-label" aria-live="polite">{position}</div></div>
    {showContext && <div className="trace-context"><span>{sourceTitle}</span><span>{trace.test_case_label}</span></div>}
    {trace.truncated && <p className="trace-warning" role="status">{reasonText[trace.truncation_reason] || '已达到执行限制'}。这里只展示停止前采集到的步骤，不能视为完整执行结果。</p>}
    {trace.exception && <p className="trace-warning" role="status">{trace.exception.type}{trace.exception.line ? ` · 第 ${trace.exception.line} 行` : ''}：{trace.exception.message}</p>}
    {step?.call_stack?.length > 1 && <div className="trace-call-stack" aria-label="调用栈">{step.call_stack.map(item =>
      item.function === '<module>' ? '主程序' : `${item.function} (${item.scope_id})`).join(' → ')}</div>}
    <div className="trace-grid">
      <section className="trace-code-pane" aria-label="回放代码，只读">
        <div className="trace-pane-title"><strong>{sourceTitle}</strong></div>
        <ol className="trace-code">{trace.code.split('\n').map((text, offset) => <li key={offset} ref={offset + 1 === line ? activeLine : null}
          className={`${offset + 1 === line ? 'is-current' : ''}${trace.exception?.line === offset + 1 ? ' has-error' : ''}`}
          aria-current={offset + 1 === line ? 'step' : undefined}>
          <span aria-hidden="true">{offset + 1}</span><code>{text || ' '}</code>
        </li>)}</ol>
      </section>
      <TraceAction action={step?.action} step={step} code={trace.code} />
      <div className="trace-data-pane">
        <section className="trace-variables" aria-label="当前变量">
          <div className="trace-pane-title"><strong>变量</strong></div>
          {trace.problem_id === 'temperature-max-v1' && step?.visual_values
            ? <TraceVisuals trace={trace} step={step} previous={previous} /> : Object.keys(variables).length ? <dl>{Object.entries(variables).map(([name, value]) => {
            const old = previous?.variables?.[name]
            const changed = old !== value
            return <div key={name} className={changed ? 'is-changed' : ''}><dt>{name}</dt><dd>
              {changed && <><span className="trace-variable-old">{old ?? '未定义'}</span><span aria-hidden="true"> → </span></>}
              <strong>{value}</strong>
            </dd></div>
          })}</dl> : <p className="trace-empty">这一刻还没有可展示的变量。</p>}
        </section>
        <section className="trace-output" aria-label="真实输出">
          <div className="trace-pane-title"><strong>累积输出</strong><small>{step?.stdout && step.stdout !== previousInTime?.stdout ? '本步有新输出' : '暂无新输出'}</small></div>
          <pre aria-label="当前步骤输出">{step?.stdout || '（当前尚无输出）'}</pre>
        </section>
      </div>
    </div>
    <TraceStepInsight key={trace.trace_id || trace.playbackId || 'preview'} trace={trace} index={index} />
    <div className="trace-controls">
      <button type="button" disabled={index === 0 || !steps.length} onClick={() => setIndex(value => Math.max(0, value - 1))}>上一步</button>
      <button type="button" disabled={!steps.length || index >= steps.length - 1}
        onClick={() => setIndex(value => Math.min(steps.length - 1, value + 1))}>下一步</button>
      <button type="button" disabled={!steps.length} onClick={() => setIndex(0)}>重新开始</button>
      <label>步骤 <strong>{steps.length ? index + 1 : 0} / {steps.length}</strong>
        <input aria-label="回放步骤" type="range" min="0" max={Math.max(0, steps.length - 1)} value={index}
          disabled={!steps.length} onChange={event => setIndex(Number(event.target.value))} /></label>
    </div>
  </div>
}

export default function ExecutionReplay({ code, problemId, submissionId, initialInput, onClose }) {
  const settings = executionReplayLessons[problemId]
  const lessonNumber = Number(settings.title.match(/\d+/)[0])
  const dialog = useRef(null)
  const generation = useRef(0)
  const [draft] = useState(code)
  const [source, setSource] = useState('draft')
  const [input, setInput] = useState(() => settings.inputKind === 'none' ? ''
    : settings.inputKind === 'integer' ? (initialInput?.trim() || settings.defaultInput)
      : (initialInput ?? settings.defaultInput))
  const [trace, setTrace] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    const id = ++generation.current
    setLoading(true)
    setError('')
    setTrace(null)
    try {
      const result = await requestExecutionTrace({ problem_id: problemId, stdin: settings.inputKind === 'integer' ? input + '\n' : input,
        ...(source === 'submission' ? { submission_id: submissionId } : { code: draft }) }, localStorage.getItem('access_token'))
      if (id === generation.current) setTrace({ ...result, replayInput: result.stdin ?? input, playbackId: id })
    } catch (error) {
      if (id === generation.current) setError(error.message)
    } finally {
      if (id === generation.current) setLoading(false)
    }
  }
  useEffect(() => {
    const element = dialog.current
    const focused = document.activeElement
    const overflow = document.body.style.overflow
    element.showModal()
    document.body.style.overflow = 'hidden'
    load()
    return () => {
      generation.current++
      element.close()
      document.body.style.overflow = overflow
      if (focused?.isConnected) focused.focus()
    }
  }, [])

  return <dialog ref={dialog} className="execution-replay" aria-labelledby="execution-replay-title"
    onCancel={event => { event.preventDefault(); onClose() }} onKeyDown={event => {
      if (event.key === 'Escape') { event.preventDefault(); onClose() }
    }}>
    <header className="trace-header"><h2 id="execution-replay-title">{`第${lessonNumbers[lessonNumber - 1]}关·代码执行回放`}</h2>
      <button type="button" onClick={onClose} autoFocus>返回做题</button></header>
    {trace && settings.inputKind === 'none' && !submissionId && <p className="trace-input-overview">本题无需输入</p>}
    {(settings.inputKind !== 'none' || submissionId) && <details className="trace-options">
      <summary>{trace && <span className="trace-input-overview">{settings.inputKind === 'none' ? '本题无需输入'
        : `本次输入：${trace.replayInput.trimEnd().replace(/\r?\n/g, ' · ') || '（空）'}`}</span>}
        <span className="trace-input-toggle">{settings.inputKind === 'none' ? '调整代码版本' : '调整输入'} <span aria-hidden="true">→</span></span></summary>
    <form className="trace-request" onSubmit={event => { event.preventDefault(); if (!loading) load() }}>
      <div className="trace-settings-bar">
        {submissionId ? <label className="trace-source-label">回放代码<select value={source} disabled={loading} onChange={event => setSource(event.target.value)}>
          <option value="draft">当前代码</option><option value="submission">提交代码 #{submissionId}</option>
        </select></label> : null}
        <details className="trace-help"><summary>回放说明</summary><div>
          <p>默认使用打开窗口时的当前代码，可在有提交记录时切换版本；回放不会修改原代码。高亮行即将执行，右侧显示此前步骤的变量和输出。</p>
          {settings.inputHelp && <p id="trace-input-help">{settings.inputHelp}</p>}
          <p>这里只运行填写的输入，不代表全部判题测试；回放不会改变通关成绩。</p>
          <p>{settings.inputKind === 'integer' ? '第8关支持整数和基本循环。' : ['temperature-max-v1', 'count-at-least-v1'].includes(problemId)
            ? '支持基本列表和普通函数，列表最多100项、调用最多16层。' : '支持基本字符串、数值运算与输入输出。'}</p>
        </div></details>
      </div>
      <div className="trace-input-row">
      {settings.inputKind === 'integer' && <label className="trace-number-label">运行输入 n<input type="number" min="0" max="100" step="1" required value={input}
        disabled={loading} onChange={event => setInput(event.target.value)} /></label>}
      {settings.inputKind === 'text' && <label className={`trace-input-label${problemId === 'greeting-v1' ? ' is-single-line' : ''}`}>运行输入<textarea rows={problemId === 'greeting-v1' ? 1 : 3} maxLength={2000} value={input}
        disabled={loading} onChange={event => setInput(event.target.value)} aria-describedby="trace-input-help" /></label>}
      {settings.inputKind === 'none' && <span className="trace-no-input">本题无需输入</span>}
      <div className="trace-generate"><button type="submit" disabled={loading}>{loading ? '准备中…' : '应用并重新运行'}</button></div>
      </div>
    </form></details>}
    {loading && <p className="trace-empty" role="status">正在准备回放，请稍候…</p>}
    {error && <div className="trace-warning" role="alert"><p>{error}</p><button type="button" disabled={loading} onClick={load}>重试</button></div>}
    {trace && <TracePlayer key={trace.playbackId} trace={trace} showContext={false} />}
  </dialog>
}
