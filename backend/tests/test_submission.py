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
        "misconception_tag": "accumulation_error",
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

    monkeypatch.setattr(error_analysis, "DEEPSEEK_API_KEY", "test-only-cloud-key")
    monkeypatch.setattr(error_analysis.httpx, "AsyncClient",
                        lambda **kwargs: pytest.fail("submit must not call the model"))
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
def test_offline_syntax_error_keeps_grounded_compiler_hints(client, monkeypatch, code):
    from app.services import error_analysis

    monkeypatch.setattr(error_analysis, "DEEPSEEK_API_KEY", "")
    monkeypatch.setattr(error_analysis.httpx, "AsyncClient",
                        lambda **kwargs: pytest.fail("Missing key must not call the model"))
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": code})
    assert data["judge"]["status"] == "execution_error"
    assert data["judge"]["cases"][0]["errors"][0]["type"] == "SYNTAX_ERROR"
    analysis = data["analysis"]
    assert analysis["status"] == "unavailable"
    assert analysis["source"] is None
    assert analysis["content"] is None
    assert "DeepSeek" in analysis["message"]


@pytest.mark.parametrize('code,tag,actual', [
    ('total = 0\nfor i in range(1, 100):\n    total += i\nprint(total)', 'range_boundary', '4950\n'),
    (OVERWRITE, 'accumulation_error', '100\n'),
    ('print(0)', 'other', '0\n'),
    ('print(missing_total)', 'variable_error', ''),
])
def test_model_tag_is_saved_with_the_same_public_judge_evidence(client, monkeypatch, code, tag, actual):
    def handler(request):
        facts = model_facts(json.loads(request.content))
        case = facts['failed_cases'][0]
        content = sample_analysis()
        content['misconception_tag'] = tag
        content['suspected_cause'] = ('疑似使用了没有定义的名字。' if case['errors'] else
                                      '疑似本次代码处理方式与题目要求不符。')
        content['evidence'][0].update(
            field='error_message' if case['errors'] else 'actual_output',
            quote=case['errors'][0]['message'] if case['errors'] else case['actual_output'].strip(),
            explanation='公开测试显示了本次失败的真实结果。',
        )
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]})

    mock_model(monkeypatch, handler)
    headers = login(client)
    result = submit_and_analyze(client, headers, json={'problem_id': 'level2', 'code': code})
    assert result['judge']['cases'][0]['actual_output'] == actual
    assert result['analysis']['content']['misconception_tag'] == tag
    history = client.get('/api/v1/code/submissions', headers=headers).json()['data']['items'][0]
    assert history['analysis']['content']['misconception_tag'] == tag


def test_unknown_model_tag_is_downgraded_to_other(client, monkeypatch):
    def handler(request):
        content = sample_analysis()
        content['misconception_tag'] = 'sum_variable_name_error'
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]})

    mock_model(monkeypatch, handler)
    result = submit_and_analyze(client, login(client), json={'problem_id': 'level2', 'code': OVERWRITE})
    assert result['analysis']['status'] == 'ready'
    assert result['analysis']['content']['misconception_tag'] == 'other'


def test_diagnosis_ignores_related_history_and_saves_current_status(client, monkeypatch):
    drafts = []

    def handler(request):
        facts = model_facts(json.loads(request.content))
        drafts.append(facts)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(sample_analysis())}}]})

    mock_model(monkeypatch, handler)
    headers = login(client)
    first = submit_and_analyze(client, headers, json={'problem_id': 'level2', 'code': OVERWRITE})
    assert first['analysis']['personalization'] == {'used': False, 'related_history_count': 0}
    second = submit_and_analyze(client, headers, json={'problem_id': 'level2', 'code': OVERWRITE})
    assert second['analysis']['personalization'] == {'used': False, 'related_history_count': 0}
    history = drafts[1]['related_history']
    assert history == []
    assert OVERWRITE not in json.dumps(history)
    assert 'analysis_json' not in json.dumps(history)
    path = f"/api/v1/code/submissions/{second['submission_id']}/analysis"
    assert client.post(path, headers=headers).json()['data']['analysis']['personalization'] == second['analysis']['personalization']
    assert len(drafts) == 2
    saved = client.get('/api/v1/code/submissions', headers=headers).json()['data']['items'][0]
    assert saved['analysis']['personalization'] == second['analysis']['personalization']


@pytest.mark.parametrize('current_tag,expected_tag', [
    ('range_boundary', 'other'), ('variable_error', 'variable_error'),
])
def test_current_name_error_cannot_inherit_a_past_range_tag(client, monkeypatch, current_tag, expected_tag):
    observed = []

    def handler(request):
        facts = model_facts(json.loads(request.content))
        observed.append(facts)
        content = sample_analysis()
        if len(observed) == 1:
            content['misconception_tag'] = 'range_boundary'
            content['evidence'][0]['quote'] = '4950'
        else:
            content['misconception_tag'] = current_tag
            content['suspected_cause'] = '疑似使用了没有定义的名字。'
            content['evidence'][0].update(
                field='error_message', quote=facts['failed_cases'][0]['errors'][0]['message'],
                explanation='公开报错说明名字尚未定义。',
            )
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]})

    mock_model(monkeypatch, handler)
    headers = login(client)
    range_code = 'total = 0\nfor i in range(1, 100):\n    total += i\nprint(total)'
    first = submit_and_analyze(client, headers, json={'problem_id': 'level2', 'code': range_code})
    assert first['analysis']['content']['misconception_tag'] == 'range_boundary'
    second = submit_and_analyze(client, headers, json={'problem_id': 'level2', 'code': 'print(missing_total)'})
    assert observed[1]['related_history'] == []
    assert second['judge']['status'] == 'execution_error'
    assert second['analysis']['content']['misconception_tag'] == expected_tag


def test_correct_range_cannot_be_reported_as_boundary_error(client, monkeypatch):
    def handler(request):
        content = sample_analysis()
        content['misconception_tag'] = 'range_boundary'
        content['suspected_cause'] = '疑似循环范围没有包含一百。'
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]})

    mock_model(monkeypatch, handler)
    headers = login(client)
    result = submit_and_analyze(client, headers, json={'problem_id': 'level2', 'code': OVERWRITE})
    assert result['judge']['status'] == 'wrong_answer'
    assert result['analysis']['status'] == 'invalid_response'
    assert result['analysis']['content'] is None
    assert result['analysis']['personalization']['used'] is False


@pytest.mark.parametrize('cause', ['疑似循环内没有正确累加总数。', '变量未正确更新。'])
def test_name_error_rejects_unrelated_cause(client, monkeypatch, cause):
    def handler(request):
        case = model_facts(json.loads(request.content))['failed_cases'][0]
        content = sample_analysis()
        content['misconception_tag'] = 'variable_error'
        content['suspected_cause'] = cause
        content['evidence'][0].update(case_id=case['case_id'], field='error_message',
                                      quote=case['errors'][0]['message'],
                                      explanation='公开报错指出变量没有定义。')
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]})

    mock_model(monkeypatch, handler)
    headers = login(client)
    result = submit_and_analyze(client, headers,
                                json={'problem_id': 'level2', 'code': 'print(missing_total)'})
    assert result['judge']['status'] == 'execution_error'
    assert result['analysis']['status'] == 'invalid_response'
    assert result['analysis']['content'] is None


def test_name_error_accepts_spelling_explanation(client, monkeypatch):
    def handler(request):
        case = model_facts(json.loads(request.content))['failed_cases'][0]
        content = sample_analysis()
        content['misconception_tag'] = 'variable_error'
        content['suspected_cause'] = '疑似变量名拼写不一致。'
        content['evidence'][0].update(case_id=case['case_id'], field='error_message',
                                      quote=case['errors'][0]['message'],
                                      explanation='公开报错指出这个名字没有定义。')
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]})

    mock_model(monkeypatch, handler)
    result = submit_and_analyze(client, login(client),
                                json={'problem_id': 'level2', 'code': 'print(missing_total)'})
    assert result['analysis']['status'] == 'ready'
    assert result['analysis']['content']['misconception_tag'] == 'variable_error'


def test_model_failure_after_related_history_does_not_claim_personalization(client, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) > 1:
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': 'invalid json'}}]})
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(sample_analysis())}}]})

    mock_model(monkeypatch, handler)
    headers = login(client)
    submit_and_analyze(client, headers, json={'problem_id': 'level2', 'code': OVERWRITE})
    second = submit_and_analyze(client, headers, json={'problem_id': 'level2', 'code': OVERWRITE})
    assert second['analysis']['status'] == 'invalid_response'
    assert second['analysis']['personalization'] == {'used': False, 'related_history_count': 0}
    assert second['judge']['status'] == 'wrong_answer'


def test_greeting_undefined_username_uses_public_error_for_variable_tag(client, monkeypatch):
    observed = []

    def handler(request):
        facts = model_facts(json.loads(request.content))
        observed.append(facts)
        case = facts['failed_cases'][0]
        content = sample_analysis()
        content.update(
            misconception_tag='variable_error',
            suspected_cause='疑似使用了尚未赋值的名字。',
            knowledge_points=['变量、输入与字符串拼接'],
        )
        content['evidence'][0].update(case_id=case['case_id'], field='error_message',
                                      quote=case['errors'][0]['message'],
                                      explanation='公开运行错误指出这个名字尚未定义。')
        content['hints']['level2'] = '查看报错行里的名字，核对前面赋值时的拼写。'
        content['hints']['level3'] = '把报错中的名字和已有赋值逐字对照，再重新运行。'
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]})

    mock_model(monkeypatch, handler)
    headers = login(client)
    passed = client.post('/api/v1/code/submit', headers=headers,
                         json={'problem_id': 'level1', 'code': "print('Hello, World!')"})
    assert passed.json()['data']['judge']['passed'] is True
    code = 'name = input()\nprint("Hello, " + username + "!")'
    result = submit_and_analyze(client, headers, json={'problem_id': 'greeting-v1', 'code': code})
    assert result['analysis']['status'] == 'ready'
    assert result['analysis']['content']['misconception_tag'] == 'variable_error'
    assert len(observed[0]['failed_cases']) == 1
    assert observed[0]['failed_cases'][0]['case_id'] == 'sample-1'
    assert all(case['expected_output'] == '' and case['errors'] == []
               for case in result['judge']['cases'] if case['visibility'] == 'hidden')


@pytest.mark.parametrize('weak_hint', [False, True])
def test_greeting_missing_punctuation_sends_public_input_to_generation_and_review(client, monkeypatch, weak_hint):
    observed = []

    def draft(request):
        facts = model_facts(json.loads(request.content))
        observed.append(facts)
        content = sample_analysis()
        content.update(misconception_tag='other', suspected_cause='疑似问候语末尾缺少感叹号。',
                       knowledge_points=['字符串拼接与输出格式'])
        content['evidence'][0].update(case_id='sample-1', quote='Hello, Ottly',
                                     explanation='输出语句连接了问候前缀和姓名，但末尾没有题目要求的标点。')
        content['hints'].update(level2='检查输出语句中前缀、姓名和末尾标点的连接方式。',
                                level3='逐字对照实际输出和样例，记录末尾缺少的标点，再修改并运行。')
        if weak_hint:
            content['hints']['level3'] = '检查格式是否正确。'
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]})

    def review(request):
        observed.append(json.loads(request.content)['messages'][-1]['content'])
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'tag_supported': True, 'issues': []})}}]})

    mock_model(monkeypatch, draft, review)
    headers = login(client)
    assert client.post('/api/v1/code/submit', headers=headers, json={
        'problem_id': 'level1', 'code': 'print("Hello, World!")',
    }).json()['data']['judge']['passed']
    code = '# 读取朋友的姓名，再输出问候语\nfriend=input()\nprint("Hello, "+friend)'
    result = submit_and_analyze(client, headers, json={'problem_id': 'greeting-v1', 'code': code})
    assert result['analysis']['source'] == 'ai'
    assert '感叹号' in result['analysis']['content']['suspected_cause']
    # The second attempt has related AI history, but formatting analysis must
    # still see only current facts rather than copying a previous diagnosis.
    again = submit_and_analyze(client, headers, json={'problem_id': 'greeting-v1', 'code': code})
    assert again['analysis']['source'] == 'ai'
    assert again['analysis']['personalization'] == {'used': False, 'related_history_count': 0}
    for facts in (json.JSONDecoder().raw_decode(item)[0] if isinstance(item, str) else item for item in observed):
        assert facts['judge_status'] == 'wrong_answer'
        assert facts['related_history'] == []
        assert len(facts['failed_cases']) == 1
        case = facts['failed_cases'][0]
        assert case['case_id'] == 'sample-1'
        assert case['stdin'] == 'Ottly\n'
        assert case['output_differences'] == [{'actual': '', 'expected': '!'}]


def mock_model(monkeypatch, handler, review_handler=None):
    from app.services import error_analysis
    factory = httpx.AsyncClient
    monkeypatch.setattr(error_analysis, "DEEPSEEK_API_KEY", "test-only-cloud-key")
    async def dispatch(request):
        payload = json.loads(request.content)
        if request_schema(payload).get("title") == "HintReview":
            result = review_handler(request) if review_handler else httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {"content": json.dumps({"issues": [], "tag_supported": True})}}]})
        else:
            result = handler(request)
        result = await result if asyncio.iscoroutine(result) else result
        # Public response fixtures include trusted hints; the model now returns
        # only the diagnosis draft, and the service supplies reviewed hints.
        if request_schema(payload).get("title") == 'DiagnosisDraft':
            try:
                body = result.json()
                draft = json.loads(body['choices'][0]['message']['content'])
                draft.pop('hints', None)
                from app.services.problem_catalog import KNOWLEDGE, KNOWLEDGE_ALIASES, alias_key
                draft['knowledge_points'] = [KNOWLEDGE[KNOWLEDGE_ALIASES[alias_key(point)]].name if alias_key(point) in KNOWLEDGE_ALIASES else point for point in draft.get('knowledge_points', [])]
                draft.setdefault('code_observation', '核对本次代码及公开执行结果。')
                body['choices'][0]['message']['content'] = json.dumps(draft)
                return httpx.Response(result.status_code, json=body)
            except (ValueError, KeyError, TypeError, AttributeError):
                pass
        return result

    monkeypatch.setattr(error_analysis.httpx, "AsyncClient", lambda **kwargs: factory(transport=httpx.MockTransport(dispatch), **kwargs))


def request_schema(payload):
    return json.loads(payload['messages'][-1]['content'].rsplit('只返回符合以下 JSON Schema 的 JSON 对象：\n', 1)[1])


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
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_API_KEY', 'test-only-cloud-key')
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
    assert data['analysis']['status'] == 'preparing'


def test_model_timings_are_saved_and_repeat_analysis_does_not_recall_model(client, monkeypatch):
    calls = []

    def draft(request):
        calls.append('draft')
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(sample_analysis())}}]})

    def review(request):
        calls.append('review')
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{"issues": [], "tag_supported": true}'}}]})

    mock_model(monkeypatch, draft, review)
    headers = login(client)
    first = client.post('/api/v1/code/submit', headers=headers,
                        json={'problem_id': 'level2', 'code': OVERWRITE}).json()['data']
    assert calls == []
    path = f"/api/v1/code/submissions/{first['submission_id']}/analysis"
    second = client.post(path, headers=headers).json()['data']
    assert calls == ['draft', 'review']
    assert second['timings']['judge_ms'] == first['timings']['judge_ms']
    assert second['timings']['model_load_ms'] == 0.0
    assert second['analysis']['content']['misconception_tag'] == 'accumulation_error'
    assert second['timings']['hint_generation_ms'] >= 0
    assert client.post(path, headers=headers).json()['data']['analysis'] == second['analysis']
    assert calls == ['draft', 'review']
    history = client.get('/api/v1/code/submissions', headers=headers).json()['data']['items'][0]
    assert history['judge'] == first['judge']
    assert history['analysis']['timings'] == second['timings']


@pytest.mark.parametrize('other_issue,expected_status', [
    (None, 'ready'),
    ('unsupported_claim', 'invalid_response'),
    ('answer_leak', 'invalid_response'),
])
def test_review_cannot_reject_server_owned_opening_question(client, monkeypatch, other_issue, expected_status):
    from app.services.error_analysis import opening_question
    from app.services.submission import PROBLEMS, judge_submission

    def draft(request):
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(sample_analysis())}}]})

    def review(request):
        issues = [{'code': 'level1_leak', 'reason': '误判服务端概念问题'}]
        if other_issue:
            issues.append({'code': other_issue, 'reason': '其他分析内容仍需拦截'})
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'issues': issues, 'tag_supported': True})}}]})

    mock_model(monkeypatch, draft, review)
    data = submit_and_analyze(client, login(client), json={'problem_id': 'level2', 'code': OVERWRITE})
    assert data['analysis']['status'] == expected_status
    assert data['judge']['status'] == 'wrong_answer'
    if expected_status == 'ready':
        problem = PROBLEMS['level2']
        assert data['analysis']['content']['hints']['level1'] == opening_question(
            problem, judge_submission(problem, OVERWRITE))
        assert data['analysis']['content']['suspected_cause'] == sample_analysis()['suspected_cause']


@pytest.mark.parametrize('issue_codes,expected_status', [
    (['weak_level2'], 'ready'),
    (['weak_level3', 'repetition'], 'ready'),
    (['weak_level2', 'unsupported_claim'], 'invalid_response'),
    (['weak_level3', 'answer_leak'], 'invalid_response'),
])
def test_review_of_weak_hints_keeps_grounded_diagnosis(client, monkeypatch, issue_codes, expected_status):
    from app.services.error_analysis import safe_hints
    from app.services.submission import PROBLEMS, judge_submission

    def draft(request):
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(sample_analysis())}}]})

    def review(request):
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
            'tag_supported': True,
            'issues': [{'code': code, 'reason': '审核发现问题'} for code in issue_codes],
        })}}]})

    mock_model(monkeypatch, draft, review)
    data = submit_and_analyze(client, login(client), json={'problem_id': 'level2', 'code': OVERWRITE})
    assert data['analysis']['status'] == expected_status
    if expected_status == 'ready':
        content = data['analysis']['content']
        assert data['analysis']['source'] == 'ai'
        assert content['suspected_cause'] == sample_analysis()['suspected_cause']
        assert content['evidence'][0]['quote'] == '100'
        hints = safe_hints(PROBLEMS['level2'], judge_submission(PROBLEMS['level2'], OVERWRITE))
        assert content['hints'] == hints.model_dump()
        assert '基础提示' in data['analysis']['message']


def test_analysis_can_resume_older_record_without_saved_analysis(client, monkeypatch):
    from main import app
    from app.api import coding
    from app.core.database import get_db
    from app.models.learning_submission import LearningSubmission
    from app.services.error_analysis import AnalysisResult

    async def unavailable(*args, **kwargs):
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


def test_model_generates_only_diagnosis_and_service_supplies_reviewed_hints(client, monkeypatch):
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        content = sample_analysis()
        content["hints"]["level2"] = "使用变量之前，需要先明确哪些信息？"
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {"content": json.dumps(content)}}]})

    mock_model(monkeypatch, handler)
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": OVERWRITE})
    assert data["analysis"]["status"] == "ready"
    assert len(calls) == 1
    assert "前两轮" in data["analysis"]["content"]["hints"]["level3"]
    assert "基础提示" in data["analysis"]["message"]
    assert 'hints' not in request_schema(calls[0])['properties']
    assert 'Hints' not in request_schema(calls[0])['$defs']


def test_invalid_analysis_is_not_retried(client, monkeypatch):
    from app.services import error_analysis
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {"content": "invalid json"}}]})

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
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {"content": json.dumps(sample_analysis())}}]})

    def review(request):
        payload = json.loads(request.content)
        reviews.append(payload)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {"content": json.dumps({
            "issues": [{"code": "unrelated_claim", "reason": "候选解释提及了当前代码不支持的原因。"}],
            "tag_supported": True,
        })}}]})

    mock_model(monkeypatch, draft, review)
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": OVERWRITE})
    assert data["analysis"]["status"] == "invalid_response"
    assert data["analysis"]["content"] is None
    assert data["judge"]["cases"][0]["actual_output"] == "100\n"
    assert len(drafts) == len(reviews) == 1
    assert model_facts(drafts[0])["student_code"] == OVERWRITE
    facts = model_facts(reviews[0])
    assert facts["student_code"] == OVERWRITE
    assert facts["failed_cases"][0]["actual_output"] == data["judge"]["cases"][0]["actual_output"]


def test_unsupported_specific_tag_is_saved_as_other(client, monkeypatch):
    def draft(request):
        content = sample_analysis()
        content['misconception_tag'] = 'range_boundary'
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]})

    def review(request):
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
            'issues': [], 'tag_supported': False,
        })}}]})

    mock_model(monkeypatch, draft, review)
    headers = login(client)
    data = submit_and_analyze(client, headers, json={'problem_id': 'level2', 'code': OVERWRITE})
    assert data['analysis']['status'] == 'ready'
    assert data['analysis']['content']['misconception_tag'] == 'other'
    items = client.get('/api/v1/code/misconceptions', headers=headers).json()['data']['items']
    assert [item['misconception_tag'] for item in items] == ['other']


@pytest.mark.parametrize("failure,expected", [("format", "invalid_response"), ("offline", "unavailable"),
                                            ("slow", "timeout"), ("plain_503", "unavailable")])
def test_unverified_analysis_is_not_displayed(client, monkeypatch, failure, expected):
    def draft(request):
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {"content": json.dumps(sample_analysis())}}]})

    def review(request):
        if failure == "offline":
            raise httpx.ConnectError("review unavailable")
        if failure == "slow":
            raise httpx.ReadTimeout("review timed out")
        if failure == "plain_503":
            return httpx.Response(503, text="review unavailable")
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {"content": "{}"}}]})

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
        if case["errors"]:
            content["suspected_cause"] = "疑似使用了没有定义的名字。"
        assert request_schema(payload)["type"] == "object"
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {"content": json.dumps(content)}}]})

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
            content["suspected_cause"] = "```python\n" + CORRECT + "\n```"
        if failure == "wrong_schema":
            content.pop("suspected_cause")
        if failure == "false_pass":
            content["suspected_cause"] = "判题已经通过所有测试。"
        return httpx.Response(200, json={'choices': [{'finish_reason': 'length' if failure == 'truncated' else 'stop', 'message': {"content": "not json" if failure == "invalid_json" else json.dumps(content)}}]})

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


def test_output_analysis_receives_verdict_and_real_character_differences(client, monkeypatch):
    observed = []

    def draft(request):
        facts = model_facts(json.loads(request.content))
        observed.append(facts)
        content = sample_analysis()
        content.update(misconception_tag='other', suspected_cause='疑似输出文本的大小写和标点不符合要求。')
        content['evidence'][0].update(quote='Hello, world', explanation='实际输出与题目要求的文本不同。')
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(content)}}]})

    mock_model(monkeypatch, draft)
    code = '# 请让 Ottly 说出她的第一句话\nprint("Hello, world")'
    result = submit_and_analyze(client, login(client), json={'problem_id': 'level1', 'code': code})
    assert result['analysis']['status'] == 'ready'
    assert result['analysis']['source'] == 'ai'
    assert observed[0]['student_code'] == code
    assert observed[0]['judge_status'] == 'wrong_answer'
    assert observed[0]['failed_cases'][0]['errors'] == []
    assert observed[0]['failed_cases'][0]['output_differences'] == [
        {'actual': 'w', 'expected': 'W'}, {'actual': '', 'expected': '!'},
    ]


@pytest.mark.parametrize('comparison,actual,expected_diff', [
    ('legacy_trim', '  Hello, World!\r\n', []),
    ('exact', 'Hello, World!\r\n', [{'actual': '\n', 'expected': ''}]),
])
def test_output_differences_follow_judge_whitespace_rules(comparison, actual, expected_diff):
    from app.services.error_analysis import output_differences
    from app.services.submission import CaseResult, PROBLEMS
    case = CaseResult(case_id='stdout-1', passed=False, expected_output='Hello, World!',
                      actual_output=actual, errors=[], execution_time=0)
    problem = PROBLEMS['level1'].model_copy(update={'comparison': comparison})
    assert output_differences(problem, case) == expected_diff


@pytest.mark.parametrize('updates', [
    {'visibility': 'hidden'}, {'output_available': False}, {'passed': True},
    {'errors': [{'type': 'NameError', 'message': 'missing name'}]},
    {'actual_output': 'x' * 1001},
])
def test_output_differences_exclude_private_missing_or_error_results(updates):
    from app.services.error_analysis import output_differences
    from app.services.submission import CaseResult, PROBLEMS
    case = CaseResult.model_validate(dict(case_id='stdout-1', passed=False, expected_output='Hello, World!',
                                         actual_output='Hello, world', errors=[], execution_time=0) | updates)
    assert output_differences(PROBLEMS['level1'], case) == []


def test_diagnosis_can_quote_the_students_existing_expression(client, monkeypatch):
    def handler(request):
        facts = model_facts(json.loads(request.content))
        content = sample_analysis()
        content["suspected_cause"] = "疑似 print(missing_total) 引用了尚未定义的变量。"
        content["evidence"][0].update(field="error_message", quote=facts["failed_cases"][0]["errors"][0]["message"])
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {"content": json.dumps(content)}}]})
    mock_model(monkeypatch, handler)
    data = submit_and_analyze(client, login(client), json={"problem_id": "level2", "code": "print(missing_total)"})
    assert data["analysis"]["status"] == "ready"


@pytest.mark.parametrize("code,quote", [("total = 0", ""), ("print('x' * 1001)", "x" * 1000),
                                        ("print('x' * 999 + ' ' + 'y')", "x" * 999)])
def test_empty_and_long_output_can_be_grounded(client, monkeypatch, code, quote):
    def handler(request):
        content = sample_analysis()
        content["evidence"][0]["quote"] = quote
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {"content": json.dumps(content)}}]})
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
