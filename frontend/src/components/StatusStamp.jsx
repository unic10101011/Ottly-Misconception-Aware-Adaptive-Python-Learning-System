import React from 'react'

export default function StatusStamp({ passed }) {
  const state = passed === true ? 'passed' : passed === false ? 'failed' : 'pending'
  const label = { passed: '已通过', failed: '未通过', pending: '待尝试' }[state]
  return <svg className={`status-stamp is-${state}`} viewBox="0 0 100 100"
    role="img" aria-label={`最近一次提交：${label}`}>
    <title>{`最近一次提交：${label}`}</title>
    <circle cx="50" cy="50" r="43" fill="currentColor" opacity=".06" />
    <circle cx="50" cy="50" r="43" fill="none" stroke="currentColor" strokeWidth="4" />
    <path d={state === 'pending' ? 'M34 55h32' : 'M30 55l14 14 28-31'}
      fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
}
