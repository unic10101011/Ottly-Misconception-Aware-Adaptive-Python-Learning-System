const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const catalog = () => JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/app/data/guides/catalog.json'), 'utf8'))

test('all 12 formal lessons have three distinct checks and valid linked explanations', () => {
  const levels = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../backend/app/data/levels.json'), 'utf8'))
  const guides = catalog()
  assert.deepEqual(Object.keys(guides).sort(), levels.map(item => item.problem_id).sort())
  for (const level of levels) {
    const story = guides[level.problem_id]
    assert.equal(story.problemId, level.problem_id)
    assert.equal(story.levelNo, level.id)
    assert.equal(story.knowledgeId, `K${String(level.id).padStart(2, '0')}`)
    const ids = story.nodes.map(node => node.id)
    assert.equal(new Set(ids).size, ids.length)
    const quizzes = story.nodes.filter(node => node.type === 'quiz')
    assert.equal(quizzes.length, 3)
    assert.equal(new Set(quizzes.map(node => node.text)).size, 3)
    for (const node of story.nodes) {
      assert.ok(node.text.trim())
      if (node.next) assert.ok(ids.includes(node.next))
      for (const option of node.options || []) {
        if (option.next) assert.ok(ids.includes(option.next))
        if (node.type === 'quiz') assert.ok(option.explanation?.trim())
      }
      if (node.type === 'quiz') {
        assert.equal(node.options.length, 3)
        assert.equal(new Set(node.options.map(option => option.text)).size, 3)
        assert.ok(node.options.some(option => option.id === node.correct))
        assert.ok(node.review.trim())
      }
    }
  }
})

test('quiz cannot advance on a wrong answer, retry clears feedback, all correct answers are required', async () => {
  const story = catalog().level1
  const { createStoryState, currentStoryNode, stepStory } = await import('../src/components/story/storyEngine.mjs')
  let state = createStoryState(story)
  while (currentStoryNode(story, state).type === 'line') state = stepStory(story, state, { type: 'next' })
  state = stepStory(story, state, { type: 'choose', optionId: 'quotes' })
  while (currentStoryNode(story, state).type === 'line') state = stepStory(story, state, { type: 'next' })
  state = stepStory(story, state, { type: 'continue' })
  while (currentStoryNode(story, state).type === 'line') state = stepStory(story, state, { type: 'next' })
  assert.equal(currentStoryNode(story, state).type, 'quiz')
  assert.equal(stepStory(story, state, { type: 'next' }), state)
  assert.equal(stepStory(story, state, { type: 'finish' }), state)
  let quiz = currentStoryNode(story, state)
  const wrong = quiz.options.find(option => option.id !== quiz.correct)
  state = stepStory(story, state, { type: 'answer', optionId: wrong.id })
  assert.equal(state.feedback.correct, false)
  assert.equal(state.answers[quiz.id], undefined)
  assert.equal(stepStory(story, state, { type: 'quiz-next' }), state)
  state = stepStory(story, state, { type: 'retry' })
  assert.equal(state.feedback, null)
  for (let n = 0; n < 3; n++) {
    quiz = currentStoryNode(story, state)
    state = stepStory(story, state, { type: 'answer', optionId: quiz.correct })
    assert.equal(state.feedback.correct, true)
    assert.equal(stepStory(story, state, { type: 'retry' }), state)
    state = stepStory(story, state, { type: 'quiz-next' })
  }
  assert.equal(currentStoryNode(story, state).type, 'end')
  assert.equal(Object.keys(state.answers).length, 3)
  assert.equal(stepStory(story, state, { type: 'finish' }).complete, true)
})
