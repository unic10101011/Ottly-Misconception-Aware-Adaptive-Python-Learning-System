"""Replay saved candidates without network calls or changes to application rules."""
import asyncio
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import re
import sys
from unittest.mock import AsyncMock, patch


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'backend'))
from app.services import error_analysis as analysis
from app.services.hint_quality import quality_issues
from app.services.problem_catalog import PROBLEMS
from app.services.submission import JudgeResult


def main():
    report = json.loads((HERE / 'responses.json').read_text(encoding='utf-8'))
    records = {record['problem_id']: record for record in
               map(json.loads, (HERE / 'acceptance.jsonl').read_text(encoding='utf-8').splitlines())}
    findings = []
    for case in report['cases']:
        problem = PROBLEMS[case['problem_id']]
        judge = JudgeResult.model_validate(case['http_response']['data']['judge'])
        record = records[case['problem_id']]
        raw = next(event['content'] for event in record['events'] if event['stage'] == 'provider_response')
        if case['id'] == 'D06':
            draft = analysis.parse_analysis_content(raw)
            content = analysis.AnalysisContent(**draft.model_dump(exclude={'code_observation'}),
                                               hints=analysis.safe_hints(problem, judge))
            analysis.validate_grounding(content, judge, problem_id=problem.problem_id, code=case['code'])
            outputs = [result.expected_output for result in judge.cases]
            before = quality_issues(content.model_dump(), case['code'], outputs)
            changed = content.model_copy(deep=True)
            for evidence in changed.evidence:
                evidence.explanation = re.sub(r'第\s*4\s*行', '额外一行', evidence.explanation)
            after = quality_issues(changed.model_dump(), case['code'], outputs)
            assert before == ['unsupported_claim'] and after == []
            findings.append({'id': case['id'], 'source_line_count': len(case['code'].splitlines()),
                             'before': before, 'after_output_line_rewording': after,
                             'model_review_was_reached': any(event['stage'] == 'diagnosis_review' for event in record['events'])})
        else:
            original = json.loads(raw)
            changed = copy.deepcopy(original)
            changed['question']['explanation'] = changed['question']['explanation'].replace('（如 total = total + i）', '')
            assert changed != original

            def replay(candidate):
                with patch.object(analysis, 'analysis_configuration_error', return_value=None), \
                        patch.object(analysis.httpx, 'AsyncClient', return_value=nullcontext(None)), \
                        patch.object(analysis, 'request_diagnosis', AsyncMock(return_value=(json.dumps(candidate, ensure_ascii=False), 0))):
                    return asyncio.run(analysis._generate_guidance(problem, case['code'], judge)).status

            before, after = replay(original), replay(changed)
            assert before == 'invalid_response' and after == 'ready'
            findings.append({'id': case['id'], 'before': before,
                             'after_removing_assignment_example_from_quiz_explanation': after})
    result = {'real_model_calls': 0, 'application_rules_modified': False,
              'note': 'Reworded candidates are offline controls, never live retest successes.', 'findings': findings}
    (HERE / 'offline-replay.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
