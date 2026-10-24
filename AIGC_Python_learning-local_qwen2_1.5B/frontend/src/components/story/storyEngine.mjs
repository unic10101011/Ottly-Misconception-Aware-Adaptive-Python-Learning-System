export function currentStoryNode(story, state) {
  return story.nodes.find(node => node.id === state.nodeId)
}

function enterNode(story, state, id) {
  const node = story.nodes.find(item => item.id === id)
  const text = node.type === 'choice' && state.heard.length
    ? '还有想问的吗？也可以继续。' : node.text
  return { ...state, nodeId: id, feedback: null,
    history: [...state.history, { id: node.id, speaker: node.speaker, text }] }
}

export function createStoryState(story) {
  return enterNode(story, { nodeId: null, heard: [], history: [], answers: {}, feedback: null, complete: false }, story.start)
}

export function stepStory(story, state, action) {
  if (state.complete) return state
  const node = currentStoryNode(story, state)
  if (action.type === 'next' && node.type === 'line') {
    const heard = node.completesOption ? [...new Set([...state.heard, node.completesOption])] : state.heard
    return enterNode(story, { ...state, heard }, node.next)
  }
  if (action.type === 'choose' && node.type === 'choice') {
    const option = node.options.find(item => item.id === action.optionId)
    if (!option) return state
    return enterNode(story, { ...state,
      history: [...state.history, { id: option.id, speaker: '我', text: option.text }] }, option.next)
  }
  if (action.type === 'continue' && node.type === 'choice' && state.heard.length >= story.requiredQuestions) {
    return enterNode(story, state, node.next)
  }
  if (node.type === 'quiz') {
    if (action.type === 'answer' && !state.feedback) {
      const option = node.options.find(item => item.id === action.optionId)
      if (!option) return state
      const correct = option.id === node.correct
      return { ...state, feedback: { correct, optionId: option.id },
        answers: correct ? { ...state.answers, [node.id]: option.id } : state.answers,
        history: [...state.history, { id: node.id, speaker: '我', text: option.text },
          { id: node.id, speaker: 'Ottly', text: option.explanation }] }
    }
    if (action.type === 'retry' && state.feedback && !state.feedback.correct) return enterNode(story, state, node.id)
    if (action.type === 'review' && state.feedback && !state.feedback.correct) return {
      ...state, history: [...state.history, { id: node.id, speaker: 'Ottly', text: node.review }],
    }
    if (action.type === 'quiz-next' && state.feedback?.correct) return enterNode(story, state, node.next)
  }
  if (action.type === 'finish' && node.type === 'end' && state.heard.length >= story.requiredQuestions) {
    if (story.nodes.some(item => item.type === 'quiz' && state.answers[item.id] !== item.correct)) return state
    return { ...state, complete: true }
  }
  return state
}
