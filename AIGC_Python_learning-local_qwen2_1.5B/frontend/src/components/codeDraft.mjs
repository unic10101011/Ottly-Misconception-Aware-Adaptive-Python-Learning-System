function draftKey(userId, problemId) {
  if (!Number.isSafeInteger(userId) || userId <= 0 || !problemId) return null
  return `ottly:code-draft:v1:${userId}:${encodeURIComponent(problemId)}`
}

export function readCodeDraft(userId, problemId) {
  const key = draftKey(userId, problemId)
  if (!key) return null
  try {
    const draft = JSON.parse(localStorage.getItem(key))
    if (typeof draft?.code !== 'string' || draft.code.length > 6000 ||
        typeof draft.stdin !== 'string' || draft.stdin.length > 8000) return null
    return draft
  } catch {
    return null
  }
}

export function saveCodeDraft(userId, problemId, code, stdin) {
  const key = draftKey(userId, problemId)
  if (!key) return false
  try {
    localStorage.setItem(key, JSON.stringify({ code, stdin }))
    return true
  } catch {
    return false
  }
}
