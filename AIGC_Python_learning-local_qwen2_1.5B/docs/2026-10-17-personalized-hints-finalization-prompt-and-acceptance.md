# 个性化历史提示验收与回归提示词

## 一、当前状态

截至 2026-10-17，当前项目已完成“个性化历史提示”的代码实现，并以 `52d0571` 提交；本地 `main` 又通过 `9d9d816` 合入当时的 `origin/main`，合并没有冲突。本次验收发现的内容校验问题以 `b9cc64c` 单独修复提交，验收记录另行提交。这些本地提交尚未推送。以下验收关注已提交实现及合并后的工作树，不再重复提交该功能。

本机默认 Ollama 服务的模型列表为空；本次使用本机已有的 Qwen2.5-Coder 3B GGUF，在隔离的临时 Ollama 服务和 SQLite 后端中完成真实模型验收。自动回归已执行，但真实模型内容质量仍有未通过项，详见第十节。本阶段不能据此宣称全面验收通过。

已有实现包括：

- 后端按当前用户选择相关历史错误；
- 使用 `knowledge_ids` 判断历史是否与当前题目相关；
- 最多向模型提供 3 条历史摘要；
- 历史摘要不包含旧代码全文、隐藏测试和账号资料；
- 当前题目、当前代码和当前判题证据优先于历史标签；
- 模型成功使用历史后保存 `personalization.used` 和 `related_history_count`；
- 前端只有在确实使用历史时才显示个性化说明；
- 模型失败、固定语法提示和正确提交不声称使用个性化历史。

本阶段不要开发同类题推荐。当前仓库没有独立加练题库，也没有加练题的 `target_misconception_tags`，因此无法进行真实题目匹配。

## 二、任务目标

请先检查当前工作树和分支，在不重写现有功能的前提下，完成个性化历史提示的真实模型验收、回归检查及必要的小范围修复。若验收产生修复，再单独提交修复。

不要开发新功能，不要创建加练题，不要让 AI 生成题目。

## 三、需要检查的文件

重点检查：

- `backend/app/services/personalized_history.py`
- `backend/app/services/error_analysis.py`
- `backend/app/api/coding.py`
- `backend/app/services/learning_contract.py`
- `backend/tests/test_personalized_history.py`
- `backend/tests/test_submission.py`
- `backend/tests/test_learning_history.py`
- `frontend/src/components/SubmissionFeedback.jsx`
- `frontend/tests/submission-flow.test.cjs`

先执行 `git status` 和 `git diff`，确认没有覆盖其他同学的题库、判题和界面修改。

## 四、真实 Ollama 验收

启动当前项目和 `qwen2.5-coder:3b-instruct`，使用同一个测试用户完成以下流程。

### 1. 第一次相关错误

提交一个循环边界错误，例如：

```python
total = 0
for i in range(1, 100):
    total += i
print(total)
```

检查：

- 程序判题先返回；
- 判题结果为真实测试结论；
- AI 分析不改变判题；
- 因为没有可用历史，`personalization.used=false`；
- 页面不显示“参考了相关练习记录”。

### 2. 第二次相关错误

在相同知识点下再次提交一个失败代码。

检查：

- 后端只选择当前用户的相关历史；
- `related_history_count` 为实际使用条数；
- AI 成功时 `personalization.used=true`；
- 页面显示“本次提示参考了你的相关练习记录”；
- AI 仍然只根据本次代码和本次判题证据确定错因；
- 提示面向十几岁的初学者，三级逐步深入且不直接给答案。

### 3. 当前错误与历史不同

历史中保留循环边界误区，然后提交变量未定义错误，例如：

```python
print(missing_total)
```

检查：

- 程序错误类型为变量未定义相关错误；
- 本次 `misconception_tag` 只能是 `variable_error` 或证据不足时的 `other`；
- 不能因为历史记录而继续输出 `range_boundary`；
- 不能说学生“一直不会循环边界”。

### 4. 后来做对

在相关错误之后提交正确答案，再制造一次相关错误。

检查：

- 历史摘要能够标记以前的题目后来已经做对；
- AI 不能说学生一直不会或从未掌握；
- 旧错误记录仍然保留；
- 正确提交不调用 AI。

### 5. 模型故障

临时停止 Ollama 或模拟超时、非法 JSON。

检查：

- 判题结果和提交记录仍然保存；
- `personalization.used=false`；
- 页面不显示个性化说明；
- 接口返回现有降级状态，不出现无法处理的 500；
- 恢复模型后，同一未完成分析可以按现有流程继续。

## 五、隐私与用户隔离验收

创建用户 A 和用户 B。

必须满足：

- A 的模型请求只能包含 A 的历史摘要；
- B 的历史不能进入 A 的分析；
- 历史摘要最多 3 条；
- 摘要不包含历史代码全文；
- 摘要不包含隐藏测试输入、期望输出或实际输出；
- 摘要不包含手机号、密码、令牌或其他账号信息；
- 前端响应不返回历史提交 ID 和完整历史摘要；
- 删除账号后，该用户历史不能继续被选择。

## 六、自动测试

运行个性化功能相关后端测试：

```powershell
cd backend
python -m pytest -q tests/test_personalized_history.py tests/test_submission.py tests/test_learning_history.py tests/test_learning_contract.py
```

运行完整后端测试：

```powershell
python -m pytest -q
```

运行前端测试和构建：

```powershell
cd ../frontend
node --test tests/*.test.cjs
npm run build
```

如果完整后端测试失败，必须区分：

- 当前个性化功能导致的回归；
- 测试环境、数据库配置或依赖版本导致的问题；
- 与本阶段无关的既有失败。

不得只报告专项测试通过，也不得为了让测试变绿而修改无关生产代码。

## 七、完成后输出

完成验收后说明：

1. 当前个性化历史选择规则；
2. 模型实际收到哪些历史字段；
3. 真实 Ollama 三类错误的结果；
4. 哪些测试通过、哪些失败及原因；
5. 修改了哪些文件；
6. 是否仍有未提交文件，修复是否需要新提交；
7. 若有修复，建议的提交信息。

建议提交信息：

```text
feat: personalize hints with relevant learning history
```

## 八、加练推荐的启动条件

只有 A 同学提供至少一批经过审核的加练题后，才能开始加练推荐。每道题至少需要：

```text
problem_id
version
title
difficulty
knowledge_ids
target_misconception_tags
tests
reference_solution
published
```

在这些数据出现之前：

- `related_questions` 继续返回空数组；
- 页面继续显示暂无已验证同类题；
- 不实现推荐算法；
- 不虚构题目和标签；
- 不让 AI 临时生成并发布加练题。

## 九、最终验收标准

当前个性化历史提示改动经过真实 Ollama 和自动测试检查，能够只使用当前用户最多 3 条相关历史摘要调整讲解方式；历史不能改变本次判题和错因证据，不能泄露其他用户、旧代码或隐藏测试。故障时保持现有判题和降级流程。完成这些验收后，本阶段结束；若验收产生修复，先提交修复。随后等待 A 提供加练题及标签再进入推荐阶段。

## 十、2026-10-17 实际执行结果

- 在隔离服务中运行真实 `qwen2.5-coder:3b-instruct`。A、B 各自第一次边界错误均判为 `wrong_answer`，且 `personalization.used=false`；A 的第二次相关错误使用 1 条历史，做对后再次错误使用 2 条历史。A 的正确提交判为 `accepted`，分析为 `skipped`，没有个性化声明。
- 可复跑的合成账号 HTTP 脚本和该次响应摘要分别保存在 `backend/tests/live_personalized_acceptance.py`、`backend/tests/live_personalized_acceptance.json`。摘要不保存密码或令牌。
- 隔离数据库核对：A 共 5 条提交，B 共 1 条；A 最后一次分析只选到 A 的 2 条历史，均带 `later_passed=true`。B 用 A 的当前提交 ID 查询不到摘要。摘要最多 3 条，字段仅为 `problem_id`、`problem_title`、`knowledge_ids`、`error_type`、`misconception_tag`、`suspected_cause`、`later_passed`、`hints_viewed_max`、`created_at`；没有旧代码、隐藏测试或账号字段。前端只根据 `ready`、`source=ai`、`personalization.used=true` 显示说明；显示条件由自动测试覆盖，本次未做浏览器手工验收。
- **未通过真实模型内容验收：** 边界错误和累加覆盖错误都被模型生成了 `variable_error`，错误原因也不能准确区分两者。变量未定义场景的公开判题为 `execution_error`，但模型给出不符的原因，服务端将分析拒绝为 `invalid_response`，`personalization.used=false`，判题和记录保留。不能把这些输出称为可靠的个性化错因分析。
- 小范围修复：当本关代码明确包含 `range(1, 101)` 时，拒绝声称边界遗漏的原因；若只有标签误选但原因没有边界断言，则降为 `other`。公开 `NameError` 时，拒绝不说明名字未定义的原因，以及在无循环代码上声称循环或累加的原因。相关回归测试已加入。
- 自动回归：后端指定 4 个文件 `77 passed`，后端全量 `223 passed, 1 skipped`，前端 `28 passed`，`npm run build` 通过。跳过项是未配置专用 MySQL 测试数据库的迁移测试。模型故障、非法响应、未完成分析恢复、账户删除清理历史等流程由自动测试覆盖；本次没有声称它们经过真实停机演练。
- 最终状态：本阶段真实模型验收发现未通过项，暂不进入加练推荐。需要在后续工作中针对模型输出质量继续修复并重跑本节场景；本次隔离服务与模型副本仅供验收，结束后清理。
