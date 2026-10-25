# K-12 Python 闯关学习游戏 · AI 技术选型报告
**（约束已修正：单卡 RTX 5060 Laptop / 8 GB 显存 / 数据不出校园网 / 零 API 成本）**

---

## 0. 核实方法与局限声明（请先读）

本环境的 **`web_fetch` 工具完全不可用**——所有域名（含 huggingface.co、arxiv.org、docs.vllm.ai）均解析到非公网 IP `198.18.0.x`，被安全策略拒绝。因此我**只能使用 `web_search`**，只能拿到搜索结果的**标题与摘要片段**，无法打开官方 LICENSE 文件或 benchmark 表格逐条比对。

为遵守"不凭记忆编造"的要求，全文用以下标记：

| 标记 | 含义 |
|---|---|
| ✅**已检索命中** | 该事实在搜索返回的**标题/摘要片段**中直接出现过 |
| ⚠️**未核实** | 我有较高把握但**未能从任何来源确认**，属推断或记忆，**必须由你最终核实** |
| 💡**我的推断** | 基于前述事实的工程推理，非来源引用 |

**最重要的一条建议**：许可证部分涉及比赛的"自主知识产权/合法授权"硬性要求，请在落地前用 10 分钟逐条打开官方 LICENSE 原文核对（下文每条都给了官方链接）。

---

## 1. 硬件重估：8 GB 显存改变了一切

| 项 | 实测值 | 影响 |
|---|---|---|
| GPU | RTX 5060 Laptop，8151 MiB | Blackwell，晶片 GB206 ✅[已检索命中](https://www.overclockers.ua/ua/notebook/msi-crosshair-16-hx-ai-d2xwfkg/all/) |
| 可用显存 | 空闲 6967 MiB（≈6.8 GB） | 扣掉 CUDA context 与显示合成，**模型预算实际约 6.0–6.3 GB** 💡 |
| 架构 | Blackwell = **sm_120**（compute capability 12.0） | 非 Hopper/Ada，**软件栈必须为 sm_120 单独编译** |
| 带宽 | ⚠️未核实：128-bit GDDR7，约 384 GB/s（[TechPowerUp 规格页](https://www.techpowerup.com/gpu-specs/geforce-rtx-5060-mobile.c4230)） | 决定 token 生成速度上限 |

### 1.1 结论先行
- **14B 必须从主推荐中移除**：Qwen2.5-Coder-14B 的 Q4_K_M 约 9 GB，DeepSeek-Coder-V2-Lite 约 9.5–10 GB，**均超过 6.3 GB 预算**，只能靠 CPU offload，速度不可用。
- **vLLM 在本机基本不可用**（原因见 §3.1），主推理引擎应选 **llama.cpp**。

### 1.2 Blackwell / sm_120 兼容性坑（真实存在）
| 问题 | 证据 | 对策 |
|---|---|---|
| 旧 PyTorch（cu124 及以下）报 `no kernel image is available for execution on the device` | ✅[FramePack #722 (RTX 5080, sm_120)](https://github.com/lllyasviel/FramePack/issues/722) | 必须 **CUDA 12.8+ / torch cu128** |
| llama.cpp 在 RTX 5060 (sm_120) 上服务初始化静默崩溃 | ✅[llama.cpp Issue #26205](https://github.com/ggml-org/llama.cpp/issues/26205) | 不要用普通 CUDA 12.4 预编译包，需 Blackwell build 或自行以 CUDA 12.8+ 编译 |
| vLLM 在 RTX 50 系上需特定组合 | ✅[vLLM 论坛：RTX 5090 + torch 2.9.0 cu128 可用配置](https://discuss.vllm.ai/t/vllm-on-rtx5090-working-gpu-setup-with-torch-2-9-0-cu128/1492)、✅[vLLM Issue #38869](https://github.com/vllm-project/vllm/issues/38869) | 版本组合需锁定，不可追新 |
| Unsloth / bitsandbytes 4-bit 内核在 Blackwell 上有兼容问题 | ✅[Unsloth Issue #1679 "Compatibility with Blackwell"](https://github.com/unslothai/unsloth/issues/1679) | 微调建议在 WSL2 + cu128 下做，或移到云端 |

💡**我的推断**：本项目最大的工程风险不是模型选型，而是 **sm_120 生态尚不成熟**。建议第一步只做一件事：**用 llama.cpp 跑通 Qwen2.5-Coder-1.5B GGUF，确认 GPU 生效（`n_gpu_layers` 全部加载）**，再往上加模型。

---

## 2. 候选模型对比

### 2.1 许可协议（比赛硬约束，逐条给官方链接）

| 模型 | 许可 | 能否商用 | 8 GB 可行性 | 核实状态 |
|---|---|---|---|---|
| **Qwen2.5-Coder-7B-Instruct** | Apache-2.0 | ✅**可** | ✅ Q4_K_M ≈4.7 GB | ✅ 摘要命中 `license: apache-2.0`（[HF](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct)） |
| **Qwen2.5-Coder-1.5B-Instruct** | Apache-2.0 | ✅**可** | ✅ 极轻松 ≈1.0 GB | ✅ 摘要命中 `license: apache-2.0`（[HF](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct)） |
| Qwen2.5-Coder-14B / 32B | Apache-2.0 | ✅可 | ❌ 14B 装不下 | ⚠️未核实（同族，预期 Apache-2.0，[14B HF](https://huggingface.co/Qwen/Qwen2.5-Coder-14B)） |
| ⚠️**Qwen2.5-Coder-3B-Instruct** | **Qwen Research License** | ❌**疑似不可商用** | ✅ 显存合适 | ⚠️**重要陷阱**：搜索结果中该模型的镜像 README 元数据为 `license: other`，而非 `apache-2.0`（[QuantFactory 镜像](https://modelscope.cn/models/QuantFactory/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/master/README.md)），且 "Qwen RESEARCH LICENSE AGREEMENT" 确为真实存在的协议名（[示例 LICENSE](https://huggingface.co/Vilyam888/Broken_Code_Generation.1.0/blob/aa988a7bb052eb977828bdc8e8625e2edbc9c831/LICENSE)）。**结论：3B 不要用于商用/比赛，请务必打开 [Qwen/Qwen2.5-Coder-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct) 的 LICENSE 亲自确认。** |
| Qwen2.5-7B / 14B-Instruct | Apache-2.0（7B/14B） | ✅可 | 7B ✅ / 14B ❌ | ⚠️未核实 |
| DeepSeek-Coder-V2-Lite-Instruct (16B MoE) | DeepSeek Model License (`deepseek-la-1.0`) | ⚠️**有限制** | ❌ ≈9.5–10 GB 装不下 | ✅ 许可实体存在：[LicenseDB deepseek-la-1.0](https://scancode-licensedb.aboutcode.org/deepseek-la-1.0.html)、[DeepSeek License FAQ](https://deepseeklicense.github.io/)。**具体条款（是否要求衍生物命名含 "DeepSeek"、输出不得用于训练其他模型）⚠️我未能读到原文，需你核实** |
| GLM-4-9B-Chat | 自定义 GLM-4 协议 | ⚠️**可能需商业授权** | ❌ 9B Q4 ≈5.7 GB，勉强但偏挤 | ✅ 智谱开放平台存在独立的[「商业授权申请」页](https://docs.bigmodel.cn/cn/faq/business-authorization)；其 LICENSE 文件 6511 字节（长篇自定义协议，非 Apache 短头，[HF](https://huggingface.co/zai-org/glm-4-9b-chat)）。**结论：走商用授权流程才有保障，不建议比赛用** |
| Codestral-22B-v0.1 | Mistral AI **Non-Production** License (MNPL) | ❌**不可商用/不可生产** | ❌ 装不下 | ⚠️未核实（MNPL 是 Mistral 对 Codestral 的公开定位；[HF](https://huggingface.co/mistralai/Codestral-22B-v0.1)）。**名称即含 Non-Production，直接排除** |
| CodeLlama-7B/13B-Instruct | Llama 2 Community License | ⚠️可商用，但有 7 亿 MAU 门槛与命名/署名要求 | 7B ✅ | ⚠️未核实（[Llama 2 许可页](https://mintlify.wiki/meta-llama/llama/resources/license)）。**能力已明显落后，不推荐** |
| StarCoder2-15B(-Instruct) | BigCode OpenRAIL-M | ⚠️可商用，但带 Attachment A **使用限制**条款 | ❌ 15B Q4 ≈9 GB | ⚠️未核实（[HF](https://huggingface.co/bigcode/starcoder2-15b)） |
| Yi-Coder-9B-Chat | Apache-2.0 | ✅可 | ❌ 9B Q4 ≈5.7 GB，偏挤 | ⚠️未核实（[HF](https://huggingface.co/01-ai/Yi-Coder-9B-Chat)） |

**许可结论**：在 8 GB 这条约束下，**唯一同时满足「Apache-2.0 明确可商用 + 显存装得下」的合格选项，是 Qwen2.5-Coder 的 7B 与 1.5B**。这大大简化了选型。

### 2.2 基准分数（诚实版）

我**无法**逐条核实 HumanEval/MBPP/LiveCodeBench 数字，**不会凭记忆填表**。以下是检索中**真实出现**的片段与官方核对入口：

| 模型 | 检索到的分数 | 来源 |
|---|---|---|
| Yi-Coder-9B-Chat | `9B \| 85.4 (74.4) \| 59.8 \| 64.0 \| 81.5 (69.3) \| 64.8 \| 71.7` | ✅ [ar5iv 2412.21199](https://ar5iv.labs.arxiv.org/html/2412.21199)（HumanEval Pro/MBPP Pro 论文表） |
| Qwen2.5-Coder-14B | 摘要原文："Qwen2.5-Coder-14B achieves **higher absolute scores than Qwen3-30B-A3B**" | ✅ [arXiv 2511.18538](https://arxiv.org/pdf/2511.18538) |
| Qwen2.5-Coder-32B | 官方宣称 HumanEval 92.7 / 比肩 GPT-4 | ✅ 媒体命中（[VentureBeat](https://venturebeat.com/ai/alibaba-new-ai-can-code-in-92-languages-and-its-completely-free)），**具体分数表请核对 [Qwen 官方博客](https://qwenlm.github.io/blog/qwen2.5-coder-family/)** ⚠️ |
| 其余模型全部分数 | — | ⚠️**未核实，我不填**。请以各模型 HF 模型卡 / 原论文为准 |

💡**我的推断**：对本项目而言，HumanEval 分数**几乎不重要**。原因见 §4：判题决策不交给模型。真正重要的是**中文话术质量**与**结构化输出遵循率**，而这两项**没有任何公开 benchmark 能回答**，只能靠你自己的 50 条抽样人工评测。

### 2.3 显存测算（公式 + 真实架构参数）

```
权重显存 = 参数量 × 每参数字节(FP16=2 / INT8=1 / INT4≈0.5~0.6)
KV cache = 2 × L(层数) × H_kv(KV头数) × d_head × 序列长度 × 并发数 × dtype字节
```

Qwen2.5 架构参数（✅ Qwen2.5-14B 的 `n_layers=48, hidden_size=5120` 已从[架构数据集](https://huggingface.co/datasets/AwaisAdilKhokhar/modeldna-atlas)摘要命中确认；其余 ⚠️按公开架构，请核对各模型 `config.json`）：

| 模型 | L | H_kv | d_head | **KV/ token (FP16)** | 8K ctx | 16K ctx | 32K ctx |
|---|---|---|---|---|---|---|---|
| Qwen2.5-Coder-1.5B | 28 | 2 | 128 | 28 KiB | 224 MiB | 448 MiB | 896 MiB |
| Qwen2.5-Coder-3B | 36 | 2 | 128 | 36 KiB | 288 MiB | 576 MiB | 1.15 GiB |
| **Qwen2.5-Coder-7B** | 28 | 4 | 128 | **56 KiB** | **448 MiB** | 896 MiB | 1.75 GiB |
| Qwen2.5-Coder-14B | 48 | 8 | 128 | 192 KiB | 1.5 GiB | 3.0 GiB | 6.0 GiB |
| Qwen2.5-Coder-32B | 64 | 8 | 128 | 256 KiB | 2.0 GiB | 4.0 GiB | 8.0 GiB |

**关键洞察**：Qwen2.5 全系使用 **GQA**（KV 头数远少于注意力头数），KV cache 极小。**7B 在 8K 上下文下 KV 仅 448 MiB**——瓶颈是**权重**，不是 KV。这决定了优化方向：**压权重（量化）比压上下文更有效**（但 llama.cpp 的 `--cache-type-k q8_0` 仍能再砍一半 KV，值得开）。

### 2.4 8 GB 总显存需求表

| 模型 | FP16 | INT8/Q8_0 | INT4/Q4_K_M | 8 GB 判定（预算 6.0–6.3 GB） |
|---|---|---|---|---|
| Qwen2.5-Coder-1.5B | 3.1 GB | 1.7 GB | **1.0 GB** | ✅ 舒适（可 32K ctx + 高并发） |
| Qwen2.5-Coder-3B | 6.2 GB | 3.3 GB | **1.9 GB** | ✅ 显存 OK，但 ❌**许可存疑** |
| **Qwen2.5-Coder-7B** | 15.2 GB ❌ | 8.1 GB ❌ | **4.7 GB** | ⚠️ **可行但紧**：4.7 + 0.45(KV 8K) + ~0.6(CUDA/activation) ≈ **5.75 GB**，余量约 0.5 GB |
| Qwen2.5-Coder-14B | 29.5 GB ❌ | 15.7 GB ❌ | 9.0 GB ❌ | ❌ **不可行**（除非 CPU offload） |
| DeepSeek-Coder-V2-Lite | ~31 GB ❌ | 16 GB ❌ | ~9.5 GB ❌ | ❌ **不可行** |

---

## 3. 部署方案

### 3.1 推理引擎对比（按 8 GB 单机场景重排）

| 引擎 | 官方定位 | 8 GB 适配 | 结构化输出 | LoRA 热加载 | 结论 |
|---|---|---|---|---|---|
| **llama.cpp** | 极致低资源、GGUF、CPU/GPU 混合 | ✅**最佳**：可精确控制 `n_gpu_layers`、KV 量化、显存指纹小 | ✅ **GBNF 语法** + JSON Schema（[官方 Grammars 文档](https://mintlify.wiki/ggml-org/llama.cpp/advanced/grammars)），另支持 llguidance | ⚠️需合并或运行时加载 | ✅ **主选** |
| Ollama | 开箱即用、llama.cpp 封装 | ✅ 可用 | ✅ [Structured Outputs 官方文档](https://docs.ollama.com/capabilities/structured-outputs)（支持 JSON Schema） | ✅ | ✅ 开发期用，生产换 llama-server |
| vLLM | 高吞吐服务化、PagedAttention | ❌ **不推荐**：为高并发设计，额外开销大，8 GB 下极易 OOM（[社区讨论](https://markaicode.com/usecases/vllm-use-cases-production-workflows/)）；且 sm_120 组合脆弱 | ✅ [Structured Outputs 文档](https://docs.vllm.ai/en/v0.14.1/api/vllm/config/structured_outputs/)，**xgrammar 已设为默认后端** ✅[PR #10785](https://github.com/vllm-project/vllm/pull/10785) | ✅ [LoRA 适配器文档](https://docs.vllm.com.cn/en/latest/features/lora/) | ❌ 本机不用；**若未来换 24 GB 卡则首选** |
| SGLang | 前缀缓存（RadixAttention）为王 | ❌ 同理偏重 | ✅ 支持 json_schema/regex | ✅ | ❌ 本机不用 |
| LMDeploy | InternLM 系、TurboMind 引擎 | ❌ | ✅ | ✅ | ❌ 生态偏向国产服务端，[吞吐 benchmark 文档](https://lmdeploy.readthedocs.io/zh-cn/v0.7.0.post1/benchmark/profile_throughput.html) |
| TGI | HF 官方、企业级 | ❌ 重 | ✅ | ✅ | ❌ |

💡**我的推断**：你的场景是**单机、低并发、需要结构化输出**——这正是 llama.cpp 的主场，而不是 vLLM 的。vLLM 的价值在几十路并发，8 GB 显存下你根本没有那个并发预算。

### 3.2 消费级单卡跑 7B 并保持可用吞吐

**7B Q4_K_M 推荐配置（llama-server）**：

```
--model qwen2.5-coder-7b-instruct-q4_k_m.gguf
--n-gpu-layers 99          # 全量上卡
--ctx-size 8192            # 上限；不要开 32K
--cache-type-k q8_0 --cache-type-v q8_0   # KV 448→224 MiB，关键技巧
--parallel 2               # 并发槽位，KV 按槽位复制
--flash-attn               # 若 sm_120 支持良好则开启
--jinja                    # 启用 JSON Schema 约束输出
```

显存账：4.7（权重）+ 0.22（KV 8K×2槽 q8）+ ≈0.8（CUDA context/激活/compute buffer）≈ **5.7 GB**，留 ~0.5 GB 余量。

**吞吐推算**（💡推断，基于"理论上限 = 带宽 ÷ 每 token 读取量"）：

| 模型 / 量化 | 权重/token | 理论上限 @384 GB/s | 实测预期（×45–65% 效率） |
|---|---|---|---|
| 7B Q4_K_M | 4.7 GB | ~82 tok/s | **35–55 tok/s** |
| 3B Q4_K_M | 1.9 GB | ~202 tok/s | 90–130 tok/s |
| 1.5B Q4_K_M | 1.0 GB | ~384 tok/s | 150–230 tok/s |

**判题场景延迟预算**（输入 ≈1.2K token，输出 ≈250 token JSON）：
- **7B Q4**：prefill ~1.2 s + decode 250/45 ≈ 5.5 s → **单题约 6–7 s**
- **1.5B Q4**：prefill ~0.5 s + decode 250/180 ≈ 1.4 s → **单题约 2 s**
- 一个 40 人班级同时提交：7B 双槽约 **2–3 分钟**，1.5B 约 **40 秒**。
- ✅ 若配合 §4 的规则层拦截（预计 60–80% 的提交在规则层就得到判定，无需调模型），实际模型调用量可再降一个量级。

### 3.3 CPU offload 的真实代价

| 场景 | 推算速度 | 说明 |
|---|---|---|
| 7B Q4 全 GPU | 35–55 tok/s | ✅ 可用 |
| 7B Q4，约 20% 层在 CPU | 15–25 tok/s | ⚠️ 勉强 |
| 14B Q4，全 GPU 放不下，约 30% 层在 CPU | 6–12 tok/s | ❌ 单题要 20–40 s，不可接受 |
| 14B Q4 纯 CPU（32 线程 DDR5） | 2–5 tok/s | ❌ 教学场景不可用 |

💡**我的推断**（未检索到本机型实测数据，⚠️请你用 `llama-bench` 实测校准）。llama.cpp 存在 offload 层数与速度的非线性关系，建议参考社区的分层扫描方法。

### 3.4 结构化输出方案

| 方案 | 适用 | 在 llama.cpp / vLLM 上怎么用 |
|---|---|---|
| **GBNF 语法** | llama.cpp 原生 | 手写或由 JSON Schema 转换；**最可控、零额外依赖** |
| llguidance | llama.cpp 新支持 | 比 GBNF 更强的 JSON Schema 约束 |
| **JSON Schema (`--jinja` / `response_format`)** | llama.cpp server / Ollama | 直接传 `{"type":"json_object","schema":{...}}`，**首选** |
| XGrammar | vLLM 默认后端 ✅ | `GuidedDecodingConfig(backend="xgrammar")` |
| Outlines | 独立库 | 可挂 xgrammar 后端（[文档](https://dottxt-ai.github.io/outlines/1.2.2/api_reference/backends/xgrammar/)） |
| Function calling | 生态成熟度不一 | ⚠️ 小模型上不稳定，不推荐 |

**工程铁律**：约束解码保证**语法合法**，**不保证语义正确**。必须叠加：
1. **Pydantic 侧校验**（枚举值域、字段长度、`confidence` 阈值）
2. **失败重试 ≤2 次**，仍失败则降级为**模板化输出**（不调模型）
3. 记录 `schema_violation` 指标，作为模型/量化选型的实测依据

### 3.5 从零部署路径（Python 3.14.4 + Docker + 无任何现成引擎）

**这是一个关键的好消息**：`llama-server` 是**独立的 C++ 可执行文件**，**完全不依赖 Python**。因此系统 Python 3.14.4 对推理链路**零影响**——你只需让 FastAPI 后端通过 HTTP 调它（你项目里 `backend/app/api/ai.py` 已经在用 `httpx` 调 `http://172.23.46.241:8000/v1/chat/completions`，改个地址即可）。

但 **Python 3.14 会阻断所有"Python 侧的 GPU 路径"**：

| 路径 | Python 3.14 影响 | 证据 |
|---|---|---|
| `llama-server`（C++/CUDA） | ✅ **无影响** | — |
| `llama-cpp-python` | ❌ 无 CUDA + sm_120 预编译轮子，需源码编译，3.14 下大概率失败 | ⚠️推断 |
| **PyTorch (CUDA)** | ❌ **PyTorch 在 Python 3.14 上没有 CUDA/GPU 轮子，只装得上 CPU 版** | ✅[pytorch#169929 "Python 3.14 – No CUDA/GPU Wheels Available (Only CPU Build Installed)"](https://github.com/pytorch/pytorch/issues/169929)、✅[pytorch#156856 "Python 3.14 support for PyTorch"](https://github.com/pytorch/pytorch/issues/156856) |
| vLLM / transformers+torch / Unsloth / LLaMA-Factory | ❌ 全部依赖 PyTorch，被上一条连带阻断 | 💡推断 |

**推荐的三段式环境隔离**：

| 用途 | 环境 | 说明 |
|---|---|---|
| **① 推理服务** | **Docker + CUDA 12.8+ 镜像**，跑 `ghcr.io/ggml-org/llama.cpp:server-cuda`（[官方 Docker 部署文档](https://mintlify.wiki/ggml-org/llama.cpp/advanced/docker)） | ✅ **最稳路径**。GPU 直通需 WSL2 后端 + NVIDIA Container Toolkit + ≥ 支持 Blackwell 的驱动。**彻底绕开 Python 3.14** |
| **② 后端胶水（FastAPI）** | 系统 Python 3.14 venv | 只需 `fastapi` / `httpx` / `pydantic` / `sqlalchemy`。⚠️ `pydantic-core`（Rust 扩展）在 3.14 上的轮子可能滞后，若安装失败，**降级到 Python 3.12 venv**，不要迁就 |
| **③ 微调（可选，非必须）** | **另一个 Docker 镜像**：Python 3.11/3.12 + cu128 + Unsloth/LLaMA-Factory | ❌ **绝不要在系统 Python 3.14 上做微调**，必失败 |

**先做这一件事验证全链路**（预计 1–2 小时，风险前置）：

```bash
# 1) 拉镜像并确认 GPU 可见
docker run --rm --gpus all ghcr.io/ggml-org/llama.cpp:server-cuda --list-devices
# 2) 起 1.5B 服务，确认 sm_120 上满层加载不崩溃
docker run --rm --gpus all -p 8080:8080 -v $PWD/models:/models \
  ghcr.io/ggml-org/llama.cpp:server-cuda \
  -m /models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
  --n-gpu-layers 99 --ctx-size 8192 --jinja --host 0.0.0.0
# 3) 检查日志里 offloaded 层数是否 = 总层数（未被静默降级到 CPU）
```

若第 1 步 `--list-devices` 看不到 GPU，或第 2 步出现 [llama.cpp #26205](https://github.com/ggml-org/llama.cpp/issues/26205) 的静默崩溃，**不要继续往上堆模型**，先换镜像/驱动版本——这就是本项目最大的单点风险。

---

## 4. 关键技术问题

### 4.1 幻觉控制：让 LLM **永远不做判题决策**

核心原则有明确的业界依据：**"LLM-as-a-Judge is not an oracle"** ✅[arXiv 2609.02246](https://export.arxiv.org/pdf/2609.02246)，以及 **"Deterministic by default: Bounding the LLM judge"** ✅[PeerJ](https://peerj.com/reviewer-match/143678)。把 LLM 当作**生成器**而非**裁判**。

四种"用执行结果/规则校验 LLM 输出"的成熟模式：

| 模式 | 做法 | 在本项目的落地 |
|---|---|---|
| ① **执行优先（Execution-first）** | 先跑测试用例，结果直接决定对错；LLM 无权推翻 | ✅ **主模式**。同时用**多组用例含边界**判定"行为等价"，而非输出字符串相等 |
| ② **结构化校验（Output conformance）** | 约束解码 + Schema 校验 + 值域白名单 | ✅ 错因只能取自**预定义 taxonomy 枚举**，禁止自由文本当结论 |
| ③ **证据锚定（Evidence-constrained）** | 强制模型引用学生代码的**行号**作为证据；行号不存在则该输出作废 | ✅ 已被用于编程教育反馈生成 ✅[arXiv 2609.29874](https://browse-export.arxiv.org/pdf/2609.29874) |
| ④ **交叉验证（Self-consistency / 小模型评审）** | 同一输入跑 3 次取多数；或用另一个小模型评审 | ⚠️ 8 GB 下算力紧张，仅对 `confidence < 0.6` 的样本启用 |

**防"把对的判成错的"（假阴性）**：这是教学产品最致命的错误。做法是**不对称设计**——规则层判定"通过"时直接通过，**不送模型复核**；只有规则层判定"不通过"或"无法归类"时才调模型，且模型输出**永远不能把"不通过"翻转为"通过"**，只能补充解释与提示。💡我的推断：这一条能消除绝大部分假阴性风险。

### 4.2 混合架构：规则优先、模型兜底

参考实现：**CodeHelp**（"Using Large Language Models with **Guardrails** for Scalable Support in Programming Classes"）✅[论文](https://papers.lunadong.com/paper/8333)——这正是"LLM + 教学护栏"的公开范式。

```
学生提交代码
   │
   ├─ L0 确定性层（已有基础！）
   │    1. ast.parse() → SyntaxError 精确行列 + error_helper 归类
   │       （你项目里 backend/app/services/sandbox/error_helper.py 已实现正则级错误→人话映射）
   │    2. sandbox 执行公开用例 + 隐藏用例（sandbox.py 已存在）
   │    3. AST 归一化指纹：变量重命名 + 常量折叠 + 结构哈希
   │       → 与参考解等价类比对 ⇒ 接受多种正确写法（语义判题的关键）
   │    4. 代码特征抽取（循环类型/range 参数/边界判断/缩进）
   │       → 规则匹配已知错因模式（如"range(n) 少算一次"）
   │
   ├─ 命中且高置信 ──→ 直接返回（预计 60–80% 提交在此结束，零延迟零显存）
   │
   └─ 未命中 / 执行失败无法归类 / 行为不等价但语义模糊
         │
         └─ L1 小模型语义诊断（唯一调模型的地方）
              输入：学生代码 + AST 摘要 + 用例 diff + 规则层候选错因
              输出（约束解码 JSON）：
              { "错因类别": <taxonomy枚举>,
                "证据行": [int],
                "思维误区": "str(≤80字, 面向少儿)",
                "提示": {"L1":"str","L2":"str","L3":"str"},
                "confidence": float }
              后置：Schema 校验 → 行号存在性校验 → 枚举合法性校验 → 通过才返回

   L2 变式题生成：低频、离线批量生成 + 教师审核后入库（不进实时链路）
```

**为什么这套架构在 8 GB 下特别正确**：模型只负责"措辞 + 已定义类别的映射"，这是**最不需要大参数量**的子任务。它把 7B/14B 的差距压缩到了最小，也让你可以放心用 Q4 量化。

### 4.3 提示词工程：防止直接给答案

```
【System】
你是少儿 Python 编程助教，服务 8–14 岁学生。当前任务：根据给定的【学生代码】【执行结果】
【规则层候选错因】，输出诊断与分级提示。

绝对禁止：
- 禁止输出完整可运行的正确代码；禁止输出超过 3 行连续代码
- 禁止直接说出最终答案或完整算法步骤
- 禁止在 L1 提示中透露 L2/L3 的内容
- 禁止批评学生（禁止"这么简单都不会"类表述）

提示分级规则：
- L1 指向：只指出"哪一行/哪个概念"可疑，不给修法
- L2 思路：给出思考方向（如"想一想 range 的两个参数分别代表什么"），仍不给代码
- L3 示例：可给一个**同构但不同题**的最小示例，绝不给本题答案

输出：严格按 JSON Schema，不得输出任何 JSON 之外的内容。
```

配套工程手段：**输出侧正则守卫**——若返回文本中检出 `def `、`for `、`print(` 等代码块且长度超阈值，直接丢弃重试；重试仍失败则降级为模板文案。

### 4.4 分级提示的学术依据

✅[CHI 2024: "Exploring How Multiple Levels of GPT-Generated Programming Hints Support or Disappoint Novices"](https://dlnext.acm.org/doi/pdf/10.1145/3613905.3650937) 直接研究了 GPT 生成的多级提示对新手的效果；另有 ✅[Aalto: "Appealing to Expert Judgement for Evaluating Human and AI Next-Step Hints"](https://research.aalto.fi/files/197673638/Howzat_Appealing_to_Expert_Judgement_for_Evaluating_Human_and_AI_Next-Step_Hints_for_Novice_Programmers.pdf)。**建议把这两篇的评测量表直接借来，作为你比赛答辩时的效果评估方法学。**

---

## 5. 微调是否有必要（8 GB 现实版）

### 5.1 结论
**分两阶段，不要一上来就微调。**

| 阶段 | 做法 | 理由 |
|---|---|---|
| **阶段 1（现在）** | ❌ 不微调。规则层 + 7B Q4 + few-shot + 强 Schema | 你**还没有标注数据**；且 sm_120 微调生态不成熟，容易卡在环境上浪费比赛时间 |
| **阶段 2（积累 1000+ 条后）** | ✅ 微调 **1.5B** 专做"诊断+提示措辞"，把 7B 降为可选 | 微调的甜区是**格式/话术/领域术语**，不是推理 |

### 5.2 小模型微调能否超过通用 7B 零样本？

💡**我的推断**：**在"格式遵循 + 既定错因分类映射 + 少儿话术"这三件事上，能超过；在"理解新写法背后的思维误区"上，不能。**

依据：✅[LoRA Learns Less and Forgets Less (arXiv 2405.09673)](https://huggingface.co/papers/2405.09673) 的结论是 LoRA 在**领域/风格适应**上接近全参微调，但在需要**习得新知识或新推理**的任务上明显落后于全参微调——即"窄任务行为克隆"正是 LoRA 的甜区，而"泛化推理"不是。（⚠️我未能打开原文，此为摘要级理解，请你核对。）

**因此**：1.5B 微调版是 7B 的**降本替代**（延迟 6 s→2 s，显存 5.7 GB→2.5 GB，话术一致性提升），**不是能力替代**。规则层与人工兜底队列必须保留。

### 5.3 数据量需求

| 数据量 | 能做到 | 不能做到 |
|---|---|---|
| 100–300 | 输出格式稳定、话术风格对齐 | 错因分类不可用 |
| **500–1500** | ✅ **推荐起点**：覆盖 15–25 类错因、每类 30–60 条 | 长尾/复合错误 |
| 3000–5000 | 分类稳定、可做 confidence 校准 | — |
| 10000+ | 边际收益递减 | — |

关键：**先定 taxonomy（15–25 个错因类别），再按类采样**，而不是盲目堆量。✅[LIMA: "Less Is More for Alignment" (arXiv 2305.11206)](https://arxiv.org/abs/2305.11206) 支持"1000 条精标即可对齐风格"。

### 5.4 数据来源（★这是"自主知识产权"的关键）

| 来源 | 评价 |
|---|---|
| **你自己的闯关系统累积的学生提交 + 教师标注** | ✅✅**最优**。完全自有 IP，分布完美匹配 |
| **规则层合成**：在正确解上做 AST 层错误注入（off-by-one、缩进、类型、边界、变量名混淆） | ✅✅**强烈推荐**。自动生成、零版权风险、可无限扩充。你已有的 `error_helper.py` 错误分类就是天然的标注 schema |
| PyBugHive（人工验证的可复现 Python bug 库） | ⚠️[论文 PDF](http://publicatio.bibl.u-szeged.hu/36181/1/PyBugHive_A_Comprehensive_Database_of_Manually_Validated_Reproducible_Python_Bugs.pdf)；是**真实项目 bug**，非 K-12 学生错误，分布差异大，只适合预热 |
| BugsInPy（493 个真实缺陷 / 17 个开源项目） | ✅[来源片段](https://cbsoft.sbc.org.br/2026/data/papers/sast/LLM-Pyro%20LLM-Based%20Mutation%20Testing%20with%20Equivalence%20Triage%20for%20Python.pdf)；同上，分布不匹配 |
| Defects4J | Java，不适配 |
| **闭源大模型蒸馏数据** | ❌**风险高**：可能违反服务条款，且对"自主知识产权"主张不利。**建议避免** |

### 5.5 工具链与 8 GB 可行性

| 工具 | 8 GB QLoRA 可行性 | 说明 |
|---|---|---|
| **Unsloth** | ✅ 最省显存，8 GB 首选 | ⚠️[Blackwell 兼容 Issue #1679](https://github.com/unslothai/unsloth/issues/1679) 需注意 |
| **LLaMA-Factory** | ✅ 可用，WebUI 友好 | 导出 GGUF 需额外步骤；[GitHub](https://github.com/hiyouga/LLaMA-Factory) |
| Axolotl | ⚠️ 偏重，配置复杂 | 不优先 |
| peft + trl | ⚠️ 最灵活但需自己写脚本 | 有经验可选 |

**显存测算**（💡推断）：

| 微调目标 | 组成 | 合计 | 判定 |
|---|---|---|---|
| **1.5B QLoRA** | 4bit 权重 1.0 + LoRA ~0.05 + 8bit AdamW ~0.1 + 激活(seq 2048, bs 1, gradient checkpointing) ~1.5–2.5 | **≈3–4 GB** | ✅ **舒适可行** |
| **7B QLoRA** | 4bit 权重 4.7 + 激活 ~1.5–2.0 | **≈6.2–6.7 GB** | ⚠️ **极限**：需 seq ≤1024、bs=1、gradient checkpointing、paged 8bit AdamW，**很可能 OOM** |
| 14B QLoRA | — | >10 GB | ❌ 不可行 |

💡**我的建议**：**7B 的微调放到云端/借卡上做一次，导出 GGUF 回本地只做推理**；本地只微调 1.5B。这样既绕开 sm_120 训练生态的坑，也不占用比赛机。

---

## 6. 最终推荐

### 6.1 主方案

| 维度 | 选择 | 理由 |
|---|---|---|
| **模型** | **Qwen2.5-Coder-7B-Instruct** | ✅ Apache-2.0 明确可商用；中文+代码双语强；唯一在 8 GB 下"装得下且许可干净"的 7B 级代码模型 |
| **量化** | **GGUF Q4_K_M**（备选 IQ4_XS 更省） | 4.7 GB，留 0.5 GB 余量；Q5_K_M 需 5.5 GB，几乎不留余量给 KV，不推荐 |
| **推理引擎** | **llama.cpp `llama-server`**（CUDA 12.8+ 编译的 Blackwell build） | 8 GB 下唯一舒适的引擎；vLLM 直接排除 |
| **结构化输出** | **JSON Schema 约束解码（`--jinja`）+ Pydantic 二次校验 + 最多 2 次重试 + 模板兜底** | 语法层与语义层双重保险 |
| **上下文** | 8192，KV cache `q8_0`，并发槽 2 | 显存测算见 §3.2 |
| **判题决策权** | **不在模型**，由 AST 归一化指纹 + 多用例执行 + 规则层决定 | 从架构上消除判题幻觉 |
| **LLM 职责** | 仅：错因归类（枚举）+ 证据行 + 少儿话术 + 三级提示 | 与 8 GB 算力相匹配 |

**风险清单**：

| 风险 | 等级 | 缓解 |
|---|---|---|
| sm_120 生态不成熟，编译/内核崩溃 | 🔴 高 | 锁定已知可用版本组合；先在 1.5B 上验证 GPU 生效再放大；参考[llama.cpp #26205](https://github.com/ggml-org/llama.cpp/issues/26205) 与 [vLLM 5090 可用配置](https://discuss.vllm.ai/t/vllm-on-rtx5090-working-gpu-setup-with-torch-2-9-0-cu128/1492) |
| **系统 Python 3.14 无 PyTorch CUDA 轮子**，阻断全部 Python GPU 路径 | 🔴 高 | 推理走 **Docker + llama-server**（不依赖 Python）；胶水层用 3.12 venv；微调单独用 3.11/3.12 镜像 |
| Q4 量化损失精细推理能力 | 🟡 中 | 模型不做决策，风险被架构吸收 |
| 7B Q4 在 8 K ctx 下显存余量仅 0.5 GB | 🟡 中 | 开 KV q8_0；`--parallel 1` 保底；实测调参 |
| 许可核实不充分（见 §2.1 标记） | 🔴 高 | **落地前逐条打开官方 LICENSE 核对** |
| 3B 许可陷阱（Research License） | 🟡 中 | **不使用 3B**，直接 7B / 1.5B |
| 冷启动延迟影响体验 | 🟢 低 | 规则层拦截大部分提交；模型侧保留常驻进程 |

### 6.2 降级 / 升级方案

| 显存 | 方案 | 预期解码速度 |
|---|---|---|
| **12 GB** | ✅**升级**：Qwen2.5-Coder-14B Q4_K_M（9 GB）+ ctx 4096 + KV q8_0。**这是 14B 唯一可行的姿势** | 15–25 tok/s |
| **8 GB（你现在）** | Qwen2.5-Coder-7B Q4_K_M + ctx 8192 + KV q8_0 | 35–55 tok/s |
| **6 GB** | Qwen2.5-Coder-**1.5B** Q8_0（1.7 GB）+ ctx 16384；或 7B IQ3_XXS（≈3.3 GB，质量下降明显）⚠️**不要退到 3B——许可问题** | 100–200 tok/s |
| **4 GB** | Qwen2.5-Coder-1.5B Q4_K_M（1.0 GB）+ ctx 8192 + 单并发 | 150–230 tok/s |

### 6.3 落地路线（建议顺序）

1. **第 1 天**：**Docker + `ghcr.io/ggml-org/llama.cpp:server-cuda`** 跑通 Qwen2.5-Coder-1.5B GGUF，确认 sm_120 上 GPU 满层加载、`--jinja` JSON Schema 可用。**这是全部风险的前置条件。**（详见 §3.5）
2. **第 2–3 天**：补齐 L0 确定性层——AST 归一化指纹（多解接受）+ 隐藏用例执行 + 规则错因匹配表（扩展你已有的 `error_helper.py`）；定义 15–25 类错因 taxonomy。
3. **第 4–5 天**：换 7B Q4_K_M，实现 §4.2 的 L1 诊断链路 + Schema 校验 + 降级兜底；用 50 条真实学生代码做人工评测，测量**格式合规率**与**错因命中率**。
4. **持续**：用规则层批量合成错误样本（AST 注入）累积标注；数据过千后评估是否微调 1.5B 替换 7B（微调放 Docker + Python 3.12 镜像，**不要碰系统 3.14**）。

---

## 7. 附：我未能核实的事项（请务必自行确认）

1. ⚠️ 所有 model card 的**具体 benchmark 数值**（除 §2.2 列出的三条）——本环境 `web_fetch` 被封，无法打开表格。
2. ⚠️ **Qwen2.5-Coder-3B-Instruct 的确切许可**——仅从镜像元数据 `license: other` 推断为 Qwen Research License，**必须打开官方 LICENSE 确认**。
3. ⚠️ **DeepSeek Model License 的具体限制条款**（命名要求、输出使用限制）——仅确认了协议实体存在（`deepseek-la-1.0`）。
4. ⚠️ **GLM-4-9B-Chat 商用授权的具体条件与费用**——仅确认智谱存在商业授权申请入口。
5. ⚠️ **Codestral MNPL 的具体条款**、StarCoder2 OpenRAIL-M 的 Attachment A 限制清单。
6. ⚠️ **RTX 5060 Laptop 的确切显存带宽**（推断约 384 GB/s，来自 128-bit GDDR7 24 Gbps）。
7. ⚠️ **本机型的实际 tokens/s**——所有速度均为"带宽÷读取量"的理论推算，请用 `llama-bench` 实测校准。
8. ⚠️ **LoRA Learns Less and Forgets Less 的具体结论**——仅基于摘要级理解。
9. ⚠️ **`llama-cpp-python` 在 Python 3.14 + sm_120 下的可编译性**——推断为不可行；但**这不影响方案**，因为主路径用不依赖 Python 的 `llama-server`。
10. ⚠️ **`ghcr.io/ggml-org/llama.cpp:server-cuda` 镜像当前的 CUDA 版本是否已覆盖 sm_120**——请用 `--list-devices` 实测确认（§3.5 第一步）。
11. ⚠️ **Docker Desktop on Windows 的 WSL2 GPU 直通在当前驱动版本下对 Blackwell 的支持情况**——需实测。
