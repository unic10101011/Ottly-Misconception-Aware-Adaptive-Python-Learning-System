import React from 'react'

function renderInline(text) {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`')) return <code key={index}>{part.slice(1, -1)}</code>
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>
    return part
  })
}

function ChatContent({ content }) {
  const value = String(content || '')
  const blocks = []
  const fence = /```([^\n`]*)\n([\s\S]*?)```/g
  let last = 0
  let match
  while ((match = fence.exec(value)) !== null) {
    if (match.index > last) blocks.push({ text: value.slice(last, match.index) })
    blocks.push({ language: match[1].trim(), code: match[2] })
    last = fence.lastIndex
  }
  if (last < value.length) blocks.push({ text: value.slice(last) })
  return <div className="chat-message-content">{blocks.map((block, index) => (
    block.code === undefined
      ? <span key={index}>{renderInline(block.text)}</span>
      : <div className="chat-code-block" key={index}>
          {block.language && <small>{block.language}</small>}
          <pre><code>{block.code}</code></pre>
        </div>
  ))}</div>
}

export default ChatContent
