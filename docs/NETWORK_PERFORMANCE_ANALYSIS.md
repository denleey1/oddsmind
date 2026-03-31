# 网络性能问题分析与解决方案

**测试结果（用户提供）**:
- 今日比赛列表：TTFB≈13.6s，TOTAL≈13.6s
- 比赛详情：TTFB≈16.6s，TOTAL≈16.6s
- 握手时间：0.01s（DNS/TLS快）

**结论**：问题在服务器响应/处理阶段，不在网络传输

---

## 🔍 根本原因分析

### 1. Rate Limiting ⚠️ **最可能的根本原因**

从日志中发现大量警告：
```
WARNING - Rate limit timeout for match 2784649, retrying after 2.5s (attempt 1/3)
WARNING - Rate limit timeout for match 2784649, retrying after 3.0s (attempt 2/3)
WARNING - Rate limit timeout for match 969000, retrying after 2.5s (attempt 1/3)
```

**问题**：
- Titan007（数据源网站）有严格的速率限制
- 每次触发2.5-3秒的延迟
- 一次请求可能重试2-3次
- 总延迟：2.5s × 3 = 7.5秒 + 实际查询时间

**为什么数据库优化后还慢？**
- 数据库查询确实快了（0.063秒）
- 但**爬虫/数据源访问**是独立的，不受数据库优化影响
- Titan007爬取仍然触发Rate Limit

### 2. 并发爬虫瓶颈

从日志看：
```
INFO - Starting odds scraping for 146 matches (max_workers=10, skip_existing=False)
```

**问题**：
- 同时启动10个worker爬取146场比赛
- 每个比赛需要访问20+家公司
- 总请求数：146 × 20 = 2920个请求
- 10个worker并发：每个worker约292个请求
- Titan007肯定会对这样的并发进行Rate Limiting

**为什么只有请求接口才慢？**
- 列表接口不需要爬取，只是查询数据库
- 但数据库中可能没有最新数据
- 触发了后台爬取任务
- 爬取触发了Rate Limit
- Rate Limit导致后续请求被延迟

### 3. Gunicorn配置不足

当前配置：
```bash
-w 4 -b 127.0.0.1:5000
```

**问题**：
- 只有4个worker
- 并发请求超过4个时会排队
- 如果有Rate Limit，worker会被长时间占用

---

## ✅ 立即可行的解决方案

### 方案1：优化爬虫并发（最优先级）

#### 修改配置文件<tool_call>read_file<arg_key>limit</arg_key><arg_value>50
