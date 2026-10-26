import React from 'react'

const labels = { input: '读取输入', add: '相加', concat: '拼接文字', print: '打印结果', replace: '替换旧值',
  assign: '保存到变量', loop: '进入本轮循环', change: '状态变化', call: '进入函数', return: '函数返回', exception: '执行遇到异常' }

export default function TraceAction({ action, step, code }) {
  const kind = action?.kind
  const text = action?.line ? code.split('\n')[action.line - 1]?.trim() : null
  const short = value => String(value).length > 100 ? String(value).slice(0, 100) + '…' : String(value)
  return <section className="trace-action-pane" aria-label="动作演示">
    <div className="trace-pane-title"><strong>动作演示</strong><small>{action?.round ? `第 ${action.round} 轮` : '真实执行数据'}</small></div>
    <div className={`trace-action-content is-${kind || 'start'}`} key={`${step?.step}-${kind}`}>
      <p className="trace-action-timing">{action ? kind === 'exception' ? `第 ${action.line} 行中断` : ['call', 'return'].includes(kind) ? '当前函数事件' : `刚执行完第 ${action.line} 行` : step?.step > 1 ? '该步骤没有可还原的动作' : '尚未执行第一行'}</p>
      {text && <code className="trace-action-source">{text}</code>}
      <h3>{labels[kind] || '准备开始'}</h3>
      {!action && <p className="trace-action-note">{step?.step > 1 ? '查看右侧真实状态，继续观察下一步。' : '点“下一步”，观察数据怎样变化。'}</p>}
      {kind === 'input' && <div className="trace-action-flow"><div className="trace-action-token"><small>输入</small><strong>{short(action.parts[0])}</strong></div><span className="trace-action-arrow">→</span><div className="trace-action-token is-result"><small>{action.target}</small><strong>{short(action.result)}</strong></div></div>}
      {['add', 'concat', 'print'].includes(kind) && <>
        <div className="trace-action-equation">{action.parts?.map((part, i) => <React.Fragment key={i}>{i > 0 && <span className="trace-action-operator">+</span>}<span className="trace-action-token">{short(part)}</span></React.Fragment>)}<span className="trace-action-arrow">→</span><strong className="trace-action-token is-result">{short(action.result)}</strong></div>
        <p className="trace-action-note">{kind === 'print' ? '↓ 送到输出' : `↓ 保存到 ${action.target}`}</p>
      </>}
      {['replace', 'assign'].includes(kind) && <div className="trace-action-flow"><div className="trace-action-token"><small>{action.target} · 原值</small><strong>{short(action.before)}</strong></div><span className="trace-action-arrow">→</span><div className="trace-action-token is-result"><small>{kind === 'replace' ? '替换为' : '新值'}</small><strong>{short(action.result)}</strong></div></div>}
      {kind === 'change' && <div className="trace-action-changes">{action.changes?.length ? action.changes.map(change => <div key={change.name}><strong>{change.name}</strong><span>{short(change.before)} → {short(change.after)}</span></div>) : <p className="trace-action-note">变量没有变化，继续观察下一步。</p>}</div>}
      {kind === 'loop' && <p className="trace-action-note">已进入循环体，查看本轮变量。</p>}
      {kind === 'call' && <p className="trace-action-note">进入 {step?.function}，右侧显示本次调用的参数与变量。</p>}
      {kind === 'return' && <div className="trace-action-token is-result"><small>{step?.function} 返回</small><strong>{short(action.result ?? 'None')}</strong></div>}
      {kind === 'exception' && <p className="trace-action-note">{step?.exception?.type || '异常'}：当前操作未成功完成，请查看错误位置。</p>}
      {action?.output && <pre className="trace-action-new-output" aria-label="本步新增输出">{action.output}</pre>}
    </div>
  </section>
}
