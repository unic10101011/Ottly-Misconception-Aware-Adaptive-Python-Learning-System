# 加练题数据统一与误区推荐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不影响现有 45 道加练题判题与主线进度的前提下，统一加练题参与推荐时使用的关键字段，并让系统优先依据“疑似误区标签＋知识点＋难度”快速推荐真实题库中的题目。

**Architecture:** 保留现有两种题目文件加载方式，先在统一的运行时 `Lesson` 模型中补齐推荐元数据，避免一次性迁移 36 道旧题。推荐先由后端确定性规则筛选和排序；只有多道题同样合适时才允许模型辅助选择，模型不可用时使用规则排序结果。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、SQLAlchemy、Pytest、React。

## 2026-10-25 合并修订

队友提交 `3712e2a` 将加练由 45 道扩至 66 道（36 道集中式、30 道独立题），提交 `73d57e6` 新增部分通过时的引导与小测。下文保留原 45 题方案作为设计依据；本次实际验收数量改为 66，新增 21 题统一补齐推荐元数据，题干和测试保留队友版本。部分通过的引导不提供诊断标签，推荐按知识点、难度排序。真实 DeepSeek 及人工语义验收在队友电脑统一执行，不能用本机模拟测试代替。

## Global Constraints

- 题目数量不同不作为本次问题，不要求每关加练题数量相同。
- 不修改程序判题规则，AI 不能决定代码是否正确。
- 不让 AI 生成新题、参考答案或测试用例。
- 不一次性重写 `practice.json` 中现有 36 道题。
- 不引入 AST 误区规则引擎、复杂误区知识库或模型训练。
- 已保存的提交、错题和推荐结果必须继续可读。
- 加练失败、通过或跳过均不能改变主线解锁状态。
- 只修改与加练题元数据和推荐直接相关的代码。

---

## 一、当前情况

### 1. 当前有两种加练题源文件

第一种是集中式简化题库：

```text
backend/app/data/practice.json
```

其中包含 36 道题，字段示例：

```json
{
  "problem_id": "practice-08-1-v1",
  "level_no": 8,
  "title": "连续编号总和",
  "focus": "累加器应在循环前初始化、在循环中更新、循环后输出。",
  "sample": {
    "stdin": "4\n",
    "stdout": "10\n"
  },
  "hidden": [
    {
      "stdin": "0\n",
      "stdout": "0\n"
    },
    {
      "stdin": "5\n",
      "stdout": "15\n"
    }
  ],
  "reference_solution": "n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    total = total + i\nprint(total)\n",
  "wrong_solution": "n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    total = i\nprint(total)\n",
  "solution_explanation": "每轮把 i 加到旧 total 上，而非用当前 i 覆盖旧总和。",
  "source_url": "https://exercism.org/tracks/python/exercises/difference-of-squares"
}
```

加载时，`problem_catalog.py` 会把它转换成完整 `Lesson`。转换过程中会自动生成知识点、前置题、提示等信息，并把难度固定为 `1`。

第二种是完整的单题文件：

```text
backend/app/data/practice-03-4-v1.json
backend/app/data/practice-03-5-v1.json
backend/app/data/practice-03-6-v1.json
backend/app/data/practice-04-4-v1.json
backend/app/data/practice-04-5-v1.json
backend/app/data/practice-04-6-v1.json
backend/app/data/practice-05-4-v1.json
backend/app/data/practice-05-5-v1.json
backend/app/data/practice-05-6-v1.json
```

它们直接使用完整 `Lesson` 结构，包含 `difficulty`、`knowledge_ids`、`tests` 和独立三级提示。

### 2. 当前能够正常工作的部分

- 两种数据源最终都会转换为 `Lesson`，可以共用详情、判题和提交接口。
- 加练题由服务器题库提供，AI 不能编造候选题 ID。
- 推荐只考虑已发布、已解锁、尚未通过且知识点相关的题目。
- 推荐只在主线题“先失败、后改对”时触发。
- 推荐失败不会撤销已经保存的通关结果。
- 推荐结果保存在成功提交的 `analysis_json` 中，重复查看不会再次调用模型。

### 3. 当前需要修改的问题

#### 3.1 推荐元数据字段不统一

两种题目源分别使用 `focus` 和 `practice_focus`，难度、来源、提示和测试结构也不同。虽然运行时能够转换，但新增题目和内容审核容易使用错误的格式。

#### 3.2 加练题没有目标误区标签

失败分析已经产生固定枚举的 `misconception_tag`，但加练题没有 `target_misconception_tags`。系统只能按 `knowledge_ids` 粗筛，再让模型理解 `practice_focus` 自由选择。

#### 3.3 难度信息不可靠

`practice.json` 中的题目在转换时统一写成 `difficulty=1`。推荐逻辑也没有根据最近错误、学生表现或题目难度排序。

#### 3.4 推荐额外依赖一次模型调用

当前从候选题中选择最终题目还会请求一次 DeepSeek，最长等待约 30 秒。模型不可用时只返回“推荐暂不可用”，没有确定性的备用推荐。

#### 3.5 目前是最近一次错误推荐，不是长期误区推荐

系统会读取最近一次失败及其 AI 分析，但没有把当前 `misconception_tag` 与题目的目标误区做精确匹配，也没有根据同类历史错误次数调整推荐优先级。

---

## 二、目标数据结构

### 1. 固定误区标签

继续使用现有六种标签，不新增自由文本标签：

```python
MisconceptionTag = Literal[
    "range_boundary",
    "accumulation_error",
    "condition_error",
    "variable_error",
    "syntax_error",
    "other",
]
```

标签含义：

| 标签 | 含义 |
|---|---|
| `range_boundary` | 循环起点、终点、步长或边界包含关系 |
| `accumulation_error` | 累加初始化、更新、重置或覆盖 |
| `condition_error` | 条件表达式、分支顺序、逻辑运算 |
| `variable_error` | 变量未定义、拼写不一致、覆盖或错误使用 |
| `syntax_error` | Python 语法或缩进问题 |
| `other` | 暂时不能归入前五类 |

### 2. 统一运行时字段

在 `Lesson` 中增加：

```python
target_misconception_tags: list[MisconceptionTag] = Field(default_factory=list)
source_url: str | None = None
```

约束：

- `kind="practice"` 的题目必须至少有一个 `target_misconception_tags`。
- 主线题允许该数组为空。
- 标签必须来自固定枚举，不能由模型自由生成。
- `source_url` 只用于来源追踪，不发送给模型，也不影响判题。
- `difficulty` 继续使用 `1 | 2 | 3`：基础、巩固、综合。

### 3. 兼容旧的集中式题库

`PracticeSpec` 增加明确字段：

```python
class PracticeSpec(CatalogModel):
    # 保留现有字段
    difficulty: Literal[1, 2, 3]
    target_misconception_tags: list[MisconceptionTag] = Field(min_length=1)
```

`practice_lesson()` 必须原样传递：

```python
return Lesson(
    # 保留现有参数
    difficulty=spec.difficulty,
    target_misconception_tags=spec.target_misconception_tags,
    source_url=spec.source_url,
)
```

这样不需要立即把 36 道题拆成 36 个文件，但运行时元数据保持一致。

### 4. 单题文件示例

```json
{
  "schema_version": "1.0.0",
  "problem_id": "practice-08-1-v1",
  "version": 1,
  "level_no": 8,
  "kind": "practice",
  "practice_focus": "累加器应在循环前初始化、在循环中更新、循环后输出。",
  "target_misconception_tags": [
    "accumulation_error"
  ],
  "difficulty": 1,
  "knowledge_ids": [
    "K08"
  ],
  "source_url": "https://exercism.org/tracks/python/exercises/difference-of-squares"
}
```

---

## 三、推荐规则

### 1. 候选题硬性过滤

候选题必须同时满足：

1. `kind == "practice"`；
2. `published == true`；
3. 学生尚未通过；
4. 所有 `prerequisite_problem_ids` 已通过；
5. 与当前错误至少有一个相同的 `knowledge_id`。

### 2. 确定性排序

对过滤后的题目计算排序元组，值越小越优先：

```python
def practice_rank(item, *, misconception_tag, knowledge_ids, target_difficulty):
    tag_mismatch = int(
        misconception_tag not in item.target_misconception_tags
        and "other" not in item.target_misconception_tags
    )
    knowledge_mismatch = int(not set(knowledge_ids).intersection(item.knowledge_ids))
    difficulty_gap = abs(item.difficulty - target_difficulty)
    return tag_mismatch, knowledge_mismatch, difficulty_gap, item.problem_id
```

第一版 `target_difficulty` 使用简单规则：

```python
target_difficulty = 1
```

本次不开发复杂学生能力模型。以后有可靠掌握度规则时再调整。

### 3. AI调用策略

- 排名第一的题在“误区标签、知识点和难度”三个维度上优于第二名时，直接推荐，不调用模型。
- 多道题前三个排序值相同时，允许把并列候选交给 DeepSeek 选择。
- DeepSeek 超时、不可用、返回非法 JSON 或返回候选集外 ID 时，直接使用规则排序第一题。
- AI只生成一句推荐理由，不能改变候选集和排序过滤结果。
- 推荐接口总等待时间不得因为AI失败超过现有超时上限。

### 4. `other` 标签处理

- 学生分析标签为 `other` 时，不声称已经识别具体误区。
- 优先根据 `knowledge_ids` 和难度推荐。
- 题目包含 `other` 只能表示通用巩固题，不能表示明确的错误诊断。

---

## 四、文件修改范围

| 文件 | 修改职责 |
|---|---|
| `backend/app/services/problem_catalog.py` | 给 `Lesson` 和 `PracticeSpec` 增加推荐元数据；校验加练标签；兼容转换旧题库 |
| `backend/app/services/practice_recommendation.py` | 增加确定性排序、唯一最佳题直推和AI失败回退 |
| `backend/app/api/coding.py` | 把可信 `misconception_tag` 传入推荐服务；保持现有权限与缓存逻辑 |
| `backend/app/data/practice.json` | 为36道题补充难度和目标误区标签 |
| `backend/app/data/practice-03-4-v1.json` 等9个文件 | 补充目标误区标签和来源地址 |
| `backend/tests/test_practice_catalog.py` | 校验所有加练题字段合法、参考解通过、典型错解失败 |
| `backend/tests/test_practice_recommendation.py` | 校验标签匹配、直接推荐、并列选择和AI不可用回退 |
| `backend/tests/verify_practice_content.py` | 离线校验集中式题库的新字段 |
| `README.md` | 更新加练推荐说明，明确规则优先和AI辅助选择 |
| `docs/2026-10-18-12关针对性加练候选题.md` | 删除“自动推荐尚未接入”等过时描述 |

本次不修改前端推荐弹窗的交互和样式，因为现有返回结构 `recommendation.problem_id/title/reason/level_no` 可以保持不变。

---

## 五、实施任务

### Task 1: 为统一元数据编写失败测试

**Files:**
- Modify: `backend/tests/test_practice_catalog.py`
- Modify: `backend/tests/verify_practice_content.py`

**Interfaces:**
- Consumes: 当前 `PROBLEMS` 运行时目录。
- Produces: 所有加练题必须满足的元数据合同。

- [ ] **Step 1: 增加运行时目录测试**

```python
def test_all_practice_questions_have_recommendation_metadata():
    practice = [item for item in PROBLEMS.values() if item.kind == "practice"]
    allowed = {
        "range_boundary", "accumulation_error", "condition_error",
        "variable_error", "syntax_error", "other",
    }
    assert practice
    for item in practice:
        assert item.difficulty in {1, 2, 3}
        assert item.target_misconception_tags
        assert set(item.target_misconception_tags) <= allowed
        assert item.source_url and item.source_url.startswith("https://")
```

- [ ] **Step 2: 运行测试并确认先失败**

```powershell
cd backend
python -m pytest tests/test_practice_catalog.py -q
```

预期：因 `Lesson` 尚无 `target_misconception_tags` 或部分题目缺少元数据而失败。

- [ ] **Step 3: 扩展离线内容校验**

在 `verify_practice_content.py` 中检查 `difficulty` 和 `target_misconception_tags`，错误信息必须包含具体 `problem_id`。

- [ ] **Step 4: 提交测试合同**

```powershell
git add backend/tests/test_practice_catalog.py backend/tests/verify_practice_content.py
git commit -m "test: define practice recommendation metadata contract"
```

### Task 2: 扩展统一题目模型并兼容两种数据源

**Files:**
- Modify: `backend/app/services/problem_catalog.py`

**Interfaces:**
- Consumes: 现有完整 `Lesson` JSON 和集中式 `PracticeSpec` JSON。
- Produces: `Lesson.target_misconception_tags`、`Lesson.source_url`。

- [ ] **Step 1: 从独立模块复用误区标签类型**

把 `MisconceptionTag` 与固定标签集合移动到不依赖 `problem_catalog.py` 的小模块，例如：

```text
backend/app/services/misconceptions.py
```

内容：

```python
from typing import Literal

MisconceptionTag = Literal[
    "range_boundary", "accumulation_error", "condition_error",
    "variable_error", "syntax_error", "other",
]

MISCONCEPTION_TAGS = {
    "range_boundary", "accumulation_error", "condition_error",
    "variable_error", "syntax_error", "other",
}
```

`error_analysis.py` 和 `personalized_history.py` 改为从该文件导入，防止 `problem_catalog` 与 `error_analysis` 循环依赖。

- [ ] **Step 2: 给模型增加字段与校验**

给 `Lesson` 添加：

```python
target_misconception_tags: list[MisconceptionTag] = Field(default_factory=list)
source_url: str | None = None
```

给 `PracticeSpec` 添加：

```python
difficulty: Literal[1, 2, 3]
target_misconception_tags: list[MisconceptionTag] = Field(min_length=1)
```

在 `Lesson.consistent()` 中拒绝没有目标标签的加练题。

- [ ] **Step 3: 更新集中式题目转换**

将原来的：

```python
difficulty=1
```

改为：

```python
difficulty=spec.difficulty,
target_misconception_tags=spec.target_misconception_tags,
source_url=spec.source_url,
```

- [ ] **Step 4: 运行测试确认失败只剩数据缺失**

```powershell
cd backend
python -m pytest tests/test_practice_catalog.py -q
```

预期：模型加载在缺失新字段的题目处失败，且错误指向具体题目。

- [ ] **Step 5: 提交模型改动**

```powershell
git add backend/app/services/misconceptions.py backend/app/services/problem_catalog.py backend/app/services/error_analysis.py backend/app/services/personalized_history.py
git commit -m "feat: add practice misconception metadata"
```

### Task 3: 补齐45道题的推荐元数据

**Files:**
- Modify: `backend/app/data/practice.json`
- Modify: `backend/app/data/practice-03-4-v1.json`
- Modify: `backend/app/data/practice-03-5-v1.json`
- Modify: `backend/app/data/practice-03-6-v1.json`
- Modify: `backend/app/data/practice-04-4-v1.json`
- Modify: `backend/app/data/practice-04-5-v1.json`
- Modify: `backend/app/data/practice-04-6-v1.json`
- Modify: `backend/app/data/practice-05-4-v1.json`
- Modify: `backend/app/data/practice-05-5-v1.json`
- Modify: `backend/app/data/practice-05-6-v1.json`

**Interfaces:**
- Consumes: Task 2 的字段合同。
- Produces: 可被确定性推荐规则读取的完整题库元数据。

- [ ] **Step 1: 按题目实际训练目标人工标注**

标注原则：

- 每题至少一个标签，最多两个标签。
- 不因为某题属于循环关就一律标为 `range_boundary`。
- 只有测试确实能区分该误区时才能添加标签。
- 通用综合题可以使用 `other`，但不能用它代替能够明确标注的标签。

例如：

```json
{
  "problem_id": "practice-08-1-v1",
  "difficulty": 1,
  "target_misconception_tags": ["accumulation_error"]
}
```

```json
{
  "problem_id": "practice-07-1-v1",
  "difficulty": 1,
  "target_misconception_tags": ["range_boundary"]
}
```

- [ ] **Step 2: 为9道单文件题补来源**

来源应记录实际参考页面。没有直接改编来源时，使用对应选题文档中已经核对过的参考链接，不能临时编造链接。

- [ ] **Step 3: 运行离线内容校验**

```powershell
cd backend
python tests/verify_practice_content.py
```

预期：45道参考解全部通过；每道典型错解至少失败一个测试；所有推荐元数据合法。

- [ ] **Step 4: 运行题库集成测试**

```powershell
python -m pytest tests/test_practice_catalog.py -q
```

预期：全部通过。

- [ ] **Step 5: 提交题库元数据**

```powershell
git add backend/app/data backend/tests/verify_practice_content.py
git commit -m "data: label practice questions for misconception matching"
```

### Task 4: 实现规则优先的推荐和AI回退

**Files:**
- Modify: `backend/app/services/practice_recommendation.py`
- Modify: `backend/app/api/coding.py`
- Modify: `backend/tests/test_practice_recommendation.py`

**Interfaces:**
- Consumes: 当前失败分析的 `misconception_tag`、`knowledge_ids` 和题目元数据。
- Produces: 保持现有 `RecommendationResult` 响应结构。

- [ ] **Step 1: 编写标签精确匹配测试**

测试至少覆盖：

```python
@pytest.mark.anyio
async def test_exact_misconception_match_is_preferred_without_model_call(monkeypatch):
    async def unexpected_request(*args, **kwargs):
        pytest.fail("unique best candidate must not call the model")

    monkeypatch.setattr(error_analysis, "request_diagnosis", unexpected_request)
    base = PROBLEMS["practice-08-1-v1"]
    exact = base.model_copy(update={
        "problem_id": "practice-exact-v1",
        "target_misconception_tags": ["accumulation_error"],
    })
    unrelated = base.model_copy(update={
        "problem_id": "practice-unrelated-v1",
        "target_misconception_tags": ["range_boundary"],
    })

    result = await recommend_practice(
        {"problem_id": "shell-total-v1"},
        [unrelated, exact],
        misconception_tag="accumulation_error",
        knowledge_ids={"K08"},
        target_difficulty=1,
    )

    assert result.status == "ready"
    assert result.recommendation.problem_id == "practice-exact-v1"
```

- [ ] **Step 2: 编写AI不可用回退测试**

```python
@pytest.mark.anyio
async def test_tied_candidates_fall_back_to_ranked_question_when_model_is_unavailable(monkeypatch):
    async def timeout(*args, **kwargs):
        request = httpx.Request("POST", "https://deepseek.test/chat/completions")
        raise httpx.ReadTimeout("timeout", request=request)

    monkeypatch.setattr(error_analysis, "request_diagnosis", timeout)
    monkeypatch.setattr(error_analysis, "analysis_configuration_error", lambda: None)
    base = PROBLEMS["practice-08-1-v1"]
    first = base.model_copy(update={"problem_id": "practice-a-v1"})
    second = base.model_copy(update={"problem_id": "practice-b-v1"})

    result = await recommend_practice(
        {"problem_id": "shell-total-v1"},
        [second, first],
        misconception_tag="accumulation_error",
        knowledge_ids={"K08"},
        target_difficulty=1,
    )

    assert result.status == "ready"
    assert result.recommendation.problem_id == "practice-a-v1"
```

- [ ] **Step 3: 运行新测试并确认失败**

```powershell
cd backend
python -m pytest tests/test_practice_recommendation.py -q
```

预期：当前实现仍会调用模型或在模型异常时返回 `unavailable`，因此新增测试失败。

- [ ] **Step 4: 实现纯函数排序**

新增：

```python
def rank_candidates(
    candidates: list[Lesson],
    *,
    misconception_tag: str | None,
    knowledge_ids: set[str],
    target_difficulty: int = 1,
) -> list[Lesson]:
    return sorted(
        candidates,
        key=lambda item: practice_rank(
            item,
            misconception_tag=misconception_tag,
            knowledge_ids=knowledge_ids,
            target_difficulty=target_difficulty,
        ),
    )
```

排序函数不得访问数据库、网络或全局用户状态。

- [ ] **Step 5: 修改推荐服务输入**

`recommend_practice()` 接收可信标签并执行：

```text
无候选题 → skipped
唯一最佳题 → 直接 ready
多题并列且模型可用 → 模型辅助选择
模型失败 → 规则第一题 ready
```

回退理由使用固定文案：

```text
这道题和你刚才练习的知识点及疑似误区相关，可以用来巩固。
```

- [ ] **Step 6: 只传递已审核的误区标签**

`coding.py` 只在分析满足以下条件时使用标签：

```python
feedback is not None
and feedback.status == "ready"
and feedback.source == "ai"
and feedback.content is not None
and feedback.content.misconception_tag in MISCONCEPTION_TAGS
```

否则传 `None`，不得把模型不可用或解析失败当成 `other`。

- [ ] **Step 7: 运行推荐测试**

```powershell
cd backend
python -m pytest tests/test_practice_recommendation.py -q
```

预期：全部通过，且原有权限、缓存、主线隔离测试继续通过。

- [ ] **Step 8: 提交推荐改动**

```powershell
git add backend/app/services/practice_recommendation.py backend/app/api/coding.py backend/tests/test_practice_recommendation.py
git commit -m "feat: prefer deterministic misconception practice matching"
```

### Task 5: 完整回归与文档更新

**Files:**
- Modify: `README.md`
- Modify: `docs/2026-10-18-12关针对性加练候选题.md`

**Interfaces:**
- Consumes: Task 1–4 的最终行为。
- Produces: 与当前代码一致的运行和验收说明。

- [ ] **Step 1: 更新功能说明**

README应明确：

```text
加练题来自经过校验的固定题库。系统先按疑似误区标签、知识点、解锁状态、完成状态和难度进行匹配；只有多道题同样合适时才让编程助教辅助选择。模型不可用时使用规则排序结果，不影响通关记录。
```

- [ ] **Step 2: 删除旧文档中的过时状态**

把“自动推荐尚未接入”更新为当前实际流程，同时保留题目来源和内容审核说明。

- [ ] **Step 3: 运行后端完整测试**

```powershell
cd backend
python -m pytest -q
```

预期：全部通过；若存在项目原有的明确跳过项，应在测试报告中记录原因，不能写成全部执行。

- [ ] **Step 4: 运行前端测试和构建**

```powershell
cd ..\frontend
node --test tests/*.test.cjs
npm run build
```

预期：测试通过，生产构建成功。

- [ ] **Step 5: 手工验证完整流程**

依次验证：

1. 新用户完成一道主线题的失败提交；
2. AI分析返回固定 `misconception_tag`；
3. 学生修改后通过；
4. 同标签加练题直接出现；
5. 点击加练能够进入真实题目；
6. 加练提交不改变下一主线关的解锁状态；
7. 关闭DeepSeek配置后再次完成“失败→改对”，仍能得到规则推荐；
8. 刷新页面后原成功提交和缓存推荐仍然存在。

- [ ] **Step 6: 提交文档和最终验证结果**

```powershell
git add README.md docs/2026-10-18-12关针对性加练候选题.md
git commit -m "docs: describe misconception based practice recommendations"
```

---

## 六、验收标准

### 数据验收

- [ ] 所有加练题在运行时都有合法 `difficulty`。
- [ ] 所有加练题至少有一个固定 `target_misconception_tags`。
- [ ] 所有加练题都保留可追踪的 `source_url`。
- [ ] 任何未知误区标签都会在题库启动校验阶段被拒绝。
- [ ] 66 道参考解全部通过自己的测试。
- [ ] 66 道典型错解全部至少失败一个测试。

### 推荐验收

- [ ] 推荐只返回题库中真实存在的 `problem_id`。
- [ ] 已通过、未发布、未解锁题目不会进入候选集。
- [ ] 有明确误区标签时，优先推荐目标标签匹配的题。
- [ ] 无可信标签时，只按知识点、难度和稳定 ID 排序，不编造误区。
- [ ] 存在唯一最佳题时不调用模型。
- [ ] 模型超时、不可用或返回非法内容时仍能返回规则推荐。
- [ ] 重复获取同一次成功提交的推荐不会再次调用模型。
- [ ] 推荐失败或跳过不影响通关结果和主线状态。

### 兼容验收

- [ ] 旧的 `practice.json` 仍由兼容加载器读取。
- [ ] 30 个完整单题文件继续直接加载。
- [ ] 前端无需修改即可展示推荐。
- [ ] 已保存提交和旧推荐仍可查看。
- [ ] API现有字段不删除、不改名。

---

## 七、本次明确不做

- 不要求各关加练题数量一致。
- 不把36道旧题立即拆成单独文件。
- 不自动给学生计算复杂能力等级。
- 不根据一次错误认定知识点未掌握。
- 不让模型创建或发布题目。
- 不建立题库管理后台。
- 不修改现有判题器和测试用例执行逻辑。
- 不更换AI供应商或训练模型。

## 八、预期结果

完成后，加练推荐流程应为：

```text
学生提交错误代码
→ 程序判题并保存真实证据
→ AI生成受控疑似误区标签
→ 学生修改后通过
→ 后端筛选已发布、已解锁、未通过的同知识点加练
→ 优先匹配目标误区标签和难度
→ 唯一最佳题直接推荐
→ 并列时允许AI辅助选择
→ AI失败时回退到规则第一题
→ 推荐结果随成功提交缓存
```

该方案解决的是数据与推荐依据不统一的问题，同时保留现有题目数量、判题流程、页面和历史记录。
