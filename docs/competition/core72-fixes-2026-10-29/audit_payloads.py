"""Verify both real replay stages sent only the captured public execution facts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    fixtures = {c['trial_id']:c for c in json.loads((ROOT/'backend/tests/data/core72_feedback_regressions.json').read_text(encoding='utf-8'))['trials']}
    records = []
    for stage in [HERE, HERE/'final']:
        for line in (stage/'provider-calls.jsonl').read_text(encoding='utf-8').splitlines():
            call = json.loads(line); request = call['request']; case = fixtures[call['trial_id']]
            facts = json.JSONDecoder().raw_decode(request['messages'][1]['content'])[0]
            assert request['model']=='deepseek-flash' and request['stream'] is False
            assert request['thinking']=={'type':'enabled'} and request['max_tokens']==8192
            lesson = json.loads((ROOT/f"backend/app/data/{case['problem_id']}.json").read_text(encoding='utf-8'))
            inputs = {c['case_id']:c['stdin'] for c in lesson['tests'] if c['visibility']=='public'}
            if case['mode']=='run':inputs={'run':case['stdin']}
            public = [c for c in case['judge']['cases'] if c['visibility']=='public']
            if 'public_cases' in facts:
                assert set(facts)=={'problem','student_code','public_cases'}
                for observed in facts['public_cases']:
                    assert observed['stdin'] in inputs.values()
                    assert any(observed['actual_output']==c['actual_output'][:1000] and
                               observed['expected_output']==c['expected_output'][:1000] for c in public)
            else:
                assert set(facts) <= {'execution_mode','judge_status','diagnosis_scope','problem','student_code',
                                      'failed_cases','allowed_evidence','related_history','candidate'}
                for observed in facts['failed_cases']:
                    assert observed['case_id'] in inputs and observed['stdin']==inputs[observed['case_id']]
                    actual = next(c for c in public if c['case_id']==observed['case_id'])
                    assert observed['actual_output']==actual['actual_output'][:1000]
                    assert observed['expected_output']==actual['expected_output'][:1000]
                for citation in facts.get('allowed_evidence',[]):
                    actual = next(c for c in public if c['case_id']==citation['case_id'])
                    quotes = ([e['message'].strip()[:1000].strip() for e in actual['errors']] if actual['errors']
                              else [actual['actual_output'].strip()[:1000].strip()])
                    assert citation['quote'] in quotes
            assert facts['student_code']==case['code']
            assert 'reference_solution' not in facts['problem'] and 'tests' not in facts['problem']
            assert not ({'human_oracle','acceptable_tags','human_review'} & set(facts))
            assert not any(k in call for k in ('headers','authorization','api_key','access_token'))
            assert 'reasoning_content' not in json.dumps(call,ensure_ascii=False)
            records.append({'stage':stage.name,'trial_id':call['trial_id'],'call_id':call['call_id'],
                            'payload_sha256':hashlib.sha256(json.dumps(request,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
                            'public_facts_verified':True})
    assert len(records)==69
    output = {'requests':len(records),'public_fact_checks_passed':len(records),
              'scope':'Structural/public-fact boundary verification, not a semantic grade.', 'items':records}
    (HERE/'payload-audit.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'requests':len(records),'public_fact_checks_passed':len(records)}))


if __name__=='__main__':
    main()
