import React, { useEffect, useState } from 'react'
import { Outlet, Link, NavLink, useNavigate } from 'react-router-dom'
import otter from '../pages/images/chathaita.png'

function Layout() {
  const navigate = useNavigate()
  const [checking, setChecking] = useState(true)
  const [userId, setUserId] = useState(null)

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    navigate('/auth')
  }

  useEffect(() => {
    let active = true
    const token = localStorage.getItem('access_token')
    if (!token) {
      navigate('/auth', { replace: true })
      return
    }
    fetch('/api/v1/auth/me', {
      headers: { Authorization: 'Bearer ' + token }
    }).then(async response => {
      if (!active) return
      if (!response.ok) {
        handleLogout()
      } else {
        const result = await response.json()
        if (!active) return
        if (!Number.isSafeInteger(result.data?.id) || result.data.id <= 0) {
          handleLogout()
          return
        }
        setUserId(result.data.id)
        setChecking(false)
      }
    }).catch(() => {
      if (active) handleLogout()
    })
    return () => { active = false }
  }, [navigate])

  if (checking) return <div className="app-checking" role="status">正在验证登录状态...</div>

  return (
    <div className="app-layout">
      <a className="skip-link" href="#main-content">跳到主内容</a>
      <aside className="app-sidebar">
        <Link className="app-brand" to="/app/levels" aria-label="Ottly，返回学习地图">
          <img src={otter} alt="" />
          <span><strong>Ottly</strong><small>和小海獭一起学 Python</small></span>
        </Link>
        <nav className="app-nav" aria-label="主要导航">
          <NavLink to="/app/levels" end={false} className={({ isActive }) => `app-nav-link ${isActive ? 'active' : ''}`}>学习地图</NavLink>
          <NavLink to="/app/practice" className={({ isActive }) => `app-nav-link ${isActive ? 'active' : ''}`}>加练题库</NavLink>
          <NavLink to="/app/ai-chat" className={({ isActive }) => `app-nav-link ${isActive ? 'active' : ''}`}>AI 对话</NavLink>
          <NavLink to="/app/history" className={({ isActive }) => `app-nav-link ${isActive ? 'active' : ''}`}>我的错题</NavLink>
          <NavLink to="/app/settings" className={({ isActive }) => `app-nav-link ${isActive ? 'active' : ''}`}>个人中心</NavLink>
        </nav>
        <div className="app-logout">
          <button onClick={handleLogout} className="app-logout-button">退出登录</button>
        </div>
      </aside>
      <div className="app-content">
        <main className="app-main" id="main-content">
          <Outlet context={{ userId }} />
        </main>
      </div>
    </div>
  )
}

export default Layout
