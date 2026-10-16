"""Run from backend: python validate_catalog.py [--check-solutions]."""
import argparse

from app.services.problem_catalog import PROBLEMS, KNOWLEDGE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-solutions', action='store_true')
    args = parser.parse_args()
    if args.check_solutions:
        from app.services.submission import judge_submission
        for lesson in PROBLEMS.values():
            result = judge_submission(lesson, lesson.reference_solution)
            if not result.passed:
                raise SystemExit(f'{lesson.problem_id}: reference solution failed: {result.status}')
    print(f'Catalog valid: {len(PROBLEMS)} problems, {len(KNOWLEDGE)} knowledge groups')


if __name__ == '__main__':
    main()
