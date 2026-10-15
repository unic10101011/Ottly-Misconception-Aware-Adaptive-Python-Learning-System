# 错题复习工作台实施计划

**目标：** 将个人错题按题聚合，并提供「重新做题」「我的情况」两个标签。

**实现边界：** 继续使用原判题与 AI 提示；只增加复习来源记录、按题聚合接口和页面，不改题目判题格式。现阶段不推断知识点掌握率，也不编造同类题。

1. 后端：新增 `learning_reviews` 关联表；给现有提交接口增加可选复习来源请求头并验证所有权、题目一致性。先写失败测试，再实现。
2. 后端：给提交列表增加 `problem_id` 过滤；新增按题聚合的个人错题摘要接口，返回真实日期、疑似错因、复习次数和最近复习表现。先写失败测试，再实现。
3. 前端：复用 `requestCode` 与 `SubmissionFeedback`，错题页改为选题区及两个标签；做题标签支持运行和复习提交，个人情况标签展示摘要与时间线。补关键交互测试。
4. 验证：完整后端测试、前端测试与构建、临时数据库 HTTP 冒烟。检查其他账号隔离和 AI 不可用时的保存结果。

**现有文件：** `backend/app/api/coding.py` 负责现有提交；`backend/app/api/learning_history.py` 负责本人历史；`frontend/src/pages/LearningHistory.jsx` 负责错题页；`frontend/src/components/codeApi.mjs` 和 `SubmissionFeedback.jsx` 可直接复用。新增表模型和页面样式各一处。
