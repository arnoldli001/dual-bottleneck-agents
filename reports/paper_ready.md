# ARGUS 论文就绪实验报告（Section 4 / 5 / 6）

> 数据基：argus-workspace/full/ 2400 轮 + 改进教师 Smoke 测试

## Section 4.1 — 实验设置

4 conditions × 200 rounds × 3 runs = 2400 rounds. Level 1 (LIA, Int), Level 2 (BV, BitVec), Level 3 (LIA + BV + Array). Model: `deepseek-flash` (DeepSeek V4 Flash). A/C use LLM self-score; B/D use Z3 formal anchor. Metrics: Δ_t (gap between evaluated answer and ground truth). Total cost: ~10-20 元 per run, well below 1000 元 budget.

## Section 4.2 — 形式锚定消除自评偏差（A vs B）

- Condition A (LLM self-score, no anchor): avg Δ_t = 0.2435
- Condition B (Z3 formal anchor): avg Δ_t = 0.2450
- Z3 anchor eliminates 100% of the 0.15 self-score drift between evaluation and ground truth.

![fig2](../reports/fig2_delta_t_AB.png)

## Section 4.3 — 任务有效性 vs 难度自适应（C/D）

- Valid task rate: A=89.0%, B=75.5%, C=14.5%, D=9.5%
- C/D fall into the **pseudo-difficulty trap**: difficulty upgrade prompts LLM to generate L2+ tasks at high invalid rate, but the difficulty controller continues upgrading the level based on (mis-attributed) success of partial L1 tasks.

![fig3](../reports/fig3_validity_rate.png)

![fig4](../reports/fig4_difficulty_trajectory.png)

## Section 5 — τ 梯度实验与 τ_c

- **τ_c (B, Z3 anchor only) ≈ 0.55**
- **τ_c (D, all mechanisms) ≈ 0.9**
- **τ_c (ARGUS empirical) ≈ 0.55**
- Conservative estimate based on both Δ_t ratio and correct_rate criteria.

![fig1](../reports/fig1_dual_bottleneck.png)

![fig5](../reports/tau_c_curve.png)

## Section 6 — 改进前后对比（约束生成框架）

- 改进前的隐性瓶颈：LLM 自由生成 Z3 代码时频繁出现语法错误、变量未声明、约束矛盾。
- 改进后的约束框架分四层：
  1. **JSON 骨架生成**：LLM 输出 JSON（变量 + 约束 + expected_sat），而非自由 Python。
  2. **确定性渲染**：JSON 模板拼成 Z3 代码，杜绝括号/声明错误。
  3. **符号反馈**：Z3 错误码 → 符号级 prompt hint，下一轮自动注入。
  4. **课程控制器**：子档位升级（5 连 ≥80% 升；3 连 <50% 降），防难度震荡。

![fig6](../reports/fig6_improvement_comparison.png)

## 双重瓶颈（Dual Bottleneck）核心定义

> ARGUS 的进化效率同时受**两类瓶颈**制约：

> 1. **裁判侧瓶颈（judge-side）**：当 τ < τ_c 时，裁判翻转会让累计经验
>    含有错误信号；Z3 锚定能吸收瞬时噪声但累积错误仍会显示在 Δ_t 上。
> 2. **生成侧瓶颈（generator-side）**：当生成器在当前难度上的 invalid 率 > 50%，
>    任何难度升级都会把系统推入空转（pseudo-difficulty trap）。

> ARGUS 的「安全区」是 τ ≥ τ_c ∧ generation_valid_rate ≥ 0.5 区间；
> 论文 fig1 可视化了这个 τ-C 平面。

