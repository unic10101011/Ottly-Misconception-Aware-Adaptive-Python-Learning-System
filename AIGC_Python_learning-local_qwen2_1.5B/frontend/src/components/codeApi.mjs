export async function requestCode(action, payload, token, options = {}) {
  if (!token) {
    const error = new Error('登录已过期，请重新登录后提交。')
    error.status = 401
    throw error
  }
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), action === 'submit' ? 180000 : 30000)
  try {
    let response
    try {
      response = await fetch(`/api/v1/code/${action}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json', Authorization: `Bearer ${token}`,
          ...(action === 'submit' && options.reviewSourceId
            ? { 'X-Review-Source-Id': String(options.reviewSourceId) } : {}),
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('请求超时，请稍后重试。')
      throw new Error('无法连接到服务器，请检查网络和后端服务。')
    }
    if (response.status === 401) {
      const error = new Error('登录已过期，请重新登录后提交。')
      error.status = 401
      throw error
    }
    let result
    try {
      result = await response.json()
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('请求超时，请稍后重试。')
      throw new Error('服务响应异常，请稍后重试。')
    }
    if (!response.ok || result.code !== 200 || !result.data) {
      const detail = typeof result.detail === 'string' ? result.detail : result.msg
      throw new Error(detail || '请求未成功，请检查代码长度后重试。')
    }
    return result.data
  } finally {
    clearTimeout(timeout)
  }
}

async function requestLearningHistory(path, method, token, body, timeoutMs = 15000) {
  if (!token) {
    const error = new Error('登录已过期，请重新登录后查看。')
    error.status = 401
    throw error
  }
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    let response
    try {
      response = await fetch(`/api/v1${path}`, {
        method,
        headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
        ...(body ? { body: JSON.stringify(body) } : {}),
        signal: controller.signal,
      })
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('请求超时，请稍后重试。')
      throw new Error('无法连接到服务器，请检查网络和后端服务。')
    }
    if (response.status === 401) {
      const error = new Error('登录已过期，请重新登录后查看。')
      error.status = 401
      throw error
    }
    let result
    try {
      result = await response.json()
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('请求超时，请稍后重试。')
      throw new Error('服务响应异常，请稍后重试。')
    }
    if (!response.ok || result.code !== 200 || !result.data) {
      throw new Error(typeof result.detail === 'string' ? result.detail : result.msg || '请求未成功，请稍后重试。')
    }
    return result.data
  } finally {
    clearTimeout(timeout)
  }
}

export function getLearningHistory(failedOnly, limit, offset, token, problemId) {
  const query = new URLSearchParams({ failed_only: String(failedOnly), limit: String(limit), offset: String(offset) })
  if (problemId) query.set('problem_id', problemId)
  return requestLearningHistory(`/code/submissions?${query}`, 'GET', token)
}

export function getMistakeQuestions(token) {
  return requestLearningHistory('/code/mistakes', 'GET', token)
}

export function saveHintView(submissionId, level, token) {
  return requestLearningHistory(`/code/submissions/${submissionId}/hints`, 'PATCH', token, { level })
}

export function requestAnalysis(submissionId, token) {
  return requestLearningHistory(`/code/submissions/${submissionId}/analysis`, 'POST', token, undefined, 100000)
}

export function getLevels(token) {
  return requestLearningHistory('/code/levels', 'GET', token)
}

export function getLesson(problemId, token) {
  return requestLearningHistory(`/code/problems/${encodeURIComponent(problemId)}`, 'GET', token)
}

export function getSolution(problemId, token) {
  return requestLearningHistory(`/code/problems/${encodeURIComponent(problemId)}/solution`, 'GET', token)
}
