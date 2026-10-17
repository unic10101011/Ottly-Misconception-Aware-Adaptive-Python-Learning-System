# 个性化历史提示实施计划

**目标：** 按 `docs/2026-10-16-personalized-hints-prompt-and-acceptance.md`，只用当前用户少量相关历史摘要辅助本次三级提示。

**设计：** 历史选择独立于 API 和模型服务。分析接口从已保存的当前提交出发选择摘要；模型服务仅在成功生成 AI 分析时记录使用条数。既有判题、证据校验、固定提示与分析快照保持原流程。

**验收：** 用户隔离、知识点交集、旧记录排除、最多三条且优先不同题目；历史输入不含代码及私有数据；当前证据优先；状态持久化和失败降级；前端有条件显示；后端、前端测试和构建通过。

## 任务 1：历史摘要选择

**文件：** `backend/app/services/personalized_history.py`、`backend/tests/test_personalized_history.py`。

- [x] 先写失败测试：筛选、排序、题目去重、后来做对、用户隔离、旧记录。
- [x] 实现只读取必要列的选择函数，最多返回三条允许字段。
- [x] 跑相关测试。

## 任务 2：分析链路和状态

**文件：** `backend/app/api/coding.py`、`backend/app/services/error_analysis.py`、`backend/app/services/learning_contract.py`、`backend/tests/test_submission.py`。

- [x] 先写失败测试：模型请求隐私、当前证据优先、重复请求、故障和固定提示状态。
- [x] 接入受控摘要；提示词明确历史仅调整讲解，审核历史断言；成功时保存使用条数，其他状态为未使用。
- [x] 跑相关测试。

## 任务 3：前端与回归

**文件：** `frontend/src/components/SubmissionFeedback.jsx`、`frontend/tests/submission-flow.test.cjs`。

- [x] 先写失败测试：只有成功使用历史才显示说明。
- [x] 实现条件文案。
- [x] 跑完整后端、前端测试和构建。
