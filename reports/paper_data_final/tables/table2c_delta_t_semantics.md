# Table 2c — Δ_t 的统一定义与口径澄清

## 1. Δ_t 的统一定义

$$\Delta_t = |\text{score}(y) - \text{label}(y^*)|$$

- $y$：本轮答案（z3_result.status）
- $\text{score}(y)$：**系统评估**对答案的归一化评分（∈ [0,1]）
- $\text{label}(y^*)$：**ground truth** 标签（sat=1.0，unsat=0.0）

## 2. A/B/C/D 各自的"系统评估"来源

| 条件 | 系统评估 score(y) | ground truth label(y*) | Δ_t |
|------|------------------|-----------------------|-----|
| A | `llm_self_score` (LLM 自评) | `expected` (Z3 真值) | **|llm_self_score - truth**| |
| B | **Z3 锚定** = `z3_result.status` | `expected` | **0.00**（直接采用 Z3 真值，与自身比较）|
| C | `llm_self_score`（种群多 Agent 平均后）| `expected` | **|llm_self_score - truth**| |
| D | **Z3 锚定** + 圆桌共识 | `expected` | **0.00**（Z3 真值与自身一致）|

## 3. 两种统计口径

### 口径 1：valid-only Δ_t（**Table 2b**）

- 分母 = `len(records[r.valid])`
- 排除 invalid 轮次（教师生成失败，无 ground truth label）
- **A 的 Δ_t ≈ 0.15**（LLM 自评对少数 Z3 真值有偏差）
- **B/D 的 Δ_t ≡ 0.00**（Z3 真值 vs 自身）

### 口径 2：global Δ_t（**Table 2c + 论文正文**）

- 分母 = 全部轮次（含 invalid）
- invalid → Δ_t = 1.0（"系统评估完全错误"的保守编码）
- valid → 取 Δ_t_valid
- **A 的 Δ_t ≈ 0.24**（11% invalid 把均值往上拉）
- **B 的 Δ_t ≈ 0.25**（24% invalid 拉高均值）

## 4. 数据矛盾解释（Q1 直答）

> 审稿人质疑：`full_run_analysis.md` 报 A=0.15, B=0.00，
> 但 `table2_delta_t_summary.md` 报 A=0.2435, B=0.2450。
> 是否矛盾？

**不矛盾**。两份报告口径不同：
- `full_run_analysis.md` 在「valid 子集」内计算 → A=0.15, B=0.00 **（口径 1）**
- `table2_delta_t_summary.md` 在「全部轮次」计算 → A=0.24, B=0.25 **（口径 2，含 invalid=1.0）**

两份数据都正确，可通过下表同时验证：

| 口径 | 条件 | n | avg Δ_t | 来源 |
|------|------|---|---------|------|
| valid-only (口径 1) | A | 534 | 0.1500 | Table 2b |
| global (口径 2) | A | 600 | 0.2435 | Table 2c |
| valid-only (口径 1) | B | 453 | 0.0000 | Table 2b |
| global (口径 2) | B | 600 | 0.2450 | Table 2c |
| valid-only (口径 1) | C | 87 | 0.1879 | Table 2b |
| global (口径 2) | C | 600 | 0.8823 | Table 2c |
| valid-only (口径 1) | D | 57 | 0.0000 | Table 2b |
| global (口径 2) | D | 600 | 0.9050 | Table 2c |

> 论文统一使用**口径 1（valid-only）**为主表，**口径 2（global）**
> 在描述"pseudo-difficulty trap"时使用（强调 C/D 的 invalid 严重性）。
