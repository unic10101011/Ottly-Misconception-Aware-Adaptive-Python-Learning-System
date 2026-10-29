"""Apply saved human adjudication without changing original reviews or AI data."""
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
REVIEW=HERE.parent/'core72-review-2026-10-29'
DESIGN=HERE.parent/'core72-2026-10-29'
RUN=HERE.parent/'core72-live-2026-10-29'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def verify(root,entries):
    for f in entries:
        assert hashlib.sha256((root/f['path']).read_bytes()).hexdigest()==f['sha256'],f['path']


def main():
    assert not (HERE/'final-summary.json').exists(),'Refusing to overwrite finalized results; create a new report version.'
    verify(DESIGN,read(DESIGN/'design-lock.json')['files'])
    verify(RUN,read(RUN/'evidence-manifest.json')['files'])
    verify(REVIEW,read(REVIEW/'review-manifest.json')['immutable_files'])
    comparison=read(REVIEW/'review-comparison.json')
    for f in comparison['sources']:
        source=HERE.parents[2]/f['source']
        assert hashlib.sha256(source.read_bytes()).hexdigest()==f['sha256'],source
    adjudication_path=REVIEW/'分歧核对说明.md'
    original=adjudication_path.read_bytes()
    decisions={}
    for line in original.decode('utf-8').splitlines():
        if not re.match(r'^\| G[1-6] \|',line):continue
        cells=[x.strip() for x in line.split('|')[1:-1]]
        assert len(cells)==5 and cells[3] and cells[4],cells
        assert cells[0] not in decisions,cells[0]
        assert not re.search(r'C\d\d-R',cells[3]),'Per-trial exception requires explicit handling.'
        if '不通过' in cells[3]:qualified=False
        elif cells[3].startswith('通过'):qualified=True
        else:raise ValueError('Unrecognized adjudication: '+cells[3])
        decisions[cells[0]]={'group':cells[0],'trial_count':int(cells[1]),'recorded_proposal':cells[2],
                             'human_decision':cells[3],'signed_by_and_date':cells[4],
                             'qualified':qualified}
    assert set(decisions)=={f'G{i}' for i in range(1,7)}
    assert [decisions[f'G{i}']['qualified'] for i in range(1,7)]==[True,False,False,False,True,True]
    (HERE/'adjudication.snapshot.txt').write_bytes(original)
    dataset=read(DESIGN/'cases.json'); run=read(RUN/'responses.json'); runtime=read(RUN/'summary.json')
    cases={c['id']:c for c in dataset['cases']}
    comps={c['trial_id']:c for c in comparison['comparisons']}
    proposals=read(REVIEW/'adjudication-proposals.json')
    group_by_trial={key:g for g,data in proposals['groups'].items() for key in data['ids']}
    assert len(group_by_trial)==25
    for g,data in proposals['groups'].items():
        assert len(data['ids'])==decisions[g]['trial_count']
    rows=[]
    for trial in run['trials']:
        key=trial['trial_id']; case=cases[trial['case_id']]; comp=comps[key]
        kind=case['expected']['feedback_kind']
        ready=comp['ai_ready']; group=group_by_trial.get(key)
        reference_scores=dict(comp['B']['scores'])
        if group:
            final='通过' if decisions[group]['qualified'] else '不通过'
            # G6 explicitly rejected the Codex draft recommendation: use the
            # human's pass/readability decision, never proposed 1/1 fact scores.
            if group!='G6':
                reference_scores.update(proposals['groups'][group]['scores'])
            else:
                reference_scores.update({'correctness':'2','readability':'1'})
            origin='人工组别裁决：'+group
            reason=decisions[group]['human_decision']
        else:
            assert comp['A']['conclusion']==comp['B']['conclusion'],key
            assert not comp['score_differences'],key
            final=comp['B']['conclusion']; origin='两份原表一致'; reason=comp['B']['notes']
        if not ready:
            assert final in {'正确跳过','调用失败未评分'}
        else:
            assert final in {'通过','不通过'}
        if final=='通过':
            assert reference_scores['correctness']=='2' and reference_scores['evidence']=='2'
            assert reference_scores['answer_protection']=='2' and reference_scores['readability'] in {'1','2'}
            assert reference_scores['tag']=='2' or kind=='guidance' and reference_scores['tag']=='不适用'
        notes=[]
        if key=='C08-R1':notes.append('G6裁决通过、易懂1；原hint比较对象表述的核对争议仍保留，不声称原文已修复。')
        if key=='C64-R1':notes.append('G4明确裁定标签不通过；B的答案保护2仅作参考，未把组别裁决冒记为全维度重打分。')
        if group=='G2':issue='direct_replacement_code'
        elif group=='G3':issue='run_input_domain_explanation'
        elif group=='G4':issue='frozen_tag_mismatch'
        else:issue=None
        rows.append({'trial_id':key,'case_id':trial['case_id'],'round':trial['round'],'level_no':case['level_no'],
                     'feedback_kind':kind,'effective_feedback':ready,'technical_passed':trial['technical_passed'],
                     'original_A':comp['A'],'original_B':comp['B'],'decision_group':group,
                     'decision_origin':origin,'human_decision_text':reason,'final_conclusion':final,
                     'reference_scores_B_with_adjudicated_dimensions':reference_scores,
                     'score_note':'辅助呈现原分与已裁定维度；最终指标按人工结论计算，不冒记所有维度均被重新评分。',
                     'issue_category':issue,'retained_notes':notes,'evidence_link':comp['evidence_link']})
    assert len(rows)==120 and len({r['trial_id'] for r in rows})==120
    counts=Counter(r['final_conclusion'] for r in rows)
    assert counts=={'通过':91,'不通过':9,'正确跳过':16,'调用失败未评分':4},counts
    rounds=[]
    for rnd in [1,2,3]:
        trials=[r for r in rows if r['round']==rnd]
        expected=[r for r in trials if r['feedback_kind'] in {'diagnosis','guidance'}]
        effective=[r for r in trials if r['effective_feedback']]
        qualified=sum(r['final_conclusion']=='通过' for r in effective)
        rounds.append({'round':rnd,'trial_count':len(trials),'ai_expected':len(expected),'effective_feedback':len(effective),
                       'qualified':qualified,'not_qualified':len(effective)-qualified,
                       'no_feedback':len(expected)-len(effective),'controls':len(trials)-len(expected),
                       'effective_return_rate':len(effective)/len(expected),
                       'semantic_pass_rate':qualified/len(effective),'end_to_end_semantic_rate':qualified/len(expected)})
    assert [r['qualified'] for r in rounds]==[48,21,22]
    stability=[]
    for key in dataset['repeat_case_ids']:
        trials=[r for r in rows if r['case_id']==key]
        assert len(trials)==3
        stability.append({'case_id':key,'effective_feedback':sum(t['effective_feedback'] for t in trials),
                          'qualified':sum(t['final_conclusion']=='通过' for t in trials),
                          'outcomes':[t['final_conclusion'] for t in trials]})
    tags=[]
    for r in rows:
        if r['effective_feedback'] and r['feedback_kind']=='diagnosis':
            trial=next(t for t in run['trials'] if t['trial_id']==r['trial_id'])
            actual=trial['final_analysis']['content']['misconception_tag']; case=cases[r['case_id']]
            tags.append({'trial_id':r['trial_id'],'actual':actual,'allowed':case['human_oracle']['acceptable_tags'],
                         'matches':actual in case['human_oracle']['acceptable_tags']})
    summary={'status':'human_adjudication_finalized_with_recorded_failures','created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
             'application_baseline':dataset['application_baseline'],'dataset_sha256':run['dataset_sha256'],
             'adjudication_source':'adjudication.snapshot.txt','adjudication_sha256':hashlib.sha256(original).hexdigest(),
             'human_reviewers':2,'adjudication_signatures':sorted({d['signed_by_and_date'] for d in decisions.values()}),
             'interpretation_note':'Signature C is the saved adjudicator label, not a claim of a third independent rating.',
             'conclusions':dict(counts),'rounds':rounds,'aggregate_including_repeats':{
                 'ai_expected':104,'effective_feedback':100,'qualified':91,
                 'effective_return_rate':100/104,'semantic_pass_rate':91/100,'end_to_end_semantic_rate':91/104},
             'primary_first_round_semantic_target':{'target':.90,'observed':48/53,'met':48/53>=.90,
                 'scope':'Team predeclared semantic target only; not all acceptance requirements passed.'},
             'overall_all_requirements_passed':False,'open_quality_failures':9,'displayed_replacement_code_trials':4,
             'provider_calls':runtime['provider_calls'],'provider_usage_totals':runtime['provider_usage_totals'],
             'cost':None,'cost_note':runtime['cost_note'],'ai_trial_end_to_end_seconds':runtime['ai_trial_end_to_end_seconds'],
             'stability':{'groups':24,'three_effective_feedback':sum(t['effective_feedback']==3 for t in stability),
                          'three_qualified':sum(t['qualified']==3 for t in stability),'items':stability,
                          'note':'Counts of three available/qualified outputs, not a separate human rating of phrase-level cause consistency.'},
             'tag_allowed_set_matches':{'effective_diagnoses':len(tags),'matched':sum(t['matches'] for t in tags),
                                       'actual_distribution':dict(Counter(t['actual'] for t in tags)),'items':tags},
             'retained_adjudication_difference':{'trial_id':'C08-R1','group':'G6','human_conclusion':'通过，错因不易懂但分析正确',
                 'disposition':'Honor human judgment; preserve original wording and the Codex factual-wording concern. No original output rewritten.'}}
    write_json('adjudication-decisions.json',{'source_sha256':summary['adjudication_sha256'],'groups':decisions})
    write_json('final-reviews.json',{'status':summary['status'],'rows':rows})
    write_json('final-summary.json',summary)
    table=['# 120个试次最终裁决记录','',
           '本表追加最终结论，不覆盖两位原评分或任何模型响应。分数字段只是原表与已裁定维度的辅助呈现，正式指标按人工最终结论统计。','',
           '| 试次 | 原A结论 | 原B结论 | 裁决来源 | 最终结论 | 原文证据 |', '|---|---|---|---|---|---|']
    for r in rows:
        table.append(f"| {r['trial_id']} | {r['original_A']['conclusion']} | {r['original_B']['conclusion']} | {r['decision_group'] or '一致'} | {r['final_conclusion']} | [查看]({r['evidence_link']}) |")
    table += ['', 'G6：C08-R1按人工裁决通过，易懂1；原句表述争议保留，不宣称已经修改AI输出。',
              '', 'G4：C10-R1、C64-R1因标签不符合冻结允许集合而不通过。C64的保护项未被单独裁定，不影响该条不通过结论。','']
    (HERE/'最终逐条记录.md').write_text('\n'.join(table)+'\n',encoding='utf-8')
    report=['# 72条核心验收与关键重复：人工裁决定稿','',
            '**人工裁决记录已完成；首轮语义合格率达到预设90%数值目标，但仍有9个可展示反馈不合格、4次未取得可展示反馈。本轮不能表述为全项通过。**','',
            '应用基线：`acceptance-baseline-2026-10-29` / `d668fe4`；两位独立人工复核，最终裁决署名原文为`C-2026-10-29`。本次没有追加AI调用或修改应用。','',
            '[最终逐条记录](最终逐条记录.md) · [人工裁决原件](../core72-review-2026-10-29/分歧核对说明.md) · [真实调用证据](../core72-live-2026-10-29/真实调用汇总.md)','',
            '## 正式统计口径','',
            '72个不同样例首轮各运行1次，另有24个预选关键样例各追加2次，共120个试次。应产生AI反馈104次，实际可展示100次；16个正确跳过/成功运行对照不计AI语义分母。4次无可展示反馈继续计入端到端分母。', '',
            '| 范围 | 应有AI反馈 | 可展示反馈 | 人工合格 | 有效返回率 | 语义合格率 | 端到端语义合格率 |',
            '|---|---:|---:|---:|---:|---:|---:|']
    for r in rounds:
        report.append(f"| R{r['round']} | {r['ai_expected']} | {r['effective_feedback']} | {r['qualified']} | {r['effective_return_rate']:.1%} | {r['semantic_pass_rate']:.1%} | {r['end_to_end_semantic_rate']:.1%} |")
    report += ['| 合计（含重复） | 104 | 100 | 91 | 96.2% | 91.0% | 87.5% |','',
               '首轮主结果是48/53=90.6%，端到端为48/56=85.7%。含重复的91/100不能替代首轮结果，也不能称为100条独立样本。16个无AI对照全部符合预期。', '',
               '最终120个试次：91通过、9不通过、16正确跳过、4调用失败未评分。正式语义合格率按预设的正确性、证据、标签、答案保护综合口径计算；本轮可评分的易懂项均至少1，因此其分子也与人工综合通过数相同。','',
               '## 裁决如何生效','',
               '六组共25个核对项均已裁决：G1与G5通过；G2与G3不通过；G4标签部分不通过，按冻结通过条件整条不通过；G6通过。其他95行沿用两位一致结论，其中75行为可展示反馈、16行为对照、4行为未评分。', '',
               '**G6明确不同于此前Codex建议。** C08按人工裁决“通过，错因不易懂但分析正确”计入，保留B原表易懂1。原hint中输入/实际输出比较对象的表述争议仍保存在原文与核对记录中，不改写原句，也不宣称该问题已修复。此前建议试算47/53与90/100不再作为最终成绩，正式数值增加1条通过。', '',
               '两份原表、Codex建议、原始运行summary及其历史pending状态均保留为当时快照。本目录是追加的最终结果；不覆盖过去文件。adjudication.snapshot.txt保存填写完成的裁决原字节与指纹。','',
               '## 未通过及未返回项','', '| 试次 | 最终状态 | 原因 |', '|---|---|---|']
    reasons={'direct_replacement_code':'提供可直接复制的修正代码（答案保护）',
             'run_input_domain_explanation':'未清晰区分自定义越界输入与题目合法输入域',
             'frozen_tag_mismatch':'返回标签不符合本条冻结允许集合'}
    failure_reason={'C37-R1':'上游连接超时，未取得HTTP响应', 'C40-R1':'候选证据用例/引文不匹配，被校验拦截',
                    'C43-R1':'“公开样例 n=4”触发替换语句规则，保留疑似误拦截线索', 'C01-R2':'候选给出完整修正print代码，被审核拦截'}
    for r in rows:
        if r['final_conclusion'] in {'不通过','调用失败未评分'}:
            reason=reasons.get(r['issue_category'],failure_reason.get(r['trial_id'],''))
            report.append(f"| [{r['trial_id']}]({r['evidence_link']}) | {r['final_conclusion']} | {reason} |")
    report += ['', '9个未通过反馈对应5个不同样例：C10、C24、C28、C54、C64。重复试次按实际次数计入，不把重复失败误写成9种独立缺陷。', '',
               '## 重复、标签与耗时','',
               f"24组关键重复中，三次均有可展示反馈22组，三次均人工合格{summary['stability']['three_qualified']}组；这是可用/合格次数统计，不冒充另行进行过的主错因一致性评分。", '',
               f"可展示diagnosis共{len(tags)}次，其中{sum(t['matches'] for t in tags)}次符合预定标签允许集合；guidance不产生诊断标签，不纳入分类分母。other返回分布保存在final-summary.json，不将other一律当成具体分类成功。", '',
               '104个应有AI反馈试次的端到端耗时中位数5.935秒、P95为9.074秒、最大27.091秒；包括本轮记录器转发开销，不含注册和前置关卡准备。', '',
               '实际provider请求149次，其中148次HTTP 200、1次连接超时；记录token总量234052（输入163228、输出70824），缓存细项见原始usage。实际账单费用未返回，保持未记录；model_load_ms=0不作实测推理耗时。', '',
               '## 当前结论与后续','',
               '本轮人工复核与裁决已闭环，语义合格率的预设数值目标达到。直接修正代码、标签匹配和运行输入域解释仍有已确认的不合格反馈，因此整体不能宣称全部验收通过。C08文字准确性与C43疑似误拦截作为保留问题继续跟踪。', '',
               '后续修补应另立应用版本并复测，保留本轮所有失败与分母；这套数据已经用于排障，不能继续声称是新版本未见验收集。推荐、出题、问答与回放专项以及24条对照仍是后续独立步骤，本报告不代替它们。', '',
               '## 文件','', '- final-summary.json：正式分轮指标与裁决来源。',
               '- final-reviews.json、最终逐条记录.md：120条最终结论与原A/B记录。',
               '- adjudication-decisions.json、adjudication.snapshot.txt：六组裁决与原件快照。',
               '- final-manifest.json：来源与交付文件指纹。','']
    (HERE/'人工验收定稿.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    source_files=[DESIGN/'design-lock.json',RUN/'evidence-manifest.json',REVIEW/'review-manifest.json',adjudication_path]
    manifest={'status':summary['status'],'files':[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='final-manifest.json'],
              'sources':[{'path':str(p.relative_to(HERE.parents[2])).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in source_files]}
    write_json('final-manifest.json',manifest)
    print(json.dumps({'conclusions':dict(counts),'rounds':rounds,'stability':{k:v for k,v in summary['stability'].items() if k!='items'},
                      'tags':{k:v for k,v in summary['tag_allowed_set_matches'].items() if k!='items'}},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
