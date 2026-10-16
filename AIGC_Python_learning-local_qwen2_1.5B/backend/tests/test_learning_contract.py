"""Contract checks exercise real API persistence while keeping model generation unchanged."""
import copy

import pytest

from test_greeting import client, account, submit


def test_snapshot_errors_failed_tests_and_deterministic_mapping(client, monkeypatch):
    from app.api import coding
    from app.services.error_analysis import AnalysisResult
    from app.services.problem_catalog import PROBLEMS, SCHEMA_VERSION
    headers = account(client)
    submit(client, headers, 'level1', "print('Hello, World!')")
    model_inputs = []

    async def analysis(problem, code, judge):
        model_inputs.append((problem, judge.model_copy(deep=True)))
        return AnalysisResult(status='ready', message='依据公开结果提供提示。', content={
            'suspected_cause': '疑似使用了未定义的变量。',
            'evidence': [{'case_id':'sample-1', 'field':'error_message',
                          'quote':judge.cases[0].errors[0].message, 'explanation':'该名称尚未定义。'}],
            'knowledge_points':[' 输入与变量 ', '变量', '陌生知识点', '列表'],
            'hints':{'level1':'使用变量前需要明确什么？','level2':'检查变量是否先赋值。','level3':'按顺序核对首次赋值和使用。'},
        })
    monkeypatch.setattr(coding, 'analyze_failure', analysis)
    response = submit(client, headers, 'greeting-v1', 'print(missing_name)')
    assert response.json()['schema_version'] == SCHEMA_VERSION
    data = response.json()['data']
    assert data['analysis']['status'] == 'preparing'
    prepared = client.post(f"/api/v1/code/submissions/{data['submission_id']}/analysis", headers=headers)
    assert prepared.status_code == 200
    data['analysis'] = prepared.json()['data']['analysis']
    assert data['error_type'] == 'NAME_ERROR'
    assert data['judge']['failed_tests'] == ['sample-1','hidden-1','hidden-2','hidden-3']
    assert data['judge']['cases'][0]['errors'][0]['type'] == 'NAME_ERROR'
    assert data['analysis']['content']['knowledge_ids'] == ['K02']
    assert data['analysis']['content']['knowledge_points'] == ['输入与变量', '变量', '陌生知识点', '列表']
    assert model_inputs[0][1].cases[0].errors[0].type == 'NameError'
    assert set(model_inputs[0][0].model_dump()) == {'problem_id','title','description','tests','comparison'}
    assert model_inputs[0][1].cases[1].errors == []
    assert 'failed_tests' not in model_inputs[0][1].model_dump()
    assert data['version'] == 1 and data['created_at'].endswith('Z')

    # Editing today's metadata must not rewrite any submitted snapshot or mapped IDs.
    changed = PROBLEMS['greeting-v1'].model_copy(update={'difficulty':3, 'knowledge_ids':['K11']})
    monkeypatch.setitem(PROBLEMS, 'greeting-v1', changed)
    row = client.get('/api/v1/code/submissions?problem_id=greeting-v1', headers=headers).json()['data']['items'][0]
    assert (row['version'], row['difficulty'], row['knowledge_ids']) == (1, 1, ['K02'])
    assert row['analysis']['content']['knowledge_ids'] == ['K02']
    assert row['judge'] == data['judge']
    assert row['error_type'] == data['error_type']


def test_unlocks_follow_config_and_unpublished_review_is_owned(client, monkeypatch):
    from app.services.problem_catalog import PROBLEMS
    headers = account(client)
    lesson = PROBLEMS['greeting-v1']
    assert submit(client, headers, lesson.problem_id, 'print(0)').status_code == 403
    monkeypatch.setitem(PROBLEMS, lesson.problem_id, lesson.model_copy(update={'prerequisite_problem_ids':[]}))
    assert client.get('/api/v1/code/problems/greeting-v1', headers=headers).status_code == 200
    failed = submit(client, headers, lesson.problem_id, 'print(0)').json()['data']
    monkeypatch.setitem(PROBLEMS, lesson.problem_id, lesson.model_copy(update={'published':False}))
    assert client.get('/api/v1/code/problems/greeting-v1', headers=headers).status_code == 403
    assert submit(client, headers, lesson.problem_id, 'print(0)').status_code == 403
    review_headers = {**headers, 'X-Review-Source-Id':str(failed['submission_id'])}
    review = submit(client, review_headers, lesson.problem_id, 'print(0)')
    assert review.status_code == 200
    history = client.get('/api/v1/code/submissions', headers=headers).json()['data']['items']
    assert history[0]['review_source_id'] == failed['submission_id']
    other = account(client, 'contract_other', '13900000002')
    assert submit(client, {**other, 'X-Review-Source-Id':str(failed['submission_id'])}, lesson.problem_id, 'print(0)').status_code == 404


def test_versions_do_not_inherit_progress_and_solution_access(client, monkeypatch):
    from app.services.problem_catalog import PROBLEMS
    headers = account(client)
    submit(client, headers, 'level1', "print('Hello, World!')")
    submit(client, headers, 'greeting-v1', 'name = input()\nprint("Hello,", name + "!")')
    v2 = PROBLEMS['greeting-v1'].model_copy(update={'problem_id':'greeting-v2','version':2})
    monkeypatch.setitem(PROBLEMS, 'greeting-v2', v2)
    assert client.get('/api/v1/code/problems/greeting-v2', headers=headers).json()['data']['completed'] is False
    assert client.get('/api/v1/code/problems/greeting-v2/solution', headers=headers).status_code == 403
    assert client.get('/api/v1/code/submissions?problem_id=greeting-v2', headers=headers).json()['data']['items'] == []


def test_old_history_keeps_unknown_metadata_null_and_redacts_again(client):
    from app.core.database import get_db
    from main import app
    from app.models.learning_submission import LearningSubmission
    headers = account(client)
    first = submit(client, headers, 'level1', 'print(missing_name)').json()['data']
    database = app.dependency_overrides[get_db]()
    db = next(database)
    try:
        record = db.get(LearningSubmission, first['submission_id'])
        record.schema_version = record.problem_version = record.difficulty = record.knowledge_ids = None
        judge = copy.deepcopy(record.judge_json)
        judge.pop('failed_tests', None)
        judge['cases'][0]['errors'][0]['type'] = 'NameError'
        judge['cases'][0]['visibility'] = 'hidden'
        judge['cases'][0]['expected_output'] = 'PRIVATE_OLD_EXPECTED'
        judge['cases'][0]['actual_output'] = 'PRIVATE_OLD_ACTUAL'
        record.judge_json = judge
        record.error_type = 'NameError'
        db.commit()
    finally:
        database.close()
    response = client.get('/api/v1/code/submissions', headers=headers)
    assert 'PRIVATE_OLD' not in response.text
    row = response.json()['data']['items'][0]
    assert row['version'] is row['difficulty'] is row['schema_version'] is None
    assert row['knowledge_ids'] == []
    assert row['judge']['failed_tests'] == ['stdout-1']
    assert row['error_type'] == 'NAME_ERROR'


def test_analysis_exception_does_not_lose_judgment(client, monkeypatch):
    from app.api import coding
    async def unavailable(*args):
        raise RuntimeError('temporary model service failure')
    monkeypatch.setattr(coding, 'analyze_failure', unavailable)
    headers = account(client)
    data = submit(client, headers, 'level1', 'print(0)').json()['data']
    assert data['analysis']['status'] == 'preparing'
    prepared = client.post(f"/api/v1/code/submissions/{data['submission_id']}/analysis", headers=headers)
    assert prepared.status_code == 200
    data['analysis'] = prepared.json()['data']['analysis']
    assert data['analysis']['status'] == 'unavailable'
    assert data['analysis']['content'] is None
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 1


def test_knowledge_dictionary_is_authenticated(client):
    assert client.get('/api/v1/code/knowledge').status_code == 401
    data = client.get('/api/v1/code/knowledge', headers=account(client)).json()
    assert data['schema_version'] == '1.0.0'
    assert len(data['data']['items']) == 12
    assert 'aliases' not in data['data']['items'][0]
