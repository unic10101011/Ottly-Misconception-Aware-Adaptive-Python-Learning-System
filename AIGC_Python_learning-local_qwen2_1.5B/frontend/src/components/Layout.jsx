import React from 'react'
import { Outlet, Link, useNavigate } from 'react-router-dom'

function Layout() {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    navigate('/auth')
  }

  return (
    <div className="d-flex h-100 bg-light">
      {/* 侧边栏 */}
      <div className="sidebar bg-white border-right" style={{ width: '250px', height: '100vh', position: 'fixed' }}>
        <div className="p-4 border-bottom">
          <h3 className="text-center">AIGC 应用</h3>
        </div>
        <div className="p-4">
          <ul className="nav flex-column">
            <li className="nav-item mb-2">
              <Link to="/app/levels" className="nav-link">关卡选择</Link>
            </li>
            <li className="nav-item mb-2">
              <Link to="/app/ai-chat" className="nav-link">AI对话</Link>
            </li>
            <li className="nav-item mb-2">
              <Link to="/app/settings" className="nav-link">设置中心</Link>
            </li>
          </ul>
        </div>
        <div className="p-4 mt-auto">
          <button onClick={handleLogout} className="btn btn-danger w-100">退出登录</button>
        </div>
      </div>

      {/* 主内容区 - 已删除顶部 AIGC 应用框 */}
      <div className="flex-grow-1 d-flex flex-column" style={{ marginLeft: '250px', height: '100vh', overflow: 'hidden' }}>
        <div className="container py-4 flex-grow-1 d-flex flex-column overflow-hidden">
          <Outlet />
        </div>
      </div>
    </div>
  )
}

export default Layout
