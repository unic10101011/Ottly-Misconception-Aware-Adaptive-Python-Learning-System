export function questionKnowledgeIds(question) {
  const ids = [...new Set((question.knowledge_ids || []).filter(id => typeof id === 'string' && id))]
  return ids.length ? ids : ['unclassified']
}

export function knowledgeName(id, names = {}) {
  return id === 'unclassified' ? '知识点待补充' : names[id] || id
}

export function groupMistakes(questions, names = {}) {
  const groups = new Map()
  for (const question of questions) {
    for (const id of questionKnowledgeIds(question)) {
      if (!groups.has(id)) groups.set(id, { id, name: knowledgeName(id, names), questions: [] })
      groups.get(id).questions.push(question)
    }
  }
  return [...groups.values()].sort((a, b) => a.id.localeCompare(b.id, 'en', { numeric: true }))
}

export function mistakeDetailUrl(problemId, knowledgeId) {
  return `/app/history/${encodeURIComponent(problemId)}?knowledge=${encodeURIComponent(knowledgeId)}`
}

export function mistakeOverviewUrl(knowledgeId) {
  return knowledgeId ? `/app/history?knowledge=${encodeURIComponent(knowledgeId)}#knowledge-${encodeURIComponent(knowledgeId)}` : '/app/history'
}
