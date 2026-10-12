【任务】从现有日志生成论文Section 4所需的补充图表。
【背景】
当前图2是分桶（20轮）的Δ_t曲线，审稿人可能要求逐轮
C/D在L1阶段的Δ_t曲线未被单独展示（这是"伪难度陷阱前"的干净数据）
【交付物】
scripts/plot_per_round_delta_t.py
reports/fig2b_delta_t_per_round.png（逐轮，4条件）
reports/fig2c_delta_t_L1_only.png（仅L1阶段，C/D的干净数据）
reports/fig3b_validity_by_level.png（按难度分级的valid率）

【实现要求】
fig2b：逐轮Δ_t（4条件）
X轴：轮次1-200
Y轴：Δ_t（仅valid轮次）
4条线：A/B/C/D
invalid轮次用灰色×标记在Y=0位置
标注：L2起始轮次用竖线标出
关键观察：A稳定0.15，B稳定0.00，C/D在L2后急剧上升

fig2c：仅L1阶段的C/D曲线
只取C/D在L1阶段的轮次（升L2之前）
展示C/D在L1的Δ_t与A/B的对比

目的：证明"种群博弈在L1阶段不损害Δ_t"
fig3b：按难度分级的valid率
分组柱状图：X轴=L1/L2/L3，每组4个柱（A/B/C/D）
Y轴=valid rate
标注：L1的valid率>75%，L2/L3的valid率<15%
目的：直观展示"伪难度陷阱"

【验收标准】
fig2b中A/B曲线清晰分离，C/D在L2后明显上升
fig2c中C/D在L1的Δ_t与A/B接近（证明种群不损害L1）
fig3b中L1/L2/L3的valid率梯度明显
所有图表用英文标签，300 DPI，可直接插入LaTeX

## 四、一句话总结
5个质疑点中，Q1/Q4/Q5用P1重新分析（0元）解决，Q2/Q3用P0真实API重跑（10元）解决。