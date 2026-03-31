#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查广义实力表更新状态
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# 设置环境变量
os.environ.setdefault('MYSQL_HOST', 'localhost')
os.environ.setdefault('MYSQL_USER', 'root')
os.environ.setdefault('MYSQL_DATABASE', 'oddsmind')

try:
    import pymysql
    
    # 连接数据库
    conn = pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', ''),
        database=os.getenv('MYSQL_DATABASE', 'oddsmind'),
        charset='utf8mb4'
    )
    
    cursor = conn.cursor()
    
    print("=" * 60)
    print("广义实力表 (team_power_ratings) 检查报告")
    print("=" * 60)
    print()
    
    # 查询最新更新时间
    cursor.execute("""
        SELECT 
            MAX(updated_at) as latest_update,
            COUNT(*) as total_records
        FROM team_power_ratings
    """)
    result = cursor.fetchone()
    latest_update = result[0]
    total_records = result[1]
    
    print(f"📊 表统计信息:")
    print(f"   总记录数: {total_records:,}")
    print(f"   最新更新时间: {latest_update}")
    
    if latest_update:
        now = datetime.now()
        if isinstance(latest_update, str):
            latest_update = datetime.strptime(latest_update, '%Y-%m-%d %H:%M:%S')
        
        time_diff = now - latest_update
        hours = time_diff.total_seconds() / 3600
        days = time_diff.days
        
        print(f"   距离现在: {days} 天 {int(hours % 24)} 小时")
        print()
        
        if days > 1:
            print(f"⚠️  警告: 表已超过 {days} 天未更新！")
        else:
            print(f"✅ 表更新正常（{hours:.1f} 小时前更新）")
    else:
        print("❌ 表中没有数据")
    
    print()
    print("📅 最近7天更新情况:")
    cursor.execute("""
        SELECT 
            DATE(updated_at) as update_date,
            COUNT(*) as records,
            MIN(updated_at) as first_update,
            MAX(updated_at) as last_update
        FROM team_power_ratings
        WHERE updated_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        GROUP BY DATE(updated_at)
        ORDER BY update_date DESC
    """)
    
    results = cursor.fetchall()
    if results:
        for row in results:
            date, count, first, last = row
            print(f"   {date}: {count:,} 条记录 ({first} ~ {last})")
    else:
        print("   ❌ 最近7天没有更新记录")
    
    print()
    print("=" * 60)
    print("定时任务状态")
    print("=" * 60)
    print()
    print("定时任务配置:")
    print("   执行时间: 每天凌晨 01:59")
    print("   任务ID: daily_strength_calculation")
    print("   任务名称: 每日广义实力计算")
    print()
    
    # 计算下次执行时间
    now = datetime.now()
    next_run = now.replace(hour=1, minute=59, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    
    print(f"   下次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 检查是否应该已经执行过
    if latest_update:
        if isinstance(latest_update, str):
            latest_update = datetime.strptime(latest_update, '%Y-%m-%d %H:%M:%S')
        
        # 检查今天凌晨1:59是否应该已经执行
        today_0159 = now.replace(hour=1, minute=59, second=0, microsecond=0)
        yesterday_0159 = today_0159 - timedelta(days=1)
        
        if now > today_0159 and latest_update < today_0159:
            print("⚠️  今天凌晨01:59的任务应该已经执行，但表未更新")
        elif now > yesterday_0159 and latest_update < yesterday_0159:
            print("⚠️  昨天凌晨01:59的任务应该已经执行，但表未更新")
        else:
            print("✅ 定时任务执行时间正常")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ 检查失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

