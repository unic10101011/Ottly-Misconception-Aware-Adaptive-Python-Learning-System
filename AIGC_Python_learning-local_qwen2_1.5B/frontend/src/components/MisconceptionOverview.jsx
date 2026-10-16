import React from 'react'

function MisconceptionOverview({ items = [], loading = false, error = '' }) {
  return <section className="misconception-overview" aria-labelledby="misconception-title">
    <h2 id="misconception-title">疑似误区概览</h2>
    <p className="misconception-note">根据提交记录推测，仅供复习参考；做对后的记录也会保留。</p>
    {loading && <p role="status">正在整理学习记录...</p>}
    {error && <p className="mistake-alert" role="alert">疑似误区暂时无法加载：{error}</p>}
    {!loading && !error && items.length === 0 &&
      <p className="misconception-empty">完成一些题目后，这里会根据你的错误记录整理容易混淆的知识点。</p>}
    {!loading && !error && items.length > 0 && <div className="misconception-list">
      {items.map(item => <article className="misconception-item" key={item.misconception_tag}>
        <h3>{item.label}</h3>
        <dl>
          <div><dt>出现次数</dt><dd>{item.occurrence_count} 次</dd></div>
          <div><dt>涉及题目</dt><dd>{item.problem_count} 道</dd></div>
          <div><dt>最近出现</dt><dd>{new Date(item.latest_at).toLocaleString('zh-CN')}</dd></div>
          <div><dt>后来做对</dt><dd>{item.later_passed_count} 道</dd></div>
        </dl>
      </article>)}
    </div>}
  </section>
}

export default MisconceptionOverview
