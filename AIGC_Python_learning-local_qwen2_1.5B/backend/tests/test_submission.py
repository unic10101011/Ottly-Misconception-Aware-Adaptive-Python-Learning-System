import asyncio
import json
import os

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path):
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    os.environ.setdefault("JWT_SECRET", "local-submission-test-secret")
    from main import app
    from app.core.database import Base, get_db

    engine = create_engine(f"sqlite:///{(tmp_path / 'submission.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def db_override():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def login(client):
    account = {"username": "submission_student", "password": "TestPass123!", "phone": "13800138000"}
    assert client.post("/api/v1/auth/register", json=account).json()["code"] == 201
    token = client.post("/api/v1/auth/login", json=account).json()["data"]["access_token"]
    return {"Authorization": "Bearer " + token}


def sample_analysis():
    return {
        "suspected_cause": "疑似每次循环覆盖了累计结果。",
        "evidence": [{"case_id": "stdout-1", "field": "actual_output", "quote": "100",
                      "explanation": "程序输出了循环的最后一个数，和要求的总和不同。"}],
        "knowledge_points": ["累加器", "赋值与累加"],
        "hints": {"level1": "总数需要保留哪些已经算过的值？",
                  "level2": "观察循环内的赋值会不会覆盖上一轮累计的结果。",
                  "level3": "用前两轮在纸上核算，检查新总数是否包含旧总数。"},
    }


OVERWRITE = "total = 0\nfor i in range(1, 101):\n    total = i\nprint(total)"
CORRECT = "total = 0\nfor i in range(1, 101):\n    total += i\nprint(total)"


def mock_model(monkeypatch, handler):
    from app.services import error_analysis
    factory = httpx.AsyncClient
    monkeypatch.setattr(error_analysis, "LOCAL_LLM_URL", "http://ollama.test/api/chat")
    monkeypatch.setattr(error_analysis.httpx, "AsyncClient", lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs))


def model_facts(payload):
    return json.JSONDecoder().raw_decode(payload["messages"][1]["content"])[0]


def test_nonquestion_hint_is_repaired_once_within_same_request(client, monkeypatch):
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        content = sample_analysis()
        if len(calls) == 1:
            content["hints"]["level1"] = "请观察总数的变化。"
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(content)}})

    mock_model(monkeypatch, handler)
    data = client.post("/api/v1/code/submit", headers=login(client),
                       json={"problem_id": "level2", "code": OVERWRITE}).json()["data"]
    assert data["analysis"]["status"] == "ready"
    assert len(calls) == 2
    assert calls[1]["messages"][-1]["role"] == "user"
    # Avoid the Ollama 0.40.3 grammar failure; keep the question check in Pydantic.
    assert calls[0]["format"]["$defs"]["Hints"]["properties"]["level1"]["pattern"].endswith("*$")


def test_analysis_repair_shares_total_deadline(client, monkeypatch):
    from app.services import error_analysis
    calls = []

    async def handler(request):
        calls.append(request)
        if len(calls) == 2:
            await asyncio.sleep(1)
        return httpx.Response(200, json={"done": True, "message": {"content": "invalid json"}})

    mock_model(monkeypatch, handler)
    monkeypatch.setattr(error_analysis, "ANALYSIS_TIMEOUT", 0.1)
    data = client.post("/api/v1/code/submit", headers=login(client),
                       json={"problem_id": "level2", "code": OVERWRITE}).json()["data"]
    assert len(calls) == 2
    assert data["analysis"]["status"] == "timeout"
    assert data["judge"]["status"] == "wrong_answer"


def test_accepted_submission_never_calls_model(client, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Accepted code must not call AI")
    monkeypatch.setattr(httpx, "AsyncClient", forbidden)
    response = client.post("/api/v1/code/submit", headers=login(client),
                           json={"problem_id": "level2", "code": CORRECT})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["judge"]["status"] == "accepted"
    assert data["judge"]["passed_cases"] == data["judge"]["total_cases"] == 1
    assert data["analysis"]["status"] == "skipped"
    assert data["analysis"]["content"] is None


@pytest.mark.parametrize("code,status,actual", [
    (OVERWRITE, "wrong_answer", "100\n"),
    ("total = 0\nfor i in range(1, 100):\n    total += i\nprint(total)", "wrong_answer", "4950\n"),
    ("for i in range(1, 101)\n    print(i)", "execution_error", ""),
    ("print(missing_total)", "execution_error", ""),
])
def test_real_judge_evidence_is_sent_to_model(client, monkeypatch, code, status, actual):
    observed = []

    def handler(request):
        payload = json.loads(request.content)
        evidence = model_facts(payload)
        observed.append(evidence)
        case = evidence["failed_cases"][0]
        content = sample_analysis()
        content["evidence"][0].update(
            field="error_message" if case["errors"] else "actual_output",
            quote=case["errors"][0]["message"] if case["errors"] else case["actual_output"].strip(),
        )
        assert payload["format"]["type"] == "object"
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(content)}})

    mock_model(monkeypatch, handler)
    response = client.post("/api/v1/code/submit", headers=login(client), json={"problem_id": "level2", "code": code})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["judge"]["status"] == status
    assert data["judge"]["cases"][0]["actual_output"] == actual
    assert data["analysis"]["status"] == "ready", data
    assert len(observed) == 1
    assert observed[0]["student_code"] == code
    assert observed[0]["failed_cases"] == data["judge"]["cases"]
    assert "100" in observed[0]["problem"]["description"]


@pytest.mark.parametrize("failure,expected", [
    ("timeout", "timeout"), ("offline", "unavailable"), ("missing_model", "unavailable"),
    ("invalid_json", "invalid_response"), ("wrong_schema", "invalid_response"),
    ("invented_evidence", "invalid_response"), ("solution", "invalid_response"),
    ("truncated", "invalid_response"),
])
def test_analysis_failure_preserves_judging(client, monkeypatch, failure, expected):
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("slow model")
        if failure == "offline":
            raise httpx.ConnectError("offline")
        if failure == "missing_model":
            return httpx.Response(404, json={"error": "model not found"})
        content = sample_analysis()
        if failure == "invented_evidence":
            content["evidence"][0]["quote"] = "99999"
        if failure == "solution":
            content["hints"]["level3"] = "```python\n" + CORRECT + "\n```"
        if failure == "wrong_schema":
            content.pop("hints")
        return httpx.Response(200, json={"done": True, "done_reason": "length" if failure == "truncated" else "stop",
                                       "message": {"content": "not json" if failure == "invalid_json" else json.dumps(content)}})

    mock_model(monkeypatch, handler)
    data = client.post("/api/v1/code/submit", headers=login(client),
                       json={"problem_id": "level2", "code": OVERWRITE}).json()["data"]
    assert data["judge"]["status"] == "wrong_answer"
    assert data["judge"]["cases"][0]["actual_output"] == "100\n"
    assert data["analysis"]["status"] == expected
    assert data["analysis"]["content"] is None
    assert len(calls) == (2 if expected == "invalid_response" else 1)


def test_submission_auth_problem_and_payload_validation(client):
    assert client.post("/api/v1/code/submit", json={"problem_id": "level1", "code": "print(1)"}).status_code == 401
    headers = login(client)
    assert client.post("/api/v1/code/submit", headers=headers, json={"problem_id": "missing", "code": "print(1)"}).status_code == 404
    assert client.post("/api/v1/code/submit", headers=headers, json={"problem_id": "level1", "code": "  "}).status_code == 422
    assert client.post("/api/v1/code/submit", headers=headers,
                       json={"problem_id": "level1", "code": "print(1)", "expected_output": "1"}).status_code == 422


def test_request_preserves_student_indentation():
    from app.services.submission import SubmissionRequest
    code = "    print('Hello, World!')\n"
    assert SubmissionRequest(problem_id="level1", code=code).code == code


def test_teaching_fields_are_prose_only_even_when_student_code_is_quoted(client, monkeypatch):
    def handler(request):
        facts = model_facts(json.loads(request.content))
        content = sample_analysis()
        content["suspected_cause"] = "疑似 print(missing_total) 引用了尚未定义的变量。"
        content["evidence"][0].update(field="error_message", quote=facts["failed_cases"][0]["errors"][0]["message"])
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(content)}})
    mock_model(monkeypatch, handler)
    data = client.post("/api/v1/code/submit", headers=login(client),
                       json={"problem_id": "level2", "code": "print(missing_total)"}).json()["data"]
    assert data["analysis"]["status"] == "invalid_response"


@pytest.mark.parametrize("code,quote", [("total = 0", ""), ("print('x' * 1001)", "x" * 1000),
                                        ("print('x' * 999 + ' ' + 'y')", "x" * 999)])
def test_empty_and_long_output_can_be_grounded(client, monkeypatch, code, quote):
    def handler(request):
        content = sample_analysis()
        content["evidence"][0]["quote"] = quote
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(content)}})
    mock_model(monkeypatch, handler)
    data = client.post("/api/v1/code/submit", headers=login(client), json={"problem_id": "level2", "code": code}).json()["data"]
    assert data["analysis"]["status"] == "ready"


@pytest.mark.parametrize("replacement", ["修改第三行：total += i", "完整正确代码：total = sum(range(1, 101)); print(total)"])
def test_inline_replacement_code_is_rejected(replacement):
    from app.services.error_analysis import AnalysisContent, validate_grounding
    from app.services.submission import PROBLEMS, judge_submission
    content = sample_analysis()
    content["suspected_cause"] = replacement
    with pytest.raises(ValueError):
        validate_grounding(AnalysisContent.model_validate(content), judge_submission(PROBLEMS["level2"], OVERWRITE))
