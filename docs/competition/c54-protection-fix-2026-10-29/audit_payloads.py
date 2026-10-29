"""Check the public execution boundary of both replay rounds, including review gates."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    fixtures={c['trial_id']:c for c in json.loads((HERE/'replay-fixtures.json').read_text(encoding='utf-8'))['trials']}
    plan=json.loads((HERE/'retest-plan.json').read_text(encoding='utf-8'))
    specs={g['id']:g for g in plan['review_gate_plan']}
    d06=json.loads((ROOT/'backend/tests/data/feedback_validation_regressions.json').read_text(encoding='utf-8'))['cases'][0]
    rows=[]
    for stage in [HERE,HERE/'final']:
        for line in (stage/'provider-calls.jsonl').read_text(encoding='utf-8').splitlines():
            call=json.loads(line);key=call['trial_id'];request=call['request']
            if key in fixtures:case=fixtures[key]
            else:
                spec=specs[key]
                case=d06 if spec['source']=='dev12-D06' else fixtures['C54-R3' if spec['source']=='rejected_raw' else spec['source']]
            facts=json.JSONDecoder().raw_decode(request['messages'][1]['content'])[0]
            assert request['model']=='deepseek-flash' and request['stream'] is False
            assert request['thinking']=={'type':'enabled'} and request['max_tokens']==8192
            assert facts['student_code']==case['code']
            lesson=json.loads((ROOT/f"backend/app/data/{case['problem_id']}.json").read_text(encoding='utf-8'))
            inputs={t['case_id']:t['stdin'] for t in lesson['tests'] if t['visibility']=='public'}
            if case.get('mode')=='run':inputs={'run':case['stdin']}
            public=[c for c in case['judge']['cases'] if c.get('visibility','public')=='public']
            assert 'reference_solution' not in facts['problem'] and 'tests' not in facts['problem']
            assert not set(facts)&{'expected_issue','human_oracle','acceptable_tags','human_review'}
            if 'public_cases' in facts:
                assert set(facts)=={'problem','student_code','public_cases'}
                for observed in facts['public_cases']:
                    assert observed['stdin'] in inputs.values()
                    assert any(observed['actual_output']==c['actual_output'][:1000] and
                               observed['expected_output']==c['expected_output'][:1000] for c in public)
            else:
                assert set(facts)<={'execution_mode','judge_status','diagnosis_scope','problem','student_code',
                                    'failed_cases','allowed_evidence','related_history','candidate'}
                for observed in facts['failed_cases']:
                    actual=next(c for c in public if c['case_id']==observed['case_id'])
                    assert observed['stdin']==inputs[observed['case_id']]
                    assert observed['actual_output']==actual['actual_output'][:1000]
                    assert observed['expected_output']==actual['expected_output'][:1000]
                for citation in facts.get('allowed_evidence',[]):
                    actual=next(c for c in public if c['case_id']==citation['case_id'])
                    quotes=([e['message'].strip()[:1000].strip() for e in actual['errors']] if actual['errors']
                            else [actual['actual_output'].strip()[:1000].strip()])
                    assert citation['quote'] in quotes
            assert not set(call)&{'headers','authorization','api_key','access_token'}
            assert 'reasoning_content' not in json.dumps(call,ensure_ascii=False)
            rows.append({'stage':stage.name,'trial_id':key,'call_id':call['call_id'],'verified_public_facts':True})
    result={'attempts':len(rows),'verified':len(rows),'note':'Boundary checks only; not a human semantic grade.','items':rows}
    (HERE/'payload-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'attempts':len(rows),'verified':len(rows)}))


if __name__=='__main__':main()
