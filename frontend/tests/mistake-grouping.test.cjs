const test = require('node:test')
const assert = require('node:assert/strict')

test('mistakes group by each real knowledge ID without repeating a question within a group', async () => {
  const { groupMistakes } = await import('../src/components/mistakeGrouping.mjs')
  const first = { problem_id: 'first', knowledge_ids: ['K08', 'K07', 'K07'] }
  const second = { problem_id: 'second', knowledge_ids: ['K08'] }
  const groups = groupMistakes([first, second], { K07: 'for 循环与 range', K08: '累加器与变量更新' })
  assert.deepEqual(groups.map(group => [group.id, group.name, group.questions.map(item => item.problem_id)]), [
    ['K07', 'for 循环与 range', ['first']],
    ['K08', '累加器与变量更新', ['first', 'second']],
  ])
})

test('historical missing tags and an unavailable dictionary preserve uncertainty', async () => {
  const { groupMistakes } = await import('../src/components/mistakeGrouping.mjs')
  const groups = groupMistakes([{ problem_id: 'legacy' }, { problem_id: 'unknown', knowledge_ids: ['K99'] }], {})
  assert.deepEqual(groups.map(group => [group.id, group.name]), [
    ['K99', 'K99'], ['unclassified', '知识点待补充'],
  ])
  assert.deepEqual(groupMistakes([], {}), [])
})

test('review links preserve the knowledge context and safely encode problem IDs', async () => {
  const { mistakeDetailUrl, mistakeOverviewUrl } = await import('../src/components/mistakeGrouping.mjs')
  assert.equal(mistakeDetailUrl('a/b ?', 'K07'), '/app/history/a%2Fb%20%3F?knowledge=K07')
  assert.equal(mistakeOverviewUrl('K07'), '/app/history?knowledge=K07#knowledge-K07')
  assert.equal(mistakeOverviewUrl(), '/app/history')
})
