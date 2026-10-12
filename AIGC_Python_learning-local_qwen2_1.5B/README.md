# Ottly 本机演示版

## 启动

在 Windows 上先启动 Docker Desktop，然后双击 start-demo.bat。首次启动会下载并构建镜像，脚本会在本目录生成仅供本机使用的 .env，其中包含随机数据库密码和 JWT 密钥。页面地址是 http://127.0.0.1:3000。

双击 stop-demo.bat 可停止服务。数据库保存在 Docker 命名卷中，停止服务不会删除账号和聊天记录。不要把 .env 上传到 GitHub。

可在本目录运行 docker compose ps 查看服务，运行 docker compose logs backend 查看后端错误。

## 注册和登录

注册需要用户名、密码和手机号。登录后页面会验证令牌；聊天记录、职业选择记录和设置接口按当前登录账号隔离。当前未接入短信验证码，所以密码重置入口和接口已停用。请保存演示账号密码。

## AI 模型

本机演示使用 Ollama 运行 qwen2.5-coder:3b-instruct。先在 Windows 安装 Ollama，重新打开 PowerShell，再运行 `ollama pull qwen2.5-coder:3b-instruct`。模型权重保存在本机，不包含在仓库或 Docker 镜像中。

如果 Ollama 模型仓库下载失败，可从 [Qwen 官方 ModelScope 仓库](https://modelscope.cn/models/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF) 下载 3B Instruct 的 Q4_K_M GGUF 文件。复制本仓库 `ollama/Modelfile`，把 FROM 改成 GGUF 的实际绝对路径，再用该文件运行 `ollama create qwen2.5-coder:3b-instruct -f 你的Modelfile路径`。保留文件中的角色对话模板与 stop 参数，不要只写 FROM。当前本机已导入并配置此模板。导入后运行 `ollama list` 检查模型；已有同名模型可在本项目目录用 `ollama create qwen2.5-coder:3b-instruct -f ollama/Modelfile` 更新模板。该模型页面标注 Qwen Research License；使用或分发权重前请查看官方许可条款，商业用途需另行确认授权。

.env 中的 LOCAL_LLM_URL 默认设为 http://host.docker.internal:11434/api/chat，OLLAMA_MODEL 默认设为 qwen2.5-coder:3b-instruct。Docker 后端通过 host.docker.internal 访问 Windows 上的 Ollama。修改配置后运行 docker compose up --build -d。若模型服务未运行，AI 聊天会显示调用失败；其他页面仍可使用。

## 当前边界

本演示只监听本机 127.0.0.1:3000。运行与提交接口要求登录，复用原沙箱，在短生命周期子进程中执行；提交限 6000 字符、每用例 3 秒、输出上限 8000 字符。超时会终止执行进程，并明确标记输出未采集。此举解决卡死与输出串扰，并不构成针对恶意代码的操作系统安全隔离；目前只供团队本机演示。

两个现有关卡已支持“提交 → 后端测试判题 → 失败时 Qwen 分析 → 三级提示”。每题目前只有一个无输入 stdout 用例；判题不验证是否真正采用了 for 循环，硬编码正确输出也能通过。关卡列表的通关展示仍是原有静态内容，提交结果尚未做历史持久化。设置页面的护眼模式和语言暂存在当前浏览器，昵称按钮尚未保存到账号；错题库、逐步回放与 AI 出题不在本阶段范围。.env、Docker 命名卷和 AI 模型服务不在 Git 仓库内。

详细接口、文件职责、三种错误示例、错误处理和测试步骤见 [提交判题与三级提示说明](docs/submission-flow.md)。真实模型验收数据见 [live-submission.json](docs/live-submission.json)。

## 开发检查

在 backend 目录使用 Python 3.11 虚拟环境安装 requirements.txt 与 pytest，运行 `python -m pytest tests -q`。在 frontend 目录运行 `npm ci`、`node --test tests/submission-flow.test.cjs` 和 `npm run build`。演示版启动后，在 backend 目录运行 `python tests/live_submission_smoke.py --output ../docs/live-submission.json` 可通过真实 HTTP 接口验证四种错误代码和正确代码；脚本每次创建一个独立 smoke_ 测试账号，报告不保存密码和令牌。
