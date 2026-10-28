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
    if (problemId === 'level1') {
      draft.code = draft.code.replace(/^# 请让 Ottly 说出她的第一句话(?=\r?\n|$)/, '#向编程世界说出你的第一句话吧！')
    }
    if (problemId === 'count-at-least-v1') {
      draft.code = draft.code.replace(
        /(^def count_at_least\(scores, threshold\):\r?\n    # begin\r?\n)    pass(\r?\n    # end)/,
        '$1    $2',
      )
    }
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

export function clearUserCodeDrafts(userId) {
  if (!Number.isSafeInteger(userId) || userId <= 0) return
  const prefix = `ottly:code-draft:v1:${userId}:`
  try {
    for (let index = localStorage.length - 1; index >= 0; index--) {
      const key = localStorage.key(index)
      if (key?.startsWith(prefix)) localStorage.removeItem(key)
    }
  } catch {
    // A blocked browser store must not prevent logout after server deletion.
  }
}
