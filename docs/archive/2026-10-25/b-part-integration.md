# B 部分现状、A/B 对接与第二阶段计划

进度（2026-10-14）：已完成一张 `learning_submissions` 表、个人提交/错题查询和提示最高已看级别记录。下文仍包含后续阶段设计；误区标签、跨题统计、历史摘要和推荐尚未实现。

## 当前已存在与缺口

已有：Ollama 聊天和失败辅导、服务器判题、三级提示、用户身份认证、MySQL/SQLAlchemy、普通聊天记录、个人提交历史与提示最高已看级别。缺少：misconception_tag、跨题误区统计、历史摘要、经过验证的练习目录和加练推荐。

AIChatRecord 只用于普通聊天，缺少题目、用例快照、通过状态、提示使用等语义。不要把编程提交硬塞进聊天表。第二阶段复用当前数据库和 User 身份，新增一张学习提交表即可起步；不建立复杂误区知识库。

## 与 A 同学需要先确认的接口

第一阶段不改公共接口。下表为讨论清单，不是已经实施的新 API。

| 语义 | 现有实现 | 需要共同确认 |
| --- | --- | --- |
| 题目 ID | 字符串 problem_id，如 level2 | question_id 是否统一名称；旧 ID 的兼容映射；题目更新时如何标识版本 |
| 题目知识点 | Problem 没有该字段；analysis.knowledge_points 是 AI 自由文本 | A 提供稳定 knowledge_point ID 或 knowledge_points ID 数组，名称只用于展示；不能拿 AI 文本作为统计主键 |
| 正确与否 | judge.passed 布尔；status 为 accepted/wrong_answer/execution_error/timeout | A 继续作为唯一来源，B 不自行运行另一套测试 |
| 程序错误类型 | cases[].errors[].type，如 NameError；输出不符时 errors 可为空 | error_type 的枚举、可空规则、语法/运行/超时/输出错误分类和多错误时的表达方式 |
| 失败用例 | cases 中 passed=false 的条目，含 case_id、expected_output、actual_output、output_available、errors | failed_tests 的输入、期望/实际、异常行号、输出截断和可用性格式；哪些隐藏用例信息可给 AI/学生 |
| 题目难度 | 当前没有 | A 提供稳定的难度值、题目 ID、知识点 ID、是否通过验证和是否可作为加练 |

建议只在 A/B 边界增加一次映射，不同时维护 problem_id 和 question_id 两套含义。必须区分：error_type 是程序实际发生的错误类型；misconception_tag 是 AI 对知识误区的疑似推断，同一种程序错误可能对应不同误区。

## 第二阶段：一张提交表 + 记录查询与提示事件

### 为什么需要新表

每次错误和正确尝试都应保留，既能回看证据，也能知道后来是否在较少帮助下做对。不能只保存错题后覆盖成“已掌握”。原聊天表不具备这些字段，新表对现有聊天和账号数据影响最小。

建议表 learning_submissions，字段分组如下：

- id、user_id（关联现有用户）、question_id、question_version、practice_session_id、created_at。
- student_code、problem_snapshot_json、judge_json、passed、error_type。
- knowledge_point_ids_json（A 的稳定知识点）、analysis_json（包含 AI 知识点文本、原因、证据、提示、状态、模型和提示词版本）。
- misconception_tag：只允许 range_boundary / accumulation_error / condition_error / variable_error / syntax_error / other；没有有效分析时为 null，不把模型不可用统计成学生的 other 误区。
- hints_viewed_max：0..3，记录实际点到了哪级；analysis_details_viewed：是否查看完整分析。
- assistance_context：记录本练习会话此前是否看过提示。正确提交本身的提示数为零，不能据此声称是独立做对。首次全新会话无本系统帮助通过、看提示后通过、无法确认三种情况分开统计。

“最终是否通过”通过同一用户、题目及练习会话内的后续 accepted 记录计算。旧错误记录保持原貌，关联后续解决情况，不能抹掉犯错历史；也不把一次无提示通过等同于证明完全掌握。

### 实施顺序

1. 与 A 确认上表，写映射契约和示例 JSON。为新增表提供明确建表迁移；现有 create_all 不负责修改旧表结构。
2. 每次判题完成先保存尝试，包括 accepted、AI 超时和不可用，再保存分析状态，避免模型失败丢记录。复用当前用户身份，不相信前端提交 user_id。
3. 在分析模型中加入固定枚举 misconception_tag（此时才改变公共分析格式，先同步双方）。证据不足用 other，界面统一显示“疑似误区”。
4. 提示展开事件用用户身份、submission_id、最高已看级别幂等更新；越权访问拒绝。保存帮助上下文，后续通过仍留下它自己的记录。
5. 提供按当前用户分页查询错题/提交的 API 和前端列表，包含题目、时间、代码、证据、分析、提示使用和后续解决情况。
6. 统计同时显示尝试数、不同题目数、近期无提示通过记录。同题重复提交不等价于跨题反复出错；只有至少两道不同题目出现同标签时提示“多题中反复出现，建议复习”，不下“没有掌握”的结论。

验收：刷新/重新登录历史仍存在；不同用户互不可见；AI 不可用仍有提交记录；一个错误不会变成掌握度结论；不同题目重复可识别；后续正确尝试保留；查看旧提示后再做对不会误标为无帮助通过。

## 第三阶段顺序（第二阶段完成后再做）

先按当前 A 知识点 ID 选择最近少量相关记录，例如最多 3 条错误摘要及 2 条后续通过摘要，摘要只含必要信息，设置字符预算，不发送全历史或账号信息。摘要只是教学背景，当前代码和真实判题仍是本次分析依据。

加练从 A 提供且已验证的题目目录筛选：知识点相关、难度合适、避免刚做过的相同题。模型不生成可直接发布的新题。推荐与主线分开、允许跳过。目录中没有合适题目时仅建议复习相关知识点，不伪造 ID 或题目。
