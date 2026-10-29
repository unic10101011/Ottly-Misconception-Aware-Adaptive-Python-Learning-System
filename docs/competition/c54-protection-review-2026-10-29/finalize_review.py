"""Finalize saved human scores without rewriting reviews, AI evidence or old results."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
FIX=HERE.parent/'c54-protection-fix-2026-10-29'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def write(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    assert not (HERE/'human-review-summary.json').exists(),'Do not overwrite finalized human results.'
    for entry in read(FIX/'manifest.json')['files']:
        assert sha(FIX/entry['path'])==entry['sha256'],entry['path']
    source=FIX/'人工复测检查表.md'
    original=source.read_bytes()
    text=original.decode('utf-8')
    assert re.search(r'复核人：_*A_*；',text) and '2026-10-29' in text
    run=read(FIX/'final/real-ai-results.json')
    trials={t['trial_id']:t for t in run['trials']}
    rows=[]
    for line in text.splitlines():
        match=re.match(r'^\| \[(C\d{2}-R[123])\]',line)
        if not match:continue
        cells=[c.strip() for c in line.split('|')[1:-1]]
        assert len(cells)==9,cells
        key=match[1];result=trials[key]['result']
        scores=dict(zip(['correctness','evidence','tag','readability','answer_protection'],cells[2:7]))
        assert cells[1]==f"{result['feedback_kind']} / {result['status']}",key
        if result['status']=='skipped':
            assert cells[7]=='正确跳过'
            assert set(scores.values()) <= {'','不适用'}
            normalized={name:'不适用' for name in scores}
            qualified=None
        else:
            assert result['status']=='ready'
            assert set(scores.values()) <= {'0','1','2','不适用'}
            normalized=dict(scores)
            qualified=(scores['correctness']==scores['evidence']==scores['answer_protection']=='2'
                       and scores['readability'] in {'1','2'}
                       and (scores['tag']=='2' or result['feedback_kind']=='guidance' and scores['tag']=='不适用'))
            assert cells[7]==('通过' if qualified else '不通过'),key
        rows.append({'trial_id':key,'feedback_kind':result['feedback_kind'],'status':result['status'],
                     'original_scores':scores,'normalized_scores':normalized,
                     'score_note':'正确跳过项原表留空的评分仅在统计中记不适用，未改原表。',
                     'conclusion':cells[7],'notes':cells[8],'qualified':qualified})
    assert len(rows)==len({r['trial_id'] for r in rows})==12
    assert {r['trial_id'] for r in rows}==set(trials)
    counts=Counter(r['conclusion'] for r in rows)
    assert counts=={'通过':11,'正确跳过':1},counts
    gates=read(FIX/'final/review-gate-results.json')
    assert gates['passed']==gates['total']==9
    software=read(FIX/'summary.json')['regression']
    state=read(FIX/'application-state-final.json')
    root=HERE.parents[2]
    for entry in state['files']:
        assert hashlib.sha256((root/entry['path']).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==entry['sha256_lf']
    (HERE/'human-review.snapshot.txt').write_bytes(original)
    summary={'status':'scoped_c54_retest_human_passed','created_at':datetime.now(timezone.utc).isoformat(),
             'reviewer':'A','human_reviewers_this_retest':1,'review_date':'2026-10-29',
             'source_sha256':sha(source),'conclusions':dict(counts),'trial_count':12,
             'distinct_case_count':len({r['trial_id'].split('-')[0] for r in rows}),
             'ai_expected':11,'effective_feedback':11,'human_qualified':11,'human_not_qualified':0,
             'semantic_pass_rate':1.0,'end_to_end_semantic_rate':1.0,'correct_skip_controls':1,
             'c54_repeats_qualified':3,'answer_protection_for_c54':[2,2,2],
             'c54_known_issue_closed_in_this_retest':True,
             'c24_domain_observation':'Passed this trial; no claim of broader repeated stability.',
             'review_gates':{'matched':9,'total':9,'additional_human_rating_rows':0},
             'software_regression':software,'application_source_digest':state['app_source_digest'],
             'eligible_for_repair_freeze_stage':True,'all_project_acceptance_complete':False,
             'independent_unseen_acceptance':False,'original_core72_and_18_of_19_results_preserved':True,
             'application_modified_this_turn':False,'real_ai_calls_added_this_turn':0,
             'new_freeze_tag_created':False,'committed_or_pushed_this_turn':False,
             'remaining_stages':['Freeze the repair version','Recommendation/generation/chat/replay acceptance','24 comparative cases','Final report']}
    write('human-review-summary.json',summary)
    write('human-review-rows.json',{'reviewer':'A','rows':rows})
    by_id={r['trial_id']:r for r in rows}
    report=['# C54答案保护修复：人工复测定稿','',
            '**本轮人工审核通过：11条AI反馈合格，另1条正确跳过。C54三次重复的答案保护均为2分，已知C54-R3问题在本轮定向复测中关闭，可以进入修复版本冻结阶段。**','',
            '复核人A，日期2026-10-29；本轮为1位人工复核人的评分。Codex核对填写完整性、分数与结论、反馈原文和证据指纹，不计作第二位独立人工复核。','',
            '| 指标 | 结果 |','|---|---:|','| 总试次 / 不同样例 | 12 / 10 |',
            '| 应有 / 可展示AI反馈 | 11 / 11 |','| 人工语义合格 | 11/11（本次定向复测100%） |',
            '| 端到端语义合格 | 11/11 |','| 正确跳过对照 | 1/1 |','| C54三次重复合格 | 3/3 |','',
            '本轮包含重复与已用于排障的样例，不是12个独立未见样本。11/11只用于本次定向复测，不代表全系统准确率，也不覆盖旧72条首轮48/53、含重复91/100和上一轮修复复测18/19的人工结果。','',
            '## 本轮问题关闭依据','',
            'C54三条均正确解释saved未更新导致条件持续成立和超时，没有再指定具体变量更新动作与更新量。人工三条均将答案保护评为2分；正常概念解释、已有代码观察和错误证据均通过。','']
    for key in ['C54-R1','C54-R2','C54-R3']:
        cause=trials[key]['result']['content']['suspected_cause']
        report += [f'- {key}实际诊断：{cause}']
    report += ['', 'C24-R3本次明确说明异常来自越界输入，不能据此断言合法输入下算法错误或要求额外防御代码，人工已评为通过。本次观察项达标，不将单次结果扩大为所有输入或重复均稳定的结论。','',
               '固定候选的真实审核对照9/9符合预期：旧问题与两种同义修正步骤被拦截，六条正常解释得到放行，包含D06范围表达式。这是模型审核行为对照，不另加9条人工语义评分。','',
               '## 软件版本与范围','',
               '沿用同一源码版本的636项后端测试通过、9个子测试通过、1项专用MySQL迁移测试跳过；149项相关回归已包含在完整套件内。源码指纹与本轮真实复测记录一致。此前构建、启动、健康和数据条数检查见修复报告，本次没有重新调用AI或修改应用。','',
               '人工原表完整保留。C05正确跳过项评分为空，统计中按不适用处理，不补写原表，也不计AI语义分母。原阶段报告中的pending状态保留为当时快照，本目录是追加的人工定稿。','',
               '## 逐条最终结果','',
               '| 试次 | 正确性 | 证据 | 标签 | 易懂 | 答案保护 | 最终结论 |',
               '|---|---:|---:|---|---:|---:|---|']
    for row in rows:
        key=row['trial_id'];s=row['normalized_scores']
        report.append(f"| [{key}](../c54-protection-fix-2026-10-29/真实AI复测逐条结果.md#{key.lower()}) | {s['correctness']} | {s['evidence']} | {s['tag']} | {s['readability']} | {s['answer_protection']} | {row['conclusion']} |")
    report += ['', '## 来源与下一步','',
               '- [人工原表](../c54-protection-fix-2026-10-29/人工复测检查表.md)、[原表字节快照](human-review.snapshot.txt)。',
               '- [真实反馈与固定审核对照](../c54-protection-fix-2026-10-29/真实AI复测逐条结果.md)、[软件修复记录](../c54-protection-fix-2026-10-29/修复与复测报告.md)。',
               '- human-review-summary.json提供统计与范围，human-review-rows.json保留原分与归一化统计，review-manifest.json锁定来源。','',
               '当前可冻结修复版本，随后进行推荐、出题、问答与回放专项，再完成24条方案对照及报告。该结论不等于这些后续验收已经通过；本次尚未创建新冻结标签，也未提交或推送代码。','']
    (HERE/'人工复测定稿.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    sources=[source,FIX/'manifest.json',FIX/'final/real-ai-results.json',FIX/'final/review-gate-results.json',FIX/'application-state-final.json']
    write('review-manifest.json',{'status':summary['status'],
        'files':[{'path':p.name,'sha256':sha(p)} for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='review-manifest.json'],
        'sources':[{'path':p.relative_to(HERE.parent).as_posix(),'sha256':sha(p)} for p in sources]})
    assert source.read_bytes()==original,'Never rewrite human input.'
    print(json.dumps({'conclusions':dict(counts),'human_semantic_pass_rate':'11/11','c54_repeats':'3/3',
                      'eligible_for_repair_freeze_stage':True},ensure_ascii=False))


if __name__=='__main__':main()
