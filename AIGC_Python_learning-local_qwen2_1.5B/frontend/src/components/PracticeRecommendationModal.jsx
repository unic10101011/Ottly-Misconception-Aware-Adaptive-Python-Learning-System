import React, { useEffect, useRef } from 'react'
import exerciseOtter from '../pages/images/ottly-exercise.png'

export default function PracticeRecommendationModal({ recommendation, onSkip, onPractice }) {
  const dialogRef = useRef(null)
  const practiceRef = useRef(null)

  useEffect(() => {
    const previousFocus = document.activeElement
    const dialog = dialogRef.current
    dialog.showModal()
    practiceRef.current.focus()
    return () => {
      dialog.close()
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [])

  return <dialog ref={dialogRef} className="practice-recommendation-modal"
    aria-labelledby="practice-recommendation-title" aria-describedby="practice-recommendation-description"
    onCancel={event => { event.preventDefault(); onSkip() }}>
    <button type="button" className="practice-recommendation-skip" onClick={onSkip}>跳过</button>
    <img className="practice-recommendation-icon" src={exerciseOtter} alt="挥手的 Ottly 小海獭" />
    <h2 id="practice-recommendation-title">Ottly 向你推荐一道加练题！</h2>
    <p id="practice-recommendation-description" className="practice-recommendation-description">快来巩固一下知识点吧～</p>
    <div className="practice-recommendation-question">
      <strong>{recommendation.title}</strong>
      <p>{recommendation.reason}</p>
    </div>
    <button ref={practiceRef} type="button" className="practice-recommendation-action" onClick={onPractice}>去看看 →</button>
  </dialog>
}
