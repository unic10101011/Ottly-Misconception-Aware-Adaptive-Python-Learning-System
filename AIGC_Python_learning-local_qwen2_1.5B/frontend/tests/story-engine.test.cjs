const test = require('node:test')
const assert = require('node:assert/strict')

async function setup() {
  const story = JSON.parse(require('node:fs').readFileSync(require('node:path').resolve(__dirname, '../../backend/app/data/guides/catalog.json'), 'utf8')).level1
  const { createStoryState, stepStory, currentStoryNode } = await import('../src/components/story/storyEngine.mjs')
  return { story, createStoryState, stepStory, currentStoryNode }
}

test('story uses valid stable nodes for the formal first lesson and does not reveal unplayed answers', async () => {
  const { story, createStoryState } = await setup()
  assert.equal(story.problemId, 'level1')
  const ids = story.nodes.map(node => node.id)
  assert.equal(new Set(ids).size, ids.length)
  for (const node of story.nodes) {
    assert.equal(typeof node.speaker, 'string')
    assert.equal(typeof node.text, 'string')
    if (node.next) assert.ok(ids.includes(node.next))
    for (const option of node.options || []) if (option.next) assert.ok(ids.includes(option.next))
  }
  const state = createStoryState(story)
  assert.equal(state.history.length, 1)
  assert.equal(state.history[0].text, story.nodes[0].text)
  assert.equal(state.complete, false)
})

test('a first question must be fully heard before continuing and both questions remain available', async () => {
  const { story, createStoryState, stepStory, currentStoryNode } = await setup()
  let state = createStoryState(story)
  while (currentStoryNode(story, state).type === 'line') state = stepStory(story, state, { type: 'next' })
  const menuId = state.nodeId
  assert.equal(stepStory(story, state, { type: 'continue' }), state)
  assert.equal(stepStory(story, state, { type: 'next' }), state)
  assert.equal(stepStory(story, state, { type: 'finish' }), state)
  const options = currentStoryNode(story, state).options
  state = stepStory(story, state, { type: 'choose', optionId: options[0].id })
  assert.equal(state.heard.length, 0)
  state = stepStory(story, state, { type: 'next' })
  assert.equal(state.heard.length, 0)
  state = stepStory(story, state, { type: 'next' })
  assert.equal(state.nodeId, menuId)
  assert.deepEqual(state.heard, [options[0].id])
  assert.equal(currentStoryNode(story, state).options.length, 2)
  assert.ok(state.history.some(line => line.speaker === '我' && line.text === options[0].text))
  assert.ok(!state.history.some(line => line.speaker === '我' && line.text === options[1].text))
  state = stepStory(story, state, { type: 'choose', optionId: options[1].id })
  state = stepStory(story, state, { type: 'next' })
  state = stepStory(story, state, { type: 'next' })
  assert.equal(state.nodeId, menuId)
  assert.deepEqual(state.heard, options.map(option => option.id))
})

test('questions can be replayed without duplicating completion and finishing requires an explicit final action', async () => {
  const { story, createStoryState, stepStory, currentStoryNode } = await setup()
  let state = createStoryState(story)
  while (currentStoryNode(story, state).type === 'line') state = stepStory(story, state, { type: 'next' })
  const option = currentStoryNode(story, state).options[1]
  for (let round = 0; round < 2; round++) {
    state = stepStory(story, state, { type: 'choose', optionId: option.id })
    state = stepStory(story, state, { type: 'next' })
    state = stepStory(story, state, { type: 'next' })
  }
  assert.deepEqual(state.heard, [option.id])
  assert.equal(state.history.filter(line => line.speaker === '我').length, 2)
  state = stepStory(story, state, { type: 'continue' })
  while (currentStoryNode(story, state).type === 'line') state = stepStory(story, state, { type: 'next' })
  while (currentStoryNode(story, state).type === 'quiz') {
    state = stepStory(story, state, { type: 'answer', optionId: currentStoryNode(story, state).correct })
    state = stepStory(story, state, { type: 'quiz-next' })
  }
  assert.equal(currentStoryNode(story, state).type, 'end')
  assert.equal(state.complete, false)
  assert.equal(stepStory(story, state, { type: 'next' }), state)
  state = stepStory(story, state, { type: 'finish' })
  assert.equal(state.complete, true)
  assert.equal(createStoryState(story).complete, false, 'an interrupted or refreshed prototype never inherits completion')
})
