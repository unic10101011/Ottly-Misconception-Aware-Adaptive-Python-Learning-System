import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import xingxing from './images/xingxing.png'
import yunduo from './images/yunduo.png'
import AuthWave from '../components/AuthWave'

function Auth() {
  const [activeTab, setActiveTab] = useState('login')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState('info')
  const [showPassword, setShowPassword] = useState(false)
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
      } else if (response.status === 401) {
        showMessage(result.detail || '用户名或密码错误', 'danger')
      } else if (response.status === 403) {
        showMessage(result.detail || '账户已被禁用', 'danger')
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
      
      if (result.code === 201) {
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

  return (
    <div className="auth-page">
      <img src={xingxing} alt="" className="auth-decoration auth-star" />
      <img src={yunduo} alt="" className="auth-decoration auth-cloud" />
      <AuthWave />
      <div className="auth-shell">
        <section className="auth-welcome" aria-label="Ottly 欢迎页">
          <img src="/login/Title.png" alt="嗨獭 Hello, Ottly!" className="auth-title-img" />
        </section>
        <section className="auth-card" aria-label="账号登录与注册">
          <h2 className="auth-card-title">开启你的Python学习之旅</h2>
          <div className="auth-tabs" role="tablist" aria-label="账号操作">
            <button type="button" role="tab" aria-selected={activeTab === 'login'} className={activeTab === 'login' ? 'active' : ''} onClick={() => { setActiveTab('login'); setShowPassword(false); setMessage('') }}>登录</button>
            <button type="button" role="tab" aria-selected={activeTab === 'register'} className={activeTab === 'register' ? 'active' : ''} onClick={() => { setActiveTab('register'); setShowPassword(false); setMessage('') }}>注册</button>
          </div>

          {message && <div className={'auth-message auth-message-' + messageType} role={messageType === 'danger' ? 'alert' : 'status'}>
            <span>{message}</span>
            <button type="button" onClick={() => setMessage('')} aria-label="关闭提示">×</button>
          </div>}

          {activeTab === 'login' ? (
            <form key="login" onSubmit={handleLogin} className="auth-form">
              <div className="auth-field">
                <label htmlFor="login-username">用户名</label>
                <input id="login-username" type="text" className="form-control" name="username" autoComplete="username" required />
                <div className="invalid-feedback">请输入用户名</div>
              </div>
              <div className="auth-field">
                <label htmlFor="login-password">密码</label>
                <div className="auth-password">
                  <input id="login-password" type={showPassword ? 'text' : 'password'} className="form-control" name="password" autoComplete="current-password" required />
                  <button type="button" aria-label={showPassword ? '隐藏密码' : '显示密码'} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}>{showPassword ? '隐藏' : '显示'}</button>
                  <div className="invalid-feedback">请输入密码</div>
                </div>
              </div>
              <button type="submit" className="auth-submit" disabled={loading}>{loading ? '正在登录...' : '登录并继续学习'}</button>
            </form>
          ) : (
            <form key="register" onSubmit={handleRegister} className="auth-form">
              <div className="auth-field">
                <label htmlFor="register-username">用户名</label>
                <input id="register-username" type="text" className="form-control" name="username" autoComplete="username" minLength={3} maxLength={50} required />
                <div className="invalid-feedback">用户名长度为 3–50 个字符</div>
              </div>
              <div className="auth-field">
                <label htmlFor="register-password">密码</label>
                <div className="auth-password">
                  <input id="register-password" type={showPassword ? 'text' : 'password'} className="form-control" name="password" autoComplete="new-password" minLength={12} maxLength={128} required />
                  <button type="button" aria-label={showPassword ? '隐藏密码' : '显示密码'} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}>{showPassword ? '隐藏' : '显示'}</button>
                  <div className="invalid-feedback">请输入 12–128 个字符的密码</div>
                </div>
                <p className="auth-help">建议使用密码管理器生成独立密码。</p>
              </div>
              <div className="auth-field">
                <label htmlFor="register-phone">手机号</label>
                <input id="register-phone" type="tel" className="form-control" name="phone" autoComplete="tel" minLength={10} maxLength={20} required />
                <div className="invalid-feedback">请输入有效手机号</div>
              </div>
              <button type="submit" className="auth-submit" disabled={loading}>{loading ? '正在注册...' : '创建账号'}</button>
            </form>
          )}
        </section>
      </div>
    </div>
  )
}

export default Auth
