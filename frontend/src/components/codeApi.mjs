export async function requestCode(action, payload, token, options = {}) {
  if (!token) {
    const error = new Error('登录已过期，请重新登录后提交。')
    error.status = 401
    throw error
  }
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), ['submit', 'run'].includes(action) ? 180000 : 30000)
  try {
    let response
    try {
      const stream = action === 'run' && options.onExecution
      response = await fetch(`/api/v1/code/${action}${stream ? '?stream_analysis=true' : ''}`, {
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
      if (response.ok && response.headers.get('content-type')?.includes('application/x-ndjson')) {
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (true) {
          const { value, done } = await reader.read()
          buffer += decoder.decode(value, { stream: !done })
          const lines = buffer.split('\n')
          buffer = lines.pop()
          for (const line of lines) {
            if (!line.trim()) continue
            result = JSON.parse(line)
            if (result.code !== 200 || !result.data) throw new Error('Invalid run result')
            if (result.data.analysis?.status === 'preparing') options.onExecution?.(result.data)
          }
          if (done) break
        }
        if (!result || buffer.trim()) throw new Error('Incomplete run result')
        if (result.data.analysis?.status === 'preparing') throw new Error('Incomplete analysis')
        return result.data
      }
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

export function getMisconceptions(token) {
  return requestLearningHistory('/code/misconceptions', 'GET', token)
}

export function saveHintView(submissionId, level, token) {
  return requestLearningHistory(`/code/submissions/${submissionId}/hints`, 'PATCH', token, { level })
}

export function requestAnalysis(submissionId, token) {
  return requestLearningHistory(`/code/submissions/${submissionId}/analysis`, 'POST', token, undefined, 100000)
}

export function requestRunAnalysis(analysisId, token) {
  return requestLearningHistory(`/code/run-analysis/${encodeURIComponent(analysisId)}`, 'POST', token, undefined, 100000)
}


export function requestPracticeRecommendation(submissionId, token) {
  return requestLearningHistory(`/code/submissions/${submissionId}/practice-recommendation`, 'POST', token, undefined, 35000)
}

export function getLevels(token) {
  return requestLearningHistory('/code/levels', 'GET', token)
}

export function getPractice(token) {
  return requestLearningHistory('/code/practice', 'GET', token)
}

export async function startEndlessChallenge(mode, token, { signal, onProgress } = {}) {
  if (!token) {
    const error = new Error('登录已过期，请重新登录。')
    error.status = 401
    throw error
  }
  const controller = new AbortController()
  const cancel = () => controller.abort()
  signal?.addEventListener('abort', cancel, { once: true })
  if (signal?.aborted) controller.abort()
  const timeout = setTimeout(cancel, 190000)
  try {
    const response = await fetch('/api/v1/code/endless', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ mode }), signal: controller.signal,
    })
    if (!response.ok) {
      const body = await response.json()
      const error = new Error(typeof body.detail === 'string' ? body.detail : '题目准备失败，请重试。')
      error.status = response.status
      throw error
    }
    let result
    const accept = body => {
      if (body.code !== 200 || !body.data) throw new Error('出题服务响应异常，请重试。')
      result = body.data
      if (result.stage === 'error') throw new Error(result.message || '题目验证失败，请重试。')
      onProgress?.(result)
    }
    if (response.headers.get('content-type')?.includes('application/x-ndjson')) {
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      try {
        while (true) {
          const { value, done } = await reader.read()
          buffer += decoder.decode(value, { stream: !done })
          const lines = buffer.split('\n')
          buffer = lines.pop()
          for (const line of lines) if (line.trim()) accept(JSON.parse(line))
          if (done) break
        }
        if (buffer.trim()) accept(JSON.parse(buffer))
      } finally {
        await reader.cancel().catch(() => {})
        reader.releaseLock()
      }
    } else {
      accept(await response.json())
    }
    if (result?.stage !== 'ready' || typeof result.problem_id !== 'string' || !result.problem_id) {
      throw new Error('题目准备尚未完成，请重试。')
    }
    return result
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('出题等待已结束，请重试或从题库中抽题。')
    if (error instanceof SyntaxError) throw new Error('出题服务响应异常，请重试。')
    if (error instanceof TypeError) throw new Error('无法连接出题服务，请检查网络后重试。')
    throw error
  } finally {
    clearTimeout(timeout)
    signal?.removeEventListener('abort', cancel)
  }
}

export function getLesson(problemId, token) {
  return requestLearningHistory(`/code/problems/${encodeURIComponent(problemId)}`, 'GET', token)
}

export function getSolution(problemId, token) {
  return requestLearningHistory(`/code/problems/${encodeURIComponent(problemId)}/solution`, 'GET', token)
}

export function getKnowledge(token) {
  return requestLearningHistory('/code/knowledge', 'GET', token)
}

export function getGuide(problemId, token) {
  return requestLearningHistory(`/code/guides/${encodeURIComponent(problemId)}`, 'GET', token)
}

export function askGuideQuestion(problemId, question, history, token) {
  return requestLearningHistory(`/code/guides/${encodeURIComponent(problemId)}/question`, 'POST', token, { question, history }, 65000)
}

export function completeGuide(problemId, version, heard, answers, token) {
  return requestLearningHistory(`/code/guides/${encodeURIComponent(problemId)}/complete`, 'POST', token, { version, heard, answers })
}

export function requestExecutionTrace(body, token) {
  return requestLearningHistory('/code/execution-trace', 'POST', token, body)
}

export function requestTraceExplanation(traceId, stepIndex, token) {
  return requestLearningHistory(`/code/execution-trace/${encodeURIComponent(traceId)}/explanation`, 'POST', token, { step_index: stepIndex }, 35000)
}
