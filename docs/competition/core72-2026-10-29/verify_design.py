"""Offline core72 design check; no HTTP, database or AI requests.

Run with the frozen backend's Python dependencies and backend on PYTHONPATH.
The JSON output contains only public execution facts and aggregate verdicts.
It is not a real AI acceptance report.
"""
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from app.services.problem_catalog import DATA_DIR, PROBLEMS
from app.services.submission import judge_submission
from app.services.sandbox.runner import run_code_process
from app.services.learning_contract import contract_judge, error_code, submission_error


HERE = Path(__file__).resolve().parent


def code_identity(code):
    try:
        return ast.dump(ast.parse(code), include_attributes=False)
    except SyntaxError:
        return code.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite existing evidence.')
    raw = (HERE / 'cases.json').read_bytes()
    dataset = json.loads(raw)
    cases = dataset['cases']
    assert [c['id'] for c in cases] == [f'C{i:02}' for i in range(1, 73)]
    assert Counter(c['level_no'] for c in cases) == Counter({i: 6 for i in range(1, 13)})
    assert Counter(c['category'] for c in cases) == {
        'typical_error': 48, 'correct_control': 12, 'boundary_or_false_positive': 12}
    repeats = [c['id'] for c in cases if c['repeat_rounds'] == 3]
    assert repeats == dataset['repeat_case_ids'] and len(repeats) == 24
    assert sum(c['repeat_rounds'] for c in cases) == 120
    dev12 = json.loads((DATA_DIR.parents[1] / 'tests/data/dev12_ai_cases.json').read_text(encoding='utf-8'))
    old = {code_identity(c['code']) for c in dev12}
    assert not [c['id'] for c in cases if code_identity(c['code']) in old], 'Repeated dev12 code'
    assert len({code_identity(c['code']) for c in cases}) == 72, 'Duplicated core code'
    # Match frozen application and catalog contents independently of line endings.
    manifest = json.loads((HERE.parent / 'layout-migration-2026-10-28/source-manifest.json').read_text(encoding='utf-8'))
    backend = DATA_DIR.parents[1]
    app_entries = [f for f in manifest['files'] if f['path'].startswith('backend/app/')]
    assert app_entries
    for entry in app_entries:
        path = backend / Path(entry['path']).relative_to('backend')
        digest = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        assert digest == entry['sha256_lf'], f"Frozen source differs: {entry['path']}"
    result = {'kind': 'offline_design_validation_not_ai_acceptance',
              'created_at': datetime.now(timezone.utc).isoformat(),
              'application_baseline': dataset['application_baseline'],
              'dataset_sha256': hashlib.sha256(raw).hexdigest(),
              'frozen_app_files_checked': len(app_entries),
              'dev12_exact_ast_overlap': [], 'real_ai_calls': 0, 'database_writes': 0,
              'cases': []}
    for c in cases:
        lesson = PROBLEMS[c['problem_id']]
        assert lesson.level_no == c['level_no'] and lesson.version == c['problem_version']
        assert hashlib.sha256(c['code'].encode()).hexdigest() == c['code_sha256']
        expected = c['expected']
        if c['mode'] == 'submit':
            raw_judge = judge_submission(lesson, c['code'])
            judge = contract_judge(raw_judge, code=c['code'])
            feedback = 'skipped' if judge.passed else 'guidance' if 0 < judge.passed_cases < judge.total_cases else 'diagnosis'
            actual = {'judge_status': judge.status, 'passed_cases': judge.passed_cases,
                      'total_cases': judge.total_cases, 'feedback_kind': feedback}
            checks = {key: actual[key] == expected[key] for key in actual}
            actual['submission_error'] = submission_error(raw_judge, code=c['code'])
            actual['error_code'] = next((e.type for item in judge.cases if item.visibility == 'public'
                                         for e in item.errors), actual['submission_error'])
            if expected['error_code']:
                checks['error_code'] = actual['error_code'] == expected['error_code']
            public = [x.model_dump(mode='json') for x in judge.cases if x.visibility == 'public']
        else:
            run = run_code_process(c['code'], timeout=c['timeout_seconds'], stdin=c['stdin'])
            errors = [error_code(e['type'], code=c['code']) for e in run['errors']]
            status = None if run['success'] else 'timeout' if 'TIMEOUT' in errors else 'execution_error'
            actual = {'judge_status': status, 'run_success': run['success'],
                      'feedback_kind': 'none' if run['success'] else 'diagnosis',
                      'output': run['output'], 'error_code': errors[0] if errors else None}
            checks = {key: actual[key] == expected[key] for key in actual}
            public = [{'stdin': c['stdin'], 'output': run['output'],
                       'output_available': run['output_available'],
                       'errors': [{**e, 'type': error_code(e['type'], code=c['code'])} for e in run['errors']]}]
        result['cases'].append({'id': c['id'], 'actual': actual, 'checks': checks,
                                'public_observations': public, 'passed': all(checks.values())})
        print(c['id'], actual['judge_status'], actual.get('passed_cases'), feedback if c['mode'] == 'submit' else actual['feedback_kind'], all(checks.values()), flush=True)
    result['passed'] = all(c['passed'] for c in result['cases'])
    result['summary'] = {'cases': 72, 'matched': sum(c['passed'] for c in result['cases']),
                         'feedback_kinds': dict(Counter(c['expected']['feedback_kind'] for c in cases)),
                         'planned_ai_feedback_trials': sum(c['repeat_rounds'] for c in cases if c['expected']['feedback_kind'] in {'diagnosis', 'guidance'})}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not result['passed']:
        raise SystemExit('Design expectations do not match frozen judge. See output.')


if __name__ == '__main__':
    main()
