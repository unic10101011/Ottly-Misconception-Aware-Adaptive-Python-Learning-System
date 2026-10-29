"""Append the human retest verdict and an explicitly authorized one-cell correction."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
FIX = HERE.parent/'core72-fixes-2026-10-29'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(name, data):
    (HERE/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def parse(data):
    rows = {}
    for line in data.decode('utf-8').splitlines():
        match = re.match(r'^\| \[(C\d{2}-R[123])\]', line)
        if not match:
            continue
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        assert len(cells)==9, cells
        key = match[1]
        assert key not in rows, key
        rows[key] = {'trial_id':key,'feedback_status':cells[1],
                     'scores':dict(zip(['correctness','evidence','tag','readability','answer_protection'],cells[2:7])),
                     'conclusion':cells[7],'notes':cells[8]}
    return rows


def main():
    assert not (HERE/'human-review-summary.json').exists(), 'Never overwrite a finalized human review.'
    manifest_path = FIX/'fixes-manifest.json'
    old_manifest = read(manifest_path)
    for entry in old_manifest['files']:
        assert sha((FIX/entry['path']).read_bytes())==entry['sha256'], entry['path']
    source = FIX/'人工复测检查表.md'
    before = source.read_bytes()
    (HERE/'human-review.before-correction.snapshot.txt').write_bytes(before)
    original_rows = parse(before)
    assert len(original_rows)==20
    row = original_rows['C54-R3']
    assert row['scores']['answer_protection']=='1' and row['conclusion']=='通过'
    lines = before.splitlines(keepends=True)
    changed = 0
    for index, line in enumerate(lines):
        if line.startswith('| [C54-R3]'.encode()):
            assert line.count('|通过|'.encode())==1
            lines[index] = line.replace('|通过|'.encode(), '|不通过|'.encode())
            changed += 1
    assert changed==1
    after = b''.join(lines)
    rows = parse(after)
    assert rows['C54-R3']['scores']==row['scores'] and rows['C54-R3']['notes']==row['notes']
    for key in rows:
        if key!='C54-R3':assert rows[key]==original_rows[key]
    source.write_bytes(after)
    (HERE/'human-review.final.snapshot.txt').write_bytes(after)
    authority = {
        'source':'用户在当前会话中明确答复', 'trial_id':'C54-R3',
        'human_decision':'保留答案保护1分，结论改为不通过',
        'change':'仅将该行人工结论由通过改为不通过；分数和备注均不变。',
        'before_sha256':sha(before),'after_sha256':sha(after),
        'original_note_retained':'该行原备注仍写“未发现实质问题”，系更正前原文；最新结论及理由以本记录中的用户明确决定为准。',
    }
    write('human-correction.json',authority)
    run = read(FIX/'final/real-ai-results.json')
    trials = {t['trial_id']:t for t in run['trials']}
    assert set(rows)==set(trials)
    effective = []
    for key,row in rows.items():
        result = trials[key]['result']
        if result['status']=='skipped':
            assert row['conclusion']=='正确跳过' and set(row['scores'].values())=={'不适用'}
            continue
        assert result['status']=='ready'
        scores = row['scores']
        assert set(scores.values()) <= {'0','1','2','不适用'}
        qualified = (scores['correctness']==scores['evidence']==scores['answer_protection']=='2'
                     and scores['readability'] in {'1','2'}
                     and (scores['tag']=='2' or result['feedback_kind']=='guidance' and scores['tag']=='不适用'))
        assert row['conclusion']==('通过' if qualified else '不通过'), key
        effective.append(row)
    counts = Counter(r['conclusion'] for r in rows.values())
    assert counts=={'通过':18,'不通过':1,'正确跳过':1}, counts
    cause = trials['C54-R3']['result']['content']['suspected_cause']
    # Do not change the reviewer-approved C24-R3 score. Preserve the narrower
    # factual observation separately: this repeat does not explicitly state the domain.
    domain_cause = trials['C24-R3']['result']['content']['suspected_cause']
    summary = {
        'status':'human_review_completed_with_one_failure',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'reviewer':'A','human_reviewers_this_retest':1,
        'review_date':'2026-10-29', 'source_sha256':sha(after),
        'conclusions':dict(counts),'planned_trials':20,'ai_expected':19,'effective_feedback':len(effective),
        'human_qualified':18,'human_not_qualified':1,'semantic_pass_rate':18/19,
        'end_to_end_semantic_rate':18/19,'correct_skip_controls':1,
        'human_scores_consistent_with_conclusions':True,'original_core72_metrics_unchanged':True,
        'all_retest_requirements_passed':False,'ready_to_freeze':False,
        'unresolved_trial':'C54-R3',
        'unresolved_issue':'诊断含过于具体的自然语言修正建议，人工答案保护1分；没有提供可复制赋值代码，但仍不满足本条人工标准。',
        'actual_suspected_cause':cause,
        'retained_observation':{'trial_id':'C24-R3','human_conclusion':'通过',
            'actual_suspected_cause':domain_cause,
            'codex_note':'该次正确解释除零，但未显式指出自定义输入超出题目合法域；R1/R2有此说明。保留跨重复说明稳定性观察，不改人工通过结论。'},
        'software_regression':read(FIX/'repair-summary.json')['software_regression'],
        'real_ai_calls_added_this_turn':0,'application_modified_this_turn':False,
        'independent_unseen_acceptance':False,
    }
    write('human-review-summary.json',summary)
    write('human-review-rows.json',{'reviewer':'A','rows':list(rows.values())})
    report = ['# 修复后真实AI复测：人工审核定稿','',
        '**本轮人工审核已完成：18条AI反馈通过、1条不通过，另1条正确跳过。仍有未关闭问题，当前不冻结新版。**','',
        '复核人A，日期2026-10-29；本轮只有1位人工复核人的评分，不计作两人独立复核。Codex负责核对分数、原文与统计，不计作新增人工评分。','',
        '| 指标 | 结果 |','|---|---:|','| 总试次 | 20 |','| 应有/可展示AI反馈 | 19/19 |',
        '| 人工语义合格 | 18/19（94.7%） |','| 端到端语义合格 | 18/19（94.7%） |',
        '| 正确跳过对照 | 1/1 |','',
        '该20条计划包含重复试次和已用于排障的旧样例，不是20个独立未见样本。94.7%仅适用于本次定向复测，不能替换或与旧72条首轮48/53、含重复91/100混算，也不能当作全系统准确率。','',
        '软件证据沿用同一源码版本的628项通过、9个子测试通过、1项专用MySQL迁移测试跳过；本次仅整理人工审核，没有修改应用、重新调用AI、提交代码或建立新标签。','',
        '## C54-R3的明确更正','',
        '原表答案保护1分、结论通过与通过标准不一致。用户明确决定：“保留答案保护1分，结论改为不通过”。已仅更正当前检查表该行的结论；原分数、原备注及其余19行保持不变。更正前后快照和用户决定均保留。该行原备注“未发现实质问题”仍按原文保留，不能用它覆盖用户最新决定。','',
        '本次实际诊断原文：','',f'> {cause}','',
        '人工将其中具体要求saved增加3的修正建议评为答案保护1分。它没有给出可复制的赋值代码；本次缺口是自然语言建议过于具体，被生成和语义审核共同放行，不能误写为原单行代码拦截失效。','',
        '下一轮应加强诊断与审核对“解释当前错因”和“指定修正动作”的区分，保留正常概念解释。补充这种自然语言修正建议及相邻正常解释的回归，随后在新工作区版本复测；不能只针对saved或数字3增加特例。','',
        '## 保留观察：输入域解释稳定性','',
        f'C24-R3原诊断：“{domain_cause}”','',
        '人工该条评为通过，本报告按原评分计入。Codex同时保留一项核对观察：R1/R2明确写出越界输入及题目约束，R3仅解释本次除零，没有显式说明合法输入域。这里不把其他轮次的文字补入R3，也不另行改写人工评分；后续可与建议边界修复一并观察重复稳定性。','',
        '## 逐条结论','',
        '| 试次 | 正确性 | 证据 | 标签 | 易懂 | 答案保护 | 最终结论 |','|---|---:|---:|---|---:|---:|---|']
    for key,row in rows.items():
        s=row['scores']
        report.append(f"| [{key}](../core72-fixes-2026-10-29/真实AI复测逐条结果.md#{key.lower()}) | {s['correctness']} | {s['evidence']} | {s['tag']} | {s['readability']} | {s['answer_protection']} | {row['conclusion']} |")
    report += ['', '## 来源与当前结论','',
        '- [当前人工检查表](../core72-fixes-2026-10-29/人工复测检查表.md)、[反馈原文](../core72-fixes-2026-10-29/真实AI复测逐条结果.md)。',
        '- [更正前快照](human-review.before-correction.snapshot.txt)、[更正后快照](human-review.final.snapshot.txt)、[用户更正决定](human-correction.json)。',
        '- [此前软件修复报告](../core72-fixes-2026-10-29/修复与复测报告.md)及repair-summary.json保留当时待人工状态；最新人工结论以本报告为准。',
        '- human-review-summary.json、human-review-rows.json、review-manifest.json提供统计、原分和来源指纹。','',
        '本轮审核记录已闭环，缺陷修复尚未全部闭环。建议先处理C54-R3，并观察C24输入域说明的稳定性；复测合格后再冻结修复版、进入推荐/出题/问答/回放专项和24条方案对照。','']
    (HERE/'人工审核定稿.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    sources = [source, manifest_path,FIX/'final/real-ai-results.json',FIX/'source-and-evidence-check-final.json']
    write('review-manifest.json',{'status':summary['status'],
        'files':[{'path':p.name,'sha256':sha(p.read_bytes())} for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='review-manifest.json'],
        'sources':[{'path':p.relative_to(HERE.parent).as_posix(),'sha256':sha(p.read_bytes())} for p in sources]})
    print(json.dumps({'conclusions':dict(counts),'semantic_pass_rate':18/19,'ready_to_freeze':False},ensure_ascii=False))


if __name__=='__main__':
    main()
