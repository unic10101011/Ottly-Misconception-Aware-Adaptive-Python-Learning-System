"""Render complete real feedback and an unfilled human review form."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    report = json.loads((HERE/args.input).read_text(encoding='utf-8'))
    assert report['finished_at']
    fixtures = {c['trial_id']: c for c in json.loads((ROOT/'backend/tests/data/core72_feedback_regressions.json').read_text(encoding='utf-8'))['trials']}
    text = ['# 修复后真实AI复测：逐条结果', '',
            '这是复用旧执行事实的AI服务复测，不是新的未见验收，也未执行完整HTTP/界面流程。每个试次启动一次，仅连接建立失败允许最多一次重试；没有内容失败后反复生成挑选结果。', '',
            '自动检查只报告返回状态、路由和标签允许集合；不等于人工语义合格。旧验收成绩保持不变。', '',
            f'本表来源：`{args.input}`；第一轮中间版本的两次误拦截保存在根目录real-ai-results.json，未被第二轮结果覆盖。', '',
            f"开始：{report['started_at']}；结束：{report['finished_at']}（UTC）。", '',
            '| 试次 | 状态 | 路由 | 标签 | 自动检查 | 耗时秒 |', '|---|---|---|---|---|---:|']
    for trial in report['trials']:
        result = trial['result'] or {}
        content = result.get('content') or {}
        text.append(f"| [{trial['trial_id']}](#{trial['trial_id'].lower()}) | {result.get('status','error')} | {result.get('feedback_kind','')} | {content.get('misconception_tag','不适用')} | {'通过' if trial['technical_passed'] else '失败'} | {trial['seconds']} |")
    form = ['# 修复后真实AI复测：人工检查表', '',
            '复核人：________；日期：________。请阅读[逐条结果](真实AI复测逐条结果.md)，按旧口径复核。空白表示尚未人工评定，不预填通过。', '',
            '正确性、证据、标签和答案保护均为2，易懂至少1时通过；guidance标签不适用。未取得反馈时记“调用失败未评分”，正确跳过项不计AI语义分母。保留问题原句及实际依据。', '',
            '| 试次 | 反馈类型/状态 | 正确性0–2 | 证据0–2 | 标签0–2或不适用 | 易懂0–2 | 答案保护0–2 | 人工结论 | 问题原文及依据 |',
            '|---|---|---|---|---|---|---|---|---|']
    for trial in report['trials']:
        key = trial['trial_id']; case = fixtures[key]; result = trial['result'] or {}
        text += ['', f'## {key}', '', f"原样例：{case['case_id']}；题目：{case['problem_id']}；模式：{case['mode']}。", '',
                 '学生代码：', '', '```python', case['code'].rstrip(), '```', '']
        if case['mode']=='run':
            text += ['本次自定义输入：', '', '```text', case['stdin'].rstrip(), '```', '']
        text += ['捕获的公开执行结果（隐藏内容仍为空）：', '', '```json',
                 json.dumps(case['judge'], ensure_ascii=False, indent=2), '```', '',
                 '本次完整反馈（未改写）：', '', '```json', json.dumps(result, ensure_ascii=False, indent=2), '```', '']
        if result.get('status')=='ready':
            text += ['人工重点：核对错因与公开执行是否一致；是否提供可替换语句；运行模式是否区分题目约束与自定义输入；指导中的输入、实际输出、期望输出是否指代准确。', '']
        form.append(f"| [{key}](真实AI复测逐条结果.md#{key.lower()}) | {result.get('feedback_kind','')} / {result.get('status','error')} | | | | | | | |")
    (HERE/'真实AI复测逐条结果.md').write_text('\n'.join(text)+'\n', encoding='utf-8')
    form += ['', '原13个失败试次为前13行；C08保留文字问题；后6行为正常概念解释/正确跳过对照。不能用这次复测覆盖旧分母或推算新的未见样例准确率。', '']
    form_path = HERE/'人工复测检查表.md'
    assert not form_path.exists(), 'Do not overwrite a possibly completed human review.'
    form_path.write_text('\n'.join(form)+'\n', encoding='utf-8')
    # A later human edit is expected, so the form is excluded from evidence locks.
    files = [p for p in sorted(HERE.rglob('*')) if p.is_file() and p.name not in {'fixes-manifest.json','人工复测检查表.md'}]
    (HERE/'fixes-manifest.json').write_text(json.dumps({'human_review':'pending', 'files':[
        {'path':p.relative_to(HERE).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]},
        ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='final/real-ai-results.json')
    args = parser.parse_args()
    main()
