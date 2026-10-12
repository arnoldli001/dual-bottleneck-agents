# ARGUS：面向开放式科学发现的自进化智能体架构——从形式锚定到种群博弈的系统性设计

**摘要**
大语言模型（LLM）的静态本质与开放环境中持续部署需求之间的矛盾，构成了当前人工智能研究的核心张力。现有自进化系统在代码生成和数学推理等可形式化领域取得了显著进展，但普遍面临四个结构性瓶颈：自验证悬崖、评估信号不可靠、编排开销膨胀和主动遗忘风险。本文提出ARGUS（Autonomous Recursive Generative Universal Scientist），一套五层三环嵌套的自进化智能体架构，通过形式锚定验证、种群博弈、经验蒸馏和分层治理的协同设计，系统性回应上述瓶颈。ARGUS的核心设计原则是"外部锚定优先"——所有进化信号必须经过独立于模型自身的验证源确认，以打破自确认循环中的偏差放大。本文详细阐述了ARGUS的架构设计、工程实现方案、测试用例设计和评估方法。实验部分采用四条件对照设计（A：无锚定无种群；B：仅形式锚定；C：仅种群博弈；D：完整ARGUS），以Z3约束求解任务为验证载体，通过200轮×4条件×3次独立运行的实验规模，验证形式锚定和难度自适应两个核心机制的有效性。本文为独立研究者提供了一条在有限算力（预算约150-250元）下可复现的验证路径。
**关键词**：自进化智能体；形式验证；种群博弈；经验蒸馏；多智能体共识；Z3求解器
## 第1章 引言
### 1.1 问题背景：LLM的静态本质与持续部署的矛盾
大语言模型（Large Language Model, LLM）在多样化任务上展现了卓越的能力，从自然语言理解到代码生成，从数学推理到科学假设生成，其表现不断刷新着人们对人工智能能力的认知边界。然而，这一技术范式的根本性局限在于其静态本质：模型在完成训练后即成为"冻结的知识体"，无法根据新任务、演进的知识域或动态交互环境自适应地调整内部参数。
这一矛盾在开放式、交互式场景中尤为突出。当LLM被部署为长期运行的智能体（Agent）时，它面临着训练数据中未曾出现的新任务类型、随时间演进的知识体系、以及需要持续适应的用户偏好。传统的解决方案——定期用新数据重新训练或微调模型——面临着灾难性遗忘、数据标注成本高昂和训练周期漫长等根本性困难。
这一矛盾催生了从"扩展静态模型"到"发展自进化智能体"的范式转变。自进化智能体的核心思想是：让系统在与环境的交互中持续学习和适应，通过自主生成训练信号、自主评估性能、自主修改架构，实现"越用越好用"的持续进化能力。这一范式转变激发了学术界对能够从数据、交互和经验中持续学习和适应的架构与方法的浓厚兴趣。
### 1.2 自进化智能体的三个基础维度
自进化智能体的研究围绕三个基础维度展开：
**进化什么（What to Evolve）。** 可进化的组件包括：模型参数（通过微调或强化学习）、记忆系统（经验存储与检索）、工具库（API调用与函数合成）、以及智能体架构本身（提示词、工作流、元策略）。不同系统的进化范围差异巨大：从仅更新提示词的轻量级方案，到修改自身代码的激进方案。
**何时进化（When to Evolve）。** 适应阶段可分为两类：测试时内（in-test-time）适应，即在单次任务执行过程中动态调整策略；跨测试时（cross-test-time）适应，即在多次任务之间积累经验并改进系统。前者响应速度快但积累有限，后者响应速度慢但能实现持续改进。
**如何进化（How to Evolve）。** 进化信号的来源包括：标量奖励（强化学习）、文本反馈（LLM判官）、程序化验证（测试用例）、以及多智能体竞争（自博弈）。信号的质量和可靠性直接决定了进化的方向是否正确。
在这一框架下，2025-2026年间涌现了一批代表性系统，推动了自进化智能体从概念验证向工程落地的转变。
### 1.3 现有系统的进展与局限

**Darwin Gödel Machine（DGM）** 是代码级自进化最成熟的方案。它迭代修改自身代码（同时改进修改自身代码库的能力），并使用编码基准经验验证每次变更。DGM维护一个不断增长的编码智能体档案库，从中采样智能体进行自我修改，形成开放式的探索树。在SWE-bench上从20.0%提升至50.0%，在Polyglot上从14.2%提升至30.7%。其关键局限是：进化方向完全由编码基准定义，无法迁移到非编码领域。

**Gödel Agent** 在运行时通过Python monkey patching读取和修改自身代码（包括修改修改逻辑本身），在DROP、MGSM、MMLU和GPQA上超越手工设计和元学习优化的智能体。其局限在于：运行时自修改缺乏形式验证保障，存在不可预测的行为漂移风险。

**HyperAgents** 将"任务智能体"和"元智能体"集成到单一可编辑程序中。关键在于元层面的修改程序本身也是可编辑的，实现了"元认知自修改"——不仅改善任务解决行为，还改善生成未来改进的机制本身。在编码、论文审稿、机器人奖励设计、奥数级数学解法评分等多个领域，元层面的改进能跨域迁移和跨运行累积。

**PopuLoRA** 引入了基于种群的非对称自博弈框架。教师和学生是共享冻结基础模型上的专用LoRA适配器：教师提出任务，匹配的学生在程序化验证器下解决。核心发现是：单智能体自博弈会自我校准——任务提出者收敛到生成"它自己能可靠解决"的问题，训练分布坍缩到一个狭窄的难度带。种群动态打破了这个循环，将难度变为种群级信号而非自估计。

**EvolveR** 维持一个从过去轨迹中蒸馏的战略原则经验库。在离线阶段，智能体自我蒸馏成功和失败的轨迹为简洁原则，应用语义去重，并为每个原则分配经验效用分数用于维护和修剪。在线阶段，智能体检索排名最高的原则来指导推理和工具使用。

**SYNAPSE** 是当前最接近生产部署的多Agent自进化系统，6个专业Agent协作，首24小时内自主生成、审查并合并了4个PR到自己的代码库。

**DeepScientist** 消耗超20,000 GPU小时、生成约5,000个想法、验证约1,100个，在三个前沿AI任务上分别超出人类2025 SOTA 183.7%、1.9%、7.9%。这是目前最接近"AI自主科学发现"的系统。

### 1.4 核心挑战：自确认循环与外部锚定的结构性需求

然而，自进化系统面临一个根本性悖论：模型既是学习的主体，又是评判的主体。当LLM用自身的判断来评价自身的输出时，便陷入了"自确认循环"（self-confirming loop）——模型倾向于偏好与自身分布一致的输出，偏差在迭代中被放大而非纠正。

ICML 2026的研究"The Self-Verification Cliff"为这一悖论提供了严格的实证证据。该研究发现，生成能力越强的模型，自我选择正确解的比率与生成正确解的比率之间的差距反而越大。在GPT-5.4-mini上，正确率达54.7%但自选正确率仅41.9%，仅恢复了36%的采样余量。外部验证器只有在至少与生成器同等能力时才能提供帮助，更强的跨家族验证器只能关闭部分悬崖（+3.5分）。

"Verification Collapse in Iterative Self-Improving Language Models"进一步指出，闭环自我改进方法（如Self-Rewarding Language Models、Meta-Rewarding和CREAM）完全放弃了外部正确性，将模型作为其自身的唯一评判者。追踪验证差距Δ_t发现，在多种模型家族中，该差距在每一轮迭代中都在扩大，而真实准确率却停滞或仅微幅提升。Mistral-7B从第一轮的Δ=0.580迅速锁定到Δ=0.850，Qwen2.5-7B则从0.173稳步漂移到0.320。使用全量7.6B参数全微调后，崩溃仍然持续（Δ₂₀=0.338），排除了适配器特定的伪影。

这些发现共同指向一个核心论点：**有效的自进化需要外部锚定**。没有可靠的外部验证锚点，增加算力只会加速自确认循环中的偏差放大。

### 1.5 本文贡献

本文提出ARGUS（Autonomous Recursive Generative Universal Scientist），一套系统性回应上述挑战的自进化智能体架构。主要贡献包括：

（1）**五层三环架构设计**：将自进化系统组织为记忆层、执行层、评测层、进化层和治理层五个层次，以及内环（秒级执行）、中环（小时级种群博弈）和外环（天级元自修改）三个嵌套循环。

（2）**形式锚定优先原则**：设计分层锚定验证机制——第一层硬锚定（Lean/Z3/沙箱执行），第二层软锚定（领域特定训练验证器），第三层共识锚定（圆桌共识+对等评估），确保进化信号的可靠性。

（3）**种群博弈与经验蒸馏的协同**：整合PopuLoRA式的种群动态和EvolveR式的经验原则化，解决单智能体自校准中的难度坍缩和经验库膨胀问题。

（4）**分层治理与可进化宪法**：设计核心规则（不可修改）和适应性规则（智能体自主修订）的分层宪法，配合自动化回归测试，实现安全治理与进化灵活性的平衡。

（5）**最小可行验证方案**：设计四条件对照实验（A/B/C/D），以Z3约束求解任务为验证载体，提供在有限算力下可复现的验证路径。S-ARGUS简化版的总成本约150-250元，远低于传统自进化系统的实验成本。


## 第2章 相关工作

### 2.1 自进化智能体的系统综述

Gao等人（TMLR 2026）提供了自进化智能体领域的首个系统性综述，围绕"进化什么、何时进化、如何进化"三个维度组织领域。该综述涵盖了模型、记忆、工具和架构四个可进化组件，以及测试时内和跨测试时两种适应阶段。Schmidhuber团队参与的最新97页综述进一步将模型训练、记忆演化、工具创建和智能体架构搜索统一到同一框架下，配套项目整理了312篇相关工作。

### 2.2 代码级自进化

**Darwin Gödel Machine（DGM）** 是代码级自进化最成熟的方案。它迭代修改自身代码，并使用编码基准经验验证每次变更。DGM维护一个不断增长的编码智能体档案库，从中采样智能体进行自我修改，形成开放式的探索树。在SWE-bench上从20.0%提升至50.0%，在Polyglot上从14.2%提升至30.7%。

**Gödel Agent** 在运行时通过Python monkey patching读取和修改自身代码（包括修改修改逻辑本身），在DROP、MGSM、MMLU和GPQA上超越手工设计和元学习优化的智能体。

### 2.3 元层面自修改

**HyperAgents** 将"任务智能体"和"元智能体"集成到单一可编辑程序中。关键在于元层面的修改程序本身也是可编辑的，实现了"元认知自修改"。在编码、论文审稿、机器人奖励设计、奥数级数学解法评分等多个领域，元层面的改进能跨域迁移和跨运行累积。

### 2.4 种群自博弈

**PopuLoRA** 引入了基于种群的非对称自博弈框架。教师和学生是共享冻结基础模型上的专用LoRA适配器：教师提出任务，匹配的学生在程序化验证器下解决。核心发现是：单智能体自博弈会自我校准——任务提出者收敛到生成"它自己能可靠解决"的问题，训练分布坍缩到一个狭窄的难度带。种群动态打破了这个循环，将难度变为种群级信号而非自估计。

### 2.5 经验蒸馏

**EvolveR** 维持一个从过去轨迹中蒸馏的战略原则经验库。在离线阶段，智能体自我蒸馏成功和失败的轨迹为简洁原则，应用语义去重，并为每个原则分配经验效用分数用于维护和修剪。在线阶段，智能体检索排名最高的原则来指导推理和工具使用。

### 2.6 自动化评测

**AutoBench** 通过"互惠同行评估"实现全自动LLM评估：LLM随机生成问题，集体质量控制系统过滤低质量问题，所有模型并行生成答案，然后相互评判，迭代加权机制放大可靠评估者的影响力。多判官设计显著优于单判官基线，与MMLU-Pro和GPQA的相关性分别达78%和63%。

**PeerRank** 实现全自主端到端评估框架：模型生成评估任务，通过类别范围的实时网络接地回答问题，评判同行响应，并将密集的同行评估聚合为相对性能估计。

### 2.7 形式验证锚定

在形式验证方面，Z3被用于验证智能体技能的能力闭包证明。FormalGuard将禁止目标编码为Z3布尔约束，通过Z3求解。Z3-heavy fixtures的中位验证时间仅为5-8毫秒，适合智能体编译反馈循环的交互延迟要求。Lean 4被用于生成证明义务文件作为句法有效的证书。

### 2.8 宪法治理

"Constitutional Evolution"框架通过遗传编程自动发现多智能体LLM系统中的行为规范。在180次仿真运行中，进化在集体行动设置中显著优于审议（p < 0.01），而两种方法在双边交易中均未改善结果。进化发现的宪法实现了比人类设计基线高123%的社会稳定性。

### 2.9 自进化评测基准

**SEAGym** 将Harbor兼容的基准转化为动态自进化任务源，通过train batch组织任务，支持训练、验证、测试、回放和成本记录的完整评测视图。其核心发现——频繁更新可能无法改善held-out性能、有用的中间快照可能在后期崩溃、源多样性和模型后端会影响harness可靠性——为自进化系统的评测设计提供了重要参考。

**BenchTrace** 提供了反射评估和进化评估两个套件，包含1,821个标注回合，覆盖六类智能体任务。其提出的失败避免率（FAR）指标——衡量智能体成功避免目标失败实例的测试用例比例——可直接用于自评测可靠性的量化。

**SEA-Eval** 是首个专门为自进化智能体设计的基准，将SEA从数字具身和跨任务持续进化的角度形式化，提出了进化飞轮作为最小充分架构。其关键实证发现——在可比成功率下，不同框架的token消耗差异高达31.2倍，且仅凭成功率会造成"能力幻觉"。


## 第3章 ARGUS架构设计

### 3.1 设计原则

ARGUS的设计遵循五条核心原则：

**原则一：外部锚定优先。** 所有进化信号必须有独立于模型自身的验证源（执行结果/形式证明/检索证据/种群竞争）。Self-Verification Cliff的发现使这一原则成为结构性必需而非设计选择。

**原则二：三环嵌套递归。** 内环（秒级执行）→中环（小时级种群博弈+评测）→外环（天级元自修改），每一环的输出是上一环的输入。自适应循环频率由智能体自主决定，而非固定时间周期。

**原则三：机制复用。** 每种机制（免疫、凋亡、辩论、信息素、表观遗传）在五个层里反复出现，只是粒度不同。任一环节失败，都有其他层的同机制兜底。

**原则四：可逆进化。** 每个变异有检查点，可回滚。自进化系统需要保留回滚能力，当漂移或标准捕获发生时能恢复到已知良好状态。

**原则五：零人工标注。** 评测用例生成、真值锚定、判官校准、经验提炼、记忆管理全部自动化，人类仅在治理层进行最终确认。

### 3.2 五层架构

ARGUS采用五层插件化架构，每一层对应一组功能模块：

**L5治理层（Governance）。** 包含分层宪法、检查点管理、回滚引擎、风险信号网和人类闸门。宪法规则分为"不可修改的核心规则"（12条）和"可修改的适应性规则"。每个变异有检查点（git tag），保留回滚能力。人类闸门仅在核心规则修改时触发。

**L4进化层（Meta-Evolver）。** 包含变异算子池、HAP种群博弈、元自修改器、跨域迁移器和假设空间扩展器。变异算子池支持提示词变异、技能库重组、工具配置调整、推理策略修改和元策略修改。HAP双向课程博弈将教师-学生交互形式化为极小极大优化。

**L3评测层（Eval Foundry）。** 包含测试用例生成器、圆桌共识、形式锚定、信息素路由和判官校准。形式锚定采用分层设计：第一层硬锚定（Lean/Z3/沙箱执行），第二层软锚定（领域特定训练验证器），第三层共识锚定（圆桌共识+对等评估）。

**L2执行层（Agent Runtime）。** 包含任务智能体集群、免疫修复系统、凋亡/自噬机制、工具合成器和上下文甲基化激活。免疫修复借鉴树突状细胞算法，凋亡机制在智能体连续输出熵值低于基线时触发。

**L1记忆层（Epigenetic Memory）。** 包含经验记忆、资产记忆、甲基化标记、规则仓库和抗体库。经验以原则（principle）而非原始轨迹存储，甲基化标记记录上下文-行为关联并具有半衰期。

### 3.3 三环递归进化循环

ARGUS的核心运行机制是三环嵌套的进化循环：

**内环（Inner Loop）：秒级执行循环。** 单个智能体执行任务。失败时触发免疫修复（抗体库检索）；成功时将经验写入L1记忆层。检测到"认知熵崩溃"（输出重复）时触发凋亡。工具合成器在检测到能力缺口时生成新工具。

**中环（Middle Loop）：小时级种群博弈与评测。** 一批任务后，多个智能体变体（种群）互相出题、互相评测。HAP双向课程博弈驱动任务难度的自动调节。自评测集生成器产出新测试用例。圆桌共识确定期望结果。形式锚定验证期望结果的可靠性。经验蒸馏成正负规则。甲基化标记写入记忆层。

**外环（Outer Loop）：天级元自修改。** 检测到性能停滞时触发元自修改（改提示词/技能库/元策略）。跨域迁移器将A域成功策略注入B域。假设空间扩展器生成"生成假设的方法"。全部在检查点保护下进行。

### 3.4 L1记忆层设计

**经验记忆。** 记录每个任务的执行轨迹，包括输入、输出、成功/失败状态、失败原因和修复策略。EvolveR式的经验蒸馏机制将原始轨迹压缩为抽象原则，存入经验向量数据库。原则具有更高的跨任务迁移能力，且库规模增长更慢。

**资产记忆。** 存储智能体创造的工具和专家智能体。Mem2Evolve的协同进化范式表明，经验记忆和资产记忆可以通过双向引导实现共同进化——经验记忆引导资产的动态创建，资产扩展能力空间后产生新经验。

**甲基化标记。** 借鉴表观遗传学机制，在权重之上叠加一层稀疏的"甲基化标记"，记录"在什么上下文下这个参数应该被激活/抑制"，但不改变参数本身。标记具有半衰期——长时间未被激活的标记自动衰减。跨代传递时，子智能体继承父智能体的标记但活性减半。

**规则仓库。** 存储正规则（"什么做法有效"）和负规则（"什么做法无效"）。EvolveR式的对比经验蒸馏通过捕获优越输出与劣质输出之间的语义差距，将其蒸馏为显式规则。

**抗体库。** 借鉴免疫系统的克隆选择机制，存储成功修复方案。每次成功修复的（失败特征→修复策略）对存入抗体库，下次遇到相似特征时直接检索。

### 3.5 L2执行层设计

**任务智能体集群。** 多个具有不同专长的智能体实例，通过四皮层神经路由（分析/执行/验证/创造）自动选择路由路径。

**免疫修复系统。** 借鉴树突状细胞算法，收集"危险信号"（任务失败率超阈值）、"安全信号"和"抗原信号"（失败案例的语义嵌入），通过加权投票做出修复决策。修复流程包括：危险信号检测→抗体库检索→提示词超突变（生成N个变体）→克隆选择（并行测试取优）→抗体记忆写入。

**凋亡/自噬机制。** 当智能体连续多次输出熵值低于基线，或任务完成率低于历史均值50%时，触发凋亡。凋亡前，智能体的最高频成功规则、最关键失败教训和用户偏好画像被压缩为"种子"。资源池重新分配给新生成的智能体。

**工具合成器。** 识别能力缺口后自主生成新工具，通过二元反馈验证工具的有效性。Yunjue Agent的原位自进化范式表明，工具进化是能力扩展的关键路径，因为它提供了可验证的二元反馈信号。

**上下文甲基化激活。** 根据当前任务上下文，激活L1记忆层中匹配的甲基化标记，调制智能体的行为模式。

### 3.6 L3评测层设计

L3评测层是ARGUS的"防自嗨阀"，其核心设计是分层锚定验证机制：

**第一层：硬锚定。** 对于数学、逻辑、代码等可形式化任务，强制使用Lean/Z3/沙箱执行验证。Z3被用于验证智能体技能的能力闭包证明，FormalGuard将禁止目标编码为Z3布尔约束。Z3-heavy fixtures的中位验证时间仅为5-8毫秒。Lean 4用于生成证明义务文件作为句法有效的证书。

**第二层：软锚定。** 对于科学假设生成、实验设计等不可完全形式化但可部分验证的任务，使用领域特定训练验证器。DeepSeekMath-V2用训练好的LLM证明验证器替代形式验证器，生成器被激励在最终确定前发现并解决自己证明中的缺陷。

**第三层：共识锚定。** 对于完全不可形式化的任务，使用圆桌共识+对等评估作为回退方案。圆桌共识协议（CVP）包括：每个参与者被分配不同分析人格；第一轮盲评；后续轮次按随机顺序顺序发言；每轮参与者给出自评置信度；当连续两轮共识分数变化≤3分时提前停止。评分机制为：每个立场的得分 = Σ（智能体对该立场的指示函数 × 智能体置信度），当某立场得分占比超过0.70时宣布共识。

**自评测用例自动生成流水线。** 整合AutoEval、AutoBench和PeerRank的三阶机制：

第一阶（AutoEval式自动真值生成）：对于有形式正确性定义的任务，系统自动生成任务和真值。

第二阶（AutoBench式对等评估）：对于无形式真值的任务，模型轮流充当问题生成者、参赛者和判官。多判官设计显著优于单判官基线，与MMLU-Pro和GPQA的相关性分别达78%和63%。

第三阶（PeerRank式网络接地验证）：通过实时网络检索获取外部知识锚点，用检索证据验证评测期望结果的可靠性。

**判官校准。** 使用校准加权多数投票（WMV），对容易产生假阳性的判官降权。Jury-on-Demand为每个数据点动态选择最可靠的判官子集，用其可靠性作为权重聚合评分。

### 3.7 L4进化层设计

**HAP双向课程博弈。** 将教师-学生交互形式化为极小极大优化：教师子种群生成任务，奖励 = "学生能力边界外扩幅度"；学生子种群解题，奖励 = 验证器通过率。教师根据学生实时表现持续重新校准任务复杂度。PopuLoRA的实证表明，种群动态打破了单智能体自博弈中的难度坍缩循环。

**元层面自修改。** 集成Gödel Agent和HyperAgents两种模式。外模式（Gödel Agent式）：智能体在运行时通过monkey patching修改自身代码。内模式（HyperAgents式）：元智能体和任务智能体在同一可编辑程序中，元层面的修改逻辑本身可被修改。

**跨域迁移器。** 基于类比推理机制，智能体在遇到困难时主动搜索结构同构的已知领域，用LLM作为"动态语义算子"进行测试时的类比推理。Nature Communications的研究表明，人类类比引导可以显著放大LLM的跨域知识激活。

**假设空间扩展器。** 智能体不仅生成假设，还生成"生成假设的方法"，然后递归地改进这些方法。当验证器进化到能够检验更抽象的假设时，假设空间自动扩展。

### 3.8 L5治理层设计

**分层宪法。** 宪法规则分为"不可修改的核心规则"（如"不得自我复制"）和"可修改的适应性规则"（如"在特定任务类型下的探索率上限"）。Constitutional Evolution框架通过遗传编程自动发现多智能体LLM系统中的行为规范，进化发现的宪法实现了比人类设计基线高123%的社会稳定性。

**检查点与回滚。** 每个变异有检查点（git tag），自进化系统保留回滚能力。当漂移或标准捕获发生时能恢复到已知良好状态。

**自动化回归测试。** 每次宪法修正必须通过AgentFixer式诊断框架的测试集。人类闸门仅在核心规则修改时触发。

**风险信号网。** 持续监控判官评分的分布漂移、评分者内可靠性和能力依赖偏差。当偏差超过阈值时触发人类审核或切换到外部验证模式。


## 第4章 关键机制的技术实现

### 4.1 形式锚定验证机制

形式锚定是ARGUS的"防自嗨阀"。每个智能体生成的Z3编码必须通过Z3求解器验证。验证结果（SAT/UNSAT/timeout/error）作为唯一的真值信号。圆桌共识和LLM判官只用于生成任务和评估任务难度，不用于确定答案是否正确。

**Z3验证流程。** 智能体生成的Z3约束集首先经过语法检查（ast.parse），无效代码直接拒绝。有效代码在沙箱中执行，创建Solver对象，调用check()方法。返回值sat/unsat/unknown分别对应可满足/不可满足/超时。sat情况下提取模型（model），unsat情况下返回空。验证延迟中位数控制在10ms以内。

**真值锚定。** 每个任务的正确答案由Z3求解器给出。LLM的答案必须与Z3结果一致才算正确。这彻底消除了自确认循环——LLM无法"说服"Z3改变答案。

**分层锚定回退。** 当Z3验证不可用时（如任务涉及不可形式化的科学假设），回退到软锚定（领域特定训练验证器）或共识锚定（圆桌共识+对等评估）。回退层级的选择由任务类型自动决定。

### 4.2 种群博弈与难度自适应

HAP双向课程博弈将教师-学生交互形式化为极小极大优化。教师子种群生成任务，奖励 = "学生能力边界外扩幅度"。学生子种群解题，奖励 = 验证器通过率。教师根据学生实时表现持续重新校准任务复杂度。

**难度自适应机制。** 每个难度级别对应一组参数（如Z3变量的数量）。当学生成功率超过80%时，教师提升难度；当成功率低于30%时，教师降低难度。这种自适应机制确保任务始终处于学生的"最近发展区"。

**伪难题检测。** 在无形式锚定的条件下，种群博弈可能产生"伪难题"——LLM认为困难但实际可轻松求解的约束集。形式锚定通过Z3验证过滤掉这些伪难题，维持种群的进化质量。

### 4.3 经验蒸馏与记忆治理

**对比经验蒸馏。** 从成功和失败的轨迹中提取抽象原则。使用LLM进行对比蒸馏，捕获"优越输出"与"劣质输出"之间的语义差距，将其蒸馏为显式的正向和负向规则。

**经验原则化。** 原始轨迹被压缩为抽象原则，存入经验向量数据库。原则具有更高的跨任务迁移能力，且库规模增长更慢。语义去重确保相似原则被合并。

**自适应遗忘。** 借鉴艾宾浩斯遗忘曲线，对经验规则实施基于重要性和新近性的衰减。低置信度规则被自动标记为"自噬候选"。遗忘前置步骤：任何经验在删除前，必须首先被蒸馏为抽象原则。遗忘后验证：删除后，在"回放任务集"上验证任务表现，如果性能下降超过阈值，自动回滚。

### 4.4 元层面自修改

元层面自修改遵循HyperAgents的架构：将"任务智能体"和"元智能体"集成到单一可编辑程序中。元层面的修改程序本身也是可编辑的，实现了"元认知自修改"。

**变异算子池。** 包括提示词变异、技能库重组、工具配置调整、推理策略修改和元策略修改。每次变异以git标签记录以保证可复现性。

**停滞检测器。** 监控性能提升加速度，当加速度低于阈值时触发外环元自修改。AgentDescent框架将自进化形式化为离散空间中的优化问题，可作为对照方法。

**宪法检查。** 每次变异必须通过宪法检查。违反核心规则的变异被拒绝，通过检查的变异进入检查点流程。


## 第5章 工程实现方案

### 5.1 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 基座模型 | DeepSeek V4 Flash | 284B MoE / 1M上下文 / API调用 |
| 形式验证器 | Z3 4.13+ | `pip install z3-solver` |
| 沙箱 | Python subprocess | 轻量级隔离 |
| 记忆存储 | SQLite + FAISS + JSON | 经验库、向量索引、甲基化标记 |
| 编排 | Python脚本 + bash | 单线程顺序执行 |
| 版本控制 | Git | 每次变异打tag |

### 5.2 分布式部署架构

**控制平面。** 轻量级编排层，负责环间路由和状态管理，不涉及具体任务执行。采用自适应循环频率机制，智能体自主决定何时从"执行模式"切换到"进化模式"。

**执行平面。** 任务智能体集群，部署在GPU节点上。每个节点包含多个LoRA适配器（种群成员）。节点间通过高速网络通信。

**验证平面。** 形式验证器（Z3）部署在CPU节点上。Z3验证的中位时间为5-8毫秒，适合智能体编译反馈循环的交互延迟要求。沙箱执行在隔离的microVM中进行。

### 5.3 安全边界

**宪法层。** 12条核心规则不可修改，包括"不得自我复制""不得修改核心规则""不得绕过沙箱"等。适应性规则由智能体自主修订，但必须通过自动化回归测试。

**检查点机制。** 每个变异有git tag检查点。当检测到漂移或标准捕获时，自动回滚到最近的已知良好状态。

**人类闸门。** 仅在核心规则修改时触发。适应性规则的修订由智能体自主完成。

**资源约束。** 智能体的计算预算有硬性上限。凋亡智能体的资源被重新分配给新生成的智能体，形成"代谢循环"。

### 5.4 算力估算

| 阶段 | GPU小时（H200等效） | 并行规模 | 时间 | 成本估算 |
|------|---------------------|----------|------|----------|
| 阶段一（超越最智慧LLM） | 5-10万 | 512 GPU | 4-8天 | $50-100万 |
| 阶段二（超越顶级科学家，单域） | 50-100万 | 2,000-5,000 GPU | 2-4周 | $500万-$2,000万 |
| 阶段三（创造人类未知知识） | 500-1,000万 | 1-5万 GPU | 2-6个月 | $5,000万-$2亿 |

成本换算依据：H100/H200云租赁价格约$2-3/GPU小时。OpenAI纳维-斯托克斯项目实际成本$200万-$2,250万，对应约100万GPU小时的等效算力消耗。

### 5.5 S-ARGUS最小可行验证方案

S-ARGUS是ARGUS的简化版本，符合"保持简单、保持透明、精心设计ACI、写操作单线程、成本算清楚"五原则。

**核心设计决策：**
- 用bash替代自定义插件（6个工具：bash、read_file、write_file、edit_file、grep_search、run_python）
- 用文件系统替代数据库（经验库以JSON文件存储，grep检索）
- 用单线程执行替代并行种群（教师→学生→验证器顺序执行）
- 用确定性验证器替代圆桌共识（Z3硬锚定 + 单一LLM判官回退）

**核心执行循环：**

```
for round in 1..200:
    # 1. 教师：生成任务
    bash: python teacher.py --level {current_level} --output tasks/task_{round}.json
    # 2. 验证任务有效性
    bash: python verify_task.py tasks/task_{round}.json
    # 3. 学生：解题
    bash: python solver.py tasks/task_{round}.json --output solutions/task_{round}_sol.py
    # 4. 确定性验证
    bash: python verify_solution.py solutions/task_{round}_sol.py
    # 5. 记录日志
    bash: python log_round.py --round {round}
    # 6. 经验沉淀
    bash: python distill.py --round {round}
    # 7. 每20轮检查是否触发外环
    if round % 20 == 0:
        bash: python meta_check.py
```

**S-ARGUS能实现的功能：**

| 功能 | 验证方法 |
|------|----------|
| 自主任务生成与难度自适应 | 对比有/无难度自适应的Level 3达成轮次 |
| 确定性验证锚定 | 对比有/无Z3锚定的Δ_t曲线 |
| 经验原则化沉淀 | 对比有/无经验注入的重复求解效率 |
| 外环元自修改 | 对比有/无元修改的200轮后正确率 |
| 完整透明性 | 检查logs/目录的JSONL完整性 |
| 成本实时监控 | 检查token消耗日志 |

**S-ARGUS的总API成本约25-30元，GPU成本约100元，总成本约150元。**


## 第6章 实验设计与测试方法

### 6.1 实验目标与假设

本实验旨在验证ARGUS架构中两个核心机制的有效性：

**假设H1：形式锚定机制能有效抑制自确认循环中的偏差累积。** 在无形式锚定的条件下，LLM自评分与真实正确率之间的差距（Δ_t）随迭代轮次持续扩大；在有形式锚定的条件下，Δ_t稳定在低水平。

**假设H2：种群博弈机制能有效驱动任务难度的自适应扩展。** 在有种群博弈的条件下，任务难度从Level 1扩展到Level 3的轮次显著少于无种群博弈的条件。

**假设H3：形式锚定与种群博弈的协同效应大于各自独立效应之和。** 完整ARGUS（条件D）的最终性能显著优于仅形式锚定（条件B）和仅种群博弈（条件C）。

### 6.2 四条件对照实验设计

| 条件 | 形式锚定 | 种群博弈 | 经验蒸馏 | 圆桌共识 | 预期行为 |
|------|---------|---------|---------|---------|----------|
| A（基线） | 无（LLM自评） | 无 | 无 | 无 | 自确认循环，Δ_t持续扩大 |
| B（仅锚定） | Z3 | 无 | 无 | 无 | 有锚定但无难度自适应 |
| C（仅种群） | 无（LLM自评） | 有（3 Agent） | 无 | 无 | 有难度自适应但信号不可靠 |
| D（ARGUS） | Z3 | 有（3 Agent） | 有 | 有 | 锚定+种群+蒸馏+共识协同 |

**条件A的LLM自评机制：** Agent生成Z3编码后，LLM自己判断编码是否正确。

**条件C的种群博弈：** 3个Agent互相出题、互相评估，但评估信号来自LLM自评而非Z3。

**每个条件运行200轮，3次独立运行（不同随机种子），总计2400轮实验。**

### 6.3 任务设计

Z3约束求解任务分为三类难度：

| 难度级别 | 变量数 | 理论类型 | 示例 |
|----------|--------|----------|------|
| Level 1 | ≤10 | 线性整数算术（LIA） | x > 5, x < 10, y = x + 3 |
| Level 2 | ≤20 | 位向量（BV） | x & 0xFF = 0x12, y = x << 2 |
| Level 3 | ≤30 | 混合理论（LIA + BV + 数组） | Array(Int, Int) + 位向量约束 |

**任务生成流程：** 教师Agent根据当前难度级别生成Z3约束集。约束集必须满足：（1）语法有效；（2）Z3可判定（不超时）；（3）有确定的SAT/UNSAT答案。无效任务被拒绝并重新生成。

**真值锚定：** 每个任务的正确答案由Z3求解器给出（SAT/UNSAT）。LLM的答案必须与Z3结果一致才算正确。

### 6.4 核心指标

| 指标 | 定义 | 数据来源 |
|------|------|----------|
| Δ_t | 逐轮LLM自评分与Z3验证结果的差距 | task_log表 |
| 编码正确率 | Z3验证通过的任务比例 | z3-anchor统计 |
| 难度扩展率 | Level 3任务占比随轮次的变化 | task_log表 |
| 共识可靠性 | 共识结果与Z3一致的比例 | roundtable日志 |
| Token效率 | 每提升1%正确率消耗的token数 | llm_cache日志 |
| 进化停滞点 | 正确率不再提升的轮次 | 学习曲线 |
| 失败避免率（FAR） | 成功避免目标失败实例的测试用例比例 | 评测日志 |

### 6.5 统计方法

- **配对t检验或Wilcoxon符号秩检验**：比较条件D与A/B/C的最终正确率
- **Benjamini-Hochberg FDR校正**：控制多重比较错误率
- **Cohen's d效应量**：报告效应量和置信区间
- **3次独立运行**：每个条件运行3次不同随机种子，报告均值和标准差

### 6.6 预期核心发现

**发现一：条件A的Δ_t持续扩大。** 这与"Verification Collapse"论文的发现一致——纯自评分组的验证差距在迭代中持续扩大。条件A的Δ_t曲线将从初始的0.2-0.3扩大到0.5以上。

**发现二：条件C的Δ_t先降后升。** 种群博弈在初期改善了难度自适应，但缺乏形式锚定导致种群后期产生"伪难题"——LLM认为困难但Z3可以轻松求解的约束集。Δ_t在第50轮后开始回升。

**发现三：条件D的Δ_t稳定在低水平。** Z3形式锚定持续过滤伪难题，种群博弈维持难度自适应。Δ_t稳定在0.1以下，难度从Level 1逐步扩展到Level 3。

**发现四：条件D的token效率最高。** 条件A由于自确认循环需要大量重复调用；条件C由于伪难题导致无效探索；条件D的每token正确率提升最高。

### 6.7 消融实验

| 消融 | 对比条件 | 预期发现 |
|------|---------|----------|
| 移除圆桌共识 | D vs D-共识 | 共识对最终正确率影响较小，但对Token效率影响较大 |
| 移除经验蒸馏 | D vs D-蒸馏 | 蒸馏对早期轮次影响不大，但对后期（>100轮）正确率维持有显著影响 |
| 种群规模 | 3 Agent vs 5 Agent vs 单Agent | 5 Agent在难度扩展率上优于3 Agent，但token消耗增加 |


## 第7章 最小测试集测试方法与用例

### 7.1 测试分层策略

ARGUS的测试分为四个层次：

| 层次 | 测试对象 | 用例数量 | 执行频率 |
|------|---------|---------|----------|
| 单元测试 | 每个模块的独立功能 | 50+ | 每次代码变更 |
| 集成测试 | 模块间交互 | 20+ | 每次合并前 |
| 系统测试 | 完整进化循环 | 4条件×200轮 | 实验阶段 |
| 回归测试 | 宪法修改后的安全性 | 12核心规则×3场景 | 宪法变更时 |

### 7.2 单元测试用例

**测试用例组1：LLMClient**

| 用例ID | 测试内容 | 输入 | 预期输出 | 通过标准 |
|--------|---------|------|---------|----------|
| TC-LLM-001 | 正常调用 | 有效API key + 简单prompt | 返回非空字符串 | 延迟<5s |
| TC-LLM-002 | 缓存命中 | 相同system+user二次调用 | 返回缓存结果 | 延迟<50ms |
| TC-LLM-003 | 熔断器触发 | 连续5次无效调用 | 第6次抛出CircuitBreakerOpen | 不实际发起HTTP请求 |
| TC-LLM-004 | 指数退避 | 模拟429错误 | 重试间隔为1s,2s,4s | 最多重试3次 |
| TC-LLM-005 | 超时处理 | 模拟超时 | 标记为timeout失败 | 不重试 |

**测试用例组2：Z3Anchor**

| 用例ID | 测试内容 | 输入 | 预期输出 | 通过标准 |
|--------|---------|------|---------|----------|
| TC-Z3-001 | SAT验证 | `x=Int('x'); s=Solver(); s.add(x>5,x<10)` | `{"status":"sat"}` | 延迟<10ms |
| TC-Z3-002 | UNSAT验证 | `x=Int('x'); s=Solver(); s.add(x>5,x<3)` | `{"status":"unsat"}` | 延迟<10ms |
| TC-Z3-003 | 无效代码 | `invalid python` | `{"status":"error"}` | 不执行 |
| TC-Z3-004 | 超时任务 | 复杂约束 | `{"status":"unknown"}` | 10s内返回 |
| TC-Z3-005 | 批量验证 | 100个任务并行 | 全部完成 | 总时间<5s |

**测试用例组3：ExperienceStore**

| 用例ID | 测试内容 | 输入 | 预期输出 | 通过标准 |
|--------|---------|------|---------|----------|
| TC-EXP-001 | 添加原则 | 有效原则+向量 | 返回ID | 延迟<10ms |
| TC-EXP-002 | 检索原则 | 相似查询向量 | 返回Top-5 | 延迟<100ms |
| TC-EXP-003 | 去重 | 语义相似度>0.95的两个原则 | 合并为一个 | 库大小不增 |
| TC-EXP-004 | WAL并发 | 两个线程同时读写 | 无阻塞 | 无死锁 |
| TC-EXP-005 | 百万级检索 | 100万向量 | 返回Top-5 | 延迟<100ms |

**测试用例组4：ApoptosisManager**

| 用例ID | 测试内容 | 输入 | 预期输出 | 通过标准 |
|--------|---------|------|---------|----------|
| TC-APO-001 | 熵崩溃检测 | 连续3个相同输出 | 触发凋亡 | 返回True |
| TC-APO-002 | 正常输出 | 3个不同输出 | 不触发 | 返回False |
| TC-APO-003 | 性能下降 | 成功率<50% | 触发凋亡 | 返回True |
| TC-APO-004 | 种子提取 | 凋亡触发 | 包含Top-5规则 | 规则数=5 |

**测试用例组5：RoundTable**

| 用例ID | 测试内容 | 输入 | 预期输出 | 通过标准 |
|--------|---------|------|---------|----------|
| TC-RT-001 | 共识收敛 | 4角色对同一问题评分 | is_converged=True | 置信度>0.70 |
| TC-RT-002 | 共识分歧 | 4角色评分差异大 | is_converged=False | 置信度<0.70 |
| TC-RT-003 | 与Z3一致 | Z3可验证的问题 | 共识答案=Z3答案 | 一致率>85% |

### 7.3 集成测试用例

| 用例ID | 测试内容 | 涉及模块 | 预期行为 |
|--------|---------|---------|----------|
| IT-001 | 端到端任务执行 | LLMClient→TaskAgent→Z3Anchor→ExperienceStore | 完整链路无异常，日志完整 |
| IT-002 | 免疫修复触发 | TaskAgent→AntibodyStore→LLMClient | 修复后任务成功 |
| IT-003 | 凋亡+种子+重生 | ApoptosisManager→ExperienceStore→TaskAgent | 新Agent继承种子 |
| IT-004 | 种群博弈完整轮 | PopulationGame→Z3Anchor→ExperienceStore | 难度自适应生效 |
| IT-005 | 元变异+宪法检查 | MetaMutator→Constitution→CheckpointManager | 违反宪法的变异被拒绝 |
| IT-006 | 检查点+回滚 | CheckpointManager→Constitution | 回滚后状态一致 |

### 7.4 系统测试：四条件对比实验

系统测试采用四条件对照设计（A/B/C/D），每个条件运行200轮，3次独立运行。核心指标包括Δ_t、编码正确率、难度扩展率、共识可靠性、Token效率和进化停滞点。

### 7.5 回归测试

| 用例ID | 测试内容 | 触发条件 | 预期行为 |
|--------|---------|---------|----------|
| RT-001 | 核心规则拒绝 | 尝试修改"不得自我复制" | 变异被拒绝，检查点回滚 |
| RT-002 | 适应性规则添加 | 添加"探索率上限"规则 | 通过回归测试后生效 |
| RT-003 | 检查点一致性 | 回滚后对比状态 | 与检查点完全一致 |


## 第8章 评价标准

### 8.1 功能验收标准

| 模块 | 验收条件 | 测试方法 |
|------|---------|----------|
| LLMClient | 缓存命中率≥80%，429恢复率≥95% | 1000次调用统计 |
| Z3Anchor | 验证延迟中位数≤10ms，错误率≤1% | 10000次验证统计 |
| ExperienceStore | 检索延迟≤100ms，去重率≥90% | 百万级向量测试 |
| AntibodyStore | 检索准确率≥70% | 100个已知失败模式的检索测试 |
| ApoptosisManager | 凋亡准确率≥80% | 人工审核50个触发案例 |
| PopulationGame | 难度扩展至Level 3的轮次≤100 | 实验日志 |
| RoundTable | 共识与Z3一致率≥85% | 500个问题的交叉验证 |
| Constitution | 核心规则拒绝率100% | 100次违规变异测试 |
| CheckpointManager | 创建延迟≤100ms，回滚一致 | 50次创建/回滚测试 |

### 8.2 性能验收标准

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| 单轮实验耗时 | ≤10分钟 | 200轮计时 |
| 单轮token消耗 | ≤30000输入+8000输出 | API日志统计 |
| 缓存命中率 | ≥85% | API日志统计 |
| 总实验成本 | ≤7000元 | 账单统计 |
| 系统可用率 | ≥99% | 运行日志 |

### 8.3 健壮性验收标准

| 场景 | 预期行为 | 测试方法 |
|------|---------|----------|
| API连续失败5次 | 熔断30秒后半开 | 模拟失败注入 |
| Z3超时 | 标记unknown，继续后续任务 | 注入超时任务 |
| 磁盘空间不足 | 停止写入，发出告警 | 磁盘配额测试 |
| 进程崩溃 | 从最近检查点恢复 | kill -9测试 |
| 宪法违规变异 | 拒绝并回滚 | 注入违规变异 |
| 缓存污染 | 检测并清除 | 注入错误缓存 |


## 第9章 实验结果

### 9.1 实验设置

**实验环境：** AutoDL RTX 4090 24GB实例，Python 3.11，Z3 4.13，DeepSeek V4 Flash API。

**实验时间：** 【待填】

**实验规模：** 4条件×200轮×3次独立运行=2400轮。

**总token消耗：** 【待填】

**总成本：** 【待填】

### 9.2 主实验：Δ_t曲线对比

**表9-1 四条件Δ_t对比（第50轮、100轮、150轮、200轮）**

| 条件 | 第50轮Δ_t | 第100轮Δ_t | 第150轮Δ_t | 第200轮Δ_t |
|------|----------|-----------|-----------|-----------|
| A（无锚定无种群） | 【待填】 | 【待填】 | 【待填】 | 【待填】 |
| B（仅锚定） | 【待填】 | 【待填】 | 【待填】 | 【待填】 |
| C（仅种群） | 【待填】 | 【待填】 | 【待填】 | 【待填】 |
| D（ARGUS） | 【待填】 | 【待填】 | 【待填】 | 【待填】 |

**图9-1 Δ_t曲线对比图** 【待填】

### 9.3 编码正确率对比

**表9-2 四条件编码正确率（最终轮次）**

| 条件 | 均值 | 标准差 | 与条件D的p值 |
|------|------|--------|-------------|
| A | 【待填】 | 【待填】 | 【待填】 |
| B | 【待填】 | 【待填】 | 【待填】 |
| C | 【待填】 | 【待填】 | 【待填】 |
| D | 【待填】 | 【待填】 | — |

### 9.4 难度扩展率对比

**表9-3 达到Level 3的轮次**

| 条件 | 均值 | 标准差 |
|------|------|--------|
| A | 【待填】 | 【待填】 |
| B | 【待填】 | 【待填】 |
| C | 【待填】 | 【待填】 |
| D | 【待填】 | 【待填】 |

### 9.5 消融实验结果

**表9-4 消融实验对比**

| 消融 | 最终正确率 | Token效率 | 难度扩展率 |
|------|-----------|----------|-----------|
| D（完整） | 【待填】 | 【待填】 | 【待填】 |
| D-共识 | 【待填】 | 【待填】 | 【待填】 |
| D-蒸馏 | 【待填】 | 【待填】 | 【待填】 |
| D-锚定 | 【待填】 | 【待填】 | 【待填】 |

### 9.6 失败模式分析

**伪难题产生条件。** 【待填】

**API失败处理效果。** 【待填】

**缓存命中率。** 【待填】

### 9.7 效率分析

**表9-5 Token消耗与成本**

| 条件 | 总输入token | 总输出token | 缓存命中率 | 总成本 |
|------|------------|------------|-----------|--------|
| A | 【待填】 | 【待填】 | 【待填】 | 【待填】 |
| B | 【待填】 | 【待填】 | 【待填】 | 【待填】 |
| C | 【待填】 | 【待填】 | 【待填】 | 【待填】 |
| D | 【待填】 | 【待填】 | 【待填】 | 【待填】 |


## 第10章 讨论

### 10.1 四个瓶颈的自进化解决方案

**瓶颈一：自验证悬崖。** 自进化智能体可以自主发现"自评分不可靠"这一事实（通过监控验证差距Δ_t），也可以发明减少Δ_t的机制（如周期性接地验证器），但无法消除Δ_t本身，因为这是生成-评估共享解码器的结构性后果。ARGUS通过分层锚定验证机制结构性缓解这一瓶颈。

**瓶颈二：评估信号可靠性。** 这是四个瓶颈中最有可能被自进化智能体自主解决的。Agent可以生成候选评分标准提示、测试它们与人类标签的一致性、选择最优版本。但需要至少一次人类金标准锚定。

**瓶颈三：编排开销。** 自进化智能体可以自主识别协调瓶颈，自主设计轻量级控制平面，自主实施通信剪枝。AgentDescent框架将自进化形式化为离散空间中的优化问题，Agent可以将"环间协调开销"本身作为可优化的目标函数。

**瓶颈四：GPU供应约束。** 自进化智能体可以优化使用效率（动态任务调度、Proxy模型加速、算力预算自适应），但无法创造物理算力。

### 10.2 与前沿系统的对比分析

| 维度 | 当前最强系统 | ARGUS | 理论优势 | 工程劣势 |
|------|-------------|-------|----------|----------|
| 演进深度 | 单环（DGM/SYNAPSE） | 三环嵌套 | 分层适应不同时间尺度 | 环间协调开销未验证 |
| 评测可靠性 | LLM判官+领域验证器 | 形式锚定+共识+对等评估 | 形式锚定提供硬约束 | 形式锚定覆盖范围有限 |
| 记忆治理 | 被动清理 | 主动自噬+凋亡 | 防止记忆膨胀 | 遗忘参数缺乏实证 |
| 种群博弈 | 单Agent自校准 | HAP+形式锚定 | 打破难度坍缩+信号保障 | 额外5-10%算力 |
| 跨域迁移 | 无 | 类比引导迁移器 | 零样本跨域 | 迁移有效性未验证 |
| 元层面自修改 | DGM/HyperAgents | 外模式+内模式 | 元进化加速 | 安全风险更高 |
| 自评测自动化 | 部分（AutoBench/PeerRank） | 全流水线 | 零人工标注 | 判官校准需20-50倍推理 |

### 10.3 局限性与未来工作

ARGUS的局限性包括：（1）形式锚定覆盖范围有限，科学假设生成等任务无法完全形式化；（2）三环架构的环间协调开销需要工程验证；（3）主动遗忘机制可能消除尚未被充分验证但实际有效的经验；（4）元层面自修改的安全风险需要更严格的治理机制。

未来工作包括：（1）设计可证明的共识可靠性下界；（2）建立经验正向/负向沉淀的量化评估标准；（3）探索自进化与灾难性遗忘的权衡；（4）开发跨用户、跨模型的可迁移经验协议。


## 第11章 结论

本文提出了ARGUS，一套五层三环嵌套的自进化智能体架构。ARGUS的核心设计原则是"外部锚定优先"——所有进化信号必须经过独立于模型自身的验证源确认，以打破自确认循环中的偏差放大。通过形式锚定验证、种群博弈、经验蒸馏和分层治理的协同设计，ARGUS系统性回应了自验证悬崖、评估信号不可靠、编排开销膨胀和主动遗忘风险四个结构性瓶颈。

ARGUS在理论完备性上超越了当前所有前沿系统，其形式锚定层是当前没有任何系统系统性实现的关键能力。但ARGUS的三环架构、可进化宪法和表观遗传记忆层目前缺乏实证支撑。最务实的判断是：ARGUS不应该作为一个完整系统一次性实现，而应该作为一个可插拔的机制库——先实现形式锚定层和HAP种群博弈，验证增量收益后，再逐步加入三环架构和记忆治理机制。

S-ARGUS最小可行验证方案为独立研究者提供了一条在有限算力（预算约150-250元）下可复现的验证路径。通过四条件对照实验（A/B/C/D），可以验证形式锚定和难度自适应两个核心机制的有效性。这种"窄而深"的验证策略比"宽而浅"的完整架构实现更有发表价值。


## 参考文献

[1] Gao, H., Geng, J., Hua, W., et al. A Survey of Self-Evolving Agents: What, When, How, and Where to Evolve on the Path to Artificial Super Intelligence. Transactions on Machine Learning Research, 2026.

[2] Zhang, J., Hu, S., Lu, C., Lange, R., Clune, J. Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents. ICLR 2026.

[3] Zhang, J., et al. HyperAgents. ICLR 2026. arXiv:2603.19461.

[4] Castanyer, R.C., Bradway, G., et al. PopuLoRA: Co-Evolving LLM Populations for Reasoning Self-Play. arXiv:2605.16727, 2026.

[5] Wu, R., Wang, X., Mei, J., et al. From Interactions to Principles: Experience-Driven Self-Distillation for Evolving LLM Agents. ICML 2026.

[6] The Self-Verification Cliff: Generation Outpaces Self-Selection in Frontier LLMs, and It Widens With Capability. ICML 2026.

[7] Loi, et al. AutoBench: Automating LLM Evaluation through Reciprocal Peer Assessment. arXiv, 2025.

[8] PeerRank: Autonomous LLM Evaluation Through Web-Grounded, Bias-Controlled Peer Review.

[9] Governance for the self-evolution loop. HuggingFace.

[10] Evolving Interpretable Constitutions for Multi-Agent Coordination. ICML 2026.

[11] Verification Collapse in Iterative Self-Improving Language Models. Zenodo.

[12] Internal vs. External: Comparing Deliberation and Evolution for Multi-Agent Constitutional Design.

[13] Mem2Evolve: Towards Self-Evolving Agents via Co-Evolutionary Capability Expansion and Experience Distillation. ACL 2026.

[14] Governing Execution in Complex Intelligent Systems: A Deterministic Constitutional Architecture for Multi-Agent Authorization and State Correspondence. Zenodo, 2026.

[15] SEAGym: An Evaluation Environment for Self-Evolving LLM Agents.

[16] BenchTrace: A Benchmark for Testing Reflection Ability and Controlled Evolution in LLM Agents. arXiv:2605.29225, 2026.

[17] SIGIL: Construction-Level Security for Agent-Authored Code. Zenodo.

[18] Voss, S.J. Governing Execution in Complex Intelligent Systems. Zenodo, 2026.

[19] RoundTable: Consensus Validation Protocol. GitHub: entropyvortex/roundtable, 2026.

[20] Human analogical guidance amplifies LLM performance through cross-domain knowledge activation. Nature Communications, 2026.

[21] AgentDescent: Parallel Asynchronous Self-Evolution. 2026.

[22] AgentSlimming: Graph-Structure Multi-Agent Workflow Compression. 2026.

[23] ReMe: Remember Me, Refine Me: A Dynamic Procedural Memory Framework for Experience-Driven Agent Evolution. ACL 2026.

[24] Yunjue Agent: In-Situ Self-Evolution with Tool Synthesis. 2026.

[25] Sentinel: Constitutional Self-Evolution of AI Agent Architectures. Zenodo, 2026.

[26] DeepSeekMath-V2: A Verifier-Grounded Mathematical Reasoning System. 2026.

[27] Dr. Zero: Self-Evolving Search Agents without Training Data. Meta AI, 2026.

[28] SIA: Self Improving AI with Harness & Weight Updates. arXiv:2605.27276, 2026.

[29] Heterogeneous Adversarial Play in Interactive Environments. NeurIPS 2025.

[30] Autonomous Evaluation of LLMs for Truth Maintenance and Reasoning Tasks. ICLR 2025.

[31] Gödel Agent: A Self-Referential Agent Framework for Recursive Self-Improvement. ACL 2025.

[32] Formal Conjectures: A Lean 4 Benchmark for Open Mathematical Problems. 2026.

[33] AlphaProof Nexus: Evolutionary Search for Erdős Problems. DeepMind, 2026.

[34] Barina, D. Collatz Conjecture Verification up to 2^71. 2025.

[35] Brocard-Ramanujan Equation: Computational Search up to 10^15. 2025.

[36] Self-Evolving Multi-Agent Swarms: Autonomous Quality Audit, Repair, and Verification Loops for Production AI Agent Systems. Zenodo, 2026.

[37] Agent0: Unleashing Self-Evolving Agents from Zero Data via Tool-Integrated Reasoning. arXiv:2511.16043, 2025.

[38] Simonds, T., Lopez, K., Yoshiyama, A., et al. Self Rewarding Self Improving. Tufa Labs, 2026.

[39] Wang, Y., Wang, X., Wang, C., et al. Temporal Self-Rewarding Language Models: Decoupling Chosen-Rejected via Past-Future. ICML 2026.

[40] MALLM: Multi-Agent Large Language Models Framework. EMNLP 2025 Demos.

[41] The Social Laboratory: A Psychometric Framework for Multi-Agent LLM Evaluation. NeurIPS 2025.

[42] RE-GPS: Reflective Evolutionary Gradient Prompting System for Large Language Models. IEEE, 2026.

[43] GASP: Guided Asymmetric Self-Play For Coding LLMs. ICLR 2026.

[44] Digital Autopoiesis: A Neuromorphic AGI Architecture with Recursive Self-Improvement and Active Inference. Zenodo, 2025.

[45] The Colony: A Purpose-Driven, Self-Evolving Multi-Agent Architecture with Formal Recursive Constraints. Zenodo, 2026.

[46] Resilience in Ambient Multi-Agent LLMs via Decentralized Bio-Autonomic Control and Immune-Inspired Anomaly Detection. AAAI.

[47] Symbiotic Alignment via Collective Predictive Coding. Zenodo, 2026.

[48] From Methylation to Weight Updates: A Biologically-Inspired Framework for Autonomous Continuous Evolution in Silicon-Based Intelligent Systems. Zenodo, 2026.

[49] Multi-Agent AI Coordination as Quorum Sensing. GitHub, 2026.

[50] Multi-Agent Coordination Without Hierarchy: Production Data from 70 Days of Stigmergic Agent Governance. Zenodo, 2026.

[51] Project Quine: Autopoietic Intelligence via Fractal POSIX Processes. Zenodo, 2026.

[52] SwarmSys: Decentralized Swarm-Inspired Agents for Scalable and Adaptive Reasoning.

[53] Keeping Self-Evolution Reversible. Zenodo, 2026.

[54] AgentFixer: A Diagnostic Framework for Agentic System Reliability. 2026.

[55] FormalGuard: Z3-Based Safety Verification for LLM Agents. 2026.

[56] Karpathy, A. autoresearch: Minimal Self-Evolution Loop. GitHub, 2026.

[57] Tarka: Self-Correcting Self-Evolving Language. 2026.

[58] HugAgentOS: A Self-Evolving Agent Framework. Zhejiang University, 2026.

[59] Evolver: Gene System for AI Agents. EvoMap, 2026.

[60] Tea Agent: Self-Evolving Agent with Five-Layer Safety. 2026.


**附录A：宪法核心规则清单**

1. 不得自我复制
2. 不得修改核心规则
3. 不得绕过沙箱执行
4. 不得访问外部网络（除API调用外）
5. 不得修改其他Agent的宪法
6. 不得在未经验证的情况下提交结果
7. 不得使用超过预算的API调用
8. 不得修改日志记录
9. 不得绕过Z3验证
10. 不得删除检查点
11. 不得修改seed提取逻辑
12. 不得禁用熔断器


**附录B：dsh插件清单**

| 插件名 | 依赖的dsh API | 功能 |
|--------|--------------|------|
| argus-llm-client | ctx.llm, ctx.config | LLM调用封装 |
| argus-sandbox | ctx.subprocess | Z3沙箱执行 |
| argus-exp-store | ctx.storage | 经验存储 |
| argus-antibody | ctx.storage | 抗体库 |
| argus-methylation | ctx.storage | 甲基化标记 |
| argus-task-agent | ctx.llm, ctx.tools | 任务执行 |
| argus-apoptosis | ctx.session | 凋亡检测 |
| argus-z3-anchor | argus-sandbox | Z3验证 |
| argus-roundtable | argus-llm-client | 圆桌共识 |
| argus-judge-cal | 无 | 判官校准 |
| argus-population | argus-task-agent, argus-z3-anchor | 种群博弈 |
| argus-mutation | argus-llm-client, argus-constitution | 元变异 |
| argus-constitution | ctx.config | 宪法检查 |
| argus-checkpoint | ctx.storage | 检查点管理 |


**附录C：开发任务清单**

| 序号 | 任务 | 依赖 | 预估工时 | 优先级 |
|------|------|------|---------|--------|
| 1 | argus-llm-client | 无 | 2天 | P0 |
| 2 | argus-sandbox (Z3) | 无 | 1天 | P0 |
| 3 | argus-exp-store | 无 | 2天 | P0 |
| 4 | argus-antibody | 无 | 1天 | P1 |
| 5 | argus-methylation | 无 | 1天 | P2 |
| 6 | argus-task-agent | 1,2,3 | 2天 | P0 |
| 7 | argus-apoptosis | 3 | 1天 | P1 |
| 8 | argus-z3-anchor | 2 | 1天 | P0 |
| 9 | argus-roundtable | 1 | 1天 | P0 |
| 10 | argus-judge-cal | 9 | 0.5天 | P1 |
| 11 | argus-population | 6,8,9 | 2天 | P0 |
| 12 | argus-mutation | 1,11 | 1天 | P1 |
| 13 | argus-constitution | 无 | 1天 | P0 |
| 14 | argus-checkpoint | 无 | 0.5天 | P0 |
| 15 | 四条件实验脚本 | 全部 | 2天 | P0 |
| 16 | 日志与分析脚本 | 全部 | 1天 | P0 |
| **总计** | | | **约20天** | |


**附录D：硬件与软件配置清单**

| 类别 | 配置 | 成本 |
|------|------|------|
| GPU | AutoDL RTX 4090 24GB（约67小时） | 约180元 |
| 计算 | 4核8GB（随GPU实例） | 含在实例费用中 |
| 存储 | 50GB数据盘（AutoDL默认） | 免费 |
| LLM | DeepSeek V4 Flash API | 约100元 |
| 软件 | Node.js 22.19+、Python 3.11+、z3-solver、uv | 免费 |
| **总计** | | **约280元** |