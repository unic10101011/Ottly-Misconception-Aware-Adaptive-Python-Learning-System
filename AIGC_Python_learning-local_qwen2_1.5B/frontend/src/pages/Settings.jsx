import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function Settings() {
  const navigate = useNavigate()
  const [account, setAccount] = useState(null)
  const [username, setUsername] = useState('')
  const [phone, setPhone] = useState('')
  const [accountPassword, setAccountPassword] = useState('')
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [deletePassword, setDeletePassword] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [eyeProtectionEnabled, setEyeProtectionEnabled] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    setEyeProtectionEnabled(localStorage.getItem('eyeProtectionEnabled') === 'true')
    fetch('/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
    }).then(async response => {
      if (!response.ok) throw new Error('账号信息加载失败，请重新登录。')
      const result = await response.json()
      setAccount(result.data)
      setUsername(result.data.username)
      setPhone(result.data.phone)
    }).catch(error => setNotice(error.message))
  }, [])

  const request = async (path, method, body) => {
    const response = await fetch(`/api/v1/auth/${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('access_token')}`,
      },
      body: JSON.stringify(body),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || result.msg || '操作失败')
    return result.data
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    navigate('/auth', { replace: true })
  }

  const saveAccount = async event => {
    event.preventDefault()
    setBusy(true)
    setNotice('')
    try {
      const data = await request('me', 'PATCH', { username, phone, current_password: accountPassword })
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      setAccount(data)
      setAccountPassword('')
      setNotice('账号信息已保存。')
    } catch (error) { setNotice(error.message) }
    finally { setBusy(false) }
  }

  const changePassword = async event => {
    event.preventDefault()
    if (newPassword !== confirmPassword) { setNotice('两次输入的新密码不一致。'); return }
    setBusy(true)
    setNotice('')
    try {
      await request('change-password', 'POST', {
        current_password: oldPassword, new_password: newPassword,
      })
      logout()
    } catch (error) { setNotice(error.message) }
    finally { setBusy(false) }
  }

  const deleteAccount = async event => {
    event.preventDefault()
    if (deleteConfirm !== account?.username) {
      setNotice('请输入当前用户名以确认注销。')
      return
    }
    if (!window.confirm('确认永久删除账号及个人学习、聊天记录？此操作无法恢复。')) return
    setBusy(true)
    setNotice('')
    try {
      await request('me', 'DELETE', { current_password: deletePassword })
      logout()
    } catch (error) { setNotice(error.message) }
    finally { setBusy(false) }
  }

  const toggleEyeProtection = event => {
    const enabled = event.target.checked
    setEyeProtectionEnabled(enabled)
    document.body.classList.toggle('eye-protection', enabled)
    localStorage.setItem('eyeProtectionEnabled', String(enabled))
  }

  return <main className="account-page">
    <h1>个人中心</h1>
    <p className="text-muted">管理账号信息、安全设置与学习偏好。</p>
    {notice && <p className="account-notice" role="status">{notice}</p>}
    {!account ? <p>正在加载账号信息...</p> : <>
      <section className="account-card">
        <h2>账号信息</h2>
        <p className="text-muted">账号编号：{account.id}</p>
        <form onSubmit={saveAccount}>
          <label>用户名<input required minLength="2" maxLength="50" value={username} onChange={event => setUsername(event.target.value)} /></label>
          <label>手机号<input required minLength="6" maxLength="20" value={phone} onChange={event => setPhone(event.target.value)} /></label>
          <label>当前密码<input required type="password" autoComplete="current-password" value={accountPassword} onChange={event => setAccountPassword(event.target.value)} /></label>
          <button className="btn btn-primary" disabled={busy}>保存账号信息</button>
        </form>
      </section>
      <section className="account-card">
        <h2>修改密码</h2>
        <form onSubmit={changePassword}>
          <label>当前密码<input required type="password" autoComplete="current-password" value={oldPassword} onChange={event => setOldPassword(event.target.value)} /></label>
          <label>新密码<input required type="password" minLength="8" autoComplete="new-password" value={newPassword} onChange={event => setNewPassword(event.target.value)} /></label>
          <label>确认新密码<input required type="password" minLength="8" autoComplete="new-password" value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} /></label>
          <button className="btn btn-primary" disabled={busy}>修改密码并重新登录</button>
        </form>
      </section>
      <section className="account-card">
        <h2>学习偏好</h2>
        <label className="account-toggle"><input type="checkbox" checked={eyeProtectionEnabled} onChange={toggleEyeProtection} />护眼模式（仅当前浏览器）</label>
      </section>
      <section className="account-card">
        <h2>退出登录</h2>
        <button type="button" className="btn btn-outline-secondary" onClick={logout}>退出当前账号</button>
      </section>
      <section className="account-card account-danger">
        <h2>永久注销账号</h2>
        <p>将删除此账号的提交、错题复习、AI 聊天和设置记录，无法恢复。</p>
        <form onSubmit={deleteAccount}>
          <label>输入用户名确认：{account.username}<input required value={deleteConfirm} onChange={event => setDeleteConfirm(event.target.value)} /></label>
          <label>当前密码<input required type="password" autoComplete="current-password" value={deletePassword} onChange={event => setDeletePassword(event.target.value)} /></label>
          <button className="btn btn-danger" disabled={busy}>永久注销账号</button>
        </form>
      </section>
    </>}
  </main>
}

export default Settings
