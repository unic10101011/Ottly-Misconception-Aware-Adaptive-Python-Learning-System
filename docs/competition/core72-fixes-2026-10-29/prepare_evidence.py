"""Preserve old evidence, record a name correction and extract replay fixtures."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCS = HERE.parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    correction = HERE / 'reviewer-name-correction.json'
    if not correction.exists():
        changes = []
        for relative, old, new, snapshot in [
            ('core72-2026-10-29/人工验收表.md', '_unic_______', '_A_______', 'core72-review-2026-10-29/review-A.snapshot.txt'),
            ('core72-review-2026-10-29/分歧核对说明.md', '复核人A：unic', '复核人A：A', 'core72-final-2026-10-29/adjudication.snapshot.txt'),
        ]:
            path = DOCS / relative
            before = path.read_bytes()
            assert before == (DOCS / snapshot).read_bytes()
            assert before.count(old.encode()) == 1
            after = before.replace(old.encode(), new.encode())
            path.write_bytes(after)
            changes.append({'path': relative, 'before_sha256': sha(before), 'after_sha256': sha(after),
                            'original_snapshot': snapshot, 'old': old, 'new': new})
        correction.write_text(json.dumps({'reason': '用户要求第一位复核人由unic匿名化为A；仅更正署名，不改评分、备注、裁决或统计。',
            'historical_snapshots': '旧快照和旧清单保持原字节；验证当前文件时同时核对此更正记录。历史脚本重放应使用已保留的原始快照。',
            'changes': changes}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    calls = [json.loads(line) for line in (DOCS / 'core72-live-2026-10-29/provider-calls.jsonl').read_text(encoding='utf-8').splitlines()]
    trials = json.loads((DOCS / 'core72-live-2026-10-29/responses.json').read_text(encoding='utf-8'))['trials']
    dataset = json.loads((DOCS / 'core72-2026-10-29/cases.json').read_text(encoding='utf-8'))
    cases = {case['id']: case for case in dataset['cases']}
    selected = ['C10-R1','C24-R1','C24-R2','C24-R3','C28-R1','C54-R1','C54-R2','C54-R3','C64-R1',
                'C37-R1','C40-R1','C43-R1','C01-R2','C08-R1',
                'C07-R1','C14-R1','C20-R1','C58-R1','C70-R1','C05-R1']
    fixtures = []
    for key in selected:
        trial = next(t for t in trials if t['trial_id'] == key)
        case = cases[trial['case_id']]
        previous = next((c for c in calls if c['trial_id'] == key), None)
        facts = json.JSONDecoder().raw_decode(previous['request']['messages'][1]['content'])[0] if previous else None
        judge = trial['submit_response']['judge'] if case['mode'] == 'submit' else trial['run_events'][-1]['data']['judge']
        # Restore internal error names from the actual request; HTTP contract enums
        # differ from the service's runner error types. Never infer a new result.
        if facts:
            for item in facts.get('failed_cases', facts.get('public_cases', [])):
                matches = [c for c in judge['cases'] if c['visibility'] == 'public' and (
                    c['case_id'] == item['case_id'] if 'case_id' in item else c['actual_output'] == item['actual_output'])]
                for found in matches:
                    found['errors'] = item['errors']
        judge.pop('failed_tests', None)
        raw = previous['response']['choices'][0]['message']['content'] if previous and previous.get('response') else None
        fixtures.append({'trial_id': key, 'case_id': case['id'], 'problem_id': case['problem_id'],
                         'mode': case['mode'], 'code': case['code'], 'stdin': case.get('stdin', ''),
                         'judge': judge, 'original_raw': raw,
                         'acceptable_tags': case['human_oracle']['acceptable_tags'],
                         'expected_feedback_kind': case['expected']['feedback_kind']})
    target = ROOT / 'backend/tests/data/core72_feedback_regressions.json'
    assert not target.exists(), 'Do not overwrite captured fixtures.'
    target.write_text(json.dumps({'source': 'core72-live-2026-10-29; frozen before fixes', 'trials': fixtures},
                                 ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE/'retest-plan.json').write_text(json.dumps({'trial_ids': selected, 'count': len(selected),
        'policy': 'Service-level real AI replay of captured execution facts, one attempt per trial; connection-only retry at most once; no content retries. Not a new independent acceptance set or a full HTTP workflow test.',
        'manual_review': 'Pending human confirmation; automated checks never replace human semantic adjudication.'},
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
