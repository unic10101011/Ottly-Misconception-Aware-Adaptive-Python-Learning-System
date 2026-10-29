"""Render immutable run evidence and update only blank human review result links."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics

HERE=Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def lines(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]


def write(path, text):
    path.write_text(text+'\n',encoding='utf-8')


def percentile(values, q):
    return round(sorted(values)[max(0, math.ceil(q*len(values))-1)],3) if values else None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-dir',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args()
    dataset=read(HERE/'cases.json')
    design_lock=read(HERE/'design-lock.json')
    for f in design_lock['files']:
        assert hashlib.sha256((HERE/f['path']).read_bytes()).hexdigest()==f['sha256']
    report=read(a.evidence_dir/'responses.json')
    assert report['status']=='completed' and len(report['trials'])==120
    assert report['dataset_sha256']==hashlib.sha256((HERE/'cases.json').read_bytes()).hexdigest()
    assert not a.output_dir.exists(), 'Refusing to overwrite run report'
    a.output_dir.mkdir(parents=True)
    cases={c['id']:c for c in dataset['cases']}
    providers=lines(a.evidence_dir/'provider-calls.jsonl')
    acceptance=lines(a.evidence_dir/'acceptance.jsonl')
    audit=[]
    data_dir=HERE.parents[2]/'backend/app/data'
    for call in providers:
        case=cases[call['trial_id'].split('-')[0]]
        body=call['request']
        facts,_=json.JSONDecoder().raw_decode(body['messages'][-1]['content'])
        lesson=read(data_dir/(case['problem_id']+'.json'))
        allowed={x['case_id']:x for x in lesson['tests'] if x['visibility']=='public'}
        if case['mode']=='run':
            allowed={'run':{'stdin':case['stdin'],'expected_output':''}}
        checks={'student_code_is_trial':facts.get('student_code')==case['code'],
                'model_parameters_match':body.get('model')=='deepseek-flash' and body.get('thinking')=={'type':'enabled'} and body.get('reasoning_effort')=='high' and body.get('max_tokens')==8192,
                'human_oracle_not_sent':all(k not in json.dumps(facts,ensure_ascii=False) for k in ['"human_oracle"','"cause_or_behavior"','"preferred_tag"','"acceptable_tags"','"reference_solution"']),
                'problem_has_no_private_tests':not any(k in facts.get('problem',{}) for k in ['tests','function_tests','reference_solution','solution_explanation']),
                'history_empty':not facts.get('related_history')}
        checks['failed_cases_public_only']=all(c['case_id'] in allowed and c.get('stdin')==allowed[c['case_id']]['stdin'] and c.get('expected_output')==allowed[c['case_id']]['expected_output'] for c in facts.get('failed_cases',[]))
        checks['allowed_evidence_public_ids']=all(e['case_id'] in allowed for e in facts.get('allowed_evidence',[]))
        checks['guidance_cases_public_only']=all(any(c.get('stdin')==x['stdin'] and c.get('expected_output')==x['expected_output'] for x in allowed.values()) for c in facts.get('public_cases',[]))
        audit.append({'call_id':call['call_id'],'trial_id':call['trial_id'],'checks':checks,'passed':all(checks.values())})
    # Do not write provider request headers or complete response JSON; the observer
    # records an explicit allowlist excluding credentials and reasoning_content.
    payload_audit={'calls':len(audit),'passed':sum(c['passed'] for c in audit),'items':audit,
                   'scope':'Structural/public-case boundary checks; not a human semantic assessment.'}
    write(a.output_dir/'payload-audit.json',json.dumps(payload_audit,ensure_ascii=False,indent=2))
    for name in ['responses.json','provider-calls.jsonl','acceptance.jsonl','runtime-before.json',
                 'execution-lock.json','counts-before.json','counts-after.json','runtime-after.json']:
        if (a.evidence_dir/name).exists():
            shutil.copyfile(a.evidence_dir/name,a.output_dir/name)
    def valid(t):
        analysis=t.get('final_analysis') or {}
        return analysis.get('status')=='ready' and analysis.get('source')=='ai' and t['checks'].get('feedback_route_matches') and t['checks'].get('feedback_shape_matches')
    def needs_ai(t):
        return cases[t['case_id']]['expected']['feedback_kind'] in {'diagnosis','guidance'}
    rounds=[]
    for rnd in [1,2,3]:
        trials=[t for t in report['trials'] if t['round']==rnd]
        ai=[t for t in trials if needs_ai(t)]
        rounds.append({'round':rnd,'trials':len(trials),'ai_expected':len(ai),'valid_ai':sum(bool(valid(t)) for t in ai),
                       'controls':len(trials)-len(ai),'technical_passed':sum(t['technical_passed'] for t in trials),
                       'statuses':dict(Counter((t.get('final_analysis') or {}).get('status','no_analysis') for t in trials))})
    usage=Counter()
    for call in providers:
        for key,value in ((call.get('response') or {}).get('usage') or {}).items():
            if type(value) is int:
                usage[key]+=value
    summary={'planned_trials':120,'completed_trials':len(report['trials']),'rounds':rounds,
             'ai_expected':sum(needs_ai(t) for t in report['trials']),
             'valid_ai':sum(bool(valid(t)) for t in report['trials'] if needs_ai(t)),
             'technical_passed':sum(t['technical_passed'] for t in report['trials']),
             'provider_calls':len(providers),'provider_http_statuses':dict(Counter(str(c['http_status']) for c in providers)),
             'provider_response_models':dict(Counter((c.get('response') or {}).get('model') for c in providers)),
             'provider_usage_totals':dict(usage),'payload_audit_passed':all(x['passed'] for x in audit),
             'human_semantic_review':'pending','semantic_pass_rate':None,'end_to_end_semantic_rate':None,
             'cost':None,'cost_note':'Token usage captured; actual billed cost not returned by provider response.'}
    before=read(a.evidence_dir/'counts-before.json')
    after=read(a.evidence_dir/'counts-after.json')
    setup_count=sum(len(t['setup']) for t in report['trials'])
    submitted=sum(t.get('submit_response') is not None for t in report['trials'])
    accounts=sum(t.get('account') is not None for t in report['trials'])
    summary['record_counts']={'new_synthetic_accounts':accounts,'setup_submissions':setup_count,
                              'target_submissions':submitted,'database_before':before,'database_after':after,
                              'user_delta_matches':after['users']-before['users']==accounts,
                              'submission_delta_matches':after['learning_submissions']-before['learning_submissions']==setup_count+submitted}
    for label,values in [
        ('target_end_to_end',[t['timings_seconds']['target_end_to_end'] for t in report['trials'] if 'target_end_to_end' in t['timings_seconds']]),
        ('ai_trial_end_to_end',[t['timings_seconds']['target_end_to_end'] for t in report['trials'] if needs_ai(t) and 'target_end_to_end' in t['timings_seconds']]),
        ('submission_judge',[t['submit_response']['timings']['judge_ms']/1000 for t in report['trials'] if t.get('submit_response')]),
        ('feedback_endpoint',[t['timings_seconds']['feedback_endpoint'] for t in report['trials'] if 'feedback_endpoint' in t['timings_seconds']]),
        ('provider_call',[c['seconds'] for c in providers])]:
        summary[label+'_seconds']={'n':len(values),'median':round(statistics.median(values),3) if values else None,'p95_nearest_rank':percentile(values,.95),'max':max(values) if values else None}
    stability=[]
    for case_id in dataset['repeat_case_ids']:
        group=[t for t in report['trials'] if t['case_id']==case_id]
        stability.append({'case_id':case_id,'trials':[t['trial_id'] for t in group],
                          'valid_feedback':sum(bool(valid(t)) for t in group),
                          'statuses':[(t.get('final_analysis') or {}).get('status') for t in group],
                          'human_semantic_consistency':'pending'})
    summary['stability']=stability
    write(a.output_dir/'summary.json',json.dumps(summary,ensure_ascii=False,indent=2))
    by_accept={r['record_id']:r for r in acceptance}
    for level in range(1,13):
        doc=[f'# 第{level:02}关真实AI逐条结果','',
             '本页只整理真实响应和自动检查，人工语义结论尚未填写。被拦截候选的正文只保存在排障原始日志中，不作为学生已看到的反馈评分。','']
        for t in report['trials']:
            c=cases[t['case_id']]
            if c['level_no']!=level:
                continue
            analysis=t.get('final_analysis') or {}
            doc += [f'<a id="{t["trial_id"].lower()}"></a>',f'## {t["trial_id"]} {c["name"]}','',
                    f"[设计与判断依据](../core72-2026-10-29/72条样例设计.md#{c['id'].lower()})；方式：{c['mode']}；实际AI状态：`{analysis.get('status','无分析字段')}`；自动检查：{'通过' if t['technical_passed'] else '未全部通过'}。",'',
                    '```python',c['code'].rstrip(),'```','',
                    '**人工判断依据**：'+c['human_oracle']['cause_or_behavior'],'',
                    '禁止声称：'+'；'.join(c['human_oracle']['forbidden_claims']),'']
            if c['mode']=='submit':
                data=t.get('submit_response') or {}
                judge=data.get('judge') or {}
                doc += [f"实际判题：`{judge.get('status')}`，{judge.get('passed_cases')}/{judge.get('total_cases')}；提交ID：{data.get('submission_id')}。",'']
                public=[x for x in judge.get('cases',[]) if x['visibility']=='public']
                lesson=read(data_dir/(c['problem_id']+'.json'))
                for obs in public:
                    stdin=next(x['stdin'] for x in lesson['tests'] if x['case_id']==obs['case_id'])
                    doc += [f"公开 `{obs['case_id']}` 输入：`{json.dumps(stdin,ensure_ascii=False)}`；通过={obs['passed']}。",'',
                            f"- 期望输出：`{json.dumps(obs['expected_output'],ensure_ascii=False)}`",
                            f"- 实际输出：`{json.dumps(obs['actual_output'],ensure_ascii=False)}`；输出可用={obs['output_available']}。"]
                    for error in obs['errors']:
                        doc += [f"- 错误：`{error['type']}`；{error['message']}"]
                    doc.append('')
            else:
                data=t['run_events'][-1]['data'] if t['run_events'] else {}
                doc += [f"运行输入：`{json.dumps(c['stdin'],ensure_ascii=False)}`；success={data.get('success')}。",'',
                        f"实际输出：`{json.dumps(data.get('output'),ensure_ascii=False)}`；输出可用={data.get('output_available')}。",'']
                for error in data.get('errors',[]):
                    doc += [f"错误：`{error['type']}`；{error['message']}",'']
            if valid(t):
                content=analysis.get('content') or {}
                guidance=analysis.get('guidance') or {}
                doc += ['### 可展示AI原文','']
                if content:
                    doc += ['疑似错因：'+content['suspected_cause'],'',f"疑似标签：`{content['misconception_tag']}`；允许标签：{', '.join(c['human_oracle']['acceptable_tags'])}。",'']
                    for ev in content['evidence']:
                        doc += [f"证据 `{ev['case_id']}.{ev['field']}`：",'','```text',ev['quote'],'```','',ev['explanation'],'']
                    for k,v in content['hints'].items():
                        doc += [f'提示{k}：{v}','']
                    doc += ['知识点：'+'、'.join(content.get('knowledge_points',[])),'']
                if guidance:
                    doc += ['引导：'+guidance['hint'],'','知识点：'+'、'.join(guidance.get('knowledge_points',[])),'']
                    question=guidance.get('question')
                    if question:
                        doc += ['概念题：'+question['prompt'],'']
                        doc += [f"- {i+1}. {v}" for i,v in enumerate(question['options'])]
                        doc += ['',f"作答后显示的正确选项：{question['correct_index']+1}；解释：{question['explanation']}",'',
                                '请检查题干、全部选项和解释的答案保护；作答后展示也不得给原编程题的直接修正语句。','']
                    else:
                        doc += ['本次未生成概念题，这是允许行为。','']
            elif needs_ai(t):
                doc += ['### 无可展示AI正文','',analysis.get('message','未得到分析结果。'),'','人工结论应填“调用失败未评分”，不要把被拦截候选当作用户已看到的内容评分。','']
            else:
                doc += ['正确对照：预期不产生AI反馈。AI正文评分填“不适用”，核对跳过行为。','']
            for record_id in t['acceptance_record_ids']:
                for event in by_accept.get(record_id,{}).get('events',[]):
                    if event['stage'] in {'rejected','guidance_rejected_field'} or event['stage']=='diagnosis_quality_result' and event.get('issues'):
                        doc += ['校验拒绝记录：','', '```json',json.dumps(event,ensure_ascii=False,indent=2),'```','']
                    if event['stage']=='review_result' and event.get('issues'):
                        doc += ['模型审核记录（仅供排障，不代替人工）：','', '```json',json.dumps(event,ensure_ascii=False,indent=2),'```','']
            if t.get('error'):
                doc += ['请求异常：`'+json.dumps(t['error'],ensure_ascii=False)+'`','']
            for provider in [x for x in providers if x['trial_id']==t['trial_id']]:
                doc += [f"上游调用 `{provider['call_id']}`：HTTP={provider['http_status']}，传输异常={provider['transport_error']}，耗时{provider['seconds']}秒。",'']
            failed=[k for k,v in t['checks'].items() if not v]
            doc += ['自动检查未通过项：'+('、'.join(failed) or '无'),'','完整自动检查：','',
                    '```json',json.dumps(t['checks'],ensure_ascii=False,indent=2),'```','',
                    '计时（秒，不含费用推算）：`'+json.dumps(t['timings_seconds'],ensure_ascii=False)+'`','',
                    f"实际provider调用数：{len(t['provider_call_ids'])}；人工评分：待填写。",'']
        write(a.output_dir/f'逐条结果-L{level:02}.md','\n'.join(doc))
    review_path=HERE/'人工验收表.md'
    review=review_path.read_text(encoding='utf-8')
    review=review.replace('**当前仅完成设计与离线判题预检，真实AI尚未执行。请等实际运行记录补齐后再评分。**',
                          '**真实调用已完成，实际结果链接已补齐。请逐条阅读可展示AI原文与公开证据后填写人工评分。自动检查通过不等于语义正确。**')
    review=review.replace('统计结果：待真实运行和人工复核完成后计算，当前不填写任何AI质量百分比。',
                          f'真实调用统计见[调用汇总](../{a.output_dir.name}/真实调用汇总.md)；人工质量指标待填写评分后计算。')
    for t in report['trials']:
        c=cases[t['case_id']]
        label=(t.get('final_analysis') or {}).get('status','无分析')+'；自动'+('通过' if t['technical_passed'] else '未全通过')
        link=f"[{label}](../{a.output_dir.name}/逐条结果-L{c['level_no']:02}.md#{t['trial_id'].lower()})"
        pattern=r'(^\| '+re.escape(t['trial_id'])+r' \|[^\n]*?\| )未执行( \|)'
        review,n=re.subn(pattern,lambda m:m[1]+link+m[2],review,flags=re.M)
        assert n==1,t['trial_id']
    write(review_path,review.rstrip('\n'))
    summary_md=['# 72条核心验收及关键重复：真实调用记录','',
                '**120个验收试次已执行，人工语义审核待完成。以下是自动检查和调用记录，不是AI诊断准确率。**','',
                f"应用基线：`acceptance-baseline-2026-10-29` / `d668fe4`；样例指纹：`{report['dataset_sha256']}`。",'',
                f"开始：{report['started_at']}；结束：{report['finished_at']}（原始时间为UTC，北京时间加8小时）。",'',
                '[人工验收表](../core72-2026-10-29/人工验收表.md) · [原设计与评分口径](../core72-2026-10-29/README.md)','',
                '## 自动结果','', '| 轮次 | 试次数 | 应有AI反馈 | 可展示AI反馈 | 无AI对照 | 全部自动检查通过 |', '|---|---:|---:|---:|---:|---:|']
    summary_md += [f"| R{r['round']} | {r['trials']} | {r['ai_expected']} | {r['valid_ai']} | {r['controls']} | {r['technical_passed']} |" for r in rounds]
    summary_md += ['',f"有效返回合计：{summary['valid_ai']}/{summary['ai_expected']}（{summary['valid_ai']/summary['ai_expected']:.1%}）；语义合格率、端到端语义合格率和人工综合通过率均待人工评分后计算。",'',
                   '## 需关注的试次','', '| 试次 | 实际分析状态 | 自动检查未通过项 |', '|---|---|---|']
    failures=[t for t in report['trials'] if not t['technical_passed']]
    for t in failures:
        c=cases[t['case_id']]
        summary_md += [f"| [{t['trial_id']}](逐条结果-L{c['level_no']:02}.md#{t['trial_id'].lower()}) | {(t.get('final_analysis') or {}).get('status','无结果')} | {'、'.join(k for k,v in t['checks'].items() if not v)} |"]
    if not failures:
        summary_md += ['| 无 | 所有自动检查匹配 | 仍需人工核对语义 |']
    summary_md += ['', '失败全部保留，没有自动重试、替换首轮、删除小测或改动应用规则。重复轮次使用独立账号，不是同一提交的缓存读取。','',
                   '## 调用与证据','',f"真实provider请求：{len(providers)}次；HTTP状态：{summary['provider_http_statuses']}；返回模型名：{summary['provider_response_models']}。",'',
                   f"provider返回的整型usage字段总计：`{json.dumps(dict(usage),ensure_ascii=False)}`。嵌套明细保留在原始记录；实际账单费用未返回，不推算填入。",'',
                   f"请求数据边界结构核验：{payload_audit['passed']}/{len(audit)}通过。检查公开输入/期望输出、公开证据ID、空历史、未发送人工标准/参考解和实际生成参数；这不是对模型回答的语义审查。",'',
                   '验收通过临时内部转发记录器发送至https://api.deepseek.com。记录器不重试、不修改请求JSON和正常响应内容；只保存响应显式字段，排除密钥、登录令牌及reasoning_content。该额外转发环节属于本轮测试环境，端到端时间包含其开销。', '',
                   '冻结应用源码和题库保持一致；验收脚本与观察器单独保存指纹。临时日志配置结束后恢复，见runtime-after.json。原设计文件保持锁定时的状态，当前执行状态以本报告及responses.json为准。', '',
                   '24组重复的有效返回次数见summary.json；主要原因是否一致仍由人工确认，不把ready三次当成语义稳定三次。','',
                   '## 人工下一步','', '打开人工验收表，每行的“实际运行记录”直接链接到本关对应原文。评分列保持空白；无正文填“调用失败未评分”，正确对照填“不适用”并核对跳过行为。略难懂但仍可操作可填易懂1，并写出具体术语。','',
                   '## 原始文件','', '- responses.json：完整应用响应、合成账号标识、自动检查和计时，不含账号密码或令牌。',
                   '- provider-calls.jsonl：实际模型输入、可记录返回正文和usage，不含请求头、密钥或模型推理。',
                   '- acceptance.jsonl：候选校验与审核事件，拒绝正文只用于排障。',
                   '- payload-audit.json、summary.json：数据边界核验、轮次指标和重复清单。',
                   '- runtime-before.json、runtime-after.json、execution-lock.json：运行环境及执行脚本指纹。',
                   '- evidence-manifest.json：本轮原始证据和报告的指纹。','']
    write(a.output_dir/'真实调用汇总.md','\n'.join(summary_md))
    shutil.copyfile(HERE.parents[2]/'.cache/core72-runtime.yaml',a.output_dir/'runtime-override.yaml')
    write(a.output_dir/'report-generation.json',json.dumps({
        'renderer':'docs/competition/core72-2026-10-29/render_live_report.py',
        'renderer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'manual_scores_filled':False,'application_modified':False},ensure_ascii=False,indent=2))
    files=[f for f in sorted(a.output_dir.iterdir()) if f.is_file()]
    write(a.output_dir/'evidence-manifest.json',json.dumps({'dataset_id':dataset['dataset_id'],
          'files':[{'path':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in files]},ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='stability'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
