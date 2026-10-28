import React from 'react'

export default function TraceVisuals({ trace, step, previous }) {
  if (!['shell-total-v1', 'temperature-max-v1'].includes(trace.problem_id) || !step?.visual_values) return null
  const values = step.visual_values
  const oldValues = previous?.visual_values || {}
  const lists = Object.entries(values).filter(([, value]) => value.kind === 'list')
  const numbers = Object.entries(values).filter(([, value]) => value.kind === 'number')
  const cause = previous?.event === 'line' ? trace.code.split('\n')[previous.line - 1]?.trim() : null
  return <div className="trace-visuals" aria-label="变量变化图">
    {cause && <p className="trace-visual-cause">执行后：<code>{cause}</code></p>}
    {lists.map(([name, value]) => {
      const before = oldValues[name]?.items || []
      const access = step.list_accesses?.find(item => item.name === name)
      return <section className="trace-list-view" key={name} aria-label={`${name} 列表格子`}>
        <div className="trace-list-caption"><strong>{name}</strong><span>{value.items.length} 个元素</span></div>
        {access && <p className="trace-list-access">即将{access.mode === 'write' ? '写入' : '读取'}下标 {access.index}</p>}
        {value.items.length ? <ol className="trace-list-cells">{value.items.map((item, i) => <li key={i}
          className={`${i >= before.length ? 'is-new' : before[i] !== item ? 'is-updated' : ''}${access?.index === i ? ' is-accessed' : ''}`}>
          <span className="trace-cell-index">[{i}]</span><strong>{item}</strong>
          <small>{i >= before.length ? '新增' : before[i] !== item ? `原来 ${before[i]}` : ' '}</small>
        </li>)}</ol> : <p className="trace-list-empty">[ ] 空列表</p>}
        {before.length > value.items.length && <p className="trace-list-access">比上一步减少 {before.length - value.items.length} 个元素</p>}
      </section>
    })}
    <div className={`trace-value-boxes${trace.problem_id === 'temperature-max-v1' ? ' is-compact' : ''}`}>
      {numbers.map(([name, value]) => {
        const old = oldValues[name]
        const changed = old?.text !== value.text
        return <div key={name} className={`trace-value-box${changed ? ' is-changed' : ''}`} aria-label={`${name}：${old?.text ?? '未定义'} → ${value.text}`}>
          <span className="trace-value-name">{name}</span><div className="trace-value-transition">
            {changed && old && <><span className="trace-value-before">{old.text}</span><span aria-hidden="true">→</span></>}
            <strong>{value.text}</strong></div><small>{!old ? '新建变量' : changed ? '值已更新' : '保持不变'}</small>
        </div>
      })}
    </div>
    {!lists.length && !numbers.length && <p className="trace-list-empty">开始执行后，这里会出现变量。</p>}
  </div>
}
