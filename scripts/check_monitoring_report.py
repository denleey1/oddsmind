#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
监控检查报告：广义实力更新 + 接口性能
"""

import re
from collections import defaultdict
from pathlib import Path
from datetime import datetime
import pymysql
import os

print('=' * 100)
print('监控检查报告')
print('=' * 100)
print()

# ========== 第一部分：广义实力更新检查 ==========
print('【第一部分：广义实力更新检查】')
print('-' * 100)

try:
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database='oddsmind',
        charset='utf8mb4'
    )
    
    cursor = conn.cursor()
    
    # 查询最新更新时间
    cursor.execute('''
        SELECT 
            MAX(updated_at) as latest_update,
            COUNT(*) as total_records
        FROM team_power_ratings
    ''')
    result = cursor.fetchone()
    latest_update = result[0]
    total_records = result[1]
    
    print(f'📊 表统计信息:')
    print(f'   总记录数: {total_records:,}')
    print(f'   最新更新时间: {latest_update}')
    
    if latest_update:
        now = datetime.now()
        if isinstance(latest_update, str):
            latest_update = datetime.strptime(latest_update, '%Y-%m-%d %H:%M:%S')
        
        time_diff = now - latest_update
        hours = time_diff.total_seconds() / 3600
        days = time_diff.days
        
        print(f'   距离现在: {days} 天 {int(hours % 24)} 小时 ({hours:.1f} 小时)')
        print()
        
        # 检查今天凌晨是否应该更新
        today_01_00 = now.replace(hour=1, minute=0, second=0, microsecond=0)
        if latest_update < today_01_00:
            print(f'⚠️  警告: 今天凌晨01:00的任务应该已经执行，但表未更新！')
            print(f'   最后更新: {latest_update}')
            print(f'   应该更新时间: {today_01_00}')
        else:
            print(f'✅ 今天凌晨已更新')
    else:
        print('❌ 表中没有数据')
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f'❌ 数据库检查失败: {e}')

print()
print()

# ========== 第二部分：接口性能分析 ==========
print('【第二部分：接口性能分析】')
print('-' * 100)

# 检查所有日志文件
log_files = list(Path('logs').glob('oddsmind.log*'))
perf_data = []

for log_file in sorted(log_files, reverse=True)[:5]:  # 检查最近5个日志文件
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if 'PERF' in line:
                    match = re.search(r'PERF \[([^\]]+)\] status=(\d+) total=([0-9.]+)s app=([0-9.]+)s db=([0-9.]+)s', line)
                    if match:
                        endpoint, status, total, app, db = match.groups()
                        perf_data.append({
                            'endpoint': endpoint,
                            'status': int(status),
                            'total': float(total),
                            'app': float(app),
                            'db': float(db)
                        })
    except Exception as e:
        pass

print(f'共找到 {len(perf_data)} 条性能记录')
print()

if perf_data:
    # 按总耗时排序
    perf_data.sort(key=lambda x: x['total'], reverse=True)
    
    print('Top 15 耗时最长的接口调用:')
    print(f"{'排名':<6s} {'接口名称':<50s} {'状态码':<8s} {'总耗时':<12s} {'应用耗时':<12s} {'数据库耗时':<12s}")
    print('-' * 100)
    for i, data in enumerate(perf_data[:15], 1):
        print(f"{i:<6d} {data['endpoint']:<50s} {data['status']:<8d} {data['total']:<12.3f}s {data['app']:<12.3f}s {data['db']:<12.3f}s")
    
    print()
    
    # 按接口分组统计
    endpoint_stats = defaultdict(lambda: {'count': 0, 'total_time': 0, 'max_time': 0, 'errors': 0})
    for data in perf_data:
        ep = data['endpoint']
        endpoint_stats[ep]['count'] += 1
        endpoint_stats[ep]['total_time'] += data['total']
        endpoint_stats[ep]['max_time'] = max(endpoint_stats[ep]['max_time'], data['total'])
        if data['status'] >= 400:
            endpoint_stats[ep]['errors'] += 1
    
    # 计算平均值并排序
    avg_stats = []
    for ep, stats in endpoint_stats.items():
        avg_time = stats['total_time'] / stats['count']
        if avg_time > 1.0:  # 只显示平均耗时超过1秒的
            avg_stats.append({
                'endpoint': ep,
                'avg_time': avg_time,
                'max_time': stats['max_time'],
                'count': stats['count'],
                'errors': stats['errors']
            })
    
    if avg_stats:
        avg_stats.sort(key=lambda x: x['avg_time'], reverse=True)
        
        print('按接口分组的统计（只显示平均耗时>1.0s的接口）:')
        print(f"{'接口名称':<50s} {'调用次数':<10s} {'平均耗时':<12s} {'最大耗时':<12s} {'错误数':<8s}")
        print('-' * 100)
        for stat in avg_stats[:10]:
            print(f"{stat['endpoint']:<50s} {stat['count']:<10d} {stat['avg_time']:<12.3f}s {stat['max_time']:<12.3f}s {stat['errors']:<8d}")
    else:
        print('✅ 没有平均耗时超过1秒的接口')
else:
    print('⚠️  未找到性能监控记录')

print()
print('=' * 100)



