# 提交判题与三级提示

本文件保留上一轮链路验收记录；本轮三级提示质量优化和最新实测结果见 [phase1-hint-quality.md](../../2026-10-25/phase1-hint-quality.md)。下方旧样例中的提示质量问题是优化前的观察。

## 当前功能和复用范围

复用原有两个关卡、React CodeEditor、认证和 Python Sandbox。原来只有前端 trim 后比较输出；现在把两道题的标准输出放在服务器，由服务器运行用例后判题。AI 只做失败分析，不修改判题结果。现有 AST 安全检查保持复用，没有新增 AST 教学规则、复杂误区库、模型训练或 AI 出题。

每个现有关卡只有一个无输入 stdout 用例：level1 输出 Hello, World!，level2 输出 5050。比较方式沿用去掉首尾空白后精确匹配；这些用例不能证明学生理解了算法，也不能阻止直接打印答案。提交记录未持久化，原关卡列表的静态通关展示未改造。

## 启动与手工体验

1. 启动 Docker Desktop。当前电脑已安装 Ollama 和 qwen2.5-coder:3b-instruct。
2. 在项目目录双击 start-demo.bat。已有 Ollama 安装时脚本会尝试启动其后台服务，并构建、启动数据库、后端和前端。
3. 打开 http://127.0.0.1:3000，注册或登录，进入 for 循环关卡。
4. 直接点“提交”，无需先点“运行”。后端判题结束后，仅失败时等待 AI 分析；期间编辑器只读，运行和提交不能重复触发。
5. 依次点击“查看第 1 级提示”“查看第 2 级提示”“查看第 3 级提示”。原因、依据和知识点默认折叠。修改代码或重新提交会清除旧提示；离开页面后旧请求不会触发跳转。
6. 停止服务用 stop-demo.bat。模型运行在 Windows Ollama 中；停止 Compose 不会卸载模型或删除数据库。

GGUF 手工导入需保留 `ollama/Modelfile` 中的 Qwen 对话模板。API 的 format 使用 JSON Schema，参考 [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)；角色模板参考 [Qwen 官方 Ollama 模型模板](https://ollama.com/library/qwen2.5-coder:3b-instruct/blobs/1e65450c3067)。配置仍使用 .env 的 LOCAL_LLM_URL 和 OLLAMA_MODEL，不新增密钥。

## 数据和错误处理

`POST /api/v1/code/submit` 需要 Bearer 登录令牌，请求只接受：

```json
{"problem_id":"level2","code":"学生本次提交的完整代码"}
```

题目不存在返回 404，未登录返回 401，空白代码、超过 6000 字符或附带 expected_output 等多余字段返回 422。缩进和换行保持原样。

正常处理后 HTTP 200，格式为 `{"code":200,"data":{"problem_id":...,"judge":...,"analysis":...}}`：

| 字段 | 含义 |
| --- | --- |
| judge.status | accepted / wrong_answer / execution_error / timeout，由用例运行确定 |
| judge.passed、passed_cases、total_cases | 是否全部通过、通过数、总数 |
| judge.cases[] | case_id、passed、expected_output、actual_output、output_available、errors、execution_time |
| errors[] | 实际执行器给出的 type、line、message，不采用 AI 生成的报错 |
| output_available | false 时输出未采集，不能解释为学生没有输出 |
| analysis.status | ready / skipped / unavailable / timeout / invalid_response |
| analysis.content | 成功时包含 suspected_cause、evidence、knowledge_points、hints；失败时为 null |
| evidence[] | case_id、field、quote、explanation；引用必须匹配本次真实失败用例 |
| hints | level1、level2、level3，前端逐级展开 |

通过时 analysis=skipped，完全不请求 Ollama。失败时将题目、原始学生代码、失败用例和允许引用的事实送给 Qwen。错误引用必须匹配对应错误信息；stdout 引用取去首尾空白后的前 1000 字，再去除截取片段首尾空白，空字符串只在确实无输出时允许。长输入超过分析预算时明确降级，保持判题证据。不会把超时的未知输出当成空输出喂给模型。

模型响应由 Pydantic 再校验；教学字段限制为自然语言，拦截代码块、赋值语句等解法泄露，证据字段保留规范化的真实引用。解析、结构、引用或提示校验失败时最多重新生成一次，仍失败才返回 invalid_response；连接失败或模型不存在返回 unavailable；两次调用共享 90 秒总期限，超时返回 timeout。上述情况不覆盖 judge。执行器本身不可用也不会让 AI 归咎于学生代码。Nginx 等待 120 秒，前端提交等待上限 180 秒。

本机 Ollama 0.40.3 在语法错误样例上，使用带问号结尾的提示正则时曾返回 peg-native HTTP 500。对照请求确认：将模型端第一级约束放宽为普通自然语言正则，可以正常返回；后端仍检查第一级必须是问句，不合格时进行上述一次修正。此处记录的是本机复现结果，不代表已经定位 Ollama 内部的唯一原因。

字符串匹配能保证引用来源，无法证明自由文本解释的所有推理正确。Qwen 3B 的分析作为“疑似原因”展示，真实样例还需人工核对；这不是学习效果或模型准确率评估。

## 2026-10-12 实际验收记录

真实 HTTP 验收经过 Nginx、注册登录、MySQL、FastAPI、子进程判题和 Windows Ollama，模型为 qwen2.5-coder:3b-instruct。完整响应见 `live-submission.json`（历史本机报告，仓库未收录）。没有使用预写 AI 答案代替模型响应。

| 提交样例 | 真实证据 | 后端结果 | 本次耗时 |
| --- | --- | --- | --- |
| 第二行缺少冒号 | expected ':'，第 2 行 | execution_error，AI ready | 15.17 秒 |
| range 上界少一 | 实际 4950，预期 5050 | wrong_answer，AI ready | 8.55 秒 |
| 循环中覆盖累计值 | 实际 100，预期 5050 | wrong_answer，AI ready | 8.78 秒 |
| 未定义变量 | missing_total 的真实 NameError | execution_error，AI ready | 8.41 秒 |
| 正确累加 | 实际 5050 | accepted，AI skipped | 0.27 秒 |

人工语义检查：四个样例的 evidence 引用全部与真实判题证据一致，未输出完整正确程序。但教学质量尚未完全达到预期：缺冒号的第一级就揭示了具体错误，三级提示有重复；边界错误的第三级建议再打印已有的最终值，帮助有限；覆盖累计值的分析额外猜测了无关的循环终止条件；未定义变量的分析定位正确。**链路和逐级显示已完成，不能据此声称三级提示的渐进性、诊断准确性已经稳定。** 这些是下一轮教学提示质量验收需要解决的问题。

后端回归覆盖接受后不调用模型、错误证据、解析/超时/不可用、一次修正与共享期限、长引用截断、执行器超时和输出隔离。前端 6 项自动测试通过；浏览器实际验证了不先运行即可提交、等待时禁用编辑、提示从 0 到 3 逐级出现、编辑后清空旧反馈、正确提交显示未调用 AI。桌面截图见 [submission-hints-browser.png](submission-hints-browser.png)。未作移动端验收。

## 文件职责

| 文件 | 本阶段职责 |
| --- | --- |
| backend/app/api/coding.py | 保留运行入口，新增经过认证的提交入口，组织判题和分析，返回明确模型 |
| backend/app/services/submission.py | 两个现有题目和用例、请求校验、确定性输出比较、判题数据模型 |
| backend/app/services/error_analysis.py | Ollama 请求、教学提示词、JSON Schema、证据引用校验和降级状态 |
| backend/app/services/sandbox/runner.py | 子进程执行、父进程强制超时、最小环境变量、输出可用性标志 |
| backend/app/services/sandbox/worker.py | 子进程 JSON 入口，调用原有 Sandbox |
| backend/app/services/sandbox/sandbox.py | 复用执行逻辑，增加输出上限，语法拒绝不再伪造 stdout |
| frontend/src/components/CodeEditor.jsx | 当前代码提交、等待互斥、编辑重置、离开页面后忽略旧结果 |
| frontend/src/components/SubmissionFeedback.jsx | 判题事实、三级按钮、折叠原因和依据、模型失败提示 |
| frontend/src/components/codeApi.mjs | 统一运行/提交请求及 401、网络、解析、超时反馈 |
| frontend/src/pages/Level1.jsx、Level2.jsx | 传服务器题目 ID，移除前端判题标准和直接揭露修正答案的提示 |
| frontend/src/styles/index.css | 结果、证据和逐级提示样式 |
| ollama/Modelfile | 手工导入模型时的 Qwen 角色模板和停止符 |
| backend/tests/test_submission.py、test_runner.py | 判题/AI 边界、异常、超时与并发回归测试 |
| frontend/tests/submission-flow.test.cjs | 请求、三级可见性、模型失败、超时输出、卸载晚响应回归测试 |
| backend/tests/live_submission_smoke.py | 使用真实登录和 HTTP API 的模型验收脚本 |

## 自动测试

在 backend 目录，用已安装依赖的 Python 3.11 环境执行：

```powershell
python -m pytest tests -q
```

本机已有的环境可用 `D:\desktop\AI+软件创新\.venv-ottly\Scripts\python.exe` 代替 python。测试使用临时 SQLite 数据库；模型异常测试通过 MockTransport 注入，实际代码判题和超时使用真实子进程。

在 frontend 目录执行：

```powershell
node --test tests/submission-flow.test.cjs
npm run build
```

演示版启动后在 backend 目录执行：

```powershell
python tests/live_submission_smoke.py --output ../docs/live-submission.json
```

该命令创建一个独立 smoke_ 账号，依次提交：缺冒号、range 上界少一、覆盖累加值、未定义变量，以及正确代码。报告保存真实学生代码、判题证据、模型响应、耗时和格式验收结果，不保存令牌或密码。运行脚本不会删除已有账号或聊天。每次模型结果可能变化，须查看报告中的 explanation 和三级 hints 是否合理，不能只看 contract_passed。

三个可手动输入的错误示例：

```python
# 语法错误：第二行缺少语句结构所需符号
total = 0
for i in range(1, 101)
    total += i
print(total)
```

```python
# 循环边界错误：真实输出应为 4950
total = 0
for i in range(1, 100):
    total += i
print(total)
```

```python
# 覆盖累计值：真实输出应为 100
total = 0
for i in range(1, 101):
    total = i
print(total)
```
