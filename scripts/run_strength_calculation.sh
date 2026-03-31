#!/bin/bash
# 广义实力计算定时任务脚本
# 每天凌晨01:00执行

# 设置工作目录
cd /home/ubuntu/oddsmind

# 记录开始时间
echo "====================================="
echo "广义实力计算开始: $(date)"
echo "====================================="

# 激活虚拟环境并执行计算
source /home/ubuntu/oddsmind/venv/bin/activate

python main.py calculate-strength --league-group monitored

# 记录结束时间和退出码
EXIT_CODE=$?
echo "-------------------------------------"
echo "广义实力计算完成: $(date)"
echo "退出码: $EXIT_CODE"
echo "====================================="

exit $EXIT_CODE

