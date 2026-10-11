import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

function Settings() {
  const [eyeProtectionEnabled, setEyeProtectionEnabled] = useState(false)
  const [language, setLanguage] = useState('zh')
  const [nickname, setNickname] = useState('游客')
  const navigate = useNavigate()

  useEffect(() => {
    setEyeProtectionEnabled(localStorage.getItem('eyeProtectionEnabled') === 'true')
    setLanguage(localStorage.getItem('language') || 'zh')
  }, [])

  const handleEyeProtection = (e) => {
    const enabled = e.target.checked
    setEyeProtectionEnabled(enabled)
    if (enabled) {
      document.body.classList.add('eye-protection')
      localStorage.setItem('eyeProtectionEnabled', 'true')
    } else {
      document.body.classList.remove('eye-protection')
      localStorage.setItem('eyeProtectionEnabled', 'false')
    }
  }

  const handleLanguageSwitch = (lang) => {
    setLanguage(lang)
    localStorage.setItem('language', lang)
  }

  const handleSaveNickname = () => {
    if (nickname.length < 2 || nickname.length > 12) {
      alert('昵称长度必须在2-12个字符之间')
      return
    }
    alert('保存成功')
  }

  const handleLogout = () => {
    localStorage.clear()
    navigate('/auth')
  }

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', height: '100%', overflowY: 'auto' }}>
      <h4 className="mb-4">设置中心</h4>

      <div className="card">
        <div className="card-body p-0">

          {/* 昵称 */}
          <div className="d-flex align-items-center justify-content-between p-3 border-bottom">
            <span>昵称</span>
            <div className="d-flex align-items-center gap-2">
              <input
                type="text"
                className="form-control form-control-sm"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                style={{ width: 140 }}
              />
              <button className="btn btn-primary btn-sm" onClick={handleSaveNickname}>保存</button>
            </div>
          </div>

          {/* 护眼模式 */}
          <div className="d-flex align-items-center justify-content-between p-3 border-bottom">
            <span>护眼模式</span>
            <div className="form-check form-switch mb-0">
              <input
                className="form-check-input"
                type="checkbox"
                checked={eyeProtectionEnabled}
                onChange={handleEyeProtection}
              />
            </div>
          </div>

          {/* 语言选择 */}
          <div className="d-flex align-items-center justify-content-between p-3 border-bottom">
            <span>语言选择</span>
            <div className="btn-group btn-group-sm">
              <button
                className={`btn ${language === 'zh' ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => handleLanguageSwitch('zh')}
              >
                中文
              </button>
              <button
                className={`btn ${language === 'en' ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => handleLanguageSwitch('en')}
              >
                English
              </button>
            </div>
          </div>

          {/* 退出登录 */}
          <div className="d-flex align-items-center justify-content-between p-3">
            <span>退出登录</span>
            <button className="btn btn-danger btn-sm" onClick={handleLogout}>退出</button>
          </div>

        </div>
      </div>
    </div>
  )
}

export default Settings
