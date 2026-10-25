"""Validate AI-authored Candidate JSON and add it to one user's endless category."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv


async def import_candidate(raw: str, user_id: int) -> str:
    from starlette.concurrency import run_in_threadpool
    from app.core.database import SessionLocal
    from app.models.user import User
    from app.services import endless, error_analysis
    from app.services.endless_catalog import save_verified_problem

    candidate = endless.Candidate.model_validate_json(raw)
    with SessionLocal() as db:
        if db.query(User).filter_by(id=user_id, status='enabled').first() is None:
            raise ValueError('目标账号不存在或已注销。')
    if error_analysis.analysis_configuration_error():
        raise ValueError('请配置 DEEPSEEK_API_KEY，以执行题意和边界审核。')
    async with asyncio.timeout(150):
        lesson = candidate.as_lesson()
        await run_in_threadpool(endless.validate_reference, lesson)
        review = await endless.review_candidate(candidate)
        lesson = await run_in_threadpool(endless.validate_review, lesson, review)
        with SessionLocal() as db:
            save_verified_problem(db, user_id, lesson, error_analysis.analysis_model())
    return lesson.problem_id


def main():
    parser = argparse.ArgumentParser(description='将 AI 编写的题目验证后写入题库的“无尽模式”类别。')
    parser.add_argument('--file', default='-', help='Candidate JSON 文件路径；默认 - 表示从标准输入读取')
    parser.add_argument('--user-id', required=True, type=int, help='题目所属账号 ID')
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    if not os.getenv('DATABASE_URL'):
        parser.error('请设置 DATABASE_URL，或在已运行的 backend 容器内执行此程序。')
    if args.user_id < 1:
        parser.error('--user-id 必须是正整数。')
    try:
        raw = sys.stdin.read() if args.file == '-' else Path(args.file).read_text(encoding='utf-8-sig')
        problem_id = asyncio.run(import_candidate(raw, args.user_id))
    except Exception as error:
        # Provider bodies and credentials are never printed by this command.
        print(json.dumps({'status': 'error', 'error_type': type(error).__name__,
                          'message': '题目未写入，请检查账号、JSON 格式、参考解、审核结果和模型配置。'},
                         ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({'status': 'ready', 'category': '无尽模式', 'problem_id': problem_id}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
