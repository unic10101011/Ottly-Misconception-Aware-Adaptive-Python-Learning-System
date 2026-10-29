import React from 'react'

// 波浪视口：路径以 period 为周期横向重复，CSS 动画把路径平移恰好一个波长后循环，
// 即得到无缝流动的水面。
const WAVE_WIDTH = 1440
const WAVE_HEIGHT = 132

// 三次贝塞尔正弦近似的控制点系数：偏移量取 2√3·A 时，波峰恰好达到 ±A
const CONTROL_FACTOR = 2 * Math.sqrt(3)

// 生成一条平滑且严格以 period 为周期的波浪填充路径。
// 路径从 -phase-period 起画并向右多画出至少一个波长的富余，
// 保证 CSS 循环平移过程中的任意中间帧都不会露出空白。
function buildWavePath({ period, amplitude, midline, phase = 0 }) {
  const controlOffset = amplitude * CONTROL_FACTOR
  const start = -phase - period
  const segments = Math.ceil((WAVE_WIDTH + 2 * period) / period) + 1
  let d = `M${start} ${midline}`
  for (let i = 0; i < segments; i += 1) {
    const x = start + i * period
    d += ` C${(x + period / 3).toFixed(2)} ${(midline + controlOffset).toFixed(2)} ${(x + (2 * period) / 3).toFixed(2)} ${(midline - controlOffset).toFixed(2)} ${(x + period).toFixed(2)} ${midline}`
  }
  const end = start + segments * period
  return `${d} L${end} ${WAVE_HEIGHT + 6} L${start} ${WAVE_HEIGHT + 6} Z`
}

// 波浪分三层：远层波长长、流速慢并向右漂，中层/近层以不同速度向左流，
// 配合轻微的上下起伏，营造水面纵深（参考 getwaves.io / svg-waves 类开源实现的分层手法）。
// 海獭渲染在中层与近层之间：近层浪的填充盖住海獭下半身，看起来像浮在水中。
const WAVE_LAYERS = [
  { key: 'back', className: 'auth-wave-back', period: 864, amplitude: 15, midline: 42, phase: 216, shift: 864 },
  { key: 'mid', className: 'auth-wave-mid', period: 648, amplitude: 20, midline: 64, phase: 162, shift: -648 }
]

const FRONT_LAYER = { key: 'front', className: 'auth-wave-front', period: 504, amplitude: 16, midline: 92, phase: 126, shift: -504 }

function renderLayer(layer) {
  return (
    <svg
      key={layer.key}
      className={`auth-wave-svg ${layer.className}`}
      style={{ '--wave-shift': `${layer.shift}px` }}
      viewBox={`0 0 ${WAVE_WIDTH} ${WAVE_HEIGHT}`}
      preserveAspectRatio="none"
    >
      <path d={buildWavePath(layer)} />
    </svg>
  )
}

function AuthWave() {
  return (
    <div className="auth-wave" aria-hidden="true">
      {WAVE_LAYERS.map(renderLayer)}
      <div className="auth-wave-otter">
        <img src="/login/Ottly.png" alt="" />
      </div>
      {renderLayer(FRONT_LAYER)}
    </div>
  )
}

export default AuthWave
