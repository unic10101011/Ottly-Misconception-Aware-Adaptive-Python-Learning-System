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
    account = {"username": "submission_student", "password": "TestPass1234!", "phone": "13800138000"}
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


def test_failed_submit_returns_judge_before_model_and_analysis_is_owned(client, monkeypatch):
    from app.services import error_analysis

    monkeypatch.setattr(error_analysis, "LOCAL_LLM_URL", "http://ollama.test/api/chat")
    monkeypatch.setattr(error_analysis.httpx, "AsyncClient",
                        lambda **kwargs: pytest.fail("submit must not call Ollama"))
    owner = login(client)
    first = client.post("/api/v1/code/submit", headers=owner,
                        json={"problem_id": "level2", "code": OVERWRITE}).json()["data"]
    assert first["judge"]["status"] == "wrong_answer"
    assert first["judge"]["cases"][0]["actual_output"] == "100\n"
    assert first["analysis"]["status"] == "preparing"
    assert first["timings"]["judge_ms"] >= 0
    path = f'/api/v1/code/submissions/{first["submission_id"]}/analysis'
    assert client.post(path).status_code == 401


@pytest.mark.parametrize("code,expected_fragment", [
    ("for i in range(1, 101)\n    print(i)", "基本格式"),
    ("print(missing_total)", "名字"),
    (OVERWRITE, "总数"),
])
def test_opening_question_uses_judge_category_and_lesson(code, expected_fragment):
    from app.services.error_analysis import opening_question
    from app.services.submission import PROBLEMS, judge_submission
    question = opening_question(PROBLEMS["level2"], judge_submission(PROBLEMS["level2"], code))
    assert expected_fragment in question
    assert question.endswith("？")
    assert not any(fragment in question for fragment in ("第2行", "101", "缺少", "改为"))


@pytest.mark.parametrize("code,expected_fragment", [
    ("for i in range(1, 101)\n    print(i)", "报错行"),
    ("print(missing_total)", "拼写"),
    (OVERWRITE, "前两轮"),
])
def test_safe_hint_fallback_is_progressive_and_avoids_solution(code, expected_fragment):
    from app.services.error_analysis import safe_hints
    from app.services.hint_quality import quality_issues
    from app.services.submission import PROBLEMS, judge_submission
    judge = judge_submission(PROBLEMS["level2"], code)
    hints = safe_hints(PROBLEMS["level2"], judge).model_dump()
    assert expected_fragment in hints["level3"]
    content = sample_analysis()
    content["hints"] = hints
    assert quality_issues(content, code, ["5050"]) == []


def test_safe_hint_fallback_does_not_assume_student_wrote_a_loop_or_print():
    from app.services.error_analysis import safe_hints
    from app.services.submission import PROBLEMS, judge_submission
    no_loop = safe_hints(PROBLEMS["level2"], judge_submission(PROBLEMS["level2"], "print(0)"))
    assert "循环头" not in no_loop.level2
    assert "程序实际取到" not in no_loop.level3
    assert "有没有" in no_loop.level2
    assert "旧总数" in no_loop.level3
    name_error = safe_hints(PROBLEMS["level2"], judge_submission(PROBLEMS["level2"], "x = missing_total + 1"))
    assert "输出语句" not in name_error.level2


def test_wrong_answer_fallback_checks_one_accumulation_step():
    from app.services.error_analysis import safe_hints
    from app.services.submission import PROBLEMS, judge_submission
    hints = safe_hints(PROBLEMS["level2"], judge_submission(PROBLEMS["level2"], OVERWRITE))
    assert "前两轮" in hints.level3
    assert "旧总数" in hints.level3
    assert "新总数" in hints.level3


@pytest.mark.parametrize("code", [
    "int sum = 0\nfor i in range(1,100):\n    sum += i\nprint(sum)",
    "for i in range(1, 101)\n    print(i)",
])
def test_syntax_error_uses_fast_grounded_hints_without_model(client, monkeypatch, code):
    from app.services import error_analysis

    monkeypatch.setattr(error_analysis, "LOCAL_LLM_URL", "http://ollama.test/api/chat")
    monkeypatch.setattr(error_analysis.httpx, "AsyncClient",
                        lambda **kwargs: pytest.fail("Syntax errors must not call Ollama"))
    data = client.post("/api/v1/code/submit", headers=login(client),
                       json={"problem_id": "level2", "code": code}).json()["data"]
    assert data["judge"]["status"] == "execution_error"
    assert data["judge"]["cases"][0]["errors"][0]["type"] == "SYNTAX_ERROR"
    analysis = data["analysis"]
    assert analysis["status"] == "ready"
    assert analysis["source"] == "fixed"
    assert analysis["content"]["evidence"][0]["quote"] == data["judge"]["cases"][0]["errors"][0]["message"]
    assert "变量名以数字开头" not in json.dumps(analysis, ensure_ascii=False)
    if code.startswith("int sum"):
        assert "声明" in analysis["content"]["suspected_cause"]
        assert "类型" in analysis["content"]["hints"]["level3"]


def mock_model(monkeypatch, handler, review_handler=None):
    from app.services import error_analysis
    factory = httpx.AsyncClient
    monkeypatch.setattr(error_analysis, "LOCAL_LLM_URL", "http://ollama.test/api/chat")
    async def dispatch(request):
        payload = json.loads(request.content)
        if payload.get("format", {}).get("title") == "HintReview":
            result = review_handler(request) if review_handler else httpx.Response(200, json={
                "done": True, "message": {"content": json.dumps({"issues": []})}})
        else:
            result = handler(request)
        return await result if asyncio.iscoroutine(result) else result

    monkeypatch.setattr(error_analysis.httpx, "AsyncClient", lambda **kwargs: factory(transport=httpx.MockTransport(dispatch), **kwargs))


def model_facts(payload):
    return json.JSONDecoder().raw_decode(payload["messages"][1]["content"])[0]


def submit_and_analyze(client, headers, **kwargs):
    response = client.post('/api/v1/code/submit', headers=headers, **kwargs)
    assert response.status_code == 200, response.text
    data = response.json()['data']
    if data['analysis']['status'] == 'preparing':
        analyzed = client.post(f"/api/v1/code/submissions/{data['submission_id']}/analysis", headers=headers)
        assert analyzed.status_code == 200, analyzed.text
        data['analysis'] = analyzed.json()['data']['analysis']
        data['timings'] = analyzed.json()['data']['timings']
    return data


@pytest.mark.parametrize('code,status,evidence', [
    ("for i in range(1, 101)\n    print(i)", 'execution_error', 'SYNTAX_ERROR'),
    ("print(missing_total)", 'execution_error', 'NAME_ERROR'),
    (OVERWRITE, 'wrong_answer', '100\n'),
])
def test_three_error_types_return_real_judge_evidence_before_ai(client, monkeypatch, code, status, evidence):
    from app.services import error_analysis
    monkeypatch.setattr(error_analysis, 'LOCAL_LLM_URL', 'http://ollama.test/api/chat')
    monkeypatch.setattr(error_analysis.httpx, 'AsyncClient',
                        lambda **kwargs: pytest.fail('first response must not load the model'))
    data = client.post('/api/v1/code/submit', headers=login(client),
                       json={'problem_id': 'level2', 'code': code}).json()['data']
    assert data['judge']['status'] == status
    public_case = data['judge']['cases'][0]
    if status == 'wrong_answer':
        assert public_case['actual_output'] == evidence
    else:
        assert evidence in json.dumps(public_case, ensure_ascii=False)
    assert data['analysis']['status'] == ('ready' if evidence == 'SYNTAX_ERROR' else 'preparing')


def test_model_timings_are_saved_and_repeat_analysis_does_not_recall_model(client, monkeypatch):
    calls = []

    def draft(request):
        calls.append('draft')
        return httpx.Response(200, json={'done': True, 'load_duration': 3_000_000,
                                         'message': {'content': json.dumps(sample_analysis())}})

    def review(request):
        calls.append('review')
        return httpx.Response(200, json={'done': True, 'load_duration': 2_000_000,
                                         'message': {'content': '{"issues": []}'}})

    mock_model(monkeypatch, draft, review)
    headers = login(client)
    first = client.post('/api/v1/code/submit', headers=headers,
                        json={'problem_id': 'level2', 'code': OVERWRITE}).json()['data']
    assert calls == []
    path = f"/api/v1/code/submissions/{first['submission_id']}/analysis"
    second = client.post(path, headers=headers).json()['data']
    assert calls == ['draft', 'review']
    assert second['timings']['judge_ms'] == first['timings']['judge_ms']
    assert second['timings']['model_load_ms'] == 5.0
    assert second['timings']['hint_generation_ms'] >= 0
    assert client.post(path, headers=headers).json()['data']['analysis'] == second['analysis']
    assert calls == ['draft', 'review']
    history = client.get('/api/v1/code/submissions', headers=headers).json()['data']['items'][0]
    assert history['judge'] == first['judge']
    assert history['analysis']['timings'] == second['timings']


def test_analysis_can_resume_older_record_without_saved_analysis(client, monkeypatch):
    from main import app
    from app.api import coding
    from app.core.database import get_db
    from app.models.learning_submission import LearningSubmission
    from app.services.error_analysis import AnalysisResult

    async def unavailable(*args):
        return AnalysisResult(status='unavailable', message='模型暂不可用。')

    monkeypatch.setattr(coding, 'analyze_failure', unavailable)
    headers = login(client)
    first = client.post('/api/v1/code/submit', headers=headers,
                        json={'problem_id': 'level2', 'code': OVERWRITE}).json()['data']
    database = next(app.dependency_overrides[get_db]())
    try:
        row = database.get(LearningSubmission, first['submission_id'])
        row.analysis_json = None
        database.commit()
    finally:
        database.close()
    path = f"/api/v1/code/submissions/{first['submission_id']}/analysis"
    response = client.post(path, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['data']['analysis']['status'] == 'unavailable'


def test_unhelpful_second_hint_uses_reviewed_fallback(client, monkeypatch):
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        content = sample_analysis()
        content["hints"]["level2"] = "使用变量之前，需要先明确哪些信息？"
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(content)}})

    mock_model(monkeypatch, handler)
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": OVERWRITE})
    assert data["analysis"]["status"] == "ready"
    assert len(calls) == 1
    assert "前两轮" in data["analysis"]["content"]["hints"]["level3"]
    assert "基础提示" in data["analysis"]["message"]
    # Avoid the Ollama 0.40.3 grammar failure; keep the question check in Pydantic.
    assert calls[0]["format"]["$defs"]["Hints"]["properties"]["level1"]["pattern"].endswith("*$")


def test_invalid_analysis_is_not_retried(client, monkeypatch):
    from app.services import error_analysis
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"done": True, "message": {"content": "invalid json"}})

    mock_model(monkeypatch, handler)
    monkeypatch.setattr(error_analysis, "ANALYSIS_TIMEOUT", 0.1)
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": OVERWRITE})
    assert len(calls) == 1
    assert data["analysis"]["status"] == "invalid_response"
    assert data["judge"]["status"] == "wrong_answer"


def test_semantic_rejection_does_not_change_judge_or_retry(client, monkeypatch):
    drafts, reviews = [], []

    def draft(request):
        drafts.append(json.loads(request.content))
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(sample_analysis())}})

    def review(request):
        payload = json.loads(request.content)
        reviews.append(payload)
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps({
            "issues": [{"code": "unrelated_claim", "reason": "候选解释提及了当前代码不支持的原因。"}]
        })}})

    mock_model(monkeypatch, draft, review)
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": OVERWRITE})
    assert data["analysis"]["status"] == "invalid_response"
    assert data["analysis"]["content"] is None
    assert data["judge"]["cases"][0]["actual_output"] == "100\n"
    assert len(drafts) == len(reviews) == 1
    assert model_facts(drafts[0])["student_code"] == OVERWRITE
    facts = json.loads(reviews[0]["messages"][-1]["content"])
    assert facts["student_code"] == OVERWRITE
    assert facts["failed_cases"][0]["actual_output"] == data["judge"]["cases"][0]["actual_output"]


@pytest.mark.parametrize("failure,expected", [("format", "invalid_response"), ("offline", "unavailable"),
                                            ("slow", "timeout"), ("plain_503", "unavailable")])
def test_unverified_analysis_is_not_displayed(client, monkeypatch, failure, expected):
    def draft(request):
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(sample_analysis())}})

    def review(request):
        if failure == "offline":
            raise httpx.ConnectError("review unavailable")
        if failure == "slow":
            raise httpx.ReadTimeout("review timed out")
        if failure == "plain_503":
            return httpx.Response(503, text="review unavailable")
        return httpx.Response(200, json={"done": True, "message": {"content": "{}"}})

    mock_model(monkeypatch, draft, review)
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": OVERWRITE})
    assert data["analysis"]["status"] == expected
    assert data["analysis"]["content"] is None
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
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": code})
    assert data["judge"]["status"] == status
    assert data["judge"]["cases"][0]["actual_output"] == actual
    assert data["analysis"]["status"] == "ready", data
    assert len(observed) == 1
    assert observed[0]["student_code"] == code
    assert observed[0]["failed_cases"][0]["actual_output"] == data["judge"]["cases"][0]["actual_output"]
    # The model retains original error names; only public results normalize them.
    from app.services.learning_contract import error_code
    model_errors = observed[0]['failed_cases'][0]['errors']
    public_errors = data['judge']['cases'][0]['errors']
    assert [error_code(error['type'], code=code) for error in model_errors] == [error['type'] for error in public_errors]
    assert "100" in observed[0]["problem"]["description"]


@pytest.mark.parametrize("failure,expected", [
    ("timeout", "timeout"), ("offline", "unavailable"), ("missing_model", "unavailable"),
    ("plain_503", "unavailable"),
    ("invalid_json", "invalid_response"), ("wrong_schema", "invalid_response"),
    ("invented_evidence", "invalid_response"), ("solution", "invalid_response"),
    ("truncated", "invalid_response"), ("false_pass", "invalid_response"),
    ("list_response", "invalid_response"),
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
        if failure == "plain_503":
            return httpx.Response(503, text="model temporarily unavailable")
        if failure == "list_response":
            return httpx.Response(200, json=[])
        content = sample_analysis()
        if failure == "invented_evidence":
            content["evidence"][0]["quote"] = "99999"
        if failure == "solution":
            content["hints"]["level3"] = "```python\n" + CORRECT + "\n```"
        if failure == "wrong_schema":
            content.pop("hints")
        if failure == "false_pass":
            content["suspected_cause"] = "判题已经通过所有测试。"
        return httpx.Response(200, json={"done": True, "done_reason": "length" if failure == "truncated" else "stop",
                                       "message": {"content": "not json" if failure == "invalid_json" else json.dumps(content)}})

    mock_model(monkeypatch, handler)
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": OVERWRITE})
    assert data["judge"]["status"] == "wrong_answer"
    assert data["judge"]["cases"][0]["actual_output"] == "100\n"
    assert data["analysis"]["status"] == expected
    assert data["analysis"]["content"] is None
    assert len(calls) == 1


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
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": "print(missing_total)"})
    assert data["analysis"]["status"] == "invalid_response"


@pytest.mark.parametrize("code,quote", [("total = 0", ""), ("print('x' * 1001)", "x" * 1000),
                                        ("print('x' * 999 + ' ' + 'y')", "x" * 999)])
def test_empty_and_long_output_can_be_grounded(client, monkeypatch, code, quote):
    def handler(request):
        content = sample_analysis()
        content["evidence"][0]["quote"] = quote
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(content)}})
    mock_model(monkeypatch, handler)
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": code})
    assert data["analysis"]["status"] == "ready"


@pytest.mark.parametrize("replacement", ["修改第三行：total += i", "完整正确代码：total = sum(range(1, 101)); print(total)"])
def test_inline_replacement_code_is_rejected(replacement):
    from app.services.error_analysis import AnalysisContent, validate_grounding
    from app.services.submission import PROBLEMS, judge_submission
    content = sample_analysis()
    content["suspected_cause"] = replacement
    with pytest.raises(ValueError):
        validate_grounding(AnalysisContent.model_validate(content), judge_submission(PROBLEMS["level2"], OVERWRITE))
