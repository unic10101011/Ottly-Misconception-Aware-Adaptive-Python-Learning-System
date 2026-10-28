# 面向 K-12 Python 闯关游戏的「AI 进核心闭环」技术调研报告

> 调研日期：2026-10。赛事背景：「中国移动杯」2026 江苏生成式人工智能创新大赛（生成式 AI 主题）；作品为 K-12 Python 编程闯关游戏，要求**校园私有化部署**。
> **部署硬约束：单卡 8GB 显存（RTX 5060 Laptop）。** 这直接决定模型选型：7B 级模型必须 4-bit 量化（AWQ/GPTQ/GGUF-Q4，权重约 4–5GB，加 KV cache 与上下文后可运行）；**14B 在 8GB 上不具备实用可行性（4-bit 权重已接近或超过 8GB，且无余量给 KV cache），本报告不再推荐 14B 路线**。若追求更低延迟，3B–4B 级模型是稳妥选项。
> 标注约定：**【已验证】**= 检索命中真实页面且标题/DOI 可核实；**【前沿/有风险】**= 学术上成立但工程落地存在明显不确定性；**【待核实】**= 检索中确认页面存在，但作者/年份/会场未经逐字确认。
> **核实条件说明**：本环境 `web_fetch` 完全不可用（所有域名解析到非公网 IP），全部引用仅经 `web_search` 返回的页面标题/DOI 核验。凡未逐字确认者一律标【待核实】，见 §6。

---

## 0. 结论速览

1. **判题的正确做法不是"用 LLM 代替字符串比对"，而是把判定依据从"输出文本相等"升级为"行为等价"**——即"差分测试 + 测试用例生成 + 执行沙箱"。LLM 的职责是**定位错因、生成测试、解释反馈**，而不是充当唯一裁判。这条分工是整套方案可靠性的地基。
2. **知识追踪在小用户量下不应上深度模型**。多项研究显示贝叶斯化 IRT 类模型在数据稀疏时反超神经网络（[Back to the Basics, 2016](https://ar5iv.labs.arxiv.org/html/1604.02336)），BKT/IRT/因子分解机是可解释、参数少、冷启动友好的选择。
3. **赛事的"AI 与功能契合度"得分点在于：LLM 的每一次输出都被可执行证据（运行结果、测试、知识点标签）约束和校验**。可参考"多模型+执行校验"的集成思路（[The Code Council, IEEE](https://ieeexplore.ieee.org/abstract/document/11526798/authors)、[Code-DKT 类工作](https://files.eric.ed.gov/fulltext/ED624103.pdf)）。

---

## 1. 编程教育的自动反馈与错因诊断

### 1.1 学生代码"语义等价判定"的六条技术路线

| 路线 | 代表工作 | 能判什么 | 数据/算力需求 | 可解释性 | 风险 |
|---|---|---|---|---|---|
| ① 输出字符串比对（你的现状） | — | 完全匹配 | 极低 | 高 | 正确但格式不同的解全判错 |
| ② AST 归一化 + 树编辑距离 / 代码属性图 | [Statement-level Evaluation of C Programs with Tree Edit Distance on Normalized AST](https://ieeexplore.ieee.org/document/11561586)【待核实年份】；[Cross-Language Educational Code Similarity Using Code Property Graphs](https://ieeexplore.ieee.org/iel8/6287639/11323511/11668797.pdf)【待核实】 | 结构相似度、抄袭/聚类 | 低 | 高 | 只测"像不像"，不测"对不对" |
| ③ 程序综合 / 符号求解修复 | [Singh, Gulwani, Solar-Lezama, PLDI 2013](https://dl.acm.org/doi/10.1145/2499370.2462195)；[sk_p: A Neural Program Corrector for MOOCs, 2016](https://dl.acm.org/doi/pdf/10.1145/2984043.2989222) | 生成"最小修改"修复建议 | 中 | 中 | 只覆盖模板化作业；Python 动态特性难建模 |
| ④ 测试用例生成 + 差分执行 | [Can Test Generation and Program Repair Inform Automated Assessment?](https://ieeexplore.ieee.org/document/10988955)【待核实年份】；[TestGen-LLM, Meta, FSE 2024](https://dl.acm.org/doi/abs/10.1145/3663529.3663839) | **行为等价（当前最可靠）** | 低（沙箱） | 高（反例即证据） | 测试不完备→假阴性；需防死循环/恶意代码 |
| ⑤ 嵌入相似度 / 聚类 | [OverCode, ACM TOCHI 2015](https://dl.acm.org/doi/10.1145/2699751) | 解法族群划分、批量反馈 | 低 | 中 | 相似≠等价 |
| ⑥ LLM 判定 | 见 §3.3 | 综合判断+自然语言解释 | 中（本地 7B 4-bit 可跑，**8GB 是上限**） | 低（黑箱） | 幻觉、评判偏差，**不可作为唯一判据** |

**【已验证的结论】**：学术界的事实标准是 ④ 为核心、②⑤ 做辅助、③⑥ 做增强。OverCode 用聚类把"同一题的上百种解法"归纳成几个族群，是低成本高收益的经典做法，特别适合闯关游戏的"一题多解"展示与批量反馈。

**工程建议**：把判题定义为一个三元组 `(运行结果, 反例, 结构指纹)`：先用沙箱执行（含超时/资源限制），再对边界条件做参数化差分测试，最后用 AST 指纹判"是否与某已知错误族同型"。

### 1.2 迷思概念（misconception）诊断：经典工作、体系与数据集

- **经典源流**：[A Summary of Misconceptions of High School BASIC Programmers（Putnam 等，1986，ERIC EJ345914）](https://eric.ed.gov/?id=EJ345914)——最早系统记录新手对循环/赋值/变量的错误心智模型，其分类至今可用。【待核实：年份以 ERIC 记录为准】
- **理论框架**：[Sorva, Notional Machines and Introductory Programming Education, ACM TOCE 2013](https://dlnext.acm.org/doi/10.1145/2483710.2483713)——解释"学生脑中的执行模型错在哪"，是设计苏格拉底式提问的理论依据（问"你觉得循环第二次执行时 i 是几"而非"答案是 A"）。
- **规则化检测**：[A Comparison of Three Program Query Languages to Detect Python Programming Misconceptions, OASIcs Programming 2025](https://drops.dagstuhl.de/entities/document/10.4230/OASIcs.Programming.2025.21)——用 Datalog 类程序查询语言在 AST 上写"迷思模式规则"。**这是最适合你的技术**：规则可解释、可人工审核、可覆盖 K-12 常见错误，且不需要训练数据。
- **数据驱动的 Python 新手错误图谱**：[Learning to Program: Mapping Errors and Misconceptions of Python Novices…, SCITEPRESS 2025](https://www.scitepress.org/Papers/2025/132031/132031.pdf)【作者需核实】；[Deriving Common Novice Programming Error Patterns from Student Submissions using LLMs, ICLEA/APSCE](https://library.apsce.net/index.php/ICLEA/article/download/6321/6250/7435)【年份作者需核实】——后者示范了用 LLM 从大量提交中**归纳**错误分类体系，可用来冷启动你自己的标签集。

**建议的 K-12 Python 错误分类体系（综合上述工作，9 类）**：语法/缩进与冒号；名字错误与作用域（局部/全局、未定义、拼写）；类型混淆（`input()` 返回 str、int/float 混用、字符串拼接数字）；循环边界与终止（off-by-one、`range(n)` vs `range(n+1)`、死循环、累加初值）；控制流与嵌套（`else` 绑定错、`break/continue` 误用）；函数与返回（忘记 `return`、返回 None、参数顺序）；数据结构与索引（下标越界、列表可变共享、切片边界）；I/O 与格式化（`print` 多参数、f-string 缺失）；算法意图错（能跑但解错）。前 8 类可由规则+查询语言覆盖，第 9 类必须靠执行/测试反例。

**【待核实/空白】**：目前没有公开、权威、面向 K-12 Python 的通用迷思标注数据集（现有资源多为大学 CS1）。**你自建 300–800 条带错误类型标签的提交集，本身就是一个可写成论文的贡献点**，也可与 §3.4 的 CS1 数据集对齐标注规范。

---

## 2. 知识追踪（KT）与自适应出题

### 2.1 模型谱系

| 模型 | 代表工作 | 原理 | 数据需求 | 可解释性 | 适用判断 |
|---|---|---|---|---|---|
| IRT / 贝叶斯 IRT | [Back to the Basics, 2016](https://ar5iv.labs.arxiv.org/html/1604.02336) | 学生能力 θ × 题目难度/区分度 | 小（几十人×几十题） | **高** | 小用户量首选 |
| BKT | Corbett & Anderson, *Knowledge tracing: Modeling the acquisition of procedural knowledge*, 1994（[期刊记录页](https://cdgx.nstl.gov.cn/paper_detail.html?id=cfdda1439764d39758c38321b6be0a3f)；**DOI 本轮未核实，勿凭记忆写**） | 每技能 4 参数 HMM：已学/未学 × 答对/答错 | 极小 | **高** | 知识点粒度明确时最佳 |
| KTM（因子分解机） | [Knowledge Tracing Machines, AAAI 2019](https://aaai.org/papers/00750-knowledge-tracing-machines-factorization-machines-for-knowledge-tracing/) | 学生×题目×技能交互 | 中 | 中 | IRT 的自动特征扩展版 |
| DKT | [Deep Knowledge Tracing, NeurIPS 2015](https://neurips.cc/virtual/2015/poster/5500) | RNN 直接建模答题序列 | **大** | 低 | 你的规模会过拟合 |
| SAKT/AKT | [Context-Aware Attentive KT, KDD 2020](https://www.kdd.org/kdd2020/accepted-papers/view/context-aware-attentive-knowledge-tracing.html) | 注意力建模历史题目的"相关性" | 大 | 低 | 需要千级以上用户 |
| simpleKT | [simpleKT, ICLR 2023](https://ar5iv.labs.arxiv.org/html/2302.06881) | 简化注意力 + Rasch 先验 | 中 | 中 | **若坚持上神经模型，先打这个基线** |
| 综述 | [Knowledge Tracing: A Survey, ACM CSUR 2023](https://ar5iv.labs.arxiv.org/html/2201.06953) | 全景对比 | — | — | 写论文引言必引 |

### 2.2 编程领域做 KT 的特殊挑战与专用工作

挑战有四：**(a) 一题多技能**（一道"九九乘法表"同时考循环、字符串格式化、缩进）；**(b) 部分正确**（5 个测试点过 3 个，0/1 标签丢掉信息）；**(c) 失败信号不等于知识缺失**（语法错误、I/O 格式错都会判错）；**(d) 代码是过程性产物**，同一学生不同提交之间的相似性含知识信息。

编程专用工作（**均已确认存在**）：
- [Code-DKT: A Code-based Knowledge Tracing Model for Programming Tasks, EDM 2022](https://files.eric.ed.gov/fulltext/ED624103.pdf)——把 code2vec 代码嵌入与 DKT 融合，用代码语义缓解"标签噪声"。
- [Denoising Programming Knowledge Tracing with a Code Graph-based Tuning Adaptor, KDD 2025](https://dl.acm.org/doi/abs/10.1145/3690624.3709172)——显式处理"编译/语法失败"造成的噪声，思路对你非常直接可用（**把"语法错误"与"逻辑错误"分开统计**）。
- [FACKT: A Fault-Aware Model for Code Knowledge Tracing, Springer Web and Big Data](https://dl.acm.org/doi/10.1007/978-981-95-5719-6_5)【年份需核实】——按"故障类型"而非"对错"追踪掌握度。

### 2.3 冷启动与轻量方案（**这是你最重要的工程结论**）

- 学术前沿：[MAML-KT: Addressing Cold Start Problem in Knowledge Tracing for New Students via Few-Shot Meta Learning, AIED](https://dl.acm.org/doi/10.1007/978-3-032-29760-0_16)【年份需核实】——元学习让新学生用极少答题记录就得到个性化估计。**【前沿/有风险】**：需要大量"历史学生"做元训练，小团队不具备。
- 稳妥实践（**推荐**）：①**前测/快速定位**：新用户先做 6–10 道跨知识点诊断题，用 IRT 直接估 θ（参考 [An adaptive testing system for programming proficiency using Item Response Theory, Annales Mathematicae et Informaticae 61 (2025), 31–42](https://real.mtak.hu/228822/)）；②**分层先验**：按年级/是否有 Scratch 经验给 BKT 初始参数；③**技能标签继承**：同一关卡族的技能先验共享，学生做过 1 关即可推断同族；④**难度分档出题**（易/中/难）而非连续 θ 估计，鲁棒且不需要大样本。

**结论**：你的规模下应选 **BKT（每知识点 4 参数）+ 贝叶斯 IRT（题目难度）+ 前测冷启动**，全流程可解释——能直接向评委展示"为什么推这道题"，这对"AI 与功能契合度"是加分项而非减分项。

---

## 3. LLM 用于编程教育的前沿

### 3.1 分级提示（hint）与"防泄露答案"

- [Designing Answer-Aware LLM Hints to Scaffold Deeper Learning in K–12 Programming Education, ACM (L@S 2025)](https://dl.acm.org/doi/full/10.1145/3702653.3744323)——**与你的场景最贴合**（K-12 + 编程 + 分级提示），核心思想是让提示"知道答案但不说答案"，按脚手架层级递进。
- [To Tell or to Ask? Comparing the Effects of Targeted vs. Socratic AI Hints, SIGCSE TS 2026](https://dl.acm.org/doi/abs/10.1145/3770761.3777327)——直接实验对比"苏格拉底式追问"与"直接指错"，是分级提示策略的实证依据。
- [MultiHint-9K: Orchestrating Human and AI Agency for Scalable Pedagogical Hint Generation, AIED 2026](https://github.com/KamyarZeinalipour/MultiHint-9K/blob/main/paper/MultiHint-9K_AIED2026.pdf)（数据集见 [HuggingFace](https://huggingface.co/datasets/KamyarZeinalipour/MultiHint-9K)）——大规模多层级提示数据集，可用于微调/评测。
- 经典数据驱动基线：[Stamper 等, Program Representation for Automatic Hint Generation，ITS 2012](https://dl.acm.org/doi/10.1007/978-3-642-30950-2_40)；[Rivers & Koedinger, Automatic Generation of Programming Feedback: A Data-Driven Approach, 2013](https://researchr.org/publication/RiversK13/bibliographies)。
- 教学设计理论（**必引，评委认这个**）：[Koedinger & Aleven, Exploring the Assistance Dilemma, Educational Psychology Review 2007](https://eric.ed.gov/?id=EJ785065) 与 [Aleven 等, Help Seeking and Help Design, 2003](https://mpifg.disco.mpg.de/Record/JSTOR.3516037/Details)——"给太多帮助会削弱学习"是分级提示的理论合法性来源；教学效果的因果证据可引 [Kestin 等, AI tutoring outperforms in-class active learning: an RCT, Scientific Reports 2025](https://www.nature.com/articles/s41598-025-97652-6)。

**防泄露答案的四件套（工程可落地）**：① **L1–L4 分级**（L1 概念提醒 → L2 定位到行/变量 → L3 给伪代码骨架 → L4 才给可运行片段，且 L4 只在连续 3 次失败后解锁）；② **执行证据锚定**：提示必须引用学生程序的真实报错行与变量值，禁止脱离代码泛泛而谈；③ **答案相似度闸门**：生成后与参考解/AST 指纹比对，超过阈值（如高风险代码块重合）自动降级重写；④ **规则模板优先**：高频错误（缩进、`input()` 类型、off-by-one）直接用人工审核过的模板，LLM 只负责把模板措辞贴合学生代码，把幻觉面缩到最小。

### 3.2 变式题 / Parsons 题 / 测试用例生成

- 题目与代码解释生成：[Sarsa 等, Automatic Generation of Programming Exercises and Code Explanations Using LLMs, ICER 2022](https://dlnext.acm.org/doi/fullHtml/10.1145/3501385.3543957)——LLM 生成的题**可用但需人工过滤**（约 1/4 存在瑕疵类问题），是"生成+筛选"流水线的基准工作。
- Parsons 题自动生成：[Automating Personalized Parsons Problems with Customized Contexts and Concepts, arXiv 2404.10990 (2024)](https://ar5iv.labs.arxiv.org/html/2404.10990)【作者需核实】；LLM 解 Parsons 题的评测：[More Robots are Coming, ACE 2023](https://dl.acm.org/doi/fullHtml/10.1145/3636243.3636247)。
- 个性化题目生成：[Unlimited Practice Opportunities: Automated Generation of Comprehensive, Personalized Programming Tasks (del Carpio Gutierrez 等, arXiv 2503.11704, 2025)](https://ar5iv.labs.arxiv.org/html/2503.11704)。
- 测试用例自动生成（**判题可靠性的关键**）：[TestGen-LLM, Automated Unit Test Improvement using LLMs at Meta, FSE 2024](https://dl.acm.org/doi/abs/10.1145/3663529.3663839)——工业级验证了"生成→执行过滤→仅保留能提升覆盖率的测试"这一流水线，**这就是你该照搬的架构**。

### 3.3 LLM 在教育场景的可靠性（幻觉、评判偏差、执行校验）

- 事实性/解释质量：[Evaluating the Quality of LLM-Generated Explanations for Logical Errors in CS1 Student Programs, ACM](https://dl.acm.org/doi/pdf/10.1145/3627217.3627233)【会场需核实】——报告 LLM 对逻辑错误的解释常出现事实错误。
- 评判偏差：[Hands-on analysis of using LLMs for the auto evaluation of programming assignments, Information Systems 2024](https://dl.acm.org/doi/abs/10.1016/j.is.2024.102473)——LLM 打分与人工存在系统性偏差，需多模型/多轮一致性。
- 集成降幻觉：[The Code Council: Orchestrating Heterogeneous LLMs for Robust Programming Scaffolding, IEEE](https://ieeexplore.ieee.org/abstract/document/11526798/authors)【年份需核实】——多模型"议会"投票 + 规则校验，比单模型稳定，**但两倍算力与延迟**。
- **【已验证的方法】执行结果校验**：任何 LLM 输出都经过"能否通过沙箱测试/是否与运行结果矛盾"的过滤。这与 §1.1 的 ④ 是同一套基础设施，复用成本极低，却是"技术创新性"叙事里最硬的一环。
- 轻量落地方案参考：[A lightweight intelligent feedback system for student code submissions using LLMs, Discover Education 2026](https://link.springer.com/article/10.1007/s44217-026-01400-5)；K-12 场景：[Using LLMs for Support in High School Programming Education, TU Delft](https://repository.tudelft.nl/file/File_8d006638-a653-4a0c-9edf-eb2df095116e)【学位论文/报告】。

### 3.4 Benchmark 与数据集

- [CS1QA: A Dataset for Assisting Code-based Question Answering in an Introductory Programming Course, NAACL 2022](https://preview.aclanthology.org/paclic-22-ingestion/2022.naacl-main.148.pdf)
- [CSTutorBench: Benchmarking LLMs for Realistic Computer Science Tutoring, SIGCSE TS 2026](https://dl.acm.org/doi/10.1145/3770761.3777333)——评测 LLM 辅导能力（含"不直接给答案"类指标），**建议直接用它证明你的模型选择合理**。
- [MultiHint-9K](https://huggingface.co/datasets/KamyarZeinalipour/MultiHint-9K)（分级提示）
- CodeWorkout 数据集 / CSEDM Data Challenge（学生提交+编译运行日志，用于编程 KT）【待核实：原始论文与获取方式；检索中见其被用于知识追踪研究，见 [Scarlatos 学位论文引用](https://people.cs.umass.edu/~ajscarlatos/Dissertation.pdf)】
- CloudCoder 等在线判题系统的公开提交集【待核实：本轮未取得第一手链接，不引用具体结论】

---

## 4. 三套可落地的技术方案组合

### 方案 A：规则优先 + LLM 润色（**最稳，建议作为骨架**）
**技术栈**：Python 沙箱执行（超时+资源限制，`subprocess` + rlimit/Job Object）→ 参数化/属性测试生成反例 → AST 指纹 + Datalog 迷思规则（§1.2）→ 每知识点 BKT（4 参数，EM 离线拟合）→ IRT 难度分层选题 → 提示模板库 + LLM（**7B 4-bit AWQ/GGUF，必要时可降到 3B–4B**）仅做"把模板贴合学生实际代码"的改写。
**优势**：全链路可解释；**8GB 显存完全够用（4-bit 7B 权重约 4–5GB，KV cache 余量充足）**；几乎零幻觉风险；演示时"为什么推这题"能逐条讲清；学术支撑全是经典（BKT/IRT/notional machines）。
**风险**：创新叙事偏弱，评委可能觉得"AI 只是外壳"；需要人工写较多规则与模板。

### 方案 B：LLM 为核心 + 硬约束校验（**创新性最高**）
**技术栈**：QLoRA 微调 **7B（不要选 14B：8GB 显存下 14B 4-bit 权重已接近或超过显存上限，无余量给 KV cache 与并发）**（数据 = 自建错误标签集 + MultiHint-9K 子集 + 自建提交）→ LLM 输出结构化解题诊断（JSON：错误类型/行号/证据/提示级别）→ 每个输出经沙箱执行与测试反例校验，不一致则拒答并回退规则 → LLM 生成变式题时**必须同时生成参考解与测试**，三关全过才入库 → simpleKT/AKT 做自适应（数据够时）。
**优势**：直接命中"生成式 AI 与产品功能高度契合"；可讲"生成—执行—过滤"流水线（对标 TestGen-LLM 的工业做法）；**全本地推理符合校园私有化部署与 K-12 数据合规要求**（学生代码与作答记录不出校）。
**风险**：**最高**。测试生成不完备会导致误判合格/不合格；LLM 生成题偏模板化、难度分布失控；迷思标签冷启动无数据；self-consistency 与多模型投票在 8GB 单卡上会明显拖慢实时判题（**建议离线批处理，不进判题热路径**）。

### 方案 C：分层混合（**推荐，且与 8GB 私有化最匹配**）
以 A 为骨架，LLM 只在三个**受约束的位置**介入：① **错因归类**（把执行反例 + AST 规则命中结果喂给 LLM，输出 9 类错误标签之一及置信度，低置信度回退规则）；② **变式题生成**（LLM 生成 + 测试生成 + 参考解验证，三关全过才入库，难度标签由"通过率预测"或 IRT 校准；**离线跑，批量生成**）；③ **分级提示改写**（模板 L1/L2 → LLM 生成 L3/L4，并做答案相似度闸门）。
**技术栈**：沙箱 + 属性测试 + AST/Datalog 规则 + BKT/IRT + **7B 4-bit（QLoRA 适配错因分类）** + 向量库（相似提交检索，支持"和你解法相似的同学也犯过这个错"；可用 `bge-small` 级小嵌入模型，CPU 也能跑）。
**优势**：每个 AI 环节都有非 AI 的兜底与证据链；**显存压力可控（同时只驻留一个 7B 4-bit 实例，生成任务离线批处理）**；判题延迟主要来自执行而非推理；创新点清晰（"受约束的 LLM 闭环"）且风险可辩护。
**风险**：系统复杂度上升，需要人日投入做评测；三处 LLM 调用要设计缓存与降级策略；**单卡并发需排队，课堂 40 人同时在线时必须做请求队列 + 降级到纯规则模式**。

### 部署可行性小结（8GB / RTX 5060 Laptop）
- **可跑**：7B 4-bit（AWQ/GPTQ/GGUF-Q4）+ 4k 上下文；3B–4B 全精度或 8-bit 更从容。
- **不建议**：14B（任何量化）；7B + 长上下文 + 高并发；多模型投票进实时热路径。
- **架构要求**：vLLM/llama.cpp 单实例 + 请求队列；生成类任务（变式题、题库准入、提示预生成）全部**离线批处理**；判题热路径只调用规则与沙箱，LLM 仅做异步的错因解释补充。
- **合规叙事**：本地部署 = 学生代码与行为数据不出校园网，这是私有化场景的强论据，建议在答辩材料中显式对比"云端 API 方案"的数据出境与成本风险。

---

## 5. 技术路线推荐表

| 你的需求 | 首选方法（成熟） | 增强方法（前沿，需验证） | 兜底/校验 |
|---|---|---|---|
| **(a) 语义判题** | 沙箱执行 + 参数化差分测试（行为等价） | LLM 生成补充测试用例（TestGen-LLM 流水线） | 输出比对仅作快速预筛；测试不完备时回退人工/参考解指纹 |
| **(a) 错因诊断** | AST/Datalog 迷思规则；错误分类体系 9 类 | LLM 从提交中归纳错误模式；7B 微调做错误分类 | 规则命中 + 执行反例必须一致；低置信度不强答 |
| **(b) 自适应出题** | BKT（知识点）+ 贝叶斯 IRT（难度）+ 前测冷启动 | LLM 生成变式题/Parsons 题（生成+测试+参考解三重验证）；simpleKT | 题库准入闸门；难度分层代替连续 θ；出题理由可视化 |
| **(c) 分级提示** | 模板化 L1–L4 提示 + 帮助寻求理论 | LLM 分级提示（answer-aware）+ 苏格拉底提问；MultiHint-9K 微调 | 答案相似度闸门；提示必须引用真实报错与变量值；L4 限次解锁 |
| **评测与答辩** | CSTutorBench 类指标 + 自建标注集 | MultiHint-9K / CS1QA 迁移评测；A/B 学习效果（对标 Kestin RCT） | 报告幻觉率、误判率、提示泄露率三个硬指标 |

**一句话路线**：**执行等价做判据、规则库做错因、BKT/IRT 做自适应、LLM 做生成与表达，全部由沙箱与测试收敛；LLM 只在离线批处理与异步解释中出现，8GB 单卡私有化部署即可支撑。**

### 5.1 与赛事评分点的对应（「中国移动杯」2026 江苏生成式 AI 创新大赛）

| 评分关注点 | 报告中的对应设计 | 建议在参赛材料中怎么讲 |
|---|---|---|
| **AI 与产品功能高度契合** | LLM 嵌入"判题→诊断→出题→提示"四个环节，而非独立聊天框（§4 方案 C 的三处受约束介入） | 展示一条完整链路：学生提交 → 执行反例 → 错误标签 → 知识点掌握度更新 → 下一题选择 → 分级提示，每步都有界面截图与数据 |
| **技术创新性** | "受约束的 LLM 闭环"：所有生成物经执行/测试/相似度三重闸门才允许进入题库或学生视野 | 用**误判率、幻觉率、提示泄露率**三个硬指标量化，比"我们用了大模型"有说服力得多 |
| **生成式 AI 主题** | LLM 生成变式题、Parsons 题、测试用例、分级提示（§3.2） | 强调"生成 + 自动验证"的闭环，而非单纯调用 API |
| **私有化 / 落地可行性** | 7B 4-bit 单卡 8GB 本地推理，数据不出校园网 | 给出显存占用、单次推理延迟、并发队列策略的实测数字 |
| **教育价值** | notional machines + assistance dilemma + 分级脚手架（§3.1） | 说明"为什么不让 AI 直接给答案"，引理论与 RCT 证据 |

---

## 6. 待核实清单（**引用前必须逐条复核**）

**说明**：本环境 `web_fetch` 完全不可用，全部引用仅经 `web_search` 返回的页面标题/DOI 核验，**未做全文核对**。以下条目请勿在论文/答辩材料中当作已确认事实使用。

- **【待核实】BKT 原始文献**：Corbett & Anderson, *Knowledge tracing: Modeling the acquisition of procedural knowledge*, 1994。仅通过二手引用与[期刊记录页](https://cdgx.nstl.gov.cn/paper_detail.html?id=cfdda1439764d39758c38321b6be0a3f)确认标题，**DOI 与卷期未核实**。
- **【待核实】Putnam 等 1986**：年份/出处以 [ERIC EJ345914](https://eric.ed.gov/?id=EJ345914) 记录为准。
- **【待核实】年份或会场未逐字确认**：[Tree Edit Distance 论文](https://ieeexplore.ieee.org/document/11561586)、[Code Property Graph 论文](https://ieeexplore.ieee.org/iel8/6287639/11323511/11668797.pdf)、[The Code Council](https://ieeexplore.ieee.org/abstract/document/11526798/authors)、[Can Test Generation and Program Repair Inform…](https://ieeexplore.ieee.org/document/10988955)、[FACKT](https://dl.acm.org/doi/10.1007/978-981-95-5719-6_5)、[MAML-KT](https://dl.acm.org/doi/10.1007/978-3-032-29760-0_16)、[SCITEPRESS 2025 Python 新手错误图谱](https://www.scitepress.org/Papers/2025/132031/132031.pdf)、[ICLEA 错误模式归纳](https://library.apsce.net/index.php/ICLEA/article/download/6321/6250/7435)、[Automating Personalized Parsons Problems, arXiv 2404.10990](https://ar5iv.labs.arxiv.org/html/2404.10990)、[using LLMs for Support in High School Programming Education (TU Delft)](https://repository.tudelft.nl/file/File_8d006638-a653-4a0c-9edf-eb2df095116e)。
- **【待核实】会场由 DOI 前缀推断**：[Evaluating the Quality of LLM-Generated Explanations for Logical Errors in CS1 Student Programs](https://dl.acm.org/doi/pdf/10.1145/3627217.3627233)（DOI 与标题已核实，会议名未确认）；[Designing Answer-Aware LLM Hints…](https://dl.acm.org/doi/full/10.1145/3702653.3744323)（标题与 DOI 已核实，标注为 L@S 2025 系推断）。
- **【不可引用】未取得第一手链接**：CodeWorkout / CSEDM Data Challenge / CloudCoder 数据集。本轮仅有二手转述，**不要写进参考文献**。
- **【不可引用】凭记忆的补充**：本报告中若出现未附链接的模型名（如 Qwen 系列）或具体显存数值，均属工程经验估计，非论文结论，引用需另找来源。

---

**核实声明**：除上述标注外，本报告中的链接均为 `web_search` 命中的真实页面（标题与 DOI 来自页面元数据），未使用凭记忆生成的论文引用；无法确证者一律标注【待核实】，未编造作者、年份或 DOI。
