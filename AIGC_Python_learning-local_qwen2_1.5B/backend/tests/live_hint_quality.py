"""Opt-in synthetic model diagnostics; captures rejected drafts for human review.

This calls the same judge/analyzer directly, without saving any student data to DB.
Use live_submission_smoke.py separately for authenticated HTTP acceptance.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import error_analysis as analysis
from app.services.submission import PROBLEMS, judge_submission
from live_submission_smoke import CASES


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=[item[0] for item in CASES], default="syntax_error")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--output", default="../docs/phase1-model-diagnostic.json")
    args = parser.parse_args()
    analysis.LOCAL_LLM_URL = args.ollama_url
    calls = []
    original_post = analysis.httpx.AsyncClient.post

    async def capture(client, *values, **kwargs):
        payload = kwargs["json"]
        record = {"stage": "review" if payload["format"]["title"] == "HintReview" else "generation"}
        calls.append(record)
        started = time.monotonic()
        try:
            response = await original_post(client, *values, **kwargs)
            record["http_status"] = response.status_code
            record["raw_response"] = response.json()
            print(record["stage"], record["http_status"], flush=True)
            return response
        finally:
            record["seconds"] = round(time.monotonic() - started, 2)

    analysis.httpx.AsyncClient.post = capture
    name, code, expected = next(item for item in CASES if item[0] == args.case)
    judge = judge_submission(PROBLEMS["level2"], code)
    started = time.monotonic()
    try:
        result = await analysis.analyze_failure(PROBLEMS["level2"], code, judge)
    finally:
        analysis.httpx.AsyncClient.post = original_post
    report = {"tested_at": datetime.now(timezone.utc).isoformat(), "name": name,
              "student_code": code, "expected_verdict": expected, "judge": judge.model_dump(),
              "analysis": result.model_dump(), "seconds": round(time.monotonic() - started, 2),
              "model_calls": calls, "boundary": "Direct service diagnostic, not HTTP/browser acceptance"}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(name, judge.status, result.status, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
