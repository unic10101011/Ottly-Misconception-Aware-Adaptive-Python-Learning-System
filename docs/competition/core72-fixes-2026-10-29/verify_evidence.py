"""Check immutable evidence plus the explicit reviewer-name amendment."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOCS = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    count = 0
    for folder, manifest, key in [
        ('core72-2026-10-29', 'design-lock.json', 'files'),
        ('core72-live-2026-10-29', 'evidence-manifest.json', 'files'),
        ('core72-review-2026-10-29', 'review-manifest.json', 'immutable_files'),
        ('core72-final-2026-10-29', 'final-manifest.json', 'files'),
    ]:
        directory = DOCS/folder
        for entry in json.loads((directory/manifest).read_text(encoding='utf-8'))[key]:
            assert sha(directory/entry['path']) == entry['sha256'], entry['path']
            count += 1
    correction = json.loads((HERE/'reviewer-name-correction.json').read_text(encoding='utf-8'))
    for entry in correction['changes']:
        current = DOCS/entry['path']; original = DOCS/entry['original_snapshot']
        assert sha(current) == entry['after_sha256'] and sha(original) == entry['before_sha256']
        assert current.read_bytes() == original.read_bytes().replace(entry['old'].encode(), entry['new'].encode())
    amendments = {str((DOCS/e['path']).relative_to(ROOT)).replace('\\','/'):e for e in correction['changes']}
    final_manifest = json.loads((DOCS/'core72-final-2026-10-29/final-manifest.json').read_text(encoding='utf-8'))
    comparison = json.loads((DOCS/'core72-review-2026-10-29/review-comparison.json').read_text(encoding='utf-8'))
    for entry in final_manifest['sources'] + [{'path':e['source'],'sha256':e['sha256']} for e in comparison['sources']]:
        if entry['path'] in amendments:
            assert entry['sha256'] == amendments[entry['path']]['before_sha256']
        else:
            assert sha(ROOT/entry['path']) == entry['sha256'], entry['path']
    manifest = json.loads((DOCS/'layout-migration-2026-10-28/source-manifest.json').read_text(encoding='utf-8'))
    changes = []
    for entry in manifest['files']:
        if entry['path'].startswith('backend/app/'):
            data = (ROOT/entry['path']).read_bytes().replace(b'\r\n', b'\n')
            if hashlib.sha256(data).hexdigest() != entry['sha256_lf']:
                changes.append(entry['path'])
    expected = ['backend/app/services/error_analysis.py','backend/app/services/hint_quality.py','backend/app/services/misconceptions.py']
    assert sorted(changes) == expected, changes
    files = [ROOT/path for path in expected] + [ROOT/'backend/tests/test_core72_feedback_regressions.py',
             ROOT/'backend/tests/test_submission.py', ROOT/'backend/tests/data/core72_feedback_regressions.json',
             ROOT/'backend/tests/data/core72_followup_regressions.json']
    record = {'immutable_evidence_files_verified': count, 'reviewer_name_only_changes_verified': 2,
              'original_metrics_unchanged': True,
              'worktree_base_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'frozen_tag_commit': subprocess.check_output(['git','rev-list','-n','1','acceptance-baseline-2026-10-29'],cwd=ROOT,text=True).strip(),
              'modified_application_files': changes,
              'repair_files': [{'path':str(p.relative_to(ROOT)).replace('\\','/'),
                               'sha256_lf':hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()} for p in files]}
    target = HERE/args.output
    if target.exists():
        assert json.loads(target.read_text(encoding='utf-8')) == record, 'Source changed after verification.'
    else:
        target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='source-and-evidence-check-final.json')
    args = parser.parse_args()
    main()
