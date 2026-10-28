"""Opt-in real HTTP/DeepSeek check. Creates one isolated demo account per run.

Run from backend: python tests/live_submission_smoke.py --output ../docs/live-submission.json
The report includes submitted code and returned evidence, never login tokens/passwords.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import time

import httpx


CASES = [
    ("syntax_error", "total = 0\nfor i in range(1, 101)\n    total += i\nprint(total)", "execution_error"),
    ("range_boundary", "total = 0\nfor i in range(1, 100):\n    total += i\nprint(total)", "wrong_answer"),
    ("overwrite_accumulator", "total = 0\nfor i in range(1, 101):\n    total = i\nprint(total)", "wrong_answer"),
    ("undefined_name", "print(missing_total)", "execution_error"),
    ("correct", "total = 0\nfor i in range(1, 101):\n    total += i\nprint(total)", "accepted"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:3000")
    parser.add_argument("--output", default="../docs/live-submission.json")
    parser.add_argument("--require-ai", action="store_true", help="Reject fixed/offline feedback during real API acceptance")
    args = parser.parse_args()
    username = "smoke_" + secrets.token_hex(5)
    password = secrets.token_urlsafe(20)
    report = {"tested_at": datetime.now(timezone.utc).isoformat(), "url": args.url,
              "username": username, "cases": []}
    with httpx.Client(base_url=args.url, timeout=180) as client:
        registered = client.post("/api/v1/auth/register", json={"username": username, "password": password,
                                                               "phone": "19" + str(secrets.randbelow(10**9)).zfill(9)})
        registered.raise_for_status()
        assert registered.json()["code"] == 201, registered.text
        logged_in = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        logged_in.raise_for_status()
        client.headers["Authorization"] = "Bearer " + logged_in.json()["data"]["access_token"]
        for name, code, verdict in CASES:
            started = time.monotonic()
            response = client.post("/api/v1/code/submit", json={"problem_id": "level2", "code": code})
            response.raise_for_status()
            data = response.json()["data"]
            judge_seconds = round(time.monotonic() - started, 2)
            if data['analysis']['status'] == 'preparing':
                prepared = client.post(f"/api/v1/code/submissions/{data['submission_id']}/analysis")
                prepared.raise_for_status()
                data['analysis'] = prepared.json()['data']['analysis']
                data['timings'] = prepared.json()['data']['timings']
            expected_analysis = "skipped" if verdict == "accepted" else "ready"
            ok = data["judge"]["status"] == verdict and data["analysis"]["status"] == expected_analysis
            if args.require_ai and verdict != 'accepted':
                ok = ok and data['analysis']['source'] == 'ai'
            report["cases"].append({"name": name, "student_code": code, "judge_seconds": judge_seconds, "seconds": round(time.monotonic() - started, 2),
                                    "contract_passed": ok, "response": data})
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(name, data["judge"]["status"], data["analysis"]["status"], flush=True)
    assert all(case["contract_passed"] for case in report["cases"]), "See report for failures"


if __name__ == "__main__":
    main()
