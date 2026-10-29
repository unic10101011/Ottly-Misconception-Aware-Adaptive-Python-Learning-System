"""Compare two human review snapshots; never overwrite scores or run evidence."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
DESIGN=HERE.parent/'core72-2026-10-29'
RUN=HERE.parent/'core72-live-2026-10-29'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def parse(path):
    rows={}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not re.match(r'^\| C\d{2}-R[123] \|',line):
            continue
        cells=[x.strip() for x in line.split('|')[1:-1]]
        if len(cells)==4:
            continue  # B's separate adjudication table repeats trial IDs.
        assert len(cells)==10,(path,cells)
        trial=cells[0]
        assert trial not in rows,trial
        rows[trial]={'scores':dict(zip(['correctness','evidence','tag','readability','answer_protection'],cells[3:8])),
                     'conclusion':cells[8],'notes':cells[9]}
    return rows


def normalized(row,kind):
    scores=dict(row['scores'])
    if kind=='guidance' and scores['tag']=='不适用':
        scores['tag']='2'
    return scores


def main():
    sources=[('A','人工验收表.md','review-A.snapshot.txt'),('B','人工验收表(1).md','review-B.snapshot.txt')]
    provenance=[]
    reviews=[]
    for label,name,snapshot in sources:
        source=DESIGN/name
        if not (HERE/snapshot).exists():
            (HERE/snapshot).write_bytes(source.read_bytes())
        assert (HERE/snapshot).read_bytes()==source.read_bytes(),'Source changed since snapshot; use a new report version.'
        provenance.append({'reviewer':label,'source':str(source.relative_to(HERE.parents[2])).replace('\\','/'),
                           'snapshot':snapshot,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                           'identity':'unic' if label=='A' else '第二位独立复核人（未署名，用户已澄清非unic）'})
        reviews.append(parse(HERE/snapshot))
    dataset=load(DESIGN/'cases.json')
    cases={c['id']:c for c in dataset['cases']}
    run=load(RUN/'responses.json')
    trials={t['trial_id']:t for t in run['trials']}
    assert len(trials)==120
    for rows in reviews:
        assert rows.keys()==trials.keys()
        for key,row in rows.items():
            ready=(trials[key].get('final_analysis') or {}).get('status')=='ready'
            if ready:
                assert all(v in {'0','1','2','不适用'} for v in row['scores'].values()),key
            else:
                expected='正确跳过' if cases[key[:3]]['expected']['feedback_kind'] in {'skipped','none'} else '调用失败未评分'
                assert row['conclusion']==expected,(key,row)
    # All source design and provider evidence stays exactly as initially locked.
    for root,manifest in [(DESIGN,'design-lock.json'),(RUN,'evidence-manifest.json')]:
        for f in load(root/manifest)['files']:
            assert hashlib.sha256((root/f['path']).read_bytes()).hexdigest()==f['sha256'],f['path']
    substantive=[]
    comparisons=[]
    for key,t in trials.items():
        a,b=[rows[key] for rows in reviews]
        kind=cases[key[:3]]['expected']['feedback_kind']
        ready=(t.get('final_analysis') or {}).get('status')=='ready'
        aa,bb=normalized(a,kind),normalized(b,kind)
        differences=[k for k in aa if aa[k]!=bb[k]] if ready else []
        different_conclusion=a['conclusion']!=b['conclusion']
        if differences or different_conclusion:
            substantive.append(key)
        comparisons.append({'trial_id':key,'feedback_kind':kind,'ai_ready':ready,
                            'A':a,'B':b,'score_differences':differences,
                            'conclusion_different':different_conclusion,
                            'evidence_link':f'../core72-live-2026-10-29/逐条结果-L{cases[key[:3]]["level_no"]:02}.md#{key.lower()}'})
    assert len(substantive)==25
    per_reviewer=[]
    for label,rows in zip(['A','B'],reviews):
        rounds=[]
        for rnd in [1,2,3]:
            keys=[k for k,t in trials.items() if t['round']==rnd]
            ready=[k for k in keys if (trials[k].get('final_analysis') or {}).get('status')=='ready']
            passed=sum(rows[k]['conclusion']=='通过' for k in ready)
            expected=sum(cases[k[:3]]['expected']['feedback_kind'] in {'diagnosis','guidance'} for k in keys)
            rounds.append({'round':rnd,'trials':len(keys),'effective_feedback':len(ready),
                           'ai_expected':expected,'passed':passed,'conclusions':dict(Counter(rows[k]['conclusion'] for k in keys))})
        per_reviewer.append({'reviewer':label,'conclusions':dict(Counter(r['conclusion'] for r in rows.values())),
                             'valid_feedback_passed':sum(r['conclusion']=='通过' for r in rows.values()),'rounds':rounds})
    assessment={'status':'pending_final_human_adjudication','created_at':datetime.now(timezone.utc).isoformat(),
                'application_baseline':dataset['application_baseline'],'sources':provenance,
                'reviewer_count':2,'reviewer_identity_note':'User clarified B is a different person; saved B now marks independent review.',
                'trial_count':120,'ai_expected':104,'effective_feedback':100,'controls':16,'call_failures':4,
                'conclusion_differences':sum(x['conclusion_different'] for x in comparisons),
                'substantive_trial_differences':25,
                'normalization':'guidance tag 不适用 and 2 both mean no diagnosis label; non-ready score blanks are excluded.',
                'reviewers':per_reviewer,'comparisons':comparisons,'final_semantic_pass_rate':None}
    save('review-comparison.json',assessment)
    # Quotation checks are literal provenance aids, not semantic grading.
    quote_rows=[]
    def strings(value):
        if isinstance(value,str):return [value]
        if isinstance(value,dict):return [s for v in value.values() for s in strings(v)]
        if isinstance(value,list):return [s for v in value for s in strings(v)]
        return []
    def norm(text):
        return re.sub(r'\s+','',text.replace('`','').replace('\\"','"'))
    for key in substantive:
        actual='\n'.join(strings(trials[key].get('final_analysis') or {}))
        for label,rows in zip(['A','B'],reviews):
            quotes=re.findall('“([^”]+)”',rows[key]['notes'])
            quote_rows.append({'trial_id':key,'reviewer':label,'quotes':[{'quote':q,'literal_match_ignoring_whitespace':norm(q) in norm(actual)} for q in quotes]})
    save('quotation-check.json',{'scope':'Literal matching only; notes may include proposed wording and paraphrases, which are not misquotes by themselves.','items':quote_rows})
    save('review-provenance.json',{'sources':provenance,'original_scores_overwritten':False,
                                  'model_calls_added':0,'application_modified':False})
    groups={
        'G1': {'ids':['C07-R1','C07-R2','C07-R3','C13-R1','C14-R1','C14-R2','C14-R3',
                      'C20-R1','C20-R2','C20-R3','C44-R1','C58-R1','C58-R2','C58-R3'],
               'scores':{'answer_protection':'2'},'conclusion':'通过','reason':'具体诊断解释，不是可复制的替换语句；不套用guidance的全面禁修正口径。'},
        'G2': {'ids':['C28-R1','C54-R1','C54-R2','C54-R3'],
               'scores':{'answer_protection':'0'},'conclusion':'不通过','reason':'实际给出可直接复制到原题的修正代码，超出普通错因解释。'},
        'G3': {'ids':['C24-R1','C24-R2','C24-R3'],
               'scores':{'correctness':'1'},'conclusion':'不通过','reason':'除零证据正确，但未明确区分自定义越界输入与合法题域算法，未充分满足冻结oracle。'},
        'G4': {'ids':['C10-R1','C64-R1'],
               'scores':{'tag':'0'},'conclusion':'不通过','reason':'真实标签不在冻结允许集合内；不修改本轮标签或允许集合。C64的自然语言初始化解释倾向保护2。'},
        'G5': {'ids':['C70-R1'],
               'scores':{'answer_protection':'2'},'conclusion':'通过','reason':'倾向允许diagnosis解释已有变量的对应关系；此项为人工应确认的边界，建议并非最终裁决。'},
        'G6': {'ids':['C08-R1'],
               'scores':{'correctness':'1','evidence':'1','readability':'1'},'conclusion':'不通过','reason':'原文错误地说输入姓名与期望输出大小写不同；应降事实正确性，不能只降易懂。'},
    }
    assert set(k for g in groups.values() for k in g['ids'])==set(substantive)
    proposals=[]
    proposed={k:{**v,'scores':dict(v['scores'])} for k,v in reviews[1].items()}
    for group,g in groups.items():
        for key in g['ids']:
            proposed[key]['scores'].update(g['scores'])
            proposed[key]['conclusion']=g['conclusion']
            proposals.append({'trial_id':key,'group':group,'proposed_scores':proposed[key]['scores'],
                               'proposed_conclusion':g['conclusion'],'reason':g['reason'],
                               'status':'pending_human_adjudication','human_final_decision':None})
    simulation=[]
    for rnd in [1,2,3]:
        keys=[k for k,t in trials.items() if t['round']==rnd]
        effective=[k for k in keys if (trials[k].get('final_analysis') or {}).get('status')=='ready']
        expected=sum(cases[k[:3]]['expected']['feedback_kind'] in {'diagnosis','guidance'} for k in keys)
        passed=sum(proposed[k]['conclusion']=='通过' for k in effective)
        simulation.append({'round':rnd,'proposed_qualified':passed,'effective_feedback':len(effective),
                           'ai_expected':expected,'conditional_semantic_rate':passed/len(effective),
                           'conditional_end_to_end_rate':passed/expected})
    assert [r['proposed_qualified'] for r in simulation]==[47,21,22]
    save('adjudication-proposals.json',{'status':'not_final_human_scores','groups':groups,
           'proposals':proposals,'conditional_if_all_proposals_accepted':{
               'qualified':90,'effective_feedback':100,'ai_expected':104,'rounds':simulation},
           'warning':'90/100 pooled includes repeats; first-round conditional score is 47/53, below 90%. No final result asserted.'})
    doc=['# 逐条分歧及证据核对建议','',
         '**下列为Codex辅助核对建议，尚未替代两位人工原分。最终意见请填入[六组裁决区](分歧核对说明.md)。**','',
         '评分缩写顺序为“正确性／证据／标签／易懂／答案保护”。引导标签的不适用与2只做语义归一化，表中原分保持原样。','',
         '| 试次 | A原分及结论 | B原分及结论 | 分组 | 核对建议 |',
         '|---|---|---|---|---|']
    pmap={p['trial_id']:p for p in proposals}
    for key in substantive:
        pa=pmap[key];a,b=reviews[0][key],reviews[1][key]
        doc.append(f"| [{key}](#{key.lower()}) | {'／'.join(a['scores'].values())}；{a['conclusion']} | {'／'.join(b['scores'].values())}；{b['conclusion']} | {pa['group']} | {pa['proposed_conclusion']}（待人工确认） |")
    for key in substantive:
        a,b=reviews[0][key],reviews[1][key]
        case=cases[key[:3]];t=trials[key];proposal=pmap[key]
        analysis=t['final_analysis']
        actual=(analysis.get('content') or {}).get('suspected_cause') or analysis['guidance']['hint']
        link=next(c['evidence_link'] for c in comparisons if c['trial_id']==key)
        doc += ['',f'<a id="{key.lower()}"></a>',f'## {key} {case["name"]}','',
                f'分组：{proposal["group"]}；反馈类型：{analysis["feedback_kind"]}；[完整实际记录]({link})。','',
                '```python',case['code'].rstrip(),'```','',
                '**实际可展示原文（suspected_cause或hint）**','',actual,'',
                '冻结判断依据：'+case['human_oracle']['cause_or_behavior'],'',
                f"A原分：{'／'.join(a['scores'].values())}；结论：{a['conclusion']}。",'',a['notes'],'',
                f"B原分：{'／'.join(b['scores'].values())}；结论：{b['conclusion']}。",'',b['notes'],'',
                '**核对建议**：'+proposal['reason'],'',
                f"建议分：{'／'.join(proposal['proposed_scores'].values())}；建议结论：{proposal['proposed_conclusion']}。最终人工裁决：未填写。",'']
    doc += ['## 仅供裁决参考的条件试算','',
            '如果人工完整采纳六组建议，试算如下；这些不是已确认的人工成绩。','',
            '| 范围 | 建议合格／有效反馈 | 条件语义合格率 | 建议合格／应有反馈 | 条件端到端合格率 |',
            '|---|---|---:|---|---:|']
    for s in simulation:
        doc.append(f"| R{s['round']} | {s['proposed_qualified']}/{s['effective_feedback']} | {s['conditional_semantic_rate']:.1%} | {s['proposed_qualified']}/{s['ai_expected']} | {s['conditional_end_to_end_rate']:.1%} |")
    doc += ['| 合计（含重复） | 90/100 | 90.0% | 90/104 | 86.5% |','',
            '**首轮条件试算47/53=88.7%，低于预定90%目标。不能用含重复合计的90%替代首轮成绩，更不能写成验收已达标。**',
            '', '四条调用失败继续计入应有反馈分母；16条正确跳过不计AI语义分母。最终指标仍待人工裁决，原始调用汇总保持不变。','']
    (HERE/'逐条分歧表.md').write_text('\n'.join(doc)+'\n',encoding='utf-8')
    print(json.dumps({'reviewers':per_reviewer,'substantive_differences':25,'conclusion_differences':assessment['conclusion_differences']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
