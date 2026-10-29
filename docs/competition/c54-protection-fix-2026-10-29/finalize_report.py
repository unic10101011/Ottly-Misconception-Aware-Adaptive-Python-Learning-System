"""Seal this repair after regression/deployment checks; leave human scores pending."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def load(name):return json.loads((HERE/name).read_text(encoding='utf-8'))


def main():
    assert not (HERE/'summary.json').exists(),'Never overwrite a sealed repair summary.'
    log=(HERE/'backend-regression.txt').read_text(encoding='utf-8')
    assert re.search(r'636 passed, 1 skipped, 1 warning, 9 subtests passed',log)
    assert '149 passed' in (HERE/'targeted-regression-final.txt').read_text(encoding='utf-8')
    state=load('application-state-final.json')
    for e in state['files']:
        assert hashlib.sha256((ROOT/e['path']).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==e['sha256_lf']
    for e in load('execution-lock-final.json')['files']:
        assert hashlib.sha256((ROOT/e['path']).read_bytes()).hexdigest()==e['sha256']
    phase1=load('application-state.json')
    snapshots={'backend/app/services/error_analysis.py':'error_analysis.phase1.snapshot.txt',
               'backend/app/services/hint_quality.py':'hint_quality.before.snapshot.txt'}
    for e in phase1['files']:
        source=HERE/snapshots[e['path']] if e['path'] in snapshots else ROOT/e['path']
        assert hashlib.sha256(source.read_bytes().replace(b'\r\n',b'\n')).hexdigest()==e['sha256_lf']
    for e in load('execution-lock.json')['files']:
        source=HERE/'test_c54.phase1.snapshot.txt' if e['path'].endswith('test_c54_answer_protection.py') else ROOT/e['path']
        assert hashlib.sha256(source.read_bytes()).hexdigest()==e['sha256']
    assert load('database-before.json')==load('database-after.json')
    assert {r['path']:r['status'] for r in load('health-check.json')}=={'/':200,'/api/v1/health':200,'/api/v1/auth/me':401}
    assert load('built-image-check.json')['built_image_matches_final_source']
    runtime=load('runtime-after.json')
    assert runtime['app_source_digest']==state['app_source_digest']
    assert runtime['key_configured'] and not runtime['acceptance_logging_enabled']
    first=load('real-ai-results.json');final=load('final/real-ai-results.json')
    assert final['summary']['technical_passed']==12 and final['summary']['statuses']=={'ready':11,'skipped':1}
    gates=load('final/review-gate-results.json');assert gates['passed']==gates['total']==9
    assert load('payload-audit.json')['verified']==60
    summary={'status':'c54_repair_automated_checks_complete_human_review_pending',
             'completed_at':datetime.now(timezone.utc).isoformat(),
             'application_source_digest':state['app_source_digest'],
             'application_files_changed_this_fix':state['application_files_changed_this_fix'],
             'regression':{'passed':636,'skipped':1,'subtests_passed':9,'warnings':1,'targeted_passed_included':149},
             'first_round':{'generation':first['summary'],'review_gates_passed':load('review-gate-results.json')['passed']},
             'final_round':{'generation':final['summary'],'review_gates_passed':9,'review_gates_total':9},
             'human_semantic_pass_rate':None,'human_review':'pending','old_human_18_of_19_preserved':True,
             'provider_attempts':60,'http_200':59,'connection_failures_before_retry':1,'usage_total_tokens':107463,
             'raw_round_provider_attempt_counts_include_review_gates':True,
             'deployed_source_verified':True,'database_counts_unchanged':load('database-after.json'),
             'independent_unseen_acceptance':False,'new_freeze_tag_created':False,'committed_or_pushed':False}
    (HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files=[p for p in sorted(HERE.rglob('*')) if p.is_file() and p.name not in {'manifest.json','人工复测检查表.md'}]
    manifest={'status':summary['status'],'mutable_human_form':'人工复测检查表.md','files':[
        {'path':p.relative_to(HERE).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
    (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'regression_passed':636,'generation_checks':'12/12','review_gates':'9/9',
                      'human_review':'pending','locked_files':len(files)}))


if __name__=='__main__':main()
