import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Auth from './pages/Auth.jsx'
import Settings from './pages/Settings.jsx'
import AIchat from './pages/AIchat.jsx'
import LevelSelection from './pages/LevelSelection.jsx'
import Level1 from './pages/Level1.jsx'
import Level2 from './pages/Level2.jsx'
import Layout from './components/Layout.jsx'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/auth" />} />
        <Route path="/auth" element={<Auth />} />
        <Route path="/app" element={<Layout />}>
          <Route index element={<Navigate to="levels" />} />
          <Route path="levels" element={<LevelSelection />} />
          <Route path="levels/1" element={<Level1 />} />
          <Route path="levels/2" element={<Level2 />} />
          <Route path="settings" element={<Settings />} />
          <Route path="ai-chat" element={<AIchat />} />
        </Route>
      </Routes>
    </Router>
  )
}

export default App
