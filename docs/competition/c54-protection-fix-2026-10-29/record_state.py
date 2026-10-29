"""Record the exact worktree source and verify retained acceptance evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old = HERE.parent/'core72-fixes-2026-10-29'
    review = HERE.parent/'core72-fixes-review-2026-10-29'
    for folder,name in [(old,'fixes-manifest.json'),(review,'review-manifest.json')]:
        for entry in json.loads((folder/name).read_text(encoding='utf-8'))['files']:
            assert digest(folder/entry['path'])==entry['sha256'],entry['path']
    before = json.loads((HERE/'source-before.json').read_text(encoding='utf-8'))
    previous = json.loads((old/'source-and-evidence-check-final.json').read_text(encoding='utf-8'))
    previous_files = {e['path']:e['sha256_lf'] for e in previous['repair_files']}
    assert before['sha256_lf']==previous_files['backend/app/services/error_analysis.py']
    changed = []
    for path,expected in previous_files.items():
        if path.startswith('backend/app/') and hashlib.sha256((ROOT/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=expected:
            changed.append(path)
    expected=['backend/app/services/error_analysis.py']
    if args.stage=='final':expected.append('backend/app/services/hint_quality.py')
    assert changed==expected,changed
    sources = [p for p in sorted((ROOT/'backend/app').rglob('*')) if p.suffix in {'.py','.json'}]
    entries = [{'path':p.relative_to(ROOT).as_posix(),'sha256_lf':hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()} for p in sources]
    record = {'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'app_source_digest':hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest(),
              'files':entries,'application_files_changed_this_fix':changed,
              'previous_human_results_preserved':True,'new_freeze_tag_created':False}
    suffix='-final' if args.stage=='final' else ''
    target=HERE/f'application-state{suffix}.json'
    if target.exists():assert json.loads(target.read_text(encoding='utf-8'))==record,'Worktree changed since this run.'
    else:target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    locks = [HERE/'retest-plan.json',HERE/'replay-fixtures.json',HERE/'live_retest.py',HERE/'source-before.json',
             ROOT/'backend/tests/test_c54_answer_protection.py',ROOT/'backend/tests/data/c54_answer_protection_regressions.json']
    if args.stage=='final':locks.append(ROOT/'backend/tests/data/c54_followup_observation.json')
    execution = {'application_digest':record['app_source_digest'],'files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in locks]}
    target=HERE/f'execution-lock{suffix}.json'
    if target.exists():assert json.loads(target.read_text(encoding='utf-8'))==execution
    else:target.write_text(json.dumps(execution,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'source_files':len(entries),'application_files_changed':changed,'old_evidence_preserved':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['phase1','final'],default='final')
    args=parser.parse_args()
    main()
