#!/bin/bash

SERVICE_NAME="oddsmind"
LOG_FILE="/var/log/oddsmind/health_check.log"
ALERT_EMAIL=""  # 设置告警邮箱

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> $LOG_FILE
}

# 检查服务状态
if ! systemctl is-active --quiet $SERVICE_NAME; then
    log_message "ERROR: Service $SERVICE_NAME is down, attempting restart..."
    systemctl restart $SERVICE_NAME
    sleep 10
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        log_message "INFO: Service $SERVICE_NAME restarted successfully"
    else
        log_message "ERROR: Failed to restart $SERVICE_NAME"
        # 发送告警邮件
        if [[ -n "$ALERT_EMAIL" ]]; then
            echo "OddsMind service failed to restart on $(hostname)" | mail -s "OddsMind Alert" $ALERT_EMAIL
        fi
    fi
fi

# 检查Web服务响应
if ! curl -s --max-time 10 http://localhost:8889/health > /dev/null; then
    log_message "WARNING: Web service not responding"
fi

# 检查数据库连接
# 这里可以添加数据库连接检查

# 检查磁盘空间
DISK_USAGE=$(df /opt | tail -1 | awk '{print $5}' | sed 's/%//')
if [[ $DISK_USAGE -gt 80 ]]; then
    log_message "WARNING: Disk usage is ${DISK_USAGE}%"
fi

# 检查内存使用
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.2f", ($3/$2) * 100.0}' | cut -d. -f1)
if [[ $MEMORY_USAGE -gt 80 ]]; then
    log_message "WARNING: Memory usage is ${MEMORY_USAGE}%"
fi
