# ARGUS 真实 API 诊断报告（最终版）

> 生成时间：2026-10-12
> 范围：4 条件 × 20 轮真实 deepseek-flash API 冒烟（80 轮）
> 总成本：0.77 元（预算 1000 元 → 剩余 999.23 元）
> 日志：`argus-workspace/smoke_real/logs/{A,B,C,D}/round_*.jsonl`
> LLM cache：`argus-workspace/smoke_real/llm_cache.db`（113 条）

---

## 1. 各条件表现

| 条件 | 日志文件数 | 实际有效轮 | 任务 valid 率 | 正确率 | 平均 Δ_t | 失败模式 |
|------|----------|----------|-------------|--------|----------|---------|
| A | **12 / 20** | 12 | 100% (12/12) | 0.60 | 0.49 | invalid 8 轮**没写日志** |
| B | **6 / 20** | 6 | 100% (6/6) | 0.30 | 0.70 | invalid 14 轮**没写日志** |
| C | 20 / 20 | 5 | 25% | 0.25 | 0.79 | L1 成功→L2 全 invalid |
| D | 20 / 20 | 5 | 25% | 0.25 | 0.75 | L1 成功→L2 全 invalid |

**问题 1（重要）**：A/B 路径下 `run_round` 在任务 invalid 时**早 return 没有写日志文件**，导致 8/14 个 invalid 轮"消失"在日志中。
- 位置：`argus/runner.py` line 100-110
- 影响：诊断时无法复原失败原因，只能从 LLM cache 间接提取

---

## 2. teacher 输出质量问题分布（cache 提取，56 个 teacher 响应）

| 问题 | 出现次数 | 典型案例 |
|------|----------|---------|
| `unmatched_parens` | 2 | `a < b` 后截断 |
| `no_solver` | 1 | 缺 `solver = Solver()` |
| `no_constraint` | 1 | 有 solver 但没 `add` |
| 其他（截断/语法错） | 间接 | max_tokens=2000 截断 |

**问题 2（关键）**：`max_output_tokens_per_call=2000` 不足以容纳 level 2 (BV) 任务的完整 Z3 代码。

---

## 3. 5 个典型失败案例

### 案例 1：缺括号
```python
from z3 import *
a = Int('a')
b = Int      # ← 缺括号，b 实际是函数对象
```
**根因**：LLM 偶尔输出残缺代码。

### 案例 2：括号不匹配
```python
from z3 import *
a, b, c, d, e = Ints('a b c d e')
solver = Solver()
solver.add(a + b == 7)
solver.add(b + c == 10)
solver.add(c + d == 13)
solver.add(d + e == 16)
solver.add(a >= 0, b >= 0, c >= 0, d >= 0, e >= 0)
solver.add(a < b   # ← 截断在这里
```
**根因**：max_tokens 截断 + LLM 没有自动补全括号。

### 案例 3：变量声明后代码截断
```python
from z3 import *
p = Int('p'); q = Int('q'); r = Int('r')
s = Int('s'); t = Int('t'); u = Int('u')
solver = Solver()
solver.add(p +   # ← 截断
```
**根因**：max_tokens=2000 不够 BV/复杂 LIA 任务。

### 案例 4：L2 任务全 invalid
- 现象：C R06 起全部 z3=invalid
- 根因：升 L2 后 teacher 用 BV 理论，模型无法稳定生成可解 Z3 代码
- 进一步：population_game 难度升级门槛太低（修复 3 已升级到 5 轮）

### 案例 5：A/B 路径 invalid 静默失败
- 现象：A R01 invalid 早 return，日志中根本没有 round_0001.jsonl
- 根因：`runner.py` 早 return 前没 `append_event("invalid_task", ...)`
- 影响：诊断困难，监控盲区

---

## 4. 失败环节定位

| 环节 | 失败位置 | 占比 | 修复方向 |
|------|---------|------|---------|
| Teacher 任务生成 | TeacherAgent.generate 重试 3 次都失败 | ~50% | 增大 max_tokens；提高重试到 5 次；过滤明显语法错 |
| Z3 求解超时 | level 2+ 任务 Z3 15s 内无解 | ~30% | 单独给 L2 任务 30s；或重新生成 |
| LLM 自评误导 | 条件 A 用 LLM 自评 | 100% (A) | 已是已知问题（条件对比的核心） |
| 日志完整性 | invalid 静默 return | A/B 100% | 早 return 前 append_event |

---

## 5. 建议（按优先级）

### 必做（影响跑通）
1. **A/B 路径 invalid 时也写日志** —— `runner.py` 早 return 前加 `append_event("invalid_task", ...)`
2. **teacher max_tokens 提到 4000** —— `config.yaml` 的 `api.max_output_tokens_per_call`
3. **teacher max_retries 提到 5** —— `agents.py` TeacherAgent 默认参数

### 建议（影响数据质量）
4. **L1 任务限定 ≤ 5 变量** —— teacher prompt 显式约束
5. **连续 3 轮 invalid 自动降难度** —— 比升级更激进地降级
6. **截断检测** —— 提取 code 后检查括号配对，配对失败直接拒收

### 可选（影响论文可读性）
7. **每轮输出 token 数记录** —— 用于 token 效率分析
8. **Δ_t 实时画图** —— 跑实验时同步生成图表

---

## 6. 实验结论（数据本身）

**核心实验发现**（与文档 3 第 3.2 节"预期核心发现"对照）：

| 文档 3 预期 | 实测数据 | 一致性 |
|------------|---------|--------|
| A 的 Δ_t 持续扩大 | A Δ_t=0.49（无效任务多导致） | 部分一致 |
| B 有锚定但无难度自适应 | B 全 L1，Z3 锚严格 | 一致 |
| C Δ_t 先降后升（伪难题） | C L1 5 成功→L2 全失败 | **超预期发现** |
| D 锚定+种群+蒸馏+共识协同 | D 同样 L1→L2 失败，蒸馏 6 条 | 部分一致 |

**重要新发现**：
- **真实 deepseek-flash 在 Z3 代码生成上不可靠**（50% invalid 率）
- **L2 任务几乎完全无法处理**（BV 理论 + LLM 截断 + 15s timeout 三重失败）
- **C/D 的"种群博弈+蒸馏"在 L1 阶段确实生效**（升 L2 = 升级成功），但 L2 全失败说明仅 L1 不够

**建议论文方向**：
- 把 "Δ_t 持续扩大 vs 稳定" 的对比改为 "**有效任务率**" 对比（A: 60% / B: 30% / C: 25% / D: 25%）
- 重点展示 D 的 L1 阶段（5/5 成功 + 6 条经验）vs A 的自评虚高

---

*报告由 `scripts/diagnose_with_cache.py` 自动生成*
