"""A submission is a user's durable learning attempt, not a chat message."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


WRONG = "total = 0\nfor i in range(1, 101):\n    total = i\nprint(total)"
CORRECT = "total = 0\nfor i in range(1, 101):\n    total += i\nprint(total)"


@pytest.fixture
def client(tmp_path, monkeypatch):
    os.environ.setdefault("DATABASE_URL", "sqlite://")
    os.environ.setdefault("JWT_SECRET", "learning-history-test-secret")
    from main import app
    from app.api import coding
    from app.core.database import Base, get_db
    from app.services.error_analysis import AnalysisResult

    engine = create_engine(f"sqlite:///{(tmp_path / 'history.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def db_override():
        with sessions() as db:
            yield db

    async def analysis_stub(problem, code, judge):
        if judge.passed:
            return AnalysisResult(status="skipped", message="测试已通过。")
        return AnalysisResult.model_validate({
            "status": "ready", "message": "基于本次证据的提示。",
            "content": {
                "suspected_cause": "疑似每轮覆盖了此前的总数。",
                "evidence": [{"case_id": "stdout-1", "field": "actual_output",
                              "quote": "100", "explanation": "实际输出只保留了最后一个值。"}],
                "knowledge_points": ["累加"],
                "hints": {"level1": "累计结果怎样变化？",
                          "level2": "观察循环体中的赋值操作。",
                          "level3": "记录前两轮的旧值与新值，再核对更新方式。"},
            },
        })

    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(coding, "analyze_failure", analysis_stub)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def account(client, username, phone):
    body = {"username": username, "password": "TestPass1234!", "phone": phone}
    assert client.post("/api/v1/auth/register", json=body).json()["code"] == 201
    token = client.post("/api/v1/auth/login", json=body).json()["data"]["access_token"]
    return {"Authorization": "Bearer " + token}


def submit(client, headers, code):
    response = client.post("/api/v1/code/submit", headers=headers,
                           json={"problem_id": "level2", "code": code})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_wrong_and_later_correct_are_both_saved_and_visible_after_relogin(client):
    headers = account(client, "learner_a", "13800000001")
    wrong = submit(client, headers, WRONG)
    correct = submit(client, headers, CORRECT)
    assert wrong["submission_id"] != correct["submission_id"]
    assert wrong["judge"]["status"] == "wrong_answer"
    assert correct["judge"]["status"] == "accepted"
    assert correct["analysis"]["status"] == "skipped"

    renewed = client.post("/api/v1/auth/login", json={
        "username": "learner_a", "password": "TestPass1234!"
    }).json()["data"]["access_token"]
    renewed_headers = {"Authorization": "Bearer " + renewed}
    all_attempts = client.get("/api/v1/code/submissions", headers=renewed_headers).json()["data"]
    assert all_attempts["total"] == 2
    assert [item["id"] for item in all_attempts["items"]] == [
        correct["submission_id"], wrong["submission_id"]
    ]
    mistakes = client.get("/api/v1/code/submissions?failed_only=true", headers=renewed_headers).json()["data"]
    assert mistakes["total"] == 1
    item = mistakes["items"][0]
    assert item["code"] == WRONG
    assert item["problem_id"] == "level2"
    assert "100" in item["problem_description"]
    assert item["judge"]["cases"][0]["actual_output"] == "100\n"
    assert item["analysis"]["status"] == "ready"
    assert item["hints_viewed_max"] == 0
    assert item["resolved_later"] is True
    assert item["created_at"].endswith("Z")


def test_histories_and_hint_updates_are_owned_by_current_user(client):
    first = account(client, "learner_first", "13800000002")
    second = account(client, "learner_second", "13800000003")
    attempt = submit(client, first, WRONG)
    submission_id = attempt["submission_id"]

    assert client.get("/api/v1/code/submissions", headers=second).json()["data"]["items"] == []
    assert client.patch(f"/api/v1/code/submissions/{submission_id}/hints",
                        headers=second, json={"level": 1}).status_code == 404
    for level, expected in [(1, 1), (3, 3), (2, 3)]:
        result = client.patch(f"/api/v1/code/submissions/{submission_id}/hints",
                              headers=first, json={"level": level})
        assert result.status_code == 200, result.text
        assert result.json()["data"]["hints_viewed_max"] == expected
    saved = client.get("/api/v1/code/submissions?failed_only=true", headers=first).json()["data"]
    assert saved["items"][0]["hints_viewed_max"] == 3
    assert client.patch(f"/api/v1/code/submissions/{submission_id}/hints",
                        headers=first, json={"level": 4}).status_code == 422
    assert client.get("/api/v1/code/submissions").status_code == 401


def test_ai_unavailable_and_accepted_submission_still_have_records(client, monkeypatch):
    from app.api import coding
    from app.services.error_analysis import AnalysisResult
    async def unavailable(problem, code, judge):
        if judge.passed:
            return AnalysisResult(status="skipped", message="测试已通过。")
        return AnalysisResult(status="unavailable", message="模型不可用。")
    monkeypatch.setattr(coding, "analyze_failure", unavailable)
    headers = account(client, "learner_offline", "13800000004")
    failed = submit(client, headers, WRONG)
    passed = submit(client, headers, CORRECT)
    items = client.get("/api/v1/code/submissions", headers=headers).json()["data"]["items"]
    assert {item["id"] for item in items} == {failed["submission_id"], passed["submission_id"]}
    error_item = next(item for item in items if not item["passed"])
    assert error_item["judge"]["status"] == "wrong_answer"
    assert error_item["analysis"]["status"] == "unavailable"
    assert client.patch(f"/api/v1/code/submissions/{failed['submission_id']}/hints",
                        headers=headers, json={"level": 1}).status_code == 409
    assert client.patch(f"/api/v1/code/submissions/{passed['submission_id']}/hints",
                        headers=headers, json={"level": 1}).status_code == 409


def test_stale_parallel_hint_update_cannot_lower_saved_level(tmp_path, monkeypatch):
    import threading
    from app.api.learning_history import HintViewRequest, record_hint_view
    from app.core.database import Base
    from app.models.learning_submission import LearningSubmission
    from app.models.user import User
    from sqlalchemy.orm import Query

    engine = create_engine(f"sqlite:///{(tmp_path / 'stale.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as setup:
        user = User(username="stale_user", password="hash", phone="13800000999")
        setup.add(user)
        setup.flush()
        record = LearningSubmission(
            user_id=user.id, problem_id="level2", problem_title="test",
            problem_description="test", code="print(0)", judge_json={},
            analysis_json={"status": "ready"}, passed=False,
        )
        setup.add(record)
        setup.commit()
        user_id, record_id = user.id, record.id

    barrier = threading.Barrier(2)
    high_finished = threading.Event()
    errors = []
    original_first = Query.first

    def pause_after_read(query):
        row = original_first(query)
        if isinstance(row, LearningSubmission):
            query.session.commit()  # Release SQLite's read transaction but keep this ORM snapshot.
            barrier.wait(timeout=5)
            if threading.current_thread().name == "low":
                assert high_finished.wait(timeout=5)
        return row

    monkeypatch.setattr(Query, "first", pause_after_read)

    def update(level):
        try:
            with sessions() as db:
                user = db.get(User, user_id)
                record_hint_view(record_id, HintViewRequest(level=level), user, db)
        except Exception as error:
            errors.append(error)
        finally:
            if level == 3:
                high_finished.set()

    high = threading.Thread(target=update, args=(3,), name="high")
    low = threading.Thread(target=update, args=(1,), name="low")
    high.start()
    low.start()
    high.join(timeout=10)
    low.join(timeout=10)
    assert not high.is_alive() and not low.is_alive()
    assert not errors, errors
    with sessions() as check:
        assert check.get(LearningSubmission, record_id).hints_viewed_max == 3
    engine.dispose()


def test_review_submissions_group_by_problem_and_keep_all_attempts(client):
    headers = account(client, "review_learner", "13800000005")
    first_wrong = submit(client, headers, WRONG)
    review_headers = {**headers, "X-Review-Source-Id": str(first_wrong["submission_id"])}
    for code in (WRONG, CORRECT, CORRECT):
        submit(client, review_headers, code)
    submit(client, headers, CORRECT)  # A normal level attempt is not a review.

    response = client.get("/api/v1/code/mistakes", headers=headers)
    assert response.status_code == 200, response.text
    summaries = response.json()["data"]["items"]
    assert len(summaries) == 1
    item = summaries[0]
    assert item["problem_id"] == "level2"
    assert item["source"] == "系统关卡"
    assert item["first_wrong_submission_id"] == first_wrong["submission_id"]
    assert item["review_count"] == 3
    assert item["recent_review_passed"] == 2
    assert item["review_rate_percent"] == 67
    assert item["attempt_count"] == 5
    assert item["latest_suspected_cause"] == "疑似每轮覆盖了此前的总数。"
    assert item["related_questions"] == []

    timeline = client.get("/api/v1/code/submissions?problem_id=level2", headers=headers).json()["data"]
    assert timeline["total"] == 5
    assert client.get("/api/v1/code/submissions?problem_id=level1", headers=headers).json()["data"]["items"] == []


def test_review_source_must_be_owned_wrong_and_same_problem(client):
    first = account(client, "review_owner", "13800000006")
    second = account(client, "review_other", "13800000007")
    wrong = submit(client, first, WRONG)
    accepted = submit(client, first, CORRECT)

    for source_id, headers, problem_id in (
        (wrong["submission_id"], second, "level2"),
        (accepted["submission_id"], first, "level2"),
        (wrong["submission_id"], first, "level1"),
    ):
        response = client.post("/api/v1/code/submit", headers={
            **headers, "X-Review-Source-Id": str(source_id),
        }, json={"problem_id": problem_id, "code": "print('Hello, World!')"})
        assert response.status_code == 404

    assert client.get("/api/v1/code/mistakes", headers=second).json()["data"]["items"] == []
