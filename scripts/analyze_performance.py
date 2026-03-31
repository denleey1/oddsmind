#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API性能分析工具
分析日志中的性能监控数据，找出瓶颈
"""

import re
import sys
from collections import defaultdict
from datetime import datetime

def analyze_performance(log_file='logs/oddsmind.log', lines_to_analyze=5000):
    """分析性能日志"""
    
    print("="*80)
    print("API 性能分析报告")
    print("="*80)
    print()
    
    # 读取日志
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        print(f"✅ 已读取日志文件，共 {len(lines)} 行")
        print(f"   分析最近 {min(lines_to_analyze, len(lines))} 行")
        print()
    except Exception as e:
        print(f"❌ 读取日志失败: {e}")
        return
    
    # 1. 分析HTTP请求
    api_requests = []
    for line in lines[-lines_to_analyze:]:
        # 匹配werkzeug日志格式
        match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?"(GET|POST|PUT|DELETE) ([^"]+)" (\d{3})', line)
        if match:
            time_str, method, path, status = match.groups()
            path = re.sub(r'\x1b\[[0-9;]*m', '', path).strip()
            api_requests.append({
                'time': time_str,
                'method': method,
                'path': path,
                'status': int(status)
            })
    
    # 2. 分析性能监控日志
    perf_pattern = r'PERF \[([^\]]+)\] status=(\d+) total=([\d.]+)s app=([\d.]+)s db=([\d.]+)s serialize=([\d.]+)s'
    perf_data = defaultdict(list)
    
    for line in lines[-lines_to_analyze:]:
        match = re.search(perf_pattern, line)
        if match:
            endpoint, status, total, app, db, serialize = match.groups()
            perf_data[endpoint].append({
                'status': int(status),
                'total': float(total),
                'app': float(app),
                'db': float(db),
                'serialize': float(serialize)
            })
    
    # 3. 显示API调用统计
    if api_requests:
        print("="*80)
        print("API 调用统计")
        print("="*80)
        print()
        
        endpoint_stats = defaultdict(lambda: {'count': 0, 'status_200': 0, 'status_4xx': 0, 'status_5xx': 0})
        
        for req in api_requests:
            path = req['path']
            endpoint = re.sub(r'/\d+', '/<id>', path)
            endpoint = re.sub(r'\?.*', '', endpoint)
            
            endpoint_stats[endpoint]['count'] += 1
            if req['status'] == 200:
                endpoint_stats[endpoint]['status_200'] += 1
            elif 400 <= req['status'] < 500:
                endpoint_stats[endpoint]['status_4xx'] += 1
            elif req['status'] >= 500:
                endpoint_stats[endpoint]['status_5xx'] += 1
        
        for endpoint, stats in sorted(endpoint_stats.items(), key=lambda x: x[1]['count'], reverse=True):
            total = stats['count']
            success_rate = (stats['status_200'] / total * 100) if total > 0 else 0
            print(f"📍 {endpoint}")
            print(f"   总调用: {total} 次 | 成功: {stats['status_200']} ({success_rate:.1f}%) | 4xx: {stats['status_4xx']} | 5xx: {stats['status_5xx']}")
            if stats['status_5xx'] > 0:
                print(f"   ⚠️  有 {stats['status_5xx']} 个500错误！")
        print()
    
    # 4. 显示性能分析
    if perf_data:
        print("="*80)
        print("性能瓶颈分析")
        print("="*80)
        print()
        
        for endpoint, data_list in sorted(perf_data.items(), key=lambda x: len(x[1]), reverse=True):
            if not data_list:
                continue
            
            total_times = [d['total'] for d in data_list]
            app_times = [d['app'] for d in data_list]
            db_times = [d['db'] for d in data_list]
            serialize_times = [d['serialize'] for d in data_list]
            
            def calc_stats(times):
                if not times:
                    return 0, 0, 0, 0
                sorted_times = sorted(times)
                count = len(sorted_times)
                avg = sum(sorted_times) / count
                p50 = sorted_times[count // 2] if count > 0 else 0
                p95 = sorted_times[int(count * 0.95)] if count > 1 else sorted_times[-1] if sorted_times else 0
                max_time = max(sorted_times) if sorted_times else 0
                return count, avg, p50, p95, max_time
            
            total_count, total_avg, total_p50, total_p95, total_max = calc_stats(total_times)
            app_count, app_avg, app_p50, app_p95, app_max = calc_stats(app_times)
            db_count, db_avg, db_p50, db_p95, db_max = calc_stats(db_times)
            serialize_count, serialize_avg, serialize_p50, serialize_p95, serialize_max = calc_stats(serialize_times)
            
            # 计算瓶颈
            if total_avg > 0:
                db_ratio = (db_avg / total_avg) * 100
                app_ratio = (app_avg / total_avg) * 100
                serialize_ratio = (serialize_avg / total_avg) * 100
                
                bottleneck = []
                if db_ratio > 50:
                    bottleneck.append(f"数据库({db_ratio:.1f}%)")
                if serialize_ratio > 30:
                    bottleneck.append(f"序列化({serialize_ratio:.1f}%)")
                if app_ratio > 40:
                    bottleneck.append(f"应用处理({app_ratio:.1f}%)")
                
                bottleneck_str = " | ".join(bottleneck) if bottleneck else "无明显瓶颈"
            else:
                bottleneck_str = "数据不足"
            
            print(f"📍 {endpoint}")
            print(f"   调用次数: {total_count}")
            print(f"   总耗时: 平均={total_avg:.3f}s | P50={total_p50:.3f}s | P95={total_p95:.3f}s | 最大={total_max:.3f}s")
            print(f"   ├─ 应用处理: 平均={app_avg:.3f}s | P95={app_p95:.3f}s")
            print(f"   ├─ 数据库查询: 平均={db_avg:.3f}s | P95={db_p95:.3f}s")
            print(f"   └─ 序列化: 平均={serialize_avg:.3f}s | P95={serialize_p95:.3f}s")
            print(f"   🔍 瓶颈: {bottleneck_str}")
            print()
        
        # 找出最慢的API
        slow_apis = []
        for endpoint, data_list in perf_data.items():
            if data_list:
                avg_total = sum(d['total'] for d in data_list) / len(data_list)
                slow_apis.append((endpoint, avg_total, len(data_list)))
        
        slow_apis.sort(key=lambda x: x[1], reverse=True)
        
        if slow_apis:
            print("="*80)
            print("最慢的API（按平均耗时排序）")
            print("="*80)
            print()
            for i, (endpoint, avg_time, count) in enumerate(slow_apis[:10], 1):
                print(f"{i:2d}. {endpoint}: {avg_time:.3f}s (调用{count}次)")
            print()
    else:
        print("⚠️  未找到性能监控数据")
        print("   可能原因:")
        print("   1. 接口还未被调用")
        print("   2. 性能监控未启用")
        print("   3. 日志格式不匹配")
        print()
    
    # 5. 优化建议
    print("="*80)
    print("优化建议")
    print("="*80)
    print()
    
    if perf_data:
        # 分析瓶颈
        db_bottleneck = []
        serialize_bottleneck = []
        
        for endpoint, data_list in perf_data.items():
            if data_list:
                avg_total = sum(d['total'] for d in data_list) / len(data_list)
                avg_db = sum(d['db'] for d in data_list) / len(data_list)
                avg_serialize = sum(d['serialize'] for d in data_list) / len(data_list)
                
                if avg_total > 0:
                    if avg_db / avg_total > 0.5:
                        db_bottleneck.append((endpoint, avg_db, avg_total))
                    if avg_serialize / avg_total > 0.3:
                        serialize_bottleneck.append((endpoint, avg_serialize, avg_total))
        
        if db_bottleneck:
            print("🔍 数据库查询瓶颈:")
            for endpoint, db_time, total_time in sorted(db_bottleneck, key=lambda x: x[1], reverse=True)[:5]:
                print(f"   - {endpoint}: 数据库耗时 {db_time:.3f}s ({db_time/total_time*100:.1f}%)")
            print("   建议:")
            print("   1. 检查SQL查询是否有索引")
            print("   2. 优化JOIN查询")
            print("   3. 添加缓存（Redis/内存缓存）")
            print("   4. 考虑分页减少数据量")
            print()
        
        if serialize_bottleneck:
            print("🔍 序列化瓶颈:")
            for endpoint, serialize_time, total_time in sorted(serialize_bottleneck, key=lambda x: x[1], reverse=True)[:5]:
                print(f"   - {endpoint}: 序列化耗时 {serialize_time:.3f}s ({serialize_time/total_time*100:.1f}%)")
            print("   建议:")
            print("   1. 减少返回数据量（字段筛选）")
            print("   2. 启用gzip压缩")
            print("   3. 优化JSON序列化")
            print()
        
        if not db_bottleneck and not serialize_bottleneck:
            print("✅ 当前性能良好，无明显瓶颈")
            print()
    else:
        print("⚠️  无法提供优化建议（缺少性能数据）")
        print()
    
    print("="*80)

if __name__ == '__main__':
    log_file = sys.argv[1] if len(sys.argv) > 1 else 'logs/oddsmind.log'
    lines_to_analyze = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    analyze_performance(log_file, lines_to_analyze)















