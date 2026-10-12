# self-evolving-agent-reliability

**研究问题：形式验证器的可靠度降到什么程度，一个自进化智能体就会停止变好？**

本仓库包含回答该问题所需的全部实验代码与原始数据：一个五层自进化智能体（ARGUS），
它的教师/学生判决被注入可调噪声，实验测量「裁判可靠度 τ」与「系统评估偏差 Δ_t」的关系。

---

## 1. 主要结论

### 1.1 双重瓶颈合成律

一轮"成功"需要两件事同时成立：教师产出可解任务（生成侧），学生判对（裁判侧）。
按概率链式法则：

```
1 − Δ_t_global = (1 − Δ_t_gen) × (1 − Δ_t_judge)
```

该式在 2400 轮四条件数据上成立到**机器精度（1.11e-16）**。
两个瓶颈**共享同一个 Δ_t 预算** —— 这是双重瓶颈框架的定量形式。

### 1.2 裁判噪声的解析形式

设单次判决翻转概率 p = (1−τ)/2。每轮有**两次独立判决**（教师任务验证 + 学生答案验证），
一轮判对当且仅当两次判决一致：

```
P(correct) = (1−p)² + p² = (1+τ²)/2
⟹  Δ_t(τ) = (1 − τ²)/2          ← 无自由参数
```

反推设计公式：

```
τ_c = √(1 − 2·Δ_t_max)
```

实测拟合 **MAE = 0.026（条件 B）/ 0.052（条件 D）**。
判别性检验：实测 `correct_rate` 支持本模型（MAE 0.039），
排除"裁判判断 + 系统接受"模型（MAE 0.229）。

### 1.3 约束生成框架的效果

把"LLM 自由生成 Z3 代码"换成四层约束管线
（JSON 骨架 → 确定性渲染 → 符号反馈 → 课程控制）后，
真实 API 下有效任务率：**L1 98.8% / L2 71.2% / L3 58.8%**
（基线在 2400 轮内只产出 11 个有效 L2 与 114 个有效 L3 任务）。

---

## 2. 复现步骤

### 2.1 安装

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2.2 单元测试

```bash
pytest tests/ -q
# 170 passed
```

### 2.3 离线复现全部图表（**不需要 API key**）

仓库内已包含论文使用的原始日志，以下命令直接读取它们并生成所有图表与数据表：

```bash
# 全量实验编排入口（查看参数）
python scripts/run_full_experiment.py --help

# Δ_t 双口径重分析 → table2b, table2c, fig2b
python scripts/reanalyze_delta_t.py

# Δ_t(τ) 解析拟合 → table4b, fig5b
python scripts/analytical_fit_tau.py

# 双重瓶颈合成律 → table4c
python scripts/dual_bottleneck_law.py

# τ_c 检测与反直觉现象分析 → tau_c_analysis_real.md, fig7
python scripts/detect_tau_c.py --within-tau --raw_root logs/tau_sweep_real
python scripts/analyze_tau_c_gap.py

# L1 阶段曲线与分级有效任务率 → fig2c, fig3b
python scripts/plot_per_round_delta_t.py

# 汇总为论文数据包 → reports/paper_data_final/ + paper_ready_final.md
python scripts/unify_paper_outputs.py
```

### 2.4 重跑实验（**需要 API key 与预算**）

```bash
export DEEPSEEK_API_KEY="sk-..."     # Windows: $env:DEEPSEEK_API_KEY="sk-..."

# τ 梯度扫描：800 轮，实测约 2.8 元 / 24 分钟
python scripts/run_tau_sweep_real.py \
    --tau_values 0.55,0.60,0.65,0.70,0.75,0.80,0.90,1.00 \
    --conditions B,D --rounds 50 --level 1 --use-real-api --cost-limit 10

# 约束框架验证：240 轮，实测约 1.9 元 / 46 分钟
python scripts/run_improved_smoke_real.py \
    --rounds_per_level 20 --levels 1,2,3 --conditions A,B,C,D \
    --use-real-api --cost-limit 10
```

> 重跑默认写入 `argus-workspace/_runtime/`（已在 `.gitignore` 中），
> **不会覆盖** `argus-workspace/` 与 `logs/` 下已发布的论文数据。

---

## 3. 数据说明

仓库中的数据按「论文哪一节用到」组织：

| 目录 | 内容 | 轮数 | 对应论文章节 |
|------|------|------|-------------|
| `argus-workspace/full/logs/` | 4 条件 × 200 轮 × 3 次基线实验 | 2,400 | **Section 4**（双重瓶颈证据） |
| `logs/tau_sweep_real/` | 8 个 τ 值 × 2 条件 × 50 轮 | 800 | **Section 5**（τ 梯度与解析公式） |
| `argus-workspace/improved_real/logs/` | 4 条件 × 3 难度 × 20 轮框架验证 | 240 | **Section 6**（约束生成框架） |
| `argus-workspace/improved_real_run1_hexbug/logs/` | 缺陷复现证据 | 49 | `reports/verification_v2.md` §3.5 |
| `argus-workspace/smoke_real/logs/` | 早期冒烟测试 | 80 | 开发过程记录 |

每个 `round_*.jsonl` 是该轮的事件流（`task_generated` / `solution_verified` /
`invalid_task` 等），可直接用 `jq` 或 Python 逐轮读取。

**产出物**（`reports/`）：

| 文件 | 说明 |
|------|------|
| `paper_ready_final.md` | 论文 Section 4/5/6 初稿 |
| `paper_data_final/` | 发布包：11 张图 + 9 张表（300 DPI，英文标签） |
| `table*.md` | 各项统计表（Δ_t 双口径、τ_c、解析拟合、合成律、改进对比） |
| `fig*.png` | 论文图 |
| `data_consistency_report.md` | 4 项数据一致性交叉验证（全部 PASS） |
| `verification_v2.md` | 验证报告，含一个只在真实 API 下暴露的缺陷复盘 |
| `cleanup_report_v2.md` | 仓库清理记录 |

---

## 4. 仓库结构

```
self-evolving-agent-reliability/
├── argus/                    # 核心代码（L0–L5 共 20 模块）
│   ├── llm_client.py         #   API 客户端（Mock + Real，缓存/熔断/退避）
│   ├── z3_runner.py          #   Z3 沙箱 + JSON→Z3 确定性渲染器
│   ├── z3_anchor.py          #   Z3 形式锚定 + τ 噪声注入
│   ├── agents.py             #   Teacher（JSON 骨架）/ Student
│   ├── population.py         #   种群博弈 + 能力边界检测
│   ├── constitution.py       #   12 核心规则
│   └── ...
├── scripts/                  # 实验与复现脚本（19 个）
│   ├── run_tau_sweep_real.py         # 800 轮 τ 扫描
│   ├── run_improved_smoke_real.py    # 240 轮框架验证
│   ├── run_full_experiment.py        # 2400 轮编排（断点续跑 + 成本监控）
│   ├── detect_tau_c.py               # τ_c 检测（双口径 + 显著性护栏）
│   ├── analytical_fit_tau.py         # Δ_t(τ) 解析拟合
│   ├── dual_bottleneck_law.py        # 双重瓶颈合成律
│   ├── unify_paper_outputs.py        # 论文数据包汇总
│   └── difficulty_controller.py      # 课程控制器
├── tests/                    # 170 个单元/集成测试
├── argus-workspace/          # 实验数据（论文用，随仓库发布）
├── logs/                     # 实验数据（Section 5）
├── reports/                  # 图表、数据表、报告
├── 文档/                     # 设计文档（需求 / 模块规格 / 验证方案）
├── 需求文档/                 # 各阶段任务规格
├── constitution/             # 12 核心规则 JSON
├── config.yaml.example       # 配置模板
├── requirements.txt
├── DEPRECATED.md             # 可能过时但暂留的文件清单
└── README.md
```

---

## 5. 架构

| 层 | 模块 | 文件 | 职责 |
|----|------|------|------|
| **L0 基座** | API Client | `argus/llm_client.py` | Mock+Real 双模式 + 缓存/熔断/退避 |
| | Z3 沙箱 | `argus/z3_runner.py` | 持久 worker + JSON 渲染 + 危险导入拦截 |
| **L1 记忆** | ExperienceStore | `argus/experience_store.py` | SQLite + Jaccard 去重 |
| | AntibodyStore | `argus/antibody.py` | FTS5 检索 |
| | MethylationStore | `argus/methylation.py` | JSON + 半衰期衰减 |
| **L2 执行** | TaskAgent | `argus/agents.py` | Teacher（JSON 骨架）+ Student |
| | ApoptosisManager | `argus/apoptosis.py` | 熵崩溃 + 性能下降检测 |
| **L3 评测** | Z3Anchor | `argus/z3_anchor.py` | 形式锚定 + τ 噪声注入 |
| | RoundTable | `argus/roundtable.py` | 4 角色盲评 + 置信度加权 |
| **L4 进化** | PopulationGame | `argus/population.py` | 难度自适应 + 能力边界 |
| | MetaMutator | `argus/meta_mutate.py` | 宪法检查 + 停滞触发 |
| | CurriculumController | `scripts/difficulty_controller.py` | 子级别升降级 |
| **L5 治理** | Constitution | `argus/constitution.py` | 12 核心规则 |
| | CheckpointManager | `argus/checkpoint.py` | 快照 + 回滚 |
| | CostMonitor | `argus/cost_monitor.py` | 成本硬上限 |

**四条件设计**：A = 无锚定无种群；B = 仅 Z3 锚定；C = 仅种群博弈；D = 全开。

---

## 6. 关键设计决策

| 编号 | 决策 | 原因 |
|------|------|------|
| ADR-001 | Z3 沙箱用持久 worker 池 | Windows spawn 冷启 150 ms+，持久池 warm 9 ms |
| ADR-002 | 成本计算 `call_cost_cny()` 单一函数 | 避免账本/监控分叉 |
| ADR-003 | 输入 token 硬上限 5000 | 防止 prompt 失控 |
| ADR-004 | 缓存 key 含 model+temperature+max_tokens | 否则实验泛化无效 |
| ADR-005 | max_tokens 按任务类型配置 | teacher=4000, student=3000 等 |
| ADR-006 | max_retries=5 | LLM 偶发错误需要恢复空间 |
| ADR-007 | invalid 必须写日志 | 修复静默失败 |
| ADR-008 | 难度升级需连续 5 轮成功 | 防止 L1→L2 过激跃迁 |
| ADR-009 | 模型名用 `deepseek-flash` | 实际 API 不支持 `deepseek-v4-flash` 别名 |
| ADR-010 | 成本按**累计值做差**得单轮增量 | runner 返回累计值，直接求和会虚高 N/2 倍 |
| ADR-011 | 数字字面量先占位再扫标识符 | 否则 `0x0F` 被切成 `x0F`，误判为未声明变量 |

---

## 7. 关键性能指标

| 指标 | 值 |
|------|-----|
| Z3 验证延迟 | warm 9.4 ms（首次 170 ms worker 冷启） |
| τ 扫描（800 轮） | 2.82 元 / 24 分钟 |
| 框架验证（240 轮） | 1.86 元 / 46 分钟 |
| 单轮成本 | 0.003–0.006 元/轮 |
| 缓存命中率 | 条件 B 100%（跨 τ 复用），条件 D 55–97% |

---

## 8. 已知局限

1. **Z3 沙箱是黑名单方案**，不是白名单 —— 见 `argus/z3_runner.py` 顶部"安全模型与已知局限"
2. **τ 扫描的难度钉定在 L1**，D 条件的种群升级机制因此被禁用；
   这使 τ_c(D) = τ_c(B)，原假设未被支持（见 `reports/paper_ready_final.md` §5.7）
3. **约束框架验证只有 240 轮**（4 条件 × 3 难度 × 20 轮），是能力探针而非 2400 轮的完整复现
4. **L2/L3 剩余失败全部是 `LLM did not return valid JSON`** ——
   真实能力边界；框架能保证合法骨架被正确渲染，但无法保证模型产出合法骨架
5. **Mock 与真实 API 行为差异大** —— mock 无法暴露框架缺陷
   （`0x0F` 字面量缺陷即为实例，见 `reports/verification_v2.md` §3.5）

---

## 9. 许可

MIT — 见 [LICENSE](LICENSE)。
