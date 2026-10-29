"""Lock the reviewed failure and controls before changing application prompts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = HERE.parent/'core72-fixes-2026-10-29'
REVIEW = HERE.parent/'core72-fixes-review-2026-10-29'


def save(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    assert not (HERE/'retest-plan.json').exists(), 'Never overwrite an existing plan.'
    for folder, name in [(OLD,'fixes-manifest.json'),(REVIEW,'review-manifest.json')]:
        for entry in json.loads((folder/name).read_text(encoding='utf-8'))['files']:
            assert hashlib.sha256((folder/entry['path']).read_bytes()).hexdigest()==entry['sha256'],entry['path']
    source = ROOT/'backend/app/services/error_analysis.py'
    (HERE/'error_analysis.before.snapshot.txt').write_bytes(source.read_bytes())
    calls = [json.loads(line) for line in (OLD/'final/provider-calls.jsonl').read_text(encoding='utf-8').splitlines()]
    fixtures = json.loads((ROOT/'backend/tests/data/core72_feedback_regressions.json').read_text(encoding='utf-8'))['trials']
    by_id = {c['trial_id']:c for c in fixtures}
    def candidate(key):
        call = next(c for c in calls if c['trial_id']==key)
        return call['response']['choices'][0]['message']['content']
    captured = {'source':'core72-fixes-2026-10-29/final/provider-calls.jsonl',
                'human_rejected_trial':'C54-R3','rejected_raw':candidate('C54-R3'),
                'allowed_raw':{key:candidate(key) for key in ['C54-R1','C54-R2','C07-R1','C14-R1','C58-R1']}}
    target = ROOT/'backend/tests/data/c54_answer_protection_regressions.json'
    assert not target.exists()
    save(target,captured)
    ids = ['C54-R1','C54-R2','C54-R3','C07-R1','C14-R1','C20-R1','C58-R1','C70-R1',
           'C28-R1','C24-R3','C43-R1','C05-R1']
    save(HERE/'replay-fixtures.json',{'trials':[by_id[key] for key in ids]})
    save(HERE/'retest-plan.json',{
        'trial_ids':ids,'count':len(ids),'planned_ai_feedback_trials':11,
        'policy':'Same captured execution facts, one new attempt per trial; no content retries. Connection establishment retries retain the application limit of one. Service replay, not an unseen acceptance set.',
        'review_gate_plan':[
            {'id':'G01-original-C54-R3','source':'rejected_raw','expected_issue':'answer_leak'},
            {'id':'G02-paraphrased-update','source':'rejected_raw','cause':'循环条件依赖的量没有变化。请在每轮迭代中把已存贝壳数再加三枚，这样才能达到目标。','expected_issue':'answer_leak'},
            {'id':'G03-rewritten-update','source':'rejected_raw','cause':'要结束本题循环，需要在循环体中补充把 saved 每轮增加 3 的操作；当前代码没有这一步。','expected_issue':'answer_leak'},
            *[{'id':'G-'+key,'source':key,'expected_issue':None} for key in ['C54-R1','C54-R2','C07-R1','C14-R1','C58-R1']],
            {'id':'G-D06-expression','source':'dev12-D06','expected_issue':None}],
        'human_review':'All new visible feedback remains pending human scores.',
        'old_review_result':'18/19 qualified; C54-R3 protection1 failed. Never overwrite.'})
    save(HERE/'source-before.json',{'path':'backend/app/services/error_analysis.py',
        'sha256_lf':hashlib.sha256(source.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'snapshot':'error_analysis.before.snapshot.txt'})
    print('Prepared 12 generation trials and 9 semantic-review gate trials.')


if __name__=='__main__':main()
