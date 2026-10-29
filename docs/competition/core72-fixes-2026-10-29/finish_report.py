"""Verify final software/runtime evidence and seal artifacts, leaving human scores blank."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def main():
    regression = (HERE/'backend-regression-complete.txt').read_text(encoding='utf-8')
    assert re.search(r'628 passed, 1 skipped, 1 warning, 9 subtests passed', regression)
    assert '125 passed' in (HERE/'targeted-regression-final-confirmed.txt').read_text(encoding='utf-8')
    assert load('database-before.json') == load('database-after.json') == {'users':150,'learning_submissions':1074}
    assert {r['path']:r['status'] for r in load('health-check.json')} == {'/':200,'/api/v1/health':200,'/api/v1/auth/me':401}
    runtime = load('runtime-after.json')
    assert runtime['key_configured'] and not runtime['acceptance_logging_enabled']
    assert runtime['provider_url']=='https://api.deepseek.com'
    sources = {r['path']:r['sha256_lf'] for r in load('source-and-evidence-check-final.json')['repair_files']}
    assert all(sources[r['path']]==r['sha256_lf'] for r in runtime['files'])
    assert load('built-image-check.json')['built_image_matches_final_source']
    first = load('real-ai-results.json'); final = load('final/real-ai-results.json')
    assert first['summary']['technical_passed']==18 and final['summary']['technical_passed']==20
    assert final['summary']['statuses']=={'ready':19,'skipped':1}
    assert first['human_review']==final['human_review']=='pending'
    assert load('payload-audit.json')['public_fact_checks_passed']==69
    summary = {'status':'software_fixed_real_replay_complete_human_review_pending',
        'completed_at':datetime.now(timezone.utc).isoformat(),
        'reviewer_A_display_name':'A', 'original_scores_and_adjudication_unchanged':True,
        'software_regression':{'passed':628,'skipped':1,'subtests_passed':9,'warnings':1,
                               'skip_reason':'Dedicated MySQL migration test database not configured'},
        'targeted_regression':{'passed':125,'included_in_full_suite':True},
        'real_ai':{'initial_repair_stage':first['summary'],'final_repair_stage':final['summary'],
                   'provider_attempts':69,'total_tokens':119734,'human_review':'pending',
                   'human_semantic_pass_rate':None,'independent_unseen_acceptance':False},
        'database_counts_before_and_after':load('database-after.json'),
        'runtime_checks':load('health-check.json'),'running_image':load('running-image.json'),
        'deployed_final_source_matches':True,'committed_or_pushed':False,'new_freeze_tag_created':False}
    (HERE/'repair-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files = [p for p in sorted(HERE.rglob('*')) if p.is_file()
             and p.name not in {'fixes-manifest.json','人工复测检查表.md'}]
    manifest = {'status':summary['status'],'human_review':'pending','mutable_human_form':'人工复测检查表.md',
                'files':[{'path':p.relative_to(HERE).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
    (HERE/'fixes-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':summary['status'],'locked_files':len(files),
                      'software_passed':628,'final_real_trials_technical_passed':20,'human_semantic_pass_rate':None},ensure_ascii=False))


if __name__=='__main__':
    main()
