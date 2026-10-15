import os

import pytest
from fastapi.testclient import TestClient


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
        first_id = first.id
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
    assert client.post("/api/v1/settings", headers=auth(second_token),
                       json={"user_id": first_id}).status_code == 403


def test_unverified_password_reset_is_disabled(client):
    response = client.post("/api/v1/auth/reset-password", json={
        "phone": "13800000001", "new_password": "StolenPassword123!",
    })
    assert response.status_code == 410


def test_settings_can_only_be_read_or_changed_by_owner(client):
    owner_id, owner_token = register_and_login(client, "settings_owner", "13800000003")
    _, other_token = register_and_login(client, "settings_other", "13800000004")
    created = client.post("/api/v1/settings", headers=auth(owner_token),
                          json={"user_id": owner_id, "eye_protection": True})
    assert created.json()["code"] == 201
    own = client.get(f"/api/v1/settings/{owner_id}", headers=auth(owner_token))
    assert own.status_code == 200
    assert own.json()["data"]["settings"]["user_id"] == owner_id
    assert client.get(f"/api/v1/settings/{owner_id}", headers=auth(other_token)).status_code == 403
    assert client.put(f"/api/v1/settings/{owner_id}", headers=auth(other_token),
                      json={"eye_protection": False}).status_code == 403

def test_ollama_chat_non_stream_and_stream_save_history(client, monkeypatch):
    import json
    import httpx
    from app.api import ai

    _, token = register_and_login(client, "ollama_student", "13800000005")
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.url.path == "/api/chat"
        assert payload["model"] == "qwen2.5-coder:3b-instruct"
        assert payload["messages"][-1]["content"] in {"Explain Python lists", "Explain a loop"}
        if payload["stream"]:
            chunks = [
                {"message": {"content": "Use "}, "done": False},
                {"message": {"content": "for."}, "done": False},
                {"message": {"content": ""}, "done": True},
            ]
            return httpx.Response(200, text="\n".join(json.dumps(c) for c in chunks) + "\n")
        return httpx.Response(200, json={"message": {"content": "A list stores values."}, "done": True})

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(ai, "LOCAL_LLM_URL", "http://ollama.test/api/chat")
    monkeypatch.setattr(ai, "OLLAMA_MODEL", "qwen2.5-coder:3b-instruct")
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
    assert requests[1]["messages"][0]["content"] == "Explain Python lists"
    history = client.get(f"/api/v1/ai/history?session_id={session_id}", headers=auth(token)).json()
    assert history["total"] == 2
    assert {item["answer"] for item in history["data"]} == {"A list stores values.", "Use for."}
