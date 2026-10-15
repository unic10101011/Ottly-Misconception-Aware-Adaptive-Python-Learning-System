import React, { useEffect, useState } from 'react'
import { Outlet, Link, useNavigate } from 'react-router-dom'

function Layout() {
  const navigate = useNavigate()
  const [checking, setChecking] = useState(true)

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
    }).then(response => {
      if (!active) return
      if (!response.ok) {
        handleLogout()
      } else {
        setChecking(false)
      }
    }).catch(() => {
      if (active) handleLogout()
    })
    return () => { active = false }
  }, [navigate])

  if (checking) return <div className="p-4">正在验证登录状态...</div>

  return (
    <div className="app-layout d-flex h-100 bg-light">
      <div className="app-sidebar sidebar bg-white border-right" style={{ width: '250px', height: '100vh', position: 'fixed' }}>
        <div className="p-4 border-bottom">
          <h3 className="text-center">AIGC 应用</h3>
        </div>
        <div className="app-nav p-4">
          <ul className="nav flex-column">
            <li className="nav-item mb-2">
              <Link to="/app/levels" className="nav-link">关卡选择</Link>
            </li>
            <li className="nav-item mb-2">
              <Link to="/app/ai-chat" className="nav-link">AI对话</Link>
            </li>
            <li className="nav-item mb-2">
              <Link to="/app/history" className="nav-link">我的错题</Link>
            </li>
            <li className="nav-item mb-2">
              <Link to="/app/settings" className="nav-link">设置中心</Link>
            </li>
          </ul>
        </div>
        <div className="app-logout p-4 mt-auto">
          <button onClick={handleLogout} className="btn btn-danger w-100">退出登录</button>
        </div>
      </div>
      <div className="app-content flex-grow-1 d-flex flex-column" style={{ marginLeft: '250px', height: '100vh', overflow: 'hidden' }}>
        <div className="app-main container py-4 flex-grow-1 d-flex flex-column overflow-hidden">
          <Outlet />
        </div>
      </div>
    </div>
  )
}

export default Layout
