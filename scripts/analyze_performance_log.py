#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分析性能监控日志，找出耗时最长的接口"""

import re
from collections import defaultdict
from pathlib import Path

log_file = Path(__file__).parent.parent / 'logs' / 'oddsmind.log'
perf_data = []

print(f"正在读取日志文件: {log_file}")
print()

# 读取日志文件
with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if 'PERF' in line:
            # 提取性能数据
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

print(f"共找到 {len(perf_data)} 条性能记录")
print()

# 只分析最近500条
recent_data = perf_data[-500:] if len(perf_data) > 500 else perf_data
print(f"分析最近 {len(recent_data)} 条记录")
print()

# 按总耗时排序
recent_data.sort(key=lambda x: x['total'], reverse=True)

print('=' * 100)
print('Top 20 耗时最长的接口调用:')
print('=' * 100)
print(f"{'排名':<6s} {'接口名称':<50s} {'状态码':<8s} {'总耗时':<12s} {'应用耗时':<12s} {'数据库耗时':<12s}")
print('-' * 100)
for i, data in enumerate(recent_data[:20], 1):
    print(f"{i:<6d} {data['endpoint']:<50s} {data['status']:<8d} {data['total']:<12.3f}s {data['app']:<12.3f}s {data['db']:<12.3f}s")

print()
print('=' * 100)
print('按接口分组的统计（只显示平均耗时>1.0s的接口）')
print('=' * 100)
print()

# 按接口分组统计
endpoint_stats = defaultdict(lambda: {'count': 0, 'total_time': 0, 'max_time': 0, 'errors': 0})
for data in recent_data:
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

avg_stats.sort(key=lambda x: x['avg_time'], reverse=True)

print(f"{'接口名称':<50s} {'调用次数':<10s} {'平均耗时':<12s} {'最大耗时':<12s} {'错误数':<8s}")
print('-' * 100)
for stat in avg_stats[:20]:
    print(f"{stat['endpoint']:<50s} {stat['count']:<10d} {stat['avg_time']:<12.3f}s {stat['max_time']:<12.3f}s {stat['errors']:<8d}")



