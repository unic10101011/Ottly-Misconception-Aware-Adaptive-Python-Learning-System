"""Small teaching-output guards. No execution, AST inspection or code diagnosis."""
from difflib import SequenceMatcher
from itertools import combinations
import keyword
import re


ISSUE_GUIDANCE = {
    "level1_leak": "第一级只提出概念方向问题，去掉行号、变量名、具体错误和修复方法。",
    "repetition": "三层分别写概念问题、知识点与观察位置、具体核验动作，不重复同一建议。",
    "answer_leak": "去掉代码、替换语句和直接输出或赋值最终答案的建议。",
    "unrelated_claim": "只讨论当前代码和真实失败证据共同支持的问题，去掉额外猜测。",
    "unsupported_claim": "不能声称已经观察到未提供的运行轨迹或不存在的代码位置。",
    "weak_level2": "第二级联系相关知识概念，引导检查学生实际代码中的位置或操作。",
    "weak_level3": "第三级给出与疑似原因对应的具体核验动作或修改思路，不能只说确保正确。",
    "format_or_evidence": "返回完整 JSON，引用只用允许的真实证据；第一级以问号结尾。",
}


def _normalized(text: str) -> str:
    text = re.sub(r"思考一下|请|一下|看看|检查|观察|是否|确保|注意|了|的", "", text)
    return re.sub(r"[\W_]", "", text).lower()


def quality_issues(content: dict, code: str, expected_outputs: list[str]) -> list[str]:
    """Conservative visible-text checks; semantic relevance is reviewed separately."""
    issues = []
    if any(point.strip() in {"知识点", "相关知识点", "直接相关知识点", "其他知识点"}
           for point in content["knowledge_points"]):
        issues.append("unrelated_claim")
    hints = list(content["hints"].values())
    first = content["hints"]["level1"]
    identifiers = set(re.findall(r"\b[A-Za-z_]\w*\b", code)) - set(keyword.kwlist)
    identifiers -= {"print", "range", "len", "input", "int", "str", "float", "sum"}
    early_detail = r"\d|第[一二三四五六七八九十]+行|[首末]行|最后一行|缺少|少了|遗漏|未定义|覆盖|冒号|加号|等号|改为|改成|添加|补上|加上|删除|替换"
    if re.search(early_detail, first) or any(re.search(rf"\b{re.escape(name)}\b", first) for name in identifiers):
        issues.append("level1_leak")
    second = content["hints"]["level2"]
    if (not re.search(r"检查|观察|对照|核对|查看|比较|找到|留意|关注", second)
            or re.search(r"(?:是否|确保).{0,12}(?:正确|符合题意)", second)):
        issues.append("weak_level2")
    if not re.search(r"列出|记录|推演|核算|对照|比较|逐[字行轮步]|尝试|调整|修改|验证|跟踪|计算", content["hints"]["level3"]):
        issues.append("weak_level3")
    for left, right in combinations(hints, 2):
        a, b = _normalized(left), _normalized(right)
        if a == b or SequenceMatcher(None, a, b).ratio() >= 0.72:
            issues.append("repetition")
            break
    for hint in hints:
        direct_answer = re.search(r"(?:直接|只需要?|只要)(?:将|把)?(?:结果|答案)?(?:打印|输出|赋值|返回)", hint)
        replacement = any(value.strip() and re.search(
            rf"(?:打印|输出|赋值|设为|改为).{{0,12}}{re.escape(value.strip())}", hint)
            for value in expected_outputs)
        if direct_answer or replacement:
            issues.append("answer_leak")
            break
    teaching = [content["suspected_cause"], *content["knowledge_points"], *hints,
                *(item["explanation"] for item in content["evidence"])]
    for text in teaching:
        if any(not 1 <= int(line) <= len(code.splitlines()) for line in re.findall(r"第\s*(\d+)\s*行", text)):
            issues.append("unsupported_claim")
            break
    return list(dict.fromkeys(issues))
