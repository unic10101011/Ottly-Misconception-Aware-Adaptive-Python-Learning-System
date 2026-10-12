export async function requestCode(action, payload, token) {
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
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
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
