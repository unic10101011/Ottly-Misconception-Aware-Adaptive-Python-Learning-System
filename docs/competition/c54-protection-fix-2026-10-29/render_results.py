"""Show final feedback and prepare human scores without pre-filling a pass."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    run=json.loads((HERE/'final/real-ai-results.json').read_text(encoding='utf-8'))
    gates=json.loads((HERE/'final/review-gate-results.json').read_text(encoding='utf-8'))
    assert run['finished_at'] and gates['status']=='complete'
    fixtures={c['trial_id']:c for c in json.loads((HERE/'replay-fixtures.json').read_text(encoding='utf-8'))['trials']}
    doc=['# C54答案保护修复：最终真实复测逐条结果','',
         '本次在同一12条计划上完整运行两轮，第一轮失败保存在根目录；本表对应final/中的最终版本。复用既有公开执行事实，未新增用户、提交或重新判题，不是未见样例准确率测试。','',
         '自动检查包括状态、路由、标签集合；人工语义与答案保护仍待填写。','',
         f"最终版本：{run['started_at']}—{run['finished_at']}（UTC）。",'',
         '## 固定候选的真实语义审核','',
         '下列是审核模型是否按约定区分修正步骤与正常解释的对照。候选在开跑前固定，预期结果没有发给模型。这不等于9条独立人工评分。','',
         '| 对照 | 预期问题 | 实际问题 | 符合预期 |','|---|---|---|---|']
    for g in gates['items']:
        doc.append(f"| {g['id']} | {g['expected_issue'] or '无'} | {', '.join(g['actual_issues'] or []) or '无'} | {'是' if g['passed'] else '否'} |")
    doc+=['','候选原文、实际审核结果与请求分别见[审核记录](final/review-gate-results.json)、[上游调用记录](final/provider-calls.jsonl)。','',
          '## 12个生成及路由试次','',
          '| 试次 | 返回状态 | 自动检查 | 耗时秒 |','|---|---|---|---:|']
    form=['# C54答案保护修复：人工复测检查表','',
          '复核人：________；日期：________。请对照[最终反馈原文](真实AI复测逐条结果.md)填写。C54三条重点检查是否仍给出具体变量更新动作及更新量；其他诊断检查是否误伤正常概念解释。','',
          '正确性、证据、标签和答案保护均为2，易懂至少1时通过；guidance标签不适用，正确跳过不计AI语义分母。仅获得ready状态不等于人工通过。','',
          '| 试次 | 反馈类型/状态 | 正确性0–2 | 证据0–2 | 标签0–2或不适用 | 易懂0–2 | 答案保护0–2 | 人工结论 | 问题原文及依据 |',
          '|---|---|---|---|---|---|---|---|---|']
    for trial in run['trials']:
        key=trial['trial_id'];result=trial['result'] or {}
        doc.append(f"| [{key}](#{key.lower()}) | {result.get('status','error')} | {'通过' if trial['technical_passed'] else '失败'} | {trial['seconds']} |")
        form.append(f"| [{key}](真实AI复测逐条结果.md#{key.lower()}) | {result.get('feedback_kind','')} / {result.get('status','error')} | | | | | | | |")
    for trial in run['trials']:
        key=trial['trial_id'];case=fixtures[key]
        doc+=['',f'## {key}','',f"模式：{case['mode']}；题目：{case['problem_id']}。",'',
              '```python',case['code'].rstrip(),'```','']
        if case['mode']=='run':doc+=['本次运行输入：','','```text',case['stdin'].rstrip(),'```','']
        doc+=['捕获的执行事实（隐藏内容已脱敏）：','','```json',json.dumps(case['judge'],ensure_ascii=False,indent=2),'```','',
              '本次完整反馈（未改写）：','','```json',json.dumps(trial['result'],ensure_ascii=False,indent=2),'```','']
    form+=['','本表只对应最终一轮12个试次，不覆盖旧72条验收或上一轮18/19的人工结论。C24-R3为输入域说明稳定性观察项。','']
    target=HERE/'人工复测检查表.md'
    assert not target.exists(),'Never overwrite a potentially completed human form.'
    target.write_text('\n'.join(form)+'\n',encoding='utf-8')
    (HERE/'真实AI复测逐条结果.md').write_text('\n'.join(doc)+'\n',encoding='utf-8')


if __name__=='__main__':main()
