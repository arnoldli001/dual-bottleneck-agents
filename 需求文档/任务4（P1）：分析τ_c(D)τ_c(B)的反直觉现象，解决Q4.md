【任务】分析并解释"τ_c(D)=0.9 > τ_c(B)=0.55"的反直觉现象。

【背景】
直觉上，D有更多机制（种群、蒸馏、共识），应该更鲁棒
但实测τ_c(D) > τ_c(B)，需在论文中解释
假设：D的种群博弈把任务推到L2/L3，生成器崩溃，导致D对裁判噪声更敏感

【交付物】
scripts/analyze_tau_c_gap.py
reports/tau_c_gap_analysis.md
reports/fig7_tau_c_gap.png

【实现要求】
Part 1：验证假设
从已有日志中提取：
条件B在τ=0.55时的难度分布（应该全是L1）
条件D在τ=0.55时的难度分布（应该包含L2/L3）
如果D在τ=0.55时有大量L2/L3轮次，且这些轮次的invalid率高，则假设成立

Part 2：生成解释性图表
fig7_tau_c_gap.png 包含两个子图：
左图：τ_c(B) vs τ_c(D)的柱状对比
右图：在τ=0.55下，B和D的难度分布（堆叠柱状图）
标注："D的更高τ_c源于其更高的任务复杂度，而非机制缺陷"

Part 3：论文文本
生成 reports/tau_c_gap_analysis.md，包含：
现象陈述：τ_c(D) > τ_c(B)
根因分析：D的难度自适应机制主动将任务推到L2/L3
理论支撑：Proposition 2（τ_c随任务复杂度递增）
论文中的表述：
"The higher τ_c(D) is not a flaw in D's mechanisms, but a direct
consequence of Proposition 2: D's population-based difficulty
adaptation pushes tasks into L2/L3, where the generator validity
rate V < 0.10. The judge must therefore be more reliable to
compensate for the noisier signal environment."

【验收标准】
能定量证明D在τ=0.55时的L2/L3轮次占比 > B
图表清晰展示"任务复杂度差异"
论文表述逻辑自洽