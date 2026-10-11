import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import xingxing from './images/xingxing.png'
import yunduo from './images/yunduo.png'
import loginhaita from './images/loginhaita.png'

function Auth() {
  const [activeTab, setActiveTab] = useState('login')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState('info')
  const navigate = useNavigate()

  const API_BASE_URL = '/api/v1'

  const showMessage = (msg, type = 'info') => {
    setMessage(msg)
    setMessageType(type)
    setTimeout(() => {
      setMessage('')
    }, 3000)
  }

  const validateForm = (form) => {
    let isValid = true
    const inputs = form.querySelectorAll('input[required]')
    
    inputs.forEach(input => {
      if (!input.value.trim()) {
        input.classList.add('is-invalid')
        isValid = false
      } else if (input.hasAttribute('minlength') && input.value.length < parseInt(input.getAttribute('minlength'))) {
        input.classList.add('is-invalid')
        isValid = false
      } else if (input.hasAttribute('maxlength') && input.value.length > parseInt(input.getAttribute('maxlength'))) {
        input.classList.add('is-invalid')
        isValid = false
      } else {
        input.classList.remove('is-invalid')
        input.classList.add('is-valid')
      }
    })
    
    return isValid
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    
    if (!validateForm(e.target)) {
      return
    }
    
    setLoading(true)
    
    const formData = new FormData(e.target)
    const data = {
      username: formData.get('username'),
      password: formData.get('password')
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      })
      
      const result = await response.json()
      
      if (result.code === 200) {
        localStorage.setItem('access_token', result.data.access_token)
        localStorage.setItem('refresh_token', result.data.refresh_token)
        showMessage('登录成功', 'success')
        setTimeout(() => {
          navigate('/app/levels')
        }, 1000)
      } else if (result.code === 401) {
        showMessage(result.msg || '用户名或密码错误', 'danger')
      } else if (result.code === 403) {
        showMessage(result.msg || '账户已被禁用', 'danger')
      } else if (result.code >= 500) {
        showMessage('服务器错误，请稍后重试', 'danger')
      } else {
        showMessage(result.msg || '登录失败', 'danger')
      }
    } catch (error) {
      showMessage('网络错误，请稍后重试', 'danger')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    
    if (!validateForm(e.target)) {
      return
    }
    
    setLoading(true)
    
    const formData = new FormData(e.target)
    const data = {
      username: formData.get('username'),
      password: formData.get('password'),
      phone: formData.get('phone')
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      })
      
      const result = await response.json()
      
      if (result.code === 200) {
        showMessage('注册成功，请登录', 'success')
        setActiveTab('login')
      } else if (result.code === 400) {
        showMessage(result.msg || '注册失败', 'danger')
      } else if (result.code >= 500) {
        showMessage('服务器错误，请稍后重试', 'danger')
      } else {
        showMessage(result.msg || '注册失败', 'danger')
      }
    } catch (error) {
      showMessage('网络错误，请稍后重试', 'danger')
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (e) => {
    e.preventDefault()
    
    if (!validateForm(e.target)) {
      return
    }
    
    setLoading(true)
    
    const formData = new FormData(e.target)
    const data = {
      phone: formData.get('phone'),
      new_password: formData.get('new_password')
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/auth/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      })
      
      const result = await response.json()
      
      if (result.code === 200) {
        showMessage('密码重置成功，请登录', 'success')
        setActiveTab('login')
      } else if (result.code === 404) {
        showMessage(result.msg || '手机号未注册', 'danger')
      } else if (result.code >= 500) {
        showMessage('服务器错误，请稍后重试', 'danger')
      } else {
        showMessage(result.msg || '密码重置失败', 'danger')
      }
    } catch (error) {
      showMessage('网络错误，请稍后重试', 'danger')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      backgroundColor: '#D6F5FF',
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
    }}>
    <div style={{
      position: 'absolute',
      width: '100%',
      height: '100%',
      top: 0,
      left: 0,
      pointerEvents: 'none',
      zIndex: 0,
    }}></div>
      {/* 底部海浪 */}
      <div style={{
        position:'absolute',
        left: 0,
        bottom: 0,
        width: '100%',
        height: '140px',
        background: 'url(\'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 120"><path fill="%23B3E5FF" d="M0,64L80,69.3C160,75,320,85,480,80C640,75,800,53,960,48C1120,43,1280,53,1360,58.7L1440,64L1440,120L1360,120C1280,120,1120,120,960,120C800,120,640,120,480,120C320,120,160,120,80,120L0,120Z"></path></svg>\')',
        backgroundSize: 'cover',
        backgroundRepeat: 'no-repeat',
        zIndex: 1,
        pointerEvents: 'none',
      }} />

      <img src={xingxing} alt="星星" style={{
    position: 'absolute',
    top: '3%',
    left: '3%',
    width: '8vw',
    maxWidth: '120px',
    minWidth: '60px',
    opacity: 0.85
  }} />
  <img src={yunduo} alt="云朵" style={{
    position: 'absolute',
    top: '2%',
    right: '3%',
    width: '10vw',
    maxWidth: '140px',
    minWidth: '70px',
    opacity: 0.85
  }} />

      {/* 加载遮罩 */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(255,255,255,0.8)',
        display: loading ? 'flex' : 'none',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">加载中...</span>
        </div>
      </div>

      {/* 登录卡片主体 */}
      <div className="auth-container" style={{
        backgroundColor: 'white',
        borderRadius: '10px',
        boxShadow: '0 0 20px rgba(0,0,0,0.1)',
        padding: '30px',
        width: '100%',
        maxWidth: '450px',
        position: 'relative',
        zIndex: 2,
      }}>
        <h2 className="text-center mb-5">用户认证系统</h2>

        {/* 标签 */}
        <ul className="nav nav-tabs mb-4">
          <li className="nav-item">
            <button className={`nav-link ${activeTab === 'login' ? 'active' : ''}`} onClick={() => setActiveTab('login')}>
              登录
            </button>
          </li>
          <li className="nav-item">
            <button className={`nav-link ${activeTab === 'register' ? 'active' : ''}`} onClick={() => setActiveTab('register')}>
              注册
            </button>
          </li>
          <li className="nav-item">
            <button className={`nav-link ${activeTab === 'reset' ? 'active' : ''}`} onClick={() => setActiveTab('reset')}>
              重置密码
            </button>
          </li>
        </ul>

        {/* 消息提示 */}
        {message && (
          <div className={`alert alert-${messageType} alert-dismissible fade show mb-3`}>
            {message}
            <button type="button" className="btn-close" onClick={() => setMessage('')} aria-label="Close"></button>
          </div>
        )}

        {/* 登录 */}
        {activeTab === 'login' && (
          <form onSubmit={handleLogin}>
            <div className="mb-3">
              <label className="form-label">用户名</label>
              <input type="text" className="form-control" name="username" required />
              <div className="invalid-feedback">请输入用户名</div>
            </div>
            <div className="mb-3">
              <label className="form-label">密码</label>
              <input type="password" className="form-control" name="password" required />
              <div className="invalid-feedback">请输入密码</div>
            </div>
            <button type="submit" className="btn btn-primary w-100">登录</button>
          </form>
        )}

        {/* 注册 */}
        {activeTab === 'register' && (
          <form onSubmit={handleRegister}>
            <div className="mb-3">
              <label className="form-label">用户名</label>
              <input type="text" className="form-control" name="username" minLength={3} maxLength={50} required />
              <div className="invalid-feedback">用户名长度3-50字符</div>
            </div>
            <div className="mb-3">
              <label className="form-label">密码</label>
              <input type="password" className="form-control" name="password" minLength={6} required />
              <div className="invalid-feedback">密码至少6位</div>
            </div>
            <div className="mb-3">
              <label className="form-label">手机号</label>
              <input type="tel" className="form-control" name="phone" minLength={10} maxLength={20} required />
              <div className="invalid-feedback">请输入有效手机号</div>
            </div>
            <button type="submit" className="btn btn-primary w-100">注册</button>
          </form>
        )}

        {/* 重置密码 */}
        {activeTab === 'reset' && (
          <form onSubmit={handleResetPassword}>
            <div className="mb-3">
              <label className="form-label">手机号</label>
              <input type="tel" className="form-control" name="phone" minLength={10} maxLength={20} required />
              <div className="invalid-feedback">请输入有效手机号</div>
            </div>
            <div className="mb-3">
              <label className="form-label">新密码</label>
              <input type="password" className="form-control" name="new_password" minLength={6} required />
              <div className="invalid-feedback">密码至少6位</div>
            </div>
            <button type="submit" className="btn btn-primary w-100">重置密码</button>
          </form>
        )}

        <img src={loginhaita} alt="海獭" style={{
           position: 'absolute',
           left: '-25vw',
           bottom: '-20px',
           width: '20vw',
           maxWidth: '200px',
           minWidth: '100px',
           opacity: 1,
           zIndex: 1,
           pointerEvents: 'none',
        }} />
      </div>
    </div>
  )
}

export default Auth
