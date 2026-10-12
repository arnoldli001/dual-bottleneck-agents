# ARGUS — 自进化智能体的可靠性研究

> 五层插件化架构 / 22 机制 / Z3 形式锚定 / DeepSeek V4 Flash 真实 API
> 核心贡献：**双重瓶颈框架**（诊断）+ **Δ_t(τ) 解析公式**（理论）

本仓库同时是论文的实验代码与数据发布包：2400 轮基线 + 800 轮 τ 梯度实验
+ 240 轮约束框架验证，全部使用真实 API，数据可逐轮追溯。

---

## 1. 核心结果

### 1.1 双重瓶颈合成律

一轮"成功"需要两件事同时成立：教师产出 valid 任务（生成侧），学生判对（裁判侧）。
按概率链式法则：

```
1 − Δ_t_global = (1 − Δ_t_gen) × (1 − Δ_t_judge)
```

该式在 2400 轮四条件数据上成立到 **机器精度（1.11e-16）**。
两个瓶颈**共享同一个 Δ_t 预算**，这是"双重瓶颈"框架的定量形式。

### 1.2 裁判噪声的解析形式

设单次判决翻转概率 p = (1−τ)/2，每轮有**两次独立判决**（教师任务验证 + 学生答案验证），
一轮判对当且仅当两次判决一致：

```
P(correct) = (1−p)² + p² = (1+τ²)/2
⟹  Δ_t(τ) = (1 − τ²)/2          ← 无自由参数
```

反推设计公式：

```
τ_c = √(1 − 2·Δ_t^max)
```

实测拟合 **MAE = 0.026 (B) / 0.052 (D)**。
判别性检验：实测 `correct_rate` 支持本模型（MAE 0.039），
排除"裁判判断 + 系统接受"模型（MAE 0.229）。

### 1.3 约束生成框架

LLM 自由生成 Z3 代码 → 四层约束管线（JSON 骨架 → 确定性渲染 → 符号反馈 → 课程控制）。

真实 API 下 valid 率：**L1 98.8% / L2 71.2% / L3 58.8%**
（基线在 2400 轮内只产出 11 个 valid L2 与 114 个 valid L3 任务）。

---

## 2. 快速开始

### 2.1 安装

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
```

### 2.2 配置 API key

推荐用环境变量（`config.yaml` 中 `key` 留空即可）：

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-xxx..."
# 或备选名
$env:Deepseek_ARGUS = "sk-xxx..."
```

或从示例创建配置文件：

```bash
cp config.yaml.example config.yaml
```

### 2.3 单元测试

```bash
.venv/Scripts/python.exe -m pytest tests/ -q
# 170 passed
```

### 2.4 复现论文结果（纯离线，无需 API key）

```bash
$env:PYTHONIOENCODING = "utf-8"

# Δ_t 双口径重分析 → table2b, table2c, fig2b
.venv/Scripts/python.exe -m scripts.reanalyze_delta_t

# Δ_t(τ) 解析拟合 → table4b, fig5b
.venv/Scripts/python.exe -m scripts.analytical_fit_tau

# 双重瓶颈合成律 → table4c
.venv/Scripts/python.exe -m scripts.dual_bottleneck_law

# τ_c 与反直觉现象分析 → tau_c_analysis_real.md, fig7
.venv/Scripts/python.exe -m scripts.detect_tau_c --within-tau --raw_root logs/tau_sweep_real
.venv/Scripts/python.exe -m scripts.analyze_tau_c_gap

# L1 阶段曲线与分级 valid 率 → fig2c, fig3b
.venv/Scripts/python.exe -m scripts.plot_per_round_delta_t

# 汇总为论文数据包 → reports/paper_data_final/ + paper_ready_final.md
.venv/Scripts/python.exe -m scripts.unify_paper_outputs
```

### 2.5 重跑实验（需要 API key + 预算）

```bash
# τ 梯度扫描：800 轮，实测约 2.8 元 / 24 分钟
.venv/Scripts/python.exe -m scripts.run_tau_sweep_real \
    --tau_values 0.55,0.60,0.65,0.70,0.75,0.80,0.90,1.00 \
    --conditions B,D --rounds 50 --level 1 --use-real-api --cost-limit 10

# 约束框架验证：240 轮，实测约 1.9 元 / 46 分钟
.venv/Scripts/python.exe -m scripts.run_improved_smoke_real \
    --rounds_per_level 20 --levels 1,2,3 --conditions A,B,C,D \
    --use-real-api --cost-limit 10
```

> 重跑默认写入 `argus-workspace/`（运行时目录，不入库），
> **不会覆盖** `logs/` 下已发布的论文数据。

---

## 3. 目录结构

```
ARGUS/
├── argus/                    # 核心代码（L0-L5 共 20 模块）
│   ├── llm_client.py         #   API 客户端（Mock + Real，缓存/熔断/退避）
│   ├── z3_runner.py          #   Z3 沙箱 + JSON→Z3 确定性渲染器
│   ├── z3_anchor.py          #   Z3 形式锚定 + τ 噪声注入
│   ├── agents.py             #   Teacher / Student（四层约束生成）
│   ├── population.py         #   种群博弈 + 能力边界检测
│   └── ...
├── scripts/                  # 实验与复现脚本
│   ├── run_tau_sweep_real.py         # P0-2: 800 轮 τ 扫描
│   ├── run_improved_smoke_real.py    # P0-3: 240 轮框架验证
│   ├── detect_tau_c.py               # τ_c 检测（双口径）
│   ├── analytical_fit_tau.py         # Δ_t(τ) 解析拟合
│   ├── dual_bottleneck_law.py        # 双重瓶颈合成律
│   ├── unify_paper_outputs.py        # 论文数据包汇总
│   └── difficulty_controller.py      # 课程控制器
├── tests/                    # 170 个单元/集成测试
├── logs/                     # 【论文数据】实验日志
│   ├── tau_sweep_real/       #   Section 5: 800 轮 τ 扫描（含逐 cell 经验库）
│   └── D/                    #   早期残留
├── argus-workspace/          # 运行时工作区（不入库；含已发布的实验数据）
│   ├── full/                 #   Section 4: 2400 轮基线（4条件×200轮×3次）
│   ├── improved_real/        #   Section 6: 240 轮框架验证
│   ├── improved_real_run1_hexbug/  # hex 字面量缺陷的原始证据（49 轮）
│   └── smoke_real/           #   P0 修复前的 80 轮 smoke
├── reports/                  # 论文图表与数据表
│   ├── paper_ready_final.md  #   论文 Section 4/5/6 初稿
│   ├── paper_data_final/     #   发布包：11 图 + 9 表
│   ├── table{1,2a,2b,2c,3,4,4b,4c,5}_*.md
│   ├── fig{1,2,2b,2c,3,3b,4,5,5b,6,7}_*.png
│   └── verification_v2.md    #   验证报告（含 hex bug 复盘）
├── 文档/                     # 设计文档（需求/规格/验证方案）
├── 需求文档/                 # 各阶段任务规格
├── constitution/             # 12 核心规则 JSON
├── config.yaml.example       # 配置模板
└── requirements.txt
```

---

## 4. 论文数据索引

| 论文位置 | 数据 | 路径 |
|---------|------|------|
| Section 4（2400 轮基线） | 原始日志 | `argus-workspace/full/logs/` |
| Section 4 图表 | Table 1/2a/2b/2c/3, Fig 1/2/2b/2c/3/3b/4 | `reports/paper_data_final/` |
| Section 5（τ 梯度） | 原始日志 | `logs/tau_sweep_real/` |
| Section 5 图表 | Table 4/4b/4c, Fig 5/5b/7 | `reports/paper_data_final/` |
| Section 6（框架验证） | 原始日志 | `argus-workspace/improved_real/logs/` |
| Section 6 图表 | Table 5, Fig 6 | `reports/paper_data_final/` |
| 数据一致性 | 4 项交叉验证 | `reports/data_consistency_report.md` |
| 缺陷复盘 | hex 字面量假阳性 | `reports/verification_v2.md` §3.5 |

---

## 5. 架构（22 机制实现状态）

| 层 | 模块 | 文件 | 状态 |
|----|------|------|------|
| **L0 基座** | API Client | `argus/llm_client.py` | ✅ Mock+Real 双模式 + 缓存/熔断/退避 |
| | Z3 沙箱 | `argus/z3_runner.py` | ✅ 持久 worker + JSON 渲染 + 危险导入拦截 |
| **L1 记忆** | ExperienceStore | `argus/experience_store.py` | ✅ SQLite + Jaccard 去重 |
| | AntibodyStore | `argus/antibody.py` | ✅ FTS5 + 退路 LIKE |
| | MethylationStore | `argus/methylation.py` | ✅ JSON + 半衰期衰减 |
| **L2 执行** | TaskAgent | `argus/agents.py` | ✅ Teacher（JSON 骨架）+ Student |
| | ApoptosisManager | `argus/apoptosis.py` | ✅ 熵崩溃 + 性能下降检测 |
| **L3 评测** | Z3Anchor | `argus/z3_anchor.py` | ✅ 累计统计 + τ 噪声注入 |
| | RoundTable | `argus/roundtable.py` | ✅ 4 角色盲评 + 置信度加权 |
| **L4 进化** | PopulationGame | `argus/population.py` | ✅ 难度自适应 + 能力边界 |
| | MetaMutator | `argus/meta_mutate.py` | ✅ 宪法检查 + 停滞触发 |
| | CurriculumController | `scripts/difficulty_controller.py` | ✅ 子级别升降级 |
| **L5 治理** | Constitution | `argus/constitution.py` | ✅ 12 核心规则 |
| | CheckpointManager | `argus/checkpoint.py` | ✅ 快照 + 回滚 |
| | CostMonitor | `argus/cost_monitor.py` | ✅ 硬上限 |

---

## 6. 关键设计决策（ADR）

| 编号 | 决策 | 原因 |
|------|------|------|
| ADR-001 | Z3 沙箱持久 worker 池 | Windows spawn 冷启 150ms+，持久池 warm 9ms |
| ADR-002 | 成本计算 `call_cost_cny()` 单一函数 | 避免账本/监控分叉 |
| ADR-003 | 输入 token 硬上限 5000 | 防止 LLM prompt 失控 |
| ADR-004 | 缓存 key 含 model+temperature+max_tokens | 否则实验泛化无效 |
| ADR-005 | max_tokens 按任务类型配置 | teacher=4000, student=3000 等 |
| ADR-006 | max_retries=5 | LLM 偶发错误恢复 |
| ADR-007 | invalid 必写日志 | 修复静默失败 |
| ADR-008 | 难度升级需 5 轮连成功 | 防止 L1→L2 过激跃迁 |
| ADR-009 | deepseek-flash 模型名 | 实际 API 不支持 "deepseek-v4-flash" 别名 |
| ADR-010 | 成本按累计值做差得单轮增量 | runner 返回的是累计值，直接求和会虚高 N/2 倍 |
| ADR-011 | 数字字面量先占位再扫标识符 | 否则 `0x0F` 被切成 `x0F` 误判为未声明变量 |

---

## 7. 关键性能指标

| 指标 | 值 |
|------|-----|
| Z3 验证延迟 | warm 9.4 ms（首次 170 ms worker 冷启） |
| τ 扫描（800 轮） | **2.82 元 / 24 分钟** |
| 框架验证（240 轮） | **1.86 元 / 46 分钟** |
| 单轮成本 | 0.003–0.006 元/轮 |
| 缓存命中率 | B 条件 100%（跨 τ 复用），D 条件 55–97% |

---

## 8. 已知局限

1. **Z3 沙箱是黑名单方案**，不是白名单 —— 见 `argus/z3_runner.py` 顶部"安全模型与已知局限"
2. **τ 扫描的难度钉定在 L1**，因此 D 条件的种群升级机制被禁用；
   这使 τ_c(D) = τ_c(B)，原 Q4 假设未被支持（见 `paper_ready_final.md` §5.7）
3. **约束框架验证只有 240 轮**（4 条件 × 3 难度 × 20 轮），
   是能力探针而非 2400 轮的完整复现
4. **L2/L3 剩余失败全部是 `LLM did not return valid JSON`** ——
   真实能力边界，框架无法保证模型产出合法骨架
5. **Mock 与真实 API 行为差异大** —— mock 无法暴露框架缺陷
   （hex bug 即为实例，见 `reports/verification_v2.md` §3.5）

---

## 9. 引用

如使用本仓库的代码或数据，请引用：

```bibtex
@misc{argus2026,
  title  = {ARGUS: Dual-Bottleneck Analysis of Self-Evolving Agents
            under Noisy Formal Verification},
  author = {arnoldli001},
  year   = {2026},
  note   = {Code and data: https://github.com/<your-repo>}
}
```

## 10. License

MIT — 见 [LICENSE](LICENSE)。
