#!/usr/bin/env bash
# ARGUS 全量实验脚本：4 条件 × N 轮 × N 次
# 用法：bash run_experiment.sh [--rounds 200] [--runs 3] [--conditions A,B,C,D]
#
# 特性：
# - 断点续跑：自动检测 logs/ 下最新完成的轮次，从下一轮开始
# - 成本监控：每轮检查累计成本，超 50 元立即停止
# - 后台运行：nohup + &，输出到 logs/full_run.log
# - 实时进度：每 10 轮写一次 reports/full_progress.txt
#
# 用 nohup 启动：nohup bash run_experiment.sh --rounds 200 --runs 3 > logs/full_run.log 2>&1 &

set -e

# 解析参数
ROUNDS=200
RUNS=3
CONDITIONS="A,B,C,D"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rounds) ROUNDS="$2"; shift 2 ;;
        --runs) RUNS="$2"; shift 2 ;;
        --conditions) CONDITIONS="$2"; shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# 检查环境
if [ -z "$DEEPSEEK_API_KEY" ] && [ -z "$Deepseek_ARGUS" ]; then
    echo "[FATAL] DEEPSEEK_API_KEY / Deepseek_ARGUS 环境变量未设置"
    exit 1
fi

# 切到项目根
cd "$(dirname "$0")"
mkdir -p reports logs

# 检查磁盘空间
AVAIL_GB=$(powershell.exe -Command "(Get-PSDrive -PSProvider FileSystem | Where-Object {\$_.Used -gt 0} | ForEach-Object {[math]::Round((\$_.Free/1GB),2)} | Measure-Object -Sum).Sum" 2>/dev/null || echo "unknown")
if [[ "$AVAIL_GB" != "unknown" ]] && (( $(echo "$AVAIL_GB < 5" | bc -l) )); then
    echo "[FATAL] 可用空间 ${AVAIL_GB}GB < 5GB"
    exit 1
fi

echo "============================================================"
echo "ARGUS 全量实验启动"
echo "  rounds=$ROUNDS  runs=$RUNS  conditions=$CONDITIONS"
echo "  available_disk=${AVAIL_GB}GB"
echo "  start_time=$(date)"
echo "============================================================"

IFS=',' read -ra COND_ARR <<< "$CONDITIONS"
for COND in "${COND_ARR[@]}"; do
    for RUN_ID in $(seq 1 $RUNS); do
        echo ""
        echo "[$(date +%H:%M:%S)] 条件 $COND 跑次 $RUN_ID 开始"
        # 断点续跑：检测该条件下该跑次的最新 round
        LOG_DIR="argus-workspace/full/logs/$COND"
        mkdir -p "$LOG_DIR"
        if [ -d "$LOG_DIR" ]; then
            LATEST=$(ls "$LOG_DIR" 2>/dev/null | grep -oE 'round_[0-9]+' | sort -V | tail -1 | grep -oE '[0-9]+' || echo "0")
            echo "  检测到断点: 已完成 R$LATEST，从 R$((LATEST+1)) 续跑"
            START=$((LATEST + 1))
        else
            START=1
        fi
        if [ $START -gt $ROUNDS ]; then
            echo "  $COND run$RUN_ID 已全部完成，跳过"
            continue
        fi
        .venv/Scripts/python.exe scripts/run_single_run.py \
            --condition "$COND" \
            --run-id "$RUN_ID" \
            --start "$START" \
            --rounds "$ROUNDS" \
            2>&1 | tee -a logs/full_run.log
        EXIT_CODE=${PIPESTATUS[0]}
        if [ $EXIT_CODE -ne 0 ]; then
            echo "[FATAL] 条件 $COND 跑次 $RUN_ID 退出码 $EXIT_CODE"
            exit 1
        fi
    done
done

echo ""
echo "============================================================"
echo "全量完成: $(date)"
echo "============================================================"
echo ""
echo "运行分析脚本："
echo "  .venv/Scripts/python.exe scripts/analyze_results.py"
