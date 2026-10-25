# 第一阶段：三级提示质量优化

## 已确认的范围与现状

用户已明确授权先检查现有项目，然后实施第一阶段。此次保持判题器、题库、数据库和公共提交接口不变。只改进 AI 分层引导、质量检查、失败降级和相关前端展示；第二、三阶段只写计划。

当前链路：coding.py 接收 problem_id/code → submission.py 判题 → error_analysis.py 调用 Ollama → SubmissionFeedback.jsx 显示 judge/analysis。分析公开格式保留 suspected_cause/evidence/knowledge_points/hints 以及原有五种 status。MySQL 通过 SQLAlchemy 管理，已有 users、ai_chat_records、class_selections 和设置相关表；聊天记录不是提交记录，没有判题快照或提示使用字段。

## 问题与方案

只改提示词不能拦截重复或无依据的解释。本阶段结合提示词、轻量输出检查、独立模型复核；不引入 AST、训练或误区规则库。所有检查只审核教学输出，不重新判定学生代码对错。本地 3B 模型会把无关的概念问题放在第一级，因此第一级改为根据现有判题错误类型和当前关卡选择经人工审查的概念问题；Qwen 继续生成疑似原因、证据说明、知识点及后两级提示。

1. 分层职责：第一级仅提出概念方向问题，不含代码位置、实际标识符、错误诊断或修复动作；第二级关联知识概念与需观察的代码；第三级给出可执行的核验或修改思路，不提供完整答案。
2. 本地检查：保留引用精确匹配和代码泄露检查；检查首级提前定位、第二级是否指向代码、三级是否给出可执行动作、近似重复、占位知识点及明确的答案直输建议。检查返回具体问题代码，供一次定向修正使用。
3. 语义复核：同一 Qwen 的独立请求同时读取题目、完整代码、真实结果和候选分析，审查层次、依据、相关性和答案泄露。复核格式不合格或无法完成时不放行。复核只能决定展示分析与否，不能改 judge。最多生成两次，每次候选通过本地检查后才复核；所有调用共享 90 秒总期限。
4. 降级：Qwen 的后两级若只有层次弱或重复问题，就换成按可靠判题类别和当前题目选择的保守教学提示，并在返回 message 中明确说明。格式错误、证据伪造、答案代码泄露、复核失败、超时或服务不可用仍返回 invalid_response/timeout/unavailable 和 content=null；任何情况都不改变 judge。兜底不生成新的错误诊断。
5. 前端：保留逐级按钮；三个提示全部展开后才允许查看完整原因和解释。真实判题证据始终可见，并显示是否采用保守提示。

## 文件与实施清单

- [x] backend/app/services/hint_quality.py：新增输出质量检查和可定位的检查原因，不分析 AST、不负责判题。
- [x] backend/app/services/error_analysis.py：优化提示词、固定安全的一级问题、增加语义复核、定向修正、共享时限和保守提示降级。
- [x] backend/tests/test_hint_quality.py：首级泄露、近似重复、弱层级、占位知识点、答案泄露及正常分层样例。
- [x] backend/tests/test_submission.py：原有接口/判题保持、复核拒绝、解析/模型故障、保守提示与共享时限。
- [x] frontend/src/components/SubmissionFeedback.jsx：延后原因详情展示、质量降级信息。
- [x] frontend/tests/submission-flow.test.cjs：验证详情不能提前展开、0→3 提示顺序和降级结果。
- [x] backend/tests/live_hint_quality.py：可选的真实模型诊断，保存原始草稿供人工核查；真实 HTTP 验收使用原有 backend/tests/live_submission_smoke.py，结果见 docs/phase1-http-acceptance.json。
- [x] docs/b-part-integration.md：明确 A/B 字段对接和第二阶段简单数据模型提案。

## 验收标准

正确提交不请求任何模型。任何生成/复核失败不改变 judge。旧格式调用方继续可用。真实 HTTP 验收：语法错误、循环边界、累加覆盖、未定义变量的判题状态均符合预期，四个失败案例均得到 ready；正确代码 accepted + skipped。四种错误的 AI 证据引用分别来自真实报错或实际输出，人工检查一级未提前泄露具体位置，三级不含完整正确代码。其中文字质量不足的三例采用了明示的保守提示，不能说是 Qwen 自由生成的三级提示全部通过。3B 模型的复核仍可能误判，不能保证任意输入的语义判断正确。

本次验证：后端 `python -m pytest -q` 为 64 通过，前端 `node --test tests/*.test.cjs` 为 7 通过，`npm run build` 通过。HTTP 验收在临时 SQLite 数据库上启动原 FastAPI 服务，注册测试账号，走 `/api/v1/code/submit` 调用本机 Ollama；Docker Desktop 未运行，因此这轮没有容器验收。

`phase1-http-acceptance.json` 是 2026-10-14 的历史快照。2026-10-15 提交前又拦截了“确保正确”式笼统二级提示，并改进第二关保守提示，使它不假定学生已写出循环；本次 Ollama 服务未运行，尚未生成修改后的真实模型验收快照。

复现：启动 Ollama 并确认已安装 `qwen2.5-coder:3b-instruct`；启动项目后，在 `backend` 目录运行 `python tests/live_submission_smoke.py --url http://127.0.0.1:3000 --output ../docs/phase1-http-acceptance.json`。也可在编辑器分别提交缺冒号、`range(1, 100)`、循环里 `total = i`、使用未定义变量这四段错误代码，逐级展开提示并核对判题证据；最后提交正确代码确认不调用 AI。

## A 部分对接边界

当前实际字段是 problem_id、judge.passed、judge.status、judge.cases[].errors[].type；没有 question_id、knowledge_point 或题目难度字段。第一阶段不改这些公共字段。第二阶段先与 A 确认字段命名/版本、失败用例结构、知识点 ID、难度和题目验证状态，再通过适配层接入；error_type 属于确定性判题，misconception_tag 属于疑似 AI 推断。
