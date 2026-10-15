"""Teaching-output checks; these tests never implement a student-code judge."""
import copy

import pytest

from app.services.hint_quality import quality_issues


CODE = "total = 0\nfor i in range(1, 101):\n    total = i\nprint(total)"
GOOD = {
    "suspected_cause": "疑似循环内的赋值覆盖了之前的累计结果。",
    "knowledge_points": ["累加器", "赋值与累加"],
    "evidence": [{"explanation": "实际结果只与最后一个取值相同，需要结合赋值语句检查。"}],
    "hints": {
        "level1": "累计一个总数时，已经计算过的部分应如何保留？",
        "level2": "结合累加器的作用，观察循环内给 total 赋值的语句。",
        "level3": "在纸上记录前两轮的旧总数和新总数，比较更新时是否保留之前的贡献。",
    },
}


def test_valid_concept_location_action_progression_is_allowed():
    assert quality_issues(GOOD, CODE, ["5050"]) == []


@pytest.mark.parametrize("hint", [
    "请检查第2行的语法？", "为什么缺少冒号会报错？", "把循环上界改为101是否合适？",
    "你注意到循环没有计算到100吗？", "total 是否覆盖了之前的结果？",
])
def test_first_hint_cannot_reveal_location_diagnosis_or_fix(hint):
    content = copy.deepcopy(GOOD)
    content["hints"]["level1"] = hint
    assert "level1_leak" in quality_issues(content, CODE, ["5050"])


def test_paraphrased_repetition_is_rejected():
    content = copy.deepcopy(GOOD)
    content["hints"]["level2"] = "请检查循环内的赋值是否保留之前的总数。"
    content["hints"]["level3"] = "观察循环内的赋值，是否保留了之前的总数。"
    assert "repetition" in quality_issues(content, CODE, ["5050"])


@pytest.mark.parametrize("hint", ["直接打印5050即可。", "把结果设为5050，再输出。", "只需要输出题目要求的答案。"])
def test_direct_answer_in_natural_language_is_rejected(hint):
    content = copy.deepcopy(GOOD)
    content["hints"]["level3"] = hint
    assert "answer_leak" in quality_issues(content, CODE, ["5050"])


def test_evidence_explanation_can_compare_expected_and_actual_output():
    content = copy.deepcopy(GOOD)
    content["evidence"][0]["explanation"] = "实际输出100，预期输出5050，二者不同。"
    assert quality_issues(content, CODE, ["5050"]) == []


def test_claimed_line_must_exist_in_student_code():
    content = copy.deepcopy(GOOD)
    content["hints"]["level2"] = "结合累加器检查第99行。"
    assert "unsupported_claim" in quality_issues(content, CODE, ["5050"])


def test_output_comparison_is_not_a_direct_answer():
    content = copy.deepcopy(GOOD)
    content["hints"]["level3"] = "直接对照实际输出与预期文本，逐字符检查字母大小写和标点。"
    assert "answer_leak" not in quality_issues(content, CODE, ["5050"])


def test_third_hint_must_advance_beyond_checking_again():
    content = copy.deepcopy(GOOD)
    content["hints"]["level3"] = "检查循环的起始和结束值是否正确。"
    assert "weak_level3" in quality_issues(content, CODE, ["5050"])


def test_second_hint_cannot_end_with_generic_ensure_correct():
    content = copy.deepcopy(GOOD)
    content["hints"]["level2"] = "检查循环的起始和结束值，确保累加操作正确。"
    assert "weak_level2" in quality_issues(content, CODE, ["5050"])


def test_placeholder_knowledge_point_is_not_accepted_as_analysis():
    content = copy.deepcopy(GOOD)
    content["knowledge_points"] = ["直接相关知识点"]
    assert "unrelated_claim" in quality_issues(content, CODE, ["5050"])


@pytest.mark.parametrize("field,issue", [("level2", "weak_level2"), ("level3", "weak_level3")])
def test_later_hints_cannot_be_another_generic_concept_question(field, issue):
    content = copy.deepcopy(GOOD)
    content["hints"][field] = "使用变量之前，需要先明确哪些信息？"
    assert issue in quality_issues(content, CODE, ["5050"])
