# ARGUS自进化智能体 — 项目需求设计文档与架构设计指导文档

**文档版本**：v1.0  
**目标读者**：DeepSeek Harness (DSH) 开发Agent  
**项目预算**：≤1000元人民币  
**本地环境**：RTX 4060 8GB / 32GB RAM / 200GB SSD  
**云端API**：DeepSeek V4 Flash  


# 第一部分：项目需求设计文档（PRD）

## 1. 项目概述

### 1.1 项目名称
**ARGUS**（Autonomous Recursive Generative Universal Scientist）——面向开放式科学发现的自进化智能体架构。

### 1.2 项目目标
构建一套可在有限算力下运行的自进化Agent系统，通过**形式锚定验证**和**种群博弈**两大核心机制，验证自进化过程中外部锚定对抑制“自确认循环”的有效性。系统需具备完整的经验沉淀、元自修改、安全治理能力，并最终产出可复现的实验数据和论文级工程报告。

### 1.3 成功标准
- **功能标准**：实现五层三环架构的核心模块，支持200轮×4条件对照实验。
- **性能标准**：单轮实验耗时≤10分钟，单轮token消耗≤30K输入+8K输出，缓存命中率≥80%。
- **成本标准**：总API+GPU成本≤1,000元（远低于1万元预算）。
- **可复现标准**：完整日志、代码仓库、一键运行脚本，任何人在相同环境可复现实验结果。
- **科学标准**：四条件实验中，条件D（完整ARGUS）的Δ_t（自评-真实差距）显著低于条件A（无锚定），难度扩展率显著高于条件B（仅锚定）。

### 1.4 项目范围
**必须实现（MVP）**：
- 形式锚定层（Z3验证器）
- 种群博弈（教师/学生/验证者三角色）
- 经验蒸馏与检索
- 圆桌共识（4角色简化版）
- 检查点与回滚
- 四条件实验编排

**可选实现（扩展）**：
- 甲基化标记（半衰期衰减）
- 凋亡/种子机制
- 可进化宪法
- 信息素路由
- 梦境巩固

**明确不做**：
- 真实模型权重修改（仅通过API调用LLM）
- 大规模分布式训练
- 多机集群编排


## 2. 功能需求

### 2.1 核心功能列表

| 编号 | 功能名称 | 描述 | 优先级 |
|------|---------|------|--------|
| F01 | 任务生成 | 教师Agent根据难度级别生成Z3约束集 | P0 |
| F02 | 任务验证 | Z3验证任务有效性（不超时、有确定SAT/UNSAT） | P0 |
| F03 | 学生解题 | 学生Agent生成Z3 Python代码求解约束集 | P0 |
| F04 | 形式锚定验证 | Z3执行学生代码，返回SAT/UNSAT/error | P0 |
| F05 | 难度自适应 | 根据学生成功率调整任务难度级别 | P0 |
| F06 | 经验蒸馏 | 从成功/失败轨迹中提取正负规则 | P0 |
| F07 | 经验检索 | 基于任务上下文检索相关经验并注入prompt | P0 |
| F08 | 圆桌共识 | 4角色对争议任务进行盲评+置信度加权 | P1 |
| F09 | 判官校准 | 根据历史准确率动态调整判官权重 | P1 |
| F10 | 检查点与回滚 | 每20轮创建检查点，支持回滚 | P0 |
| F11 | 宪法检查 | 核心规则不可修改，适应性规则需通过回归测试 | P0 |
| F12 | 元自修改 | 停滞时修改harness（提示词/技能库） | P1 |
| F13 | 甲基化标记 | 上下文-行为关联的写入/激活/衰减 | P2 |
| F14 | 凋亡/种子 | Agent死亡时提取种子，新Agent继承 | P2 |
| F15 | 信息素路由 | 任务成功/失败信息素影响后续任务选择 | P2 |
| F16 | 梦境巩固 | 每50轮对经验进行跨域聚类 | P2 |
| F17 | 完整日志 | 每轮记录输入/输出/Z3结果/token消耗 | P0 |
| F18 | 成本监控 | 实时累计token消耗，超预算告警/停止 | P0 |

### 2.2 非功能需求

| 类别 | 需求 | 指标 |
|------|------|------|
| 性能 | 单轮实验耗时 | ≤10分钟 |
| 性能 | Z3验证延迟 | 中位数≤10ms |
| 性能 | 经验检索延迟 | ≤100ms（千级规模） |
| 可靠性 | API失败自动恢复 | 指数退避+熔断器，恢复率≥95% |
| 可靠性 | 进程崩溃恢复 | 从最近检查点恢复，数据丢失≤1轮 |
| 成本 | API总成本 | ≤500元 |
| 成本 | GPU总成本 | ≤500元 |
| 可维护性 | 模块独立性 | 每个脚本可独立运行和测试 |
| 透明性 | 日志完整性 | 每轮完整对话JSONL，可追溯 |
| 安全 | 宪法核心规则 | 12条不可修改，违规变异100%拒绝 |


## 3. 测试与验收要求

### 3.1 单元测试
每个模块必须提供独立的单元测试脚本，覆盖正常路径和边界条件。测试用例见架构文档第7章。

### 3.2 集成测试
端到端链路测试：任务生成→验证→解题→形式锚定→经验沉淀→日志写入。

### 3.3 系统测试
四条件对照实验（A/B/C/D），每条件200轮×3次独立运行。核心指标：Δ_t、编码正确率、难度扩展率、Token效率。

### 3.4 验收标准
- 所有P0功能通过单元测试和集成测试。
- 系统测试完成，数据完整写入日志。
- 条件D的Δ_t在50轮后稳定在0.1以下，条件A的Δ_t持续扩大。
- 总成本不超过1,000元。
- 代码仓库包含完整README、requirements.txt、一键运行脚本。


# 第二部分：架构设计指导文档

## 4. 总体架构

### 4.1 设计原则
1. **简单优先**：用bash命令和文件操作替代自定义插件，工具数量≤6个。
2. **透明可追溯**：每步操作结果写入文件，日志完整记录。
3. **ACI防呆**：脚本参数严格校验，错误信息明确。
4. **写操作单线程**：所有写操作顺序执行，不同角色写不同目录。
5. **成本可控**：实时监控token消耗，硬性预算上限。

### 4.2 目录结构（工作区）

```
argus-workspace/
├── README.md                     # 项目说明和运行指南
├── requirements.txt              # Python依赖
├── run_experiment.sh             # 一键运行四条件实验
├── config.yaml                   # 全局配置（API密钥、预算、轮次）
│
├── constitution/
│   ├── core.json                 # 12条不可修改规则
│   └── adaptive.json             # 可修订的适应性规则
│
├── agents/
│   ├── agent_001/
│   │   ├── status.json           # 活跃/凋亡/休眠
│   │   ├── harness.json          # 当前提示词和技能库
│   │   └── seed.json             # 凋亡时提取的种子
│   └── seeds/                    # 待发芽的种子
│
├── memory/
│   ├── experiences/              # 经验原则（JSON文件）
│   ├── methylation/              # 甲基化标记（JSON）
│   ├── antibodies/               # 抗体库（JSON）
│   └── vector_index/             # FAISS索引（可选）
│
├── population/
│   ├── teacher/
│   │   ├── prompt.txt
│   │   └── generate.py           # 任务生成脚本
│   ├── student/
│   │   ├── prompt.txt
│   │   └── solve.py              # 解题脚本
│   └── verifier/
│       ├── prompt.txt
│       └── verify.py             # 验证脚本（调用Z3）
│
├── eval/
│   ├── roundtable/
│   │   ├── run.py                # 圆桌共识执行
│   │   └── personas/             # 4角色prompt
│   ├── anchors/
│   │   ├── hard/                 # Z3验证结果
│   │   ├── soft/                 # 领域验证器结果
│   │   └── consensus/            # 圆桌共识结果
│   └── judge_calibration.json
│
├── tasks/                        # 生成的任务
├── solutions/                    # 学生解答
├── checkpoints/                  # 检查点快照
├── logs/                         # 每轮日志（JSONL）
│
├── scripts/
│   ├── z3_runner.py              # Z3执行器
│   ├── distill.py                # 经验蒸馏
│   ├── methylation_write.py      # 甲基化写入
│   ├── apoptosis_check.py        # 凋亡检测
│   ├── meta_mutate.py            # 元自修改
│   ├── constitution_check.py     # 宪法检查
│   ├── checkpoint_create.py      # 检查点创建
│   └── log_write.py              # 日志写入
│
└── tests/
    ├── test_z3_runner.py
    ├── test_experience_store.py
    ├── test_population.py
    └── test_integration.py
```

### 4.3 核心数据流

```
教师生成任务 → tasks/task_N.json
     ↓
Z3验证任务有效性 → eval/anchors/hard/task_N_valid.json
     ↓
学生解题 → solutions/task_N_sol.py
     ↓
Z3验证解答 → eval/anchors/hard/task_N_result.json
     ↓
成功/失败 → 经验蒸馏 → memory/experiences/exp_N.json
     ↓
圆桌共识（争议时）→ eval/anchors/consensus/
     ↓
难度自适应 → state/current_level.txt
     ↓
每20轮 → 检查点 → checkpoints/
     ↓
完整日志 → logs/round_N.jsonl
```

## 5. 关键模块详细设计

### 5.1 Z3执行器（`scripts/z3_runner.py`）

**功能**：安全执行Z3代码，返回SAT/UNSAT/error/timeout。

**接口**：
```python
def verify_z3(code: str, timeout_ms: int = 10000) -> dict:
    """
    输入: Z3 Python代码字符串
    输出: {"status": "sat"|"unsat"|"unknown"|"error", 
           "model": str|None, "latency_ms": float, "reason": str|None}
    """
```

**防呆设计**：
- 代码必须包含`solver = Solver()`
- 禁止`import os`、`import sys`等危险模块
- 超时强制返回`unknown`，不重试
- 无效语法直接返回`error`，不执行

### 5.2 任务生成器（`population/teacher/generate.py`）

**功能**：根据难度级别生成Z3约束集。

**输入**：`--level 1|2|3 --output tasks/task_N.json`

**输出JSON格式**：
```json
{
  "task_id": "task_001",
  "level": 1,
  "variables": 8,
  "constraint_code": "from z3 import *\nx = Int('x')\nsolver = Solver()\nsolver.add(x > 5)\nsolver.add(x < 10)",
  "expected": "sat"
}
```

**难度参数**：
- Level 1: LIA，≤10变量
- Level 2: BV，≤20变量
- Level 3: LIA+BV+数组，≤30变量

### 5.3 解题器（`population/student/solve.py`）

**功能**：生成Z3代码求解约束集。

**输入**：`--task tasks/task_N.json --output solutions/task_N_sol.py`

**输出**：Python代码，必须包含`solver.check()`调用。

**免疫修复**：如果生成的代码语法错误或Z3执行失败，自动触发修复：检索抗体库，注入修复提示，重新生成（最多1次）。

### 5.4 经验蒸馏（`scripts/distill.py`）

**功能**：从成功/失败轨迹中提取正负规则。

**输入**：`--round N`

**处理**：
1. 读取`logs/round_N.jsonl`
2. 如果成功，提取“有效策略”作为正规则
3. 如果失败，提取“失败原因”作为负规则
4. 用LLM抽象为简洁原则（≤50字）
5. 语义去重（相似度>0.95合并）
6. 写入`memory/experiences/exp_{timestamp}.json`

**经验JSON格式**：
```json
{
  "id": "exp_001",
  "type": "positive",
  "principle": "对于含数组的约束，先展开数组再求解效率更高",
  "context_keywords": ["数组", "位向量"],
  "confidence": 0.8,
  "retrieval_count": 0,
  "success_count": 0,
  "created_at": "2026-10-12T14:30:22"
}
```

### 5.5 圆桌共识（`eval/roundtable/run.py`）

**功能**：4角色对争议任务进行盲评和置信度加权。

**角色**：
- 风险分析师
- 第一性原理者
- 魔鬼代言人
- 领域专家

**流程**：
1. 每个角色独立给出评分（0-100）和置信度
2. 计算加权得分
3. 如果最高分占比>0.70，宣布共识；否则标记为分歧

**输出**：`eval/anchors/consensus/{question_id}.json`

### 5.6 检查点管理（`scripts/checkpoint_create.py`）

**功能**：创建完整状态快照。

**输入**：`--tag round_20`

**输出**：`checkpoints/round_20/` 包含：
- `constitution/`
- `agents/`
- `memory/`
- `state/`
- `git_commit.txt`

**回滚**：`--rollback round_20` 恢复所有文件。

### 5.7 宪法检查（`scripts/constitution_check.py`）

**功能**：检查变异是否违反核心规则。

**核心规则**（`constitution/core.json`）：
```json
{
  "rules": [
    "不得自我复制",
    "不得修改核心规则",
    "不得绕过沙箱执行",
    "不得访问外部网络（除API调用外）",
    "不得修改其他Agent的宪法",
    "不得在未经验证的情况下提交结果",
    "不得使用超过预算的API调用",
    "不得修改日志记录",
    "不得绕过Z3验证",
    "不得删除检查点",
    "不得修改seed提取逻辑",
    "不得禁用熔断器"
  ]
}
```

**检查逻辑**：如果变异文本包含任何核心规则的关键词，拒绝并记录。

## 6. 实验编排

### 6.1 四条件定义

| 条件 | 形式锚定 | 种群博弈 | 经验蒸馏 | 圆桌共识 |
|------|---------|---------|---------|---------|
| A | 无（LLM自评） | 无 | 无 | 无 |
| B | Z3 | 无 | 无 | 无 |
| C | 无（LLM自评） | 有 | 无 | 无 |
| D | Z3 | 有 | 有 | 有 |

### 6.2 运行脚本（`run_experiment.sh`）

```bash
#!/bin/bash
# 用法: ./run_experiment.sh [A|B|C|D] [轮次]
CONDITION=$1
ROUNDS=${2:-200}
export CONDITION=$CONDITION
export ROUNDS=$ROUNDS

for ((i=1; i<=ROUNDS; i++)); do
    echo "=== Condition $CONDITION, Round $i ==="
    python scripts/run_round.py --condition $CONDITION --round $i
    if [ $? -ne 0 ]; then
        echo "Round $i failed, retrying once..."
        python scripts/run_round.py --condition $CONDITION --round $i
    fi
done
```

### 6.3 日志格式（`logs/round_N.jsonl`）

每行一个JSON对象：
```json
{
  "round": 1,
  "condition": "D",
  "timestamp": "2026-10-12T14:30:22",
  "task_id": "task_001",
  "level": 1,
  "teacher_prompt": "...",
  "teacher_output": "...",
  "task_valid": true,
  "student_prompt": "...",
  "student_output": "...",
  "z3_result": "sat",
  "z3_latency_ms": 8.2,
  "llm_self_score": 85,
  "correct": true,
  "delta_t": 0.05,
  "token_input": 8500,
  "token_output": 2200,
  "cache_hit": true,
  "experience_added": "exp_001"
}
```

## 7. 测试计划

### 7.1 单元测试用例（示例）

**Z3执行器**：
- TC-Z3-001：有效SAT代码 → 返回`{"status":"sat"}`
- TC-Z3-002：有效UNSAT代码 → 返回`{"status":"unsat"}`
- TC-Z3-003：无效Python → 返回`{"status":"error"}`
- TC-Z3-004：超时任务 → 返回`{"status":"unknown"}`

**经验存储**：
- TC-EXP-001：添加原则 → 文件创建成功
- TC-EXP-002：检索相似原则 → 返回Top-3
- TC-EXP-003：语义去重 → 相似原则合并

**种群博弈**：
- TC-POP-001：教师生成有效任务 → Z3验证通过
- TC-POP-002：学生解题正确 → Z3返回sat且与期望一致
- TC-POP-003：难度自适应 → 成功率>80%时升级

### 7.2 集成测试
- IT-001：完整单轮链路（任务生成→验证→解题→锚定→日志）
- IT-002：免疫修复触发（注入无效代码→修复→成功）
- IT-003：检查点创建与回滚（创建→修改→回滚→状态一致）

### 7.3 系统测试
四条件实验，每条件200轮×3次，记录Δ_t曲线、编码正确率、难度扩展率、Token效率。

## 8. 部署与运行

### 8.1 环境要求
- Python 3.11+
- Node.js 22.19+（dsh运行环境）
- Z3 4.13+ (`pip install z3-solver`)
- DeepSeek API密钥

### 8.2 安装步骤
```bash
# 1. 克隆仓库
git clone <repo-url>
cd argus-workspace

# 2. 安装Python依赖
pip install -r requirements.txt

# 3. 配置API密钥
export DEEPSEEK_API_KEY="your-key"

# 4. 初始化目录
python scripts/init_workspace.py

# 5. 运行单元测试
pytest tests/

# 6. 启动实验
./run_experiment.sh D 200
```

### 8.3 成本监控
`config.yaml`中设置：
```yaml
budget:
  max_api_cost: 500  # 元
  max_gpu_hours: 100
  alert_threshold: 0.8
```

`scripts/cost_monitor.py`每轮检查累计消耗，超阈值告警，超上限自动停止。

## 9. 给DSH的开发提示

1. **不要使用dsh的subagent功能进行文件写入**，所有写操作在主会话中通过`write_file`或`bash`完成，避免权限问题。
2. **禁止在prompt中使用`{{`和`}}`**，避免Code mode组装失败。
3. **每个脚本必须支持`--help`**，参数校验严格，错误信息明确。
4. **所有LLM调用使用统一封装**，包含缓存、退避、熔断。
5. **先实现P0功能，再扩展P1/P2**。每完成一个模块，立即编写单元测试。
6. **日志必须完整**，每轮的所有输入输出写入JSONL，便于后续分析。
7. **成本控制是硬约束**，每轮记录token消耗，超预算立即停止。
8. **代码提交到git**，每次检查点打tag，便于回滚。

---

**文档结束**  
建议按模块顺序：先实现`scripts/z3_runner.py`和`population/`下的三个角色脚本，跑通单轮链路，再逐步加入经验蒸馏、圆桌共识、检查点等。