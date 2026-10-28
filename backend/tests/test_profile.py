import pytest

from test_submission import client, login


def test_profile_defaults_and_persistence_keep_login_username_and_session(client):
    owner = login(client)
    original = client.get('/api/v1/auth/me', headers=owner).json()['data']
    assert original['nickname'] == original['username']
    assert original['signature'] == ''
    response = client.patch('/api/v1/auth/profile', headers=owner, json={
        'nickname': '  海边小獭  ', 'signature': '  每天学一点 Python  ', 'phone': original['phone'],
    })
    assert response.status_code == 200
    saved = client.get('/api/v1/auth/me', headers=owner).json()['data']
    assert saved['nickname'] == '海边小獭'
    assert saved['signature'] == '每天学一点 Python'
    assert saved['username'] == original['username']
    assert 'password' not in saved
    assert client.post('/api/v1/auth/login', json={'username': original['username'],
                       'password': 'TestPass1234!'}).status_code == 200


def test_profile_phone_changes_still_require_password_and_fail_atomically(client):
    owner = login(client)
    original = client.get('/api/v1/auth/me', headers=owner).json()['data']
    update = {'nickname': '新昵称', 'signature': '新签名', 'phone': '13900000001'}
    for extra in ({}, {'current_password': 'wrong'}):
        assert client.patch('/api/v1/auth/profile', headers=owner, json={**update, **extra}).status_code == 403
        assert client.get('/api/v1/auth/me', headers=owner).json()['data'] == original
    assert client.patch('/api/v1/auth/profile', headers=owner,
                        json={**update, 'current_password': 'TestPass1234!'}).status_code == 200
    assert client.get('/api/v1/auth/me', headers=owner).json()['data']['phone'] == update['phone']


@pytest.mark.parametrize('changes', [
    {'nickname': '   '}, {'nickname': 'x' * 51}, {'signature': 'x' * 201},
    {'phone': '123'}, {'user_id': 999}, {'username': 'replace_login'},
])
def test_invalid_profile_data_is_rejected(client, changes):
    owner = login(client)
    update = {'nickname': '小獭', 'signature': '', 'phone': '13800138000', **changes}
    assert client.patch('/api/v1/auth/profile', headers=owner, json=update).status_code == 422


def test_profile_is_authenticated_isolated_and_deleted_with_account(client):
    from app.core.database import get_db
    from app.models.user import UserProfile
    from main import app
    update = {'nickname': '小獭', 'signature': '练习中', 'phone': '13800138000'}
    assert client.patch('/api/v1/auth/profile', json=update).status_code == 401
    owner = login(client)
    owner_id = client.get('/api/v1/auth/me', headers=owner).json()['data']['id']
    assert client.patch('/api/v1/auth/profile', headers=owner, json=update).status_code == 200
    other = {'username': 'profile_other', 'password': 'OtherPassword123!', 'phone': '13900000002'}
    client.post('/api/v1/auth/register', json=other)
    token = client.post('/api/v1/auth/login', json=other).json()['data']['access_token']
    other_info = client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token}).json()['data']
    assert other_info['nickname'] == other['username'] and other_info['signature'] == ''
    assert client.patch('/api/v1/auth/profile', headers=owner, json={
        **update, 'phone': other['phone'], 'current_password': 'TestPass1234!',
    }).status_code == 409
    assert client.request('DELETE', '/api/v1/auth/me', headers=owner,
                          json={'current_password': 'TestPass1234!'}).status_code == 200
    dependency = app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        assert db.get(UserProfile, owner_id) is None
    finally:
        dependency.close()


def test_password_spaces_are_preserved_when_confirming_phone_change(client):
    account = {'username': 'spaced_password', 'phone': '13900000003', 'password': '  StrongPassword123!  '}
    assert client.post('/api/v1/auth/register', json=account).json()['code'] == 201
    token = client.post('/api/v1/auth/login', json=account).json()['data']['access_token']
    assert client.patch('/api/v1/auth/profile', headers={'Authorization': 'Bearer ' + token}, json={
        'nickname': '小獭', 'signature': '', 'phone': '13900000004', 'current_password': account['password'],
    }).status_code == 200
