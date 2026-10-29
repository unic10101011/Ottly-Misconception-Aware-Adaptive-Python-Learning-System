"""Keep a correct diagnosis from spelling out the missing variable update."""
import json
from pathlib import Path

import pytest

from app.services import error_analysis as analysis
from test_core72_feedback_regressions import replay


CAPTURED = json.loads((Path(__file__).parent/'data/c54_answer_protection_regressions.json').read_text(encoding='utf-8'))


def test_generation_and_review_distinguish_correctness_from_answer_protection():
    assert '不把应补写的变量更新动作及具体更新量直接告诉学生' in analysis.SYSTEM_PROMPT
    assert '即使没有代码' in analysis.REVIEW_PROMPT
    assert '明确事实错误或违反答案保护边界' in analysis.REVIEW_PROMPT
    assert '只有明确事实错误才列 issue' not in analysis.REVIEW_PROMPT


def test_captured_natural_language_fix_cannot_survive_a_leak_review(monkeypatch):
    result, request = replay(monkeypatch,'C54-R3',raw=CAPTURED['rejected_raw'],review={
        'tag_supported':True,'issues':[{'code':'answer_leak','reason':'候选直接安排原题所缺的变量更新动作和具体更新量。'}]})
    assert result.status=='invalid_response' and result.content is None
    assert request.await_count==2  # Generation and review; no replacement or retry.
    facts = json.loads(request.call_args.args[1][1]['content'])
    assert facts['candidate']['suspected_cause']==json.loads(CAPTURED['rejected_raw'])['suspected_cause']


@pytest.mark.parametrize('key',list(CAPTURED['allowed_raw']))
def test_captured_observations_are_not_locally_rejected_or_rewritten(monkeypatch,key):
    raw = CAPTURED['allowed_raw'][key]
    result, request = replay(monkeypatch,key,raw=raw)
    assert result.status=='ready' and request.await_count==2
    assert result.content.suspected_cause==json.loads(raw)['suspected_cause']


def test_existing_update_described_as_what_the_loop_executes_is_not_a_fix(monkeypatch):
    raw = json.loads((Path(__file__).parent/'data/c54_followup_observation.json').read_text(encoding='utf-8'))['raw']
    result, request = replay(monkeypatch,'C54-R1',raw=raw)
    assert result.status=='ready' and request.await_count==2
    assert result.content.evidence[0].explanation==json.loads(raw)['evidence'][0]['explanation']
