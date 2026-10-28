# 疑似误区追踪实施计划

**目标：** 按 `docs/2026-10-16-misconception-tracking-prompt-and-acceptance.md` 为本次失败分析保存受控疑似误区标签，并在当前用户的错题页展示历史统计。

**现有链路：** `/code/submit` 先保存判题，`/code/submissions/{id}/analysis` 后续保存分析；`LearningSubmission.analysis_json` 保存当时快照。沿用该流程，不增加表或改动判题器。

**验收标准：** 六种固定标签严格校验；成功提交及分析故障不计入统计；语法错误直接标记；统计隔离用户并区分错误次数、题目数及后来做对的题目数；前端展示疑似性质与空状态；后端、前端回归通过。

## 任务 1：分析标签与历史快照

**文件：** `backend/app/services/error_analysis.py`、`backend/tests/test_submission.py`。

- [x] 先增加标签枚举、语法固定提示、模型标签非法、故障及历史快照的失败测试，并确认失败原因。
- [x] 在分析内容中加入受控 `misconception_tag`。提示词要求从题目、代码和公开判题证据中选择；审核标签与同一证据是否一致。证据不足使用 `other`；分析不成功使用 `null`。
- [x] 保持旧历史记录可读取；新标签随现有 `analysis_json` 一起保存，不在历史查询时重新分类。
- [x] 运行相关后端测试。

## 任务 2：当前用户统计

**文件：** `backend/app/api/learning_history.py`、`backend/tests/test_learning_history.py`。

- [x] 先写失败测试，覆盖同题重复、跨题重复、后来做对、故障记录和双用户隔离。
- [x] 增加 `GET /api/v1/code/misconceptions`，仅从当前用户已保存的失败且分析成功记录汇总六种标签。`later_passed_count` 计后来做对的不同题目数。
- [x] 运行相关后端测试。

## 任务 3：错题页概览与回归

**文件：** `frontend/src/components/codeApi.mjs`、`frontend/src/components/MisconceptionOverview.jsx`、`frontend/src/pages/LearningHistory.jsx`、`frontend/tests/submission-flow.test.cjs`、`frontend/src/styles/index.css`。

- [x] 先写失败测试，覆盖带令牌请求和概览展示。
- [x] 在错题页请求统计、展示中文标签与五项指标；无数据时显示文档指定的空状态；复习提交后的分析完成时刷新统计。
- [x] 运行 `node --test tests/*.test.cjs` 和 `npm run build`；运行后端完整测试并记录环境限制。
