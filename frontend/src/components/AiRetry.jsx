import React from 'react'

export default function AiRetry({ status, message = '', pending = false, onRetry, label = '重新生成', pendingLabel = '正在重新生成…' }) {
  const configuration = /密钥|Key|额度|余额|配置|401|402/i.test(message)
  const text = configuration ? 'AI 服务暂不可用，请检查模型配置'
    : status === 'timeout' || /超时|timeout/i.test(message) ? '生成超时'
    : status === 'invalid_response' || /内容检查|格式|校验/.test(message) ? '本次回答未能生成'
    : /网络|连接|fetch|network/i.test(message) ? '连接失败'
    : /繁忙|限流|429/.test(message) ? '服务繁忙，请稍后重试' : '本次回答暂不可用'
  return <span className="ai-retry" role={pending ? 'status' : 'alert'}>
    <span>{pending ? pendingLabel : text}</span>
    {onRetry && <button type="button" className="ai-retry-button" onClick={onRetry} disabled={pending}
      aria-label={label} aria-busy={pending} title={pending ? pendingLabel : `${text}，点击重试`}>
      <svg className={pending ? 'is-spinning' : ''} aria-hidden="true" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M20 7v5h-5M4 17v-5h5" /><path d="M6.1 7a7 7 0 0 1 11.8-1L20 9M4 15l2.1 3A7 7 0 0 0 17.9 17" />
      </svg><span>{pending ? '正在重试' : '点击重试'}</span>
    </button>}
    {!pending && message && <small className="ai-retry-detail">{message}</small>}
  </span>
}
