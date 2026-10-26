import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("ottly") / "test.sqlite"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["JWT_SECRET"] = "test-secret-for-local-integration"
    from main import app
    from app.core.database import engine

    assert engine.url.get_backend_name() == "sqlite"
    with TestClient(app) as test_client:
        yield test_client


def register_and_login(client, username, phone):
    registered = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "TestPass1234!", "phone": phone},
    )
    assert registered.status_code == 200
    assert registered.json()["code"] == 201
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "TestPass1234!"},
    )
    assert logged_in.status_code == 200
    return registered.json()["data"]["id"], logged_in.json()["data"]["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_access_token_lasts_eight_hours(client):
    _, token = register_and_login(client, "eight_hour_student", "13800000088")
    payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    remaining_seconds = payload["exp"] - datetime.now(timezone.utc).timestamp()
    assert 8 * 60 * 60 - 10 <= remaining_seconds <= 8 * 60 * 60 + 10


@pytest.mark.parametrize('password', ['', '123456', 'x' * 129, ' ' * 12,
                                      '123456789012', 'password1234', 'a' * 12,
                                      'policy_student', '139123456789'])
def test_registration_rejects_weak_password_without_echoing_it(client, password):
    from app.core.database import SessionLocal
    from app.models.user import User
    response = client.post('/api/v1/auth/register', json={
        'username': 'policy_student', 'phone': '139123456789', 'password': password,
    })
    assert response.json()['code'] == 400
    assert response.json()['data'] == {}
    if password.strip():
        assert password not in response.text
    with SessionLocal() as db:
        assert db.query(User).filter(User.username == 'policy_student').first() is None


def test_password_is_salted_hashed_and_old_short_password_still_logs_in(client):
    from app.core.auth import get_password_hash, verify_password
    from app.core.database import SessionLocal
    from app.models.user import User
    register_and_login(client, 'hashed_student', '13988880001')
    with SessionLocal() as db:
        stored = db.query(User).filter(User.username == 'hashed_student').one().password
        assert stored.startswith('$argon2id$')
        assert stored != 'TestPass1234!'
        assert verify_password('TestPass1234!', stored)
        assert get_password_hash('TestPass1234!') != stored
        db.add(User(username='legacy_short_password', phone='13988880002', password=get_password_hash('old123')))
        db.commit()
    response = client.post('/api/v1/auth/login', json={'username': 'legacy_short_password', 'password': 'old123'})
    assert response.status_code == 200
    assert 'old123' not in response.text


def test_login_identifies_each_user_and_protects_private_routes(client):
    first_id, first_token = register_and_login(client, "student_one", "13800000001")
    second_id, second_token = register_and_login(client, "student_two", "13800000002")
    assert first_id != second_id
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth(first_token)).json()["data"]["id"] == first_id
    assert client.get("/api/v1/auth/me", headers=auth(second_token)).json()["data"]["id"] == second_id
    assert client.post("/api/v1/code/run", json={"code": "print(1)"}).status_code == 401


def test_chat_history_and_class_records_are_user_isolated(client):
    from app.core.database import SessionLocal
    from app.models.user import AIChatRecord, User

    db = SessionLocal()
    try:
        first = db.query(User).filter(User.username == "student_one").one()
        second = db.query(User).filter(User.username == "student_two").one()
        db.add(AIChatRecord(
            user_id=first.id, conversation_id=1, session_id="shared-session",
            question="my question", question_type="text", answer="my answer",
        ))
        db.commit()
    finally:
        db.close()

    first_token = client.post("/api/v1/auth/login", json={
        "username": "student_one", "password": "TestPass1234!",
    }).json()["data"]["access_token"]
    second_token = client.post("/api/v1/auth/login", json={
        "username": "student_two", "password": "TestPass1234!",
    }).json()["data"]["access_token"]
    first_history = client.get("/api/v1/ai/history", headers=auth(first_token)).json()
    second_history = client.get("/api/v1/ai/history", headers=auth(second_token)).json()
    assert first_history["total"] == 1
    assert second_history["total"] == 0

    selected = client.post("/api/v1/class/select", headers=auth(first_token),
                           json={"class_name": "变量巫师"})
    assert selected.status_code == 200
    assert len(client.get("/api/v1/class/records", headers=auth(first_token)).json()["data"]) == 1
    assert client.get("/api/v1/class/records", headers=auth(second_token)).json()["data"] == []


def test_unverified_password_reset_is_disabled(client):
    response = client.post("/api/v1/auth/reset-password", json={
        "phone": "13800000001", "new_password": "StolenPassword123!",
    })
    assert response.status_code == 410


def test_account_update_password_and_permanent_deletion(client):
    from app.core.database import SessionLocal
    from app.models.class_selection import ClassSelection
    from app.models.learning_review import LearningReview
    from app.models.learning_submission import LearningSubmission
    from sqlalchemy import text
    from app.models.user import AIChatRecord, User

    user_id, token = register_and_login(client, "account_owner", "13800000008")
    other_id, other_token = register_and_login(client, "account_other", "13800000009")
    headers = auth(token)
    assert client.patch("/api/v1/auth/me", headers=headers, json={
        "username": "account_owner_new", "phone": "13800000018", "current_password": "wrong",
    }).status_code == 403
    updated = client.patch("/api/v1/auth/me", headers=headers, json={
        "username": "account_owner_new", "phone": "13800000018", "current_password": "TestPass1234!",
    })
    assert updated.status_code == 200
    token = updated.json()["data"]["access_token"]
    headers = auth(token)
    assert client.get("/api/v1/auth/me", headers=headers).json()["data"]["phone"] == "13800000018"
    assert client.get("/api/v1/auth/me", headers=auth(other_token)).json()["data"]["username"] == "account_other"

    changed = client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "TestPass1234!", "new_password": "NewPass123!",
    })
    assert changed.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "username": "account_owner_new", "password": "TestPass1234!",
    }).status_code == 401
    token = client.post("/api/v1/auth/login", json={
        "username": "account_owner_new", "password": "NewPass123!",
    }).json()["data"]["access_token"]
    headers = auth(token)

    db = SessionLocal()
    try:
        db.add(AIChatRecord(user_id=user_id, conversation_id=1, session_id="remove-me",
                            question="question", question_type="text", answer="answer"))
        db.add(ClassSelection(user_id=user_id, class_name="变量巫师"))
        # Simulate rows left by an older deployment, without registering retired ORM models.
        db.execute(text('CREATE TABLE user_settings (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL)'))
        db.execute(text('CREATE TABLE notification_preferences (id INTEGER PRIMARY KEY, user_settings_id INTEGER NOT NULL REFERENCES user_settings(id))'))
        db.execute(text('CREATE TABLE language_settings (id INTEGER PRIMARY KEY, user_settings_id INTEGER NOT NULL REFERENCES user_settings(id))'))
        db.execute(text('INSERT INTO user_settings (id, user_id) VALUES (501, :owner), (502, :other)'),
                   {'owner': user_id, 'other': other_id})
        for name in ('notification_preferences', 'language_settings'):
            db.execute(text(f'INSERT INTO {name} (id, user_settings_id) VALUES (501, 501), (502, 502)'))
        wrong = LearningSubmission(user_id=user_id, problem_id="level1", problem_title="t",
                                   problem_description="d", code="bad", judge_json={}, passed=False)
        db.add(wrong)
        db.flush()
        passed = LearningSubmission(user_id=user_id, problem_id="level1", problem_title="t",
                                    problem_description="d", code="good", judge_json={}, passed=True)
        db.add(passed)
        db.flush()
        db.add(LearningReview(user_id=user_id, submission_id=passed.id, source_submission_id=wrong.id))
        db.commit()
    finally:
        db.close()

    assert client.get("/api/v1/code/progress", headers=headers).json()["data"]["passed_problem_ids"] == ["level1"]
    assert client.get("/api/v1/code/progress", headers=auth(other_token)).json()["data"]["passed_problem_ids"] == []

    assert client.request("DELETE", "/api/v1/auth/me", headers=headers,
                          json={"current_password": "wrong"}).status_code == 403
    assert client.request("DELETE", "/api/v1/auth/me", headers=headers,
                          json={"current_password": "NewPass123!"}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    db = SessionLocal()
    try:
        for model in (User, AIChatRecord, ClassSelection, LearningSubmission, LearningReview):
            key = User.id if model is User else model.user_id if hasattr(model, "user_id") else None
            if key is not None:
                assert db.query(model).filter(key == user_id).count() == 0
        assert db.execute(text('SELECT COUNT(*) FROM user_settings WHERE user_id = :id'), {'id': user_id}).scalar() == 0
        assert db.execute(text('SELECT COUNT(*) FROM user_settings WHERE user_id = :id'), {'id': other_id}).scalar() == 1
        for name in ('notification_preferences', 'language_settings'):
            assert db.execute(text(f'SELECT COUNT(*) FROM {name} WHERE user_settings_id = 501')).scalar() == 0
            assert db.execute(text(f'SELECT COUNT(*) FROM {name} WHERE user_settings_id = 502')).scalar() == 1
    finally:
        db.close()

    from app.api.ai import save_chat_if_active
    db = SessionLocal()
    try:
        assert not save_chat_if_active(db, user_id, AIChatRecord(
            user_id=user_id, conversation_id=1, session_id="late-chat",
            question="late", question_type="text", answer="late answer",
        ))
        assert db.query(AIChatRecord).filter_by(session_id="late-chat").count() == 0
    finally:
        db.close()
    _, new_token = register_and_login(client, "account_owner_new", "13800000018")
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.get("/api/v1/ai/history", headers=auth(new_token)).json()["total"] == 0


def test_retired_preferences_have_no_routes_or_registered_models(client):
    from app.core.database import Base
    assert {'user_settings', 'notification_preferences', 'language_settings'}.isdisjoint(Base.metadata.tables)
    for method, path in [
        ('POST', '/api/v1/settings'),
        ('GET', '/api/v1/settings/1'), ('PUT', '/api/v1/settings/1'),
        ('GET', '/api/v1/settings/1/notifications'), ('PUT', '/api/v1/settings/1/notifications'),
        ('GET', '/api/v1/settings/1/language'), ('PUT', '/api/v1/settings/1/language'),
    ]:
        assert client.request(method, path).status_code == 404


def test_delayed_judge_cannot_write_after_account_delete(client, monkeypatch):
    from app.api import coding
    from app.core.database import SessionLocal
    from app.models.learning_submission import LearningSubmission
    from app.models.user import User

    user_id, token = register_and_login(client, "delayed_student", "13800000010")

    async def delete_before_judge_returns(fn, problem, code):
        with SessionLocal() as db:
            db.query(User).filter(User.id == user_id).delete()
            db.commit()
        return fn(problem, code)

    monkeypatch.setattr(coding, "run_in_threadpool", delete_before_judge_returns)
    response = client.post("/api/v1/code/submit", headers=auth(token), json={
        "problem_id": "level1", "code": "print('Hello, World!')",
    })
    assert response.status_code == 401
    with SessionLocal() as db:
        assert db.query(LearningSubmission).filter_by(user_id=user_id).count() == 0

def test_deepseek_chat_non_stream_and_stream_save_history(client, monkeypatch):
    import json
    import httpx
    from app.api import ai

    _, token = register_and_login(client, "deepseek_student", "13800000005")
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.url.path == "/chat/completions"
        assert payload["model"] == "deepseek-flash"
        assert payload["messages"][-1]["content"] in {"Explain Python lists", "Explain a loop"}
        if payload["stream"]:
            chunks = [
                {"choices": [{"delta": {"content": "Use "}, "finish_reason": None}]},
                {"choices": [{"delta": {"content": "for."}, "finish_reason": None}]},
                {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            ]
            return httpx.Response(200, text="\n\n".join("data: " + json.dumps(c) for c in chunks) + "\n\n")
        return httpx.Response(200, json={"choices": [{"message": {"content": "A list stores values."}, "finish_reason": "stop"}]})

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(ai.error_analysis, "DEEPSEEK_API_KEY", "test-chat-key")
    monkeypatch.setattr(ai.error_analysis, "DEEPSEEK_BASE_URL", "https://deepseek.test")
    monkeypatch.setattr(ai.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))

    normal = client.post("/api/v1/ai/chat", headers=auth(token), json={
        "question": "Explain Python lists", "stream": False,
    })
    assert normal.status_code == 200
    assert normal.json()["data"]["answer"] == "A list stores values."
    session_id = normal.json()["data"]["session_id"]

    streamed = client.post("/api/v1/ai/chat", headers=auth(token), json={
        "question": "Explain a loop", "stream": True, "session_id": session_id,
    })
    assert streamed.status_code == 200
    assert "\n\n" in streamed.text
    assert '"content": "Use "' in streamed.text
    assert '"content": "for."' in streamed.text
    assert requests[0]["stream"] is False
    assert requests[1]["stream"] is True
    assert requests[1]["messages"][0]["role"] == "system"
    assert "简短" in requests[1]["messages"][0]["content"]
    assert requests[1]["messages"][1]["content"] == "Explain Python lists"
    history = client.get(f"/api/v1/ai/history?session_id={session_id}", headers=auth(token)).json()
    assert history["total"] == 2
    assert {item["answer"] for item in history["data"]} == {"A list stores values.", "Use for."}
