【任务】用真实DeepSeek V4 Flash API重跑约束生成框架验证，替换mock数据。
【背景】
当前改进框架的100% valid率来自mock LLM
需用真实API验证：JSON骨架+确定性渲染+符号反馈+课程控制是否真的有效
【交付物】
scripts/run_improved_smoke_real.py
reports/improvement_validation_real.md
reports/fig6_improvement_comparison_real.png
reports/improvement_real.json

【实现要求】
实验设置
条件：A, B, C, D
难度：L1, L2, L3
每条件×每难度：20轮
总轮次：4 × 3 × 20 = 240轮
模型：deepseek-v4-flash（真实API）
预算上限：20元

对比基线：
Legacy：已有2400轮数据（argus-workspace/full/logs/）
Improved：本次真实API跑出的240轮

执行流程：
python scripts/run_improved_smoke_real.py \
    --rounds_per_level 20 \
    --levels 1,2,3 \
    --conditions A,B,C,D \
    --use-real-api \
    --cost-limit 10


关键指标：
对每个（条件，难度）组合计算：
valid rate（valid / total）
avg Δ_t（仅valid轮次）
与legacy同难度子集的对比

输出要求：
reports/improvement_validation_real.md 必须包含：
实验设置表（含"real API"标注）
改进前后valid rate对比表（按难度分级）
改进前后avg Δ_t对比表
统计检验：Welch's t检验 + Cohen's d

与mock数据的对比：
明确写出："真实API下L1/L2/L3的valid率分别是X%/Y%/Z%"

验收标准：
L1有效任务率 > 80%
L2有效任务率 > 30%（相比legacy的<5%显著提升）
L3有效任务率 > 15%
所有日志写入 argus-workspace/improved_real/logs/

禁止事项：
不要用mock替换真实API
不要修改约束生成框架的核心逻辑
如果某个难度级别的valid率<10%，记录失败原因（不要静默跳过）