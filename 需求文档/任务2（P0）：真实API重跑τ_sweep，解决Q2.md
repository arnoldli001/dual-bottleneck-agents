【任务】用真实DeepSeek V4 Flash API重跑τ_sweep实验，替换现有mock数据。

【背景】
- 当前τ_c(B)≈0.55, τ_c(D)≈0.90来自mock LLM，审稿人质疑
- 需用真实API在L1任务上重跑，隔离生成器瓶颈

【交付物】
1. scripts/run_tau_sweep_real.py（修改现有脚本，强制真实API）
2. reports/tau_c_analysis_real.md
3. reports/fig5_tau_c_curve_real.png
4. reports/tau_c_real.json（原始数据）

【实现要求】

**实验设置**
- τ值：{0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90, 1.00}
- 条件：B（仅锚定）, D（完整ARGUS）
- 轮次：每τ×每条件×50轮
- 难度：仅L1（隔离生成器瓶颈）
- 总轮次：8 × 2 × 50 = 800轮
- 模型：deepseek-v4-flash（真实API）
- 预算上限：10元（CostMonitor硬限制）

**噪声注入**
使用已有 scripts/verifier.py 的 verify_with_noise：
- τ=1.0：不翻转
- τ<1.0：以概率 (1-τ)/2 翻转SAT↔UNSAT
- 每τ使用固定noise_seed=42，保证可复现

**执行流程**
```bash
python scripts/run_tau_sweep_real.py \
    --tau_values 0.55,0.60,0.65,0.70,0.75,0.80,0.90,1.00 \
    --conditions B,D \
    --rounds 50 \
    --level 1 \
    --use-real-api \
    --cost-limit 10




τ_c检测
使用 scripts/detect_tau_c.py 的双口径：
Δ_t口径：后25轮Δ_t均值 > 前25轮均值×1.5 → 退化
正确率口径：后25轮正确率 < 前25轮×0.7 → 退化
τ_c = 最大的"稳定"τ值

输出要求
reports/tau_c_analysis_real.md 必须包含：
实验设置表（含"real API"标注）
τ vs avg Δ_t 原始数据表
τ vs late Δ_t（后25轮）原始数据表
τ_c的确定过程
与mock数据的对比（如果mock τ_c=0.55-0.90，real是多少？）
与Ratchet理论值 (1-τ)/2 的对比
可直接用于论文的图表

验收标准
τ=1.0时，B的Δ_t=0.00（与已有数据一致）
τ=0.55时，B的Δ_t显著高于τ=1.0（验证噪声注入有效）
真实API的总成本<10元
所有800轮日志完整写入 logs/tau_sweep_real/

禁止事项
不要修改verifier.py的噪声注入逻辑
不要用mock替换真实API
如果API失败，重试而非静默跳过