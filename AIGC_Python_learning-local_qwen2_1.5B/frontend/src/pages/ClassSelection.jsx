import React, { useState } from 'react'

function ClassSelection() {
  const [selectedClass, setSelectedClass] = useState(null)
  const [statusMessage, setStatusMessage] = useState('请选择一个职业开始冒险')
  const [statusType, setStatusType] = useState('info')
  const [characterInfo, setCharacterInfo] = useState(null)

  const selectClass = async (className, button) => {
    // 播放攻击动画
    const icon = button.closest('.hero-card').querySelector('.hero-icon')
    icon.classList.add('attack-animation')
    setTimeout(() => {
      icon.classList.remove('attack-animation')
    }, 500)
    
    // 发送请求到后端
    try {
      const response = await fetch('/api/v1/class/select', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({ class_name: className })
      })
      
      const data = await response.json()
      
      if (data.code === 200) {
        // 显示成功消息
        setStatusMessage(data.msg || `职业选择成功！你的职业是：${className}`)
        setStatusType('success')
        
        // 显示角色信息
        setCharacterInfo({
          className,
          level: 1,
          skill: '基础 Python 技能'
        })
        
        // 禁用所有选择按钮
        document.querySelectorAll('.btn-select').forEach(btn => {
          btn.disabled = true
          btn.className = 'btn btn-secondary btn-select'
        })
        
        // 模拟受击反馈
        setTimeout(() => {
          icon.classList.add('hit-animation')
          setTimeout(() => {
            icon.classList.remove('hit-animation')
          }, 500)
        }, 1000)
      } else {
        setStatusMessage(data.msg || '选择职业失败，请重试')
        setStatusType('danger')
      }
    } catch (error) {
      setStatusMessage('网络错误，请稍后重试')
      setStatusType('danger')
      console.error('Error:', error)
    }
  }

  const getAvatar = (className) => {
    switch (className) {
      case '变量巫师':
        return '🧙‍♂️'
      case '逻辑骑士':
        return '🛡️'
      case '循环射手':
        return '🏹'
      default:
        return ''
    }
  }

  return (
    <div className="container py-5">
      <div className="text-center mb-5">
        <h1 className="display-4">勇者职业选择</h1>
        <p className="lead">选择你的职业，开始冒险之旅</p>
      </div>
      
      <div className="row g-4">
        {/* 变量巫师 */}
        <div className="col-lg-4 col-md-6">
          <div className="hero-card card p-4">
            <div className="hero-image idle-animation" style={{
              position: 'relative',
              height: '200px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: '#e9ecef',
              borderRadius: '0.5rem'
            }}>
              <div className="hero-icon" style={{ fontSize: '4rem' }}>🧙‍♂️</div>
            </div>
            <div className="class-info mt-4">
              <h3 className="text-center">变量巫师</h3>
              <p className="text-center text-muted">扁平化 2D 形象，手持代码法杖，攻击动效为简单的"法球飞行"。</p>
              <button 
                className="btn btn-primary btn-select w-100 mt-3"
                onClick={(e) => selectClass('变量巫师', e.target)}
              >
                选择职业
              </button>
            </div>
          </div>
        </div>
        
        {/* 逻辑骑士 */}
        <div className="col-lg-4 col-md-6">
          <div className="hero-card card p-4">
            <div className="hero-image idle-animation" style={{
              position: 'relative',
              height: '200px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: '#e9ecef',
              borderRadius: '0.5rem'
            }}>
              <div className="hero-icon" style={{ fontSize: '4rem' }}>🛡️</div>
            </div>
            <div className="class-info mt-4">
              <h3 className="text-center">逻辑骑士</h3>
              <p className="text-center text-muted">扁平化 2D 形象，背负逻辑之盾，攻击动效为简单的"盾牌冲撞"。</p>
              <button 
                className="btn btn-primary btn-select w-100 mt-3"
                onClick={(e) => selectClass('逻辑骑士', e.target)}
              >
                选择职业
              </button>
            </div>
          </div>
        </div>
        
        {/* 循环射手 */}
        <div className="col-lg-4 col-md-6">
          <div className="hero-card card p-4">
            <div className="hero-image idle-animation" style={{
              position: 'relative',
              height: '200px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: '#e9ecef',
              borderRadius: '0.5rem'
            }}>
              <div className="hero-icon" style={{ fontSize: '4rem' }}>🏹</div>
            </div>
            <div className="class-info mt-4">
              <h3 className="text-center">循环射手</h3>
              <p className="text-center text-muted">扁平化 2D 形象，手持循环长弓，攻击动效为连续的"箭矢连发"。</p>
              <button 
                className="btn btn-primary btn-select w-100 mt-3"
                onClick={(e) => selectClass('循环射手', e.target)}
              >
                选择职业
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <div className="mt-5 status-bar bg-white rounded-3 shadow p-4">
        <h4 className="mb-3">状态信息</h4>
        <div className={`alert alert-${statusType}`} role="alert">
          {statusMessage}
        </div>
        {characterInfo && (
          <div className="mt-3">
            <h5>角色信息</h5>
            <div className="row">
              <div className="col-md-3">
                <div className="hero-icon" style={{ fontSize: '4rem' }}>
                  {getAvatar(characterInfo.className)}
                </div>
              </div>
              <div className="col-md-9">
                <p><strong>职业：</strong>{characterInfo.className}</p>
                <p><strong>等级：</strong>{characterInfo.level}</p>
                <p><strong>技能：</strong>{characterInfo.skill}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default ClassSelection