"""Feedback routing and privacy work without calling a live model or database."""
import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from app.services import error_analysis as analysis
from app.services.learning_contract import contract_analysis, history_analysis
from app.services.lesson_feedback import with_lesson_hints
from app.services.problem_catalog import PROBLEMS, Problem, TestCase
from app.services.submission import CaseResult, JudgeResult


class FeedbackRoutingTests(unittest.TestCase):
    def setUp(self):
        self.problem = Problem(
            problem_id='private-evidence-test-v1', title='公开分支练习',
            description='根据公开题意检查条件分支。', comparison='exact', tests=[
                TestCase(case_id='sample-1', stdin='PUBLIC_INPUT', expected_output='PUBLIC_OUTPUT'),
                TestCase(case_id='hidden-SECRET_ID', stdin='SECRET_INPUT',
                         expected_output='SECRET_EXPECTED', visibility='hidden'),
            ],
        )
        self.guidance = {
            'hint': '结合题目要求检查条件分支的范围，想一想哪些情况还需要核对。',
            'knowledge_points': ['比较与条件分支'],
            'question': {'prompt': '一个分支已经执行后，后面的 elif 还会执行吗？',
                         'options': ['继续执行', '不再执行'], 'correct_index': 1,
                         'explanation': '分支链只执行第一个成立的分支。'},
        }
        self.model = AsyncMock(return_value=(json.dumps(self.guidance, ensure_ascii=False), 1.5))
        for target, kwargs in [
            ('analysis_configuration_error', {'return_value': None}),
            ('analysis_model', {'return_value': 'offline-test'}),
            ('request_diagnosis', {'new': self.model}),
        ]:
            patcher = patch.object(analysis, target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def judge(self, public_pass=True, hidden_pass=False):
        cases = [CaseResult(
            case_id=test.case_id, passed=passed, expected_output=test.expected_output,
            actual_output='PUBLIC_OUTPUT' if test.visibility == 'public' else 'SECRET_ACTUAL',
            errors=[], execution_time=0.01, visibility=test.visibility,
        ) for test, passed in zip(self.problem.tests, [public_pass, hidden_pass])]
        passed = sum(case.passed for case in cases)
        return JudgeResult(status='accepted' if passed == 2 else 'wrong_answer',
                           passed=passed == 2, passed_cases=passed, total_cases=2, cases=cases)

    def generate(self, judge=None):
        return asyncio.run(analysis.analyze_failure(self.problem, 'print("example")', judge or self.judge()))

    def test_hidden_only_failure_generates_guidance_without_private_evidence(self):
        result = self.generate()
        self.assertEqual(result.status, 'ready')
        self.assertEqual(result.feedback_kind, 'guidance')
        self.assertIsNone(result.content)
        self.assertEqual(result.guidance.question.correct_index, 1)
        self.model.assert_awaited_once()
        messages = self.model.call_args.args[1]
        payload = messages[1]['content']
        self.assertNotIn('SECRET', payload)
        self.assertNotIn('hidden-', payload)
        self.assertNotIn('reference_solution', payload)
        facts = json.loads(payload)
        self.assertEqual(len(facts['public_cases']), 1)
        self.assertTrue(facts['public_cases'][0]['passed'])

    def test_partial_public_failure_also_uses_guidance(self):
        result = self.generate(self.judge(False, True))
        self.assertEqual(result.feedback_kind, 'guidance')
        facts = json.loads(self.model.call_args.args[1][1]['content'])
        self.assertFalse(facts['public_cases'][0]['passed'])
        self.assertNotIn('SECRET', json.dumps(facts))

    def test_all_failed_uses_existing_diagnosis_pipeline(self):
        full = analysis.AnalysisResult(status='ready', message='diagnosis')
        with patch.object(analysis, '_analyze_failure', new=AsyncMock(return_value=full)) as diagnosis:
            result = self.generate(self.judge(False, False))
        self.assertEqual(result.feedback_kind, 'diagnosis')
        diagnosis.assert_awaited_once()
        self.model.assert_not_awaited()

    def test_all_passed_skips_model(self):
        self.assertEqual(self.generate(self.judge(True, True)).status, 'skipped')
        self.model.assert_not_awaited()

    def test_guidance_can_omit_question(self):
        self.guidance['question'] = None
        self.model.return_value = (json.dumps(self.guidance), 0)
        self.assertIsNone(self.generate().guidance.question)

    def test_private_case_claims_and_solution_code_are_rejected(self):
        for hint in ['隐藏测试输入为 90', 'hidden-5 expects GOLD', '```python\nprint(1)\n```', '改成 print(1)', '改成 total = 0']:
            with self.subTest(hint=hint):
                self.guidance['hint'] = hint
                self.model.return_value = (json.dumps(self.guidance), 0)
                result = self.generate()
                self.assertEqual(result.status, 'invalid_response')
                self.assertIsNone(result.guidance)

    def test_invalid_question_answer_is_rejected(self):
        self.guidance['question']['correct_index'] = 3
        self.model.return_value = (json.dumps(self.guidance), 0)
        self.assertEqual(self.generate().status, 'invalid_response')

    def test_service_failures_do_not_become_diagnoses(self):
        for error, status in [(httpx.ConnectError('offline'), 'unavailable'), (TimeoutError(), 'timeout')]:
            with self.subTest(status=status):
                self.model.side_effect = error
                result = self.generate()
                self.assertEqual(result.status, status)
                self.assertEqual(result.feedback_kind, 'guidance')
                self.assertIsNone(result.content)
                self.assertIs(with_lesson_hints(PROBLEMS['badge-v1'], result, self.judge()), result)

    def test_saved_guidance_round_trip_keeps_question(self):
        public = contract_analysis(self.generate(), ['K05'])
        record = SimpleNamespace(analysis_json=public.model_dump(mode='json'),
                                 knowledge_ids=['K05'], schema_version='1.0.0')
        restored = history_analysis(record, self.judge())
        self.assertEqual(restored.feedback_kind, 'guidance')
        self.assertEqual(restored.guidance.question.options, self.guidance['question']['options'])
        self.assertIsNone(restored.content)


class ApiFeedbackRoutingTests(unittest.TestCase):
    def test_fifth_lesson_partial_failure_then_full_failure_and_pass(self):
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from main import app
        from app.core.database import Base, get_db
        from app.core.auth import get_current_user
        from app.models.user import User
        from app.services.problem_catalog import LEVELS

        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        with sessions() as db:
            user = User(username='feedback_test', password='test-only', phone='13900000998', status='enabled')
            db.add(user)
            db.commit()

        def database():
            with sessions() as db:
                yield db

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_current_user] = lambda: user
        self.addCleanup(app.dependency_overrides.clear)
        payloads = []

        async def respond(client, messages, schema, *args):
            facts = json.JSONDecoder().raw_decode(messages[1]['content'])[0]
            payloads.append(facts)
            self.assertNotIn('hidden-', json.dumps(facts))
            if 'hint' in schema['properties']:
                self.assertEqual(len(facts['public_cases']), 1)
                self.assertTrue(facts['public_cases'][0]['passed'])
                result = {'hint': '想一想不同分数区间是否都被条件覆盖。',
                          'knowledge_points': ['比较与条件分支'], 'question': None}
            elif 'code_observation' in schema['properties']:
                result = {
                    'code_observation': '程序只打印固定文字，没有读取分数。',
                    'suspected_cause': '程序打印固定文字，没有根据分数选择对应结果。',
                    'evidence': [{**facts['allowed_evidence'][0], 'explanation': '公开样例显示固定文字。'}],
                    'knowledge_points': ['比较与条件分支'], 'misconception_tag': 'other',
                }
            else:
                result = {'tag_supported': True, 'issues': []}
            return json.dumps(result, ensure_ascii=False), 0

        client = TestClient(app)

        def submit(problem_id, code):
            response = client.post('/api/v1/code/submit', json={'problem_id': problem_id, 'code': code})
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()['data']

        def feedback(submission_id):
            response = client.post(f'/api/v1/code/submissions/{submission_id}/analysis')
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()['data']['analysis']

        with patch.object(analysis, 'ANALYSIS_PROVIDER', 'deepseek'), \
                patch.object(analysis, 'analysis_configuration_error', return_value=None), \
                patch.object(analysis, 'analysis_model', return_value='offline-test'), \
                patch.object(analysis, 'request_diagnosis', side_effect=respond):
            for slot in LEVELS[:4]:
                self.assertTrue(submit(slot.problem_id, PROBLEMS[slot.problem_id].reference_solution)['judge']['passed'])
            lesson = PROBLEMS['badge-v1']
            partial = submit(lesson.problem_id, lesson.reference_solution.replace('score >= 90', 'score > 100'))
            self.assertEqual(partial['judge']['passed_cases'], 5)
            self.assertEqual(partial['analysis']['feedback_kind'], 'guidance')
            hint = feedback(partial['submission_id'])
            self.assertEqual(hint['status'], 'ready')
            self.assertIsNotNone(hint['guidance'])
            self.assertIsNone(hint['content'])
            self.assertEqual(feedback(partial['submission_id']), hint)
            self.assertEqual(len(payloads), 1, 'saved guidance must not call the model again')
            full = submit(lesson.problem_id, 'print("WRONG")')
            self.assertEqual(full['judge']['passed_cases'], 0)
            diagnosis = feedback(full['submission_id'])
            self.assertEqual(diagnosis['status'], 'ready')
            self.assertEqual(diagnosis['feedback_kind'], 'diagnosis')
            self.assertIsNotNone(diagnosis['content'])
            self.assertIsNone(diagnosis['guidance'])
            self.assertEqual(len(payloads), 3, 'one guidance, one diagnosis, one diagnosis review')
            passed = submit(lesson.problem_id, lesson.reference_solution)
            self.assertEqual(passed['analysis']['status'], 'skipped')
            self.assertEqual(len(payloads), 3)
            saved = client.get('/api/v1/code/submissions').json()['data']['items']
            restored = next(item for item in saved if item['id'] == partial['submission_id'])
            self.assertEqual(restored['analysis']['guidance'], hint['guidance'])


if __name__ == '__main__':
    unittest.main()
