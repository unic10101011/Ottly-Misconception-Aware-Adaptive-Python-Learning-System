# K-12 少儿编程 × AI：市场格局、AI 渗透度与差异化机会

**调研方法与证据边界（重要）**：本环境 **web_fetch 完全不可用**（所有域名解析到非公网 IP），沙箱内 HTTPS 出网同样被阻断，因此全部结论仅基于 `web_search` 返回的**页面标题/摘要 + URL**，**未逐篇核读正文**。凡标【事实】者指"检索结果明确显示该主张"，标【推断】者为我的判断。

**未经交叉核实、请谨慎引用的条目**：①各国内厂商（核桃编程、猿编程、编程猫、有道、作业帮、讯飞）的 AI 功能描述多来自**企业新闻稿或二手报道**，无独立第三方验证；②"CodeMonkey/西瓜创客没有产品级 AI"是**检索未命中**，不等于不存在；③韩国 AI 教科书"降级"、LAUSD "Ed" 项目始末仅见标题级证据；④各地区 AI 教育政策的执行细则与课时要求，我未读到文件正文。

## 一、主要玩家盘点

| 产品 | 定位 / 年龄段 | 核心玩法 | 商业模式 | 已核实的 AI 能力 |
|---|---|---|---|---|
| [CodeCombat](https://codecombat.com/) / [Ozaria](https://aojiarui.com/premium) | 游戏化闯关学 Python/JS，8–16 岁 | 写真实代码操控英雄通关 | [面向学校授权 + 家庭订阅](https://www.codecombat.com/investors) | [AI Hints（AI 提示）](https://blog.codecombat.com/product-update-new-teacher-dashboard-ai-hints-more/)；官方论坛有"自适应"讨论但非产品化 |
| [Tynker](https://www.tynker.com/) | 图形化→Python，K-12 | 积木到文本过渡 | 家庭+学校订阅 | [Tynker Copilot（首个面向儿童的 LLM 编程伴侣）](https://www.tynker.com/about/press/2023/10-introducing-tynker-copilot-the-first-ever-llm-powered-coding-companion-for-young-coders)，[自研微调 Llama 2 做积木 Copilot](https://www.tynker.com/blog/how-we-fine-tuned-llama-2-for-our-block-coding-copilot/) |
| [CodeMonkey](https://www.codemonkey.com/) | 游戏化，5–14 岁 | 关卡式解题 | 学校订阅 | 未检索到产品级 AI 功能说明（**不代表不存在**），主打 [2025 年度游戏化学习平台奖](https://www.codemonkey.com/blog/game-based-learning-platform-of-the-year-2025/) |
| [Scratch](https://scratch.mit.edu/) | 图形化创作社区，8–16 岁 | 自由创作+社区分享 | 非营利免费 | 平台本身无内建大模型；AI 概念靠 [Machine Learning for Kids](https://www.google.bg/books/edition/Machine_Learning_for_Kids/jWTvDwAAQBAJ) 等外部课程补 |
| [Code.org](https://code.org/) | 免费 K-12 CS 课程 | 课程+项目 | 非营利 | [AI 教学助手](https://code.org/zh-Hans/artificial-intelligence/teaching-assistant)：面向**教师**生成课堂材料、辅助评分，[用 Amazon Bedrock 把教师评分时间缩减一半](https://aws.amazon.com/cn/solutions/case-studies/codeorg-bedrock/) |
| [Khanmigo](https://www.khanmigo.ai/) | AI 家教，K-12 全科含 CS | 苏格拉底式追问 | [教师免费，家长/学生 4 美元/月](https://www.khanmigo.ai/pricing) | 全科对话式导师；研究显示[编程新手认为其苏格拉底式引导有帮助](https://s3.amazonaws.com/assets.pubpub.org/w9c2ix175uqqi0gt2vo4zcq0459r89pe.pdf) |
| [编程猫](https://www.codemao.cn/) | 图形化+Python，国内头部 | 工具+课程+社区 | 课程+校园合作 | [算法备案公示](https://static-platform.codemao.cn/926/protocols/PxtCITc9_algorithmServiceDescription.html)；[发布 AI 教育生态布局](https://edu.codemao.cn/news/412)；[与 UNESCO 发起"AI Day"](https://www.stdaily.com/web/gdxw/2025-03/09/content_307295.html)；[沙利文认证累计用户数第一](https://finance.sina.cn/2026-01-05/detail-inhfhavn6758951.d.html) |
| 核桃编程 | 线上少儿编程，6–15 岁 | 人机双师（AI+真人） | 年课；[拟赴美上市集资约 1 亿美元](https://dxpress.gelonghui.com/live/1887179)，[资本化存在三道坎](http://finance.china.com.cn/jiaoyu/20250425/6236213.shtml) | 主打 AI 双师协同；具体大模型用途公开信息有限 |
| 猿编程 / 猿力科技 | K-12 编程+素养 | 直播课+平台 | 课程订阅 | [2025 云栖大会称大模型"全链路赋能"AI 教育](https://www.donews.com/news/detail/4/6148603.html)，[自研教育大模型](https://sdxw.iqilu.com/share/YS0yMS0xNTcyODkzMg==.html) |
| [西瓜创客](https://post.smzdm.com/p/a4q5z6v8/) | 图形化→Python，7–12 岁 | 课程+赛事 | 年课（价格/退费是家长关注点） | 未检索到核心闭环 AI 的公开说明 |
| 小码王 | 线下+线上少儿编程 | OMO 教学 | 课程 | [自称行业唯一"准独角兽"](https://www.xiaomawang.cn/news/231481.html) |
| 科大讯飞 | 学习机硬件 | 作业辅导+课程 | 硬件销售 | [星火大模型七项功能主打"因材施教"](https://m.zhidx.com/p/390940.html) |
| 腾讯扣叮 | 校内 AI 教育平台 | 课程+工具 | 校园合作 | [2026 新品主打人工智能教育普及](https://www.sohu.com/a/969537708_362042) |
| 有道（小图灵） | 少儿编程+AI 答疑 | 系列课 | 课程+硬件 | [有道 CEO 称"教育 AI 比聊天和编程更难"](https://www.stdaily.com/web/gdxw/2026-04/30/content_510928.html)（**推断**：侧面承认教育场景落地难度高于套壳聊天） |

**三点观察（推断）**：① 海外头部（CodeCombat/Tynker/Code.org）的 AI 已落地但集中在"提示"和"教师侧工具"；② 国内头部的 AI 叙事多为"双师/全链路赋能"级别的话术，缺少可验证的闭环细节；③ 谁都没有把 AI 变成判题与选题的一部分。

## 二、AI 的真实渗透程度：三层光谱

**Layer A｜教师侧效率工具（真落地，但不在学生学习闭环）**：Code.org 的 AI 教学助手可生成课堂材料、辅助评分并缩短评分时间（[AWS 案例](https://aws.amazon.com/cn/solutions/case-studies/codeorg-bedrock/)）；CodeCombat 把 AI 提示与教师仪表盘打包发布（[官方更新](https://blog.codecombat.com/product-update-new-teacher-dashboard-ai-hints-more/)）。【事实】

**Layer B｜学生侧对话/提示（AI 是"旁边的助手"，与判题解耦）**：Tynker Copilot、CodeCombat AI Hints、Khanmigo。Khanmigo 的苏格拉底式追问是这其中最接近教学法的（[研究](https://s3.amazonaws.com/assets.pubpub.org/w9c2ix175uqqi0gt2vo4zcq0459r89pe.pdf)）。但没有任何证据显示这类助手知道"学生当前关卡 + 当前代码 + 判题失败的具体位置"。【事实+推断】

**Layer C｜核心学习闭环（判题、错因诊断、自适应出题）——产品级基本空白，仅存于论文原型**：
- 个性化出题：[AIED 2025 用认知状态图 + 最近发展区（ZPD）驱动提示生成个性化编程练习](https://dl.acm.org/doi/10.1007/978-3-032-29744-0_10)；[arXiv《Unlimited Practice Opportunities：自动生成个性化编程任务》](https://ar5iv.labs.arxiv.org/html/2503.11704)。
- 错因诊断：[NTNU 的"带迷思概念诊断的编程学习平台"](https://scholar.lib.ntnu.edu.tw/en/publications/a-programming-learning-platform-with-misconception-diagnosis/)；[Koli Calling 2024 测量小学生编程迷思概念流行率](https://dl.acm.org/doi/full/10.1145/3699538.3699568)。
- 提示与判分：[Virginia Tech《Designing Answer-Aware LLM Hints to Scaffold Deeper Learning in K–12 Programming Education》](https://dl.acm.org/doi/full/10.1145/3702653.3744323)；[万方《大模型赋能的编程作业评估智能体设计与应用》](https://d.wanfangdata.com.cn/periodical/CihQZXJpb2RpY2FsQ0hJU29scjkyMDI2MDYxMDIwMjYwNjEwMTYxMjM4Eg5qc2pqeTIwMjYwMjAxNxoINHJlMTdmcHc%3D)；[PP-Checker（容忍歧义的 LLM 协同自动判分）](https://www.jstage.jst.go.jp/article/jssst/43/1/43_1_15/_article/-char/ja)。

**判题技术的公认短板（这是你作品的直接抓手）**：ACM 文献指出自动评测工具（AAT）反馈"往往过于简陋，通常只显示测试通过或失败"（[ACM DL](https://dl.acm.org/doi/pdf/10.1145/3636515)）——这与"字符串相等比对判题"是同一类问题。同时[《Don't Judge Code by Its Cover》](https://aclanthology.org/2026.findings-eacl.70/)证明 LLM 判代码存在系统性偏见（如受变量命名、风格影响），**纯靠 LLM 判题同样危险**。【事实】

## 三、空白与机会（逐条回答你的四问）

**1）错因诊断：有研究、没产品。** 迷思概念诊断在中小学 Scratch/xLogo 场景已被量化研究（[Koli Calling](https://dl.acm.org/doi/full/10.1145/3699538.3699568)），但检索到的都是原型平台或论文，未见任何商业化少儿编程产品宣称做到"诊断思维误区"。**这是最大的空白。**【事实+推断】

**2）自适应出题：只有论文。** ZPD/认知状态图驱动的个性化出题（[AIED 2025](https://dl.acm.org/doi/10.1007/978-3-032-29744-0_10)）尚处研究阶段；产品侧最多是"按关卡解锁"的线性难度。**【事实】**

**3）本地化/私有化：在 K-12 是真需求，且是合规刚需。** 政策侧：《生成式人工智能服务管理暂行办法》明确要求防范未成年人"过度依赖或沉迷"（[原文](https://wxb.xzdw.gov.cn/qwfb/xgbmfb/202307/t20230714_376781.html)）；教育部《中小学生成式人工智能使用指南（2025 年版）》要求[禁止小学生独自使用开放式内容生成功能](https://www.workercn.cn/c/2025-05-14/8520696.shtml)（[中国教育学会发布页](https://www.cse.edu.cn/index/detail.html?category=31&id=4242)、[光明网](https://m.gmw.cn/2025-05/12/content_1304034930.htm)）；《未成年人网络保护条例》对不满十四周岁个人信息设监护人同意等要求（[国务院公报](https://www.gov.cn/gongbao/2023/issue_10806/202311/content_6913813.html)）。实践侧：北京把 AI 课程纳入[全学段衔接与综合素质评价](https://www.beijing.gov.cn/fuwu/bmfw/sy/jrts/202506/t20250630_4133821.html)，上海虹口则[用"智能体"让师生在校内用上大模型](https://news.qq.com/rain/a/20250507A061IV00)，《中国教育报》已在讨论[让大模型进入中小学信息科技课](https://share.app3.jyb.cn/news_d/cbca3a57b9673228a48b30843f3e4847)。**"要 AI，但不能把学生数据发给公网大模型，也不能让小学生自由对话生成"——这正是本地 Qwen 部署的卖点。**【事实+推断】

**4）中文语境的特殊痛点（有文献支撑）**：① 非英语母语者学编程存在额外认知负荷与归属感问题（[Non-Native English Speakers in CS1](https://dlnext.acm.org/doi/pdf/10.1145/3803400.3809308)），教学语言显著影响编程学习效果（[Lau & Yuen，见 ACM 综述参考文献](https://dl.acm.org/doi/pdf/10.1145/3815397)）；② 从积木到文本的过渡中，Python 的英文关键字、英文报错、打字速度是明确障碍（[FutureLearn《5 Python literacy challenges for young learners》](https://www.futurelearn.com/info/courses/block-to-text-based-programming/0/steps/39480)）。→ 中文报错解释、少打字输入、关键字中英对照，是低龄与农村校的真实需求。

## 四、反面案例与教训

1. **洛杉矶学区 AI 聊天机器人 "Ed"（AllHere）**：技术先行于教学，最终演变为[总监离职后的"大胆技术项目"复盘](https://www.edweek.org/leadership/lessons-learned-about-bold-tech-initiatives-from-the-lausd-chiefs-departure/2026/06)，供应商合约因[联邦搜查](https://www.dailybreeze.com/2026/02/26/what-to-know-about-lausds-allhere-contract-following-federal-searches/)备受质疑。教训：**先定教学问题，再选技术；供应商与数据条款先谈清。**
2. **韩国 AI 数字教科书**：从"强制教科书"退为[学校自主选用的"教育资料"](https://tech.ifeng.com/c/8nV1C4XRVYw)，国会同步修法（[法案原文](https://likms.assembly.go.kr/filegate/servlet/FileGate?bookId=8402F5C0-4156-9B01-4B18-C32CF58F3A56&type=1)）。教训：**教师不认、效果不明，政策也会回撤。**
3. **无护栏 AI 反而损害学习**：PNAS 论文[《Generative AI Without Guardrails Can Harm Learning》（高中数学）](https://pmc.ncbi.nlm.nih.gov/articles/PMC12232635/pdf/pnas.202422633.pdf)发现，无约束使用 AI 的学生在撤掉 AI 后成绩更差；对照[哈佛物理课按教学法定制的 AI 导师让参与度翻倍](https://news.harvard.edu/gazette/story/2024/09/professor-tailored-ai-tutor-to-physics-course-engagement-doubled/)、[世界银行尼日利亚课后 AI 辅导研究](https://reproducibility.worldbank.org/catalog/419/)。教训：**"不给答案、只给最小提示、绑定课程进度"是设计红线，不是可选项。**
4. **判题/识别翻车**：家长反馈 [AI 学习机把孩子写的 7 误判成 9](https://www.sohu.com/a/996227717_132336)、[儿童学习机三大乱象调查](https://app.bjtitle.com/8816/newshow.php?newsid=6754113)；科大讯飞 2023 年[学习机内容风波](https://news.qq.com/rain/a/20231025A04U2U00)（官方[澄清与星火大模型无关](http://finance.china.com.cn//roll/20231025/6044712.shtml)）。教训：**准确率与内容审核是少儿产品的生死线，一次误判就摧毁家长信任。**
5. **数据与儿童权利**：英国报告发现课堂 AI 应用[嵌入色情网站追踪器、给英国学生返回美国求助热线](https://www.digital-futures-for-children.net/digitalfutures-assets/digitalfutures-documents/Press-release-AI-in-EdTech-casestudy-research-V5.pdf)（[相关儿童权利审计](https://link.icahdq.org/discussion/a-child-rights-audit-of-genai-in-edtech-learning-from-five-uk-case-studies)）。教训：**本地化不只是合规，也是产品卖点。**
6. **商业模式警示**：[Chegg 因 AI 冲击裁员 22%](https://www.36kr.com/p/3292545206601731)、[印度 Byju's 崩塌后 edtech 集体转向"AI 改造"](https://www.outlookbusiness.com/news/year-ender-in-2024-edtech-sought-an-ai-makeover-while-trying-to-overcome-byjus-blow)。教训：**只有"答案分发"价值的 AI 会被通用模型抹平。**

## 五、赛事与部署约束下的适配判断（中国移动杯·江苏生成式AI创新大赛）

**推断（无公开评审细则可查，仅基于赛事名与赛道名）**：赛道名为"AI+**软件创新**"、赛事主题是"**生成式**人工智能"，评审注意力的落点大概率是"**你生成了什么原来看不到的东西**"，而非"你调用了一个模型来做分类/比对"。因此应把作品叙事从"分析型判题"整体翻转成"**生成型教学**"：

| 生成能力 | 具体形态（在你的 React + FastAPI + 本地 Qwen2 架构内可实现） | 对应赛道卖点 |
|---|---|---|
| 生成诊断 | 由失败用例 + 代码结构，**生成**一份"误解假设 + 证据"的错因报告（不是给错误码） | 生成式推理，落地在教学 |
| 生成提示 | **生成**分级提示阶梯（追问→定位→最小改写建议），永不给完整答案 | 与 PNAS/哈佛"护栏"结论一致 |
| 生成题目 | 按薄弱知识点**现场生成**变式题 + 标准答案 + 测试用例，自动入沙箱校验后入库 | 最能体现"生成"，也最难，建议做薄 |
| 生成学习路径 | 跨关卡**生成**个性化下一步路线图与复习清单 | 直接对应政策"因材施教"表述 |

**私有化部署（数据不出校园网）是硬约束，也是叙事优势**：本地 Qwen2 意味着 ① 满足《中小学生成式人工智能使用指南（2025 年版）》"禁止小学生独自使用开放式内容生成功能"——你的 AI 必须是**受关卡上下文约束的封闭式生成**，而不是通用聊天框；② 满足《未成年人网络保护条例》与数据不出校的校园采购要求；③ 可在答辩中直接宣称"断网可用"。**建议把"AI 聊天页"整页删除**，改为判题失败界面内的"错因诊断卡 + 分级提示按钮"，让 AI 的生成结果直接触发下一步学习动作。



## 六、差异化机会清单（按可行性排序）

| # | 机会 | 为什么是机会 | 谁买单 |
|---|---|---|---|
| 1 | **错因诊断引擎**：把"输出不匹配"转为"误解假设集"（沙箱执行轨迹 + AST 结构比对 + 规则库 + 本地 LLM 归因） | 全行业空白；ACM 已证明"只显示通过/失败"是公认短板；纯 LLM 判题有偏见，需规则+LLM 混合 | 教师与教研（校内采购）、家长（付费理由最直观） |
| 2 | **关卡内嵌 AI 教练**：AI 知道当前关卡、代码、失败用例，只给最小提示、苏格拉底式追问 | 现有产品 AI 与判题解耦（Layer B）；PNAS/哈佛研究已给出"护栏"设计范式 | C 端家长、B 端学校 |
| 3 | **判题从字符串比对升级为语义等价**（结构化输出 + 容差比对 + 多解接受） | 与自己作品现状直接对应，是"AI 进闭环"的最低成本证明；避免 7/9 误判类事故 | 竞赛评委（技术分）、教师（减负） |
| 4 | **中文友好输入层**：中文报错解读、关键字中英对照、补全/填空式编码 | 有非母语者编程困难的文献支撑；低龄与农村校刚需 | 校内普及课、农村校、家长 |
| 5 | **本地化"判题+诊断"一体机**：校内私有部署 Qwen，数据不出校 | 政策要求防沉迷/禁小学生自由生成，学校又要用 AI；已有校内"智能体"实践先例 | 教育局/学校 B 端（合规即卖点） |
| 6 | **教师学情看板**：班级"误解热力图"，指出集体性思维误区 | 教师是校内预算与口碑的关键决策者；海外已验证教师侧 AI 付费意愿 | 学校 B 端 |
| 7 | **自适应补题**：按诊断出的错因现场生成变式题 | 最前沿、最有想象空间，但技术上最难、易失控 | 后期再做；先做 1–3 攒数据 |

**给竞赛的一句话建议（推断）**：评委最容易识别的差异不是"用了大模型"，而是"**AI 的输出直接改变了下一个学习动作**"。把 AI 从独立聊天页搬进判题失败的那一刻，用"错因标签 → 最小提示 → 变式题"三段闭环呈现，就同时踩中了本报告中最大的市场空白（Layer C）和最强的政策约束（本地化 + 不给答案）。
