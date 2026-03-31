#!/bin/bash
# v3.1 信号扫描器
# 用法:
#   ./scan_signals.sh              # 扫描未来24小时
#   ./scan_signals.sh 3            # 扫描未来3小时
#   ./scan_signals.sh 72           # 扫描未来72小时
#   ./scan_signals.sh 24 -v        # 详细模式(显示规则明细)
#   ./scan_signals.sh 24 --save    # 同时保存到数据库

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/scan_signals.py"

# 设置环境变量
export MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"

HOURS="${1:-24}"
shift 2>/dev/null

python3 "$PY_SCRIPT" -H "$HOURS" "$@"
