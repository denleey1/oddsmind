# API 性能优化记录

## 日期
2025-12-27

## 优化内容

### 1. 修复 datetime 未定义错误 ✅
- **问题**: `NameError: name 'datetime' is not defined`
- **位置**: `application/routes/web.py` 第399行和第618行
- **修复**: 将 `isinstance(match['match_time'], datetime)` 改为 `hasattr(match['match_time'], 'isoformat')`
- **影响**: 修复了微信小程序调用 API 时的 500 错误

### 2. 添加性能监控系统 ✅
- **文件**: `utils/performance_monitor.py`
- **功能**:
  - 记录请求各阶段耗时（DNS、连接、TLS、应用处理、数据库查询、序列化）
  - 自动记录到日志，格式：`PERF [endpoint] status=200 total=0.123s app=0.050s db=0.030s serialize=0.020s`
  - 支持装饰器方式使用：`@performance_monitor`
- **使用**: 已应用到 `/api/matches/today` 和 `/api/public/matches/today` 接口

### 3. 接口优化 ✅
- **分页支持**:
  - 参数: `page` (默认1), `page_size` (默认50, 最大200)
  - 返回: `total`, `page`, `page_size`, `has_more`
- **字段筛选**:
  - 参数: `fields` (逗号分隔的字段列表)
  - 只返回请求的字段，减少传输数据量
- **性能监控**: 自动记录数据库查询和序列化耗时

### 4. 数据库查询优化（进行中）
- **待完成**:
  - 检查索引是否缺失
  - 分析慢查询
  - 优化 N+1 查询

### 5. 缓存机制（待实施）
- **计划**:
  - 使用 Redis 或内存缓存热点数据
  - 缓存公共列表数据
  - 设置合理的过期时间

### 6. Nginx 配置优化（待实施）
- **计划**:
  - 启用 gzip/brotli 压缩
  - 配置 keep-alive
  - 优化静态资源缓存

## 性能监控日志示例

```
PERF [web.get_today_matches] status=200 total=0.123s app=0.050s db=0.030s serialize=0.020s connect=0.010s tls=0.013s
```

## API 使用示例

### 分页查询
```
GET /api/matches/today?page=1&page_size=20
```

### 字段筛选
```
GET /api/matches/today?fields=matchId,homeTeam,awayTeam,matchTime
```

### 组合使用
```
GET /api/matches/today?page=1&page_size=20&fields=matchId,homeTeam,awayTeam&status=scheduled
```

## 下一步优化建议

1. **数据库优化**:
   - 检查慢查询日志
   - 添加必要的索引
   - 优化 JOIN 查询

2. **缓存策略**:
   - 缓存今日比赛列表（5分钟过期）
   - 缓存比赛详情（1分钟过期）
   - 使用 Redis 或内存缓存

3. **响应压缩**:
   - 配置 Nginx gzip/brotli
   - 减少 JSON 响应大小

4. **并发优化**:
   - 检查 worker 进程数
   - 优化数据库连接池大小

5. **监控指标**:
   - 记录 p50/p95/p99 响应时间
   - 监控错误率
   - 设置告警阈值















