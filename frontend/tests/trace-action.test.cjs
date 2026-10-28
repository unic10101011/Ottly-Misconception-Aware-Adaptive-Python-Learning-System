const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const Module = require('node:module')
const { transformSync } = require('esbuild')
const { renderToStaticMarkup } = require('react-dom/server')

function render(action, step = { event: 'line', line: 3 }) {
  const filename = path.resolve(__dirname, '../src/components/TraceAction.jsx')
  const loaded = new Module(filename, module)
  loaded.filename = filename; loaded.paths = Module._nodeModulePaths(path.dirname(filename))
  loaded._compile(transformSync(fs.readFileSync(filename, 'utf8'), { loader: 'jsx', format: 'cjs' }).code, filename)
  return renderToStaticMarkup(loaded.exports.default({ action, step, code: 'friend = input()\nprint(friend)' }))
}

test('input and print show recorded data only and absent actions never invent output', () => {
  assert.match(render({ kind: 'input', line: 1, target: 'friend', parts: ["'Ottly'"], result: "'Ottly'" }), /输入|friend|Ottly/)
  const printed = render({ kind: 'print', line: 2, parts: ["'Hello, '", "'Ottly'", "'!'"], result: "'Hello, Ottly!'", output: 'Hello, Ottly!\n' })
  assert.match(printed, /Hello, Ottly!/)
  assert.match(printed, /送到输出/)
  assert.doesNotMatch(render(null), /Hello, Ottly!/)
})

test('addition and replacement have different truthful labels without diagnosing wrong code', () => {
  const add = render({ kind: 'add', target: 'total', parts: ['1', '2'], before: '1', result: '3', round: 2, line: 1 })
  const replace = render({ kind: 'replace', target: 'total', parts: ['2'], before: '1', result: '2', round: 2, line: 1 })
  assert.match(add, /加法|相加/)
  assert.match(replace, /替换|覆盖/)
  assert.doesNotMatch(replace, /错误|应该累加/)
  assert.match(replace, /第.*2.*轮/)
})

test('generic and exception actions retain facts without fabricated expression parts', () => {
  assert.match(render({ kind: 'change', line: 1, changes: [{ name: 'a', before: '2', after: '6' }] }), /a|2|6/)
  assert.match(render({ kind: 'exception', line: 2 }, { event: 'exception', exception: { type: 'TypeError' } }), /异常|TypeError/)
})
