"""Opt-in real-model evaluation; does not train or modify the model.

Run inside the backend environment with DEEPSEEK_API_KEY set.
The report contains only synthetic code and public judge evidence.
"""

import asyncio
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.error_analysis import analyze_failure
from app.services.problem_catalog import PROBLEMS
from app.services.submission import judge_submission, public_judge
from personalized_hint_eval_cases import CASES


OUTPUT = Path(os.getenv('EVAL_REPORT_PATH', '/app/tests/personalized_hint_eval_result.json'))
HISTORY_CASE_IDS = {'range_ends_100', 'overwrite_each_turn', 'missing_print_name'}


async def evaluate(case: dict, *, with_history: bool = False) -> dict:
    problem = PROBLEMS['level2']
    judge = public_judge(judge_submission(problem.execution_problem(), case['code']))
    history = [{
        'problem_id': 'level2', 'problem_title': problem.title,
        'knowledge_ids': ['K08'], 'error_type': 'WRONG_ANSWER',
        'misconception_tag': 'range_boundary',
        'suspected_cause': '先前一次练习可能漏掉范围终点。',
        'later_passed': False, 'hints_viewed_max': 0,
        'created_at': '2026-10-17T00:00:00Z',
    }] if with_history else []
    started = time.monotonic()
    result = await analyze_failure(problem.execution_problem(), case['code'], judge, history)
    tag = result.content.misconception_tag if result.content else None
    if case['tag'] is None:
        outcome = 'correctly_skipped' if result.status == 'skipped' else 'unexpected_analysis'
    elif result.status != 'ready':
        outcome = 'no_diagnosis'
    else:
        outcome = 'correct_tag' if tag == case['tag'] else 'wrong_tag'
    return {
        'id': case['id'], 'history': with_history, 'code': case['code'],
        'gold_tag': case['tag'], 'gold_reason': case['reason'],
        'judge_status': judge.status,
        'actual_output': judge.cases[0].actual_output,
        'public_errors': [error.type for error in judge.cases[0].errors],
        'analysis_status': result.status,
        'model_tag': tag,
        'model_cause': result.content.suspected_cause if result.content else None,
        'personalization': result.personalization.model_dump(),
        'outcome': outcome,
        'seconds': round(time.monotonic() - started, 2),
    }


async def main() -> None:
    if not os.getenv('DEEPSEEK_API_KEY'):
        raise SystemExit('DEEPSEEK_API_KEY is required for real-model evaluation')
    results = []
    for case in CASES:
        item = await evaluate(case)
        results.append(item)
        print(item['id'], item['outcome'], item['model_tag'], flush=True)
    for case in CASES:
        if case['id'] in HISTORY_CASE_IDS:
            item = await evaluate(case, with_history=True)
            results.append(item)
            print(item['id'], 'with_history', item['outcome'], item['model_tag'], flush=True)
    report = {
        'model': 'deepseek-flash',
        'problem_id': 'level2',
        'note': 'Gold labels were written before model calls; this is evaluation, not training.',
        'results': results,
        'counts': {outcome: sum(item['outcome'] == outcome for item in results)
                   for outcome in ('correct_tag', 'wrong_tag', 'no_diagnosis',
                                   'correctly_skipped', 'unexpected_analysis')},
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Report saved:', OUTPUT, flush=True)


if __name__ == '__main__':
    asyncio.run(main())
