# Redis 部署指南

## 是否需要部署Redis？

### 当前状态
- ✅ Redis Python库已安装
- ❌ Redis服务未运行
- ✅ 系统已支持Redis（如果不可用会自动fallback到内存缓存）

### 推荐：部署Redis

**优势**：
1. **多进程共享缓存**：如果应用有多个worker进程，内存缓存无法共享，Redis可以
2. **持久化**：Redis可以配置持久化，重启不丢失缓存
3. **更好的性能**：Redis是专门的内存数据库，性能更优
4. **支持分布式**：如果未来需要多服务器部署，Redis可以共享缓存

**不使用Redis的影响**：
- 系统仍可正常工作，使用内存缓存
- 多进程环境下缓存无法共享
- 应用重启后缓存丢失

## 安装和配置Redis

### 1. 安装Redis

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server -y

# 或者使用Docker
docker run -d --name redis -p 6379:6379 redis:latest
```

### 2. 启动Redis服务

```bash
# 启动服务
sudo systemctl start redis-server

# 设置开机自启
sudo systemctl enable redis-server

# 检查状态
sudo systemctl status redis-server
```

### 3. 配置Redis（可选，推荐）

编辑配置文件 `/etc/redis/redis.conf`：

```bash
sudo nano /etc/redis/redis.conf
```

**推荐配置**：
```conf
# 最大内存（根据服务器内存调整，例如2GB）
maxmemory 2gb

# 内存淘汰策略（LRU）
maxmemory-policy allkeys-lru

# 持久化（可选，如果希望重启后保留缓存）
save 900 1
save 300 10
save 60 10000

# 绑定地址（如果只本地访问，保持127.0.0.1）
bind 127.0.0.1

# 端口（默认6379）
port 6379
```

**重启Redis使配置生效**：
```bash
sudo systemctl restart redis-server
```

### 4. 测试Redis连接

```bash
# 命令行测试
redis-cli ping
# 应该返回: PONG

# 或者使用Python测试
python3 -c "
import redis
r = redis.Redis(host='localhost', port=6379, db=0)
print('Redis连接成功:', r.ping())
"
```

### 5. 验证应用是否使用Redis

重启应用后，查看日志：

```bash
# 查看应用日志
tail -f logs/oddsmind.log | grep -i redis

# 应该看到：
# Redis缓存已启用
```

或者检查缓存统计：

```python
from utils.cache import get_cache_stats
stats = get_cache_stats()
print(f"Redis可用: {stats['redis_available']}")
```

## 性能监控

### Redis监控命令

```bash
# 查看Redis信息
redis-cli info

# 查看内存使用
redis-cli info memory

# 查看连接数
redis-cli info clients

# 查看键数量
redis-cli dbsize

# 查看所有键（谨慎使用，数据量大时很慢）
redis-cli keys "*"
```

### 清理Redis缓存（如果需要）

```bash
# 清空当前数据库
redis-cli flushdb

# 清空所有数据库
redis-cli flushall
```

## 故障排查

### 问题1: Redis连接失败

**检查**：
```bash
# 检查服务是否运行
sudo systemctl status redis-server

# 检查端口是否监听
sudo netstat -tlnp | grep 6379
# 或
sudo ss -tlnp | grep 6379
```

**解决**：
```bash
# 启动服务
sudo systemctl start redis-server
```

### 问题2: 内存不足

**检查**：
```bash
redis-cli info memory | grep used_memory_human
```

**解决**：
- 调整 `maxmemory` 配置
- 确保 `maxmemory-policy` 设置为 `allkeys-lru`（自动淘汰）

### 问题3: 权限问题

**检查**：
```bash
# 查看Redis日志
sudo tail -f /var/log/redis/redis-server.log
```

**解决**：
- 确保Redis用户有权限访问配置文件和日志目录
- 检查SELinux/AppArmor设置（如果启用）

## 生产环境建议

### 1. 安全配置

```conf
# 设置密码（推荐）
requirepass your_strong_password_here

# 禁用危险命令
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
```

**应用代码需要相应修改**（如果需要密码）：
```python
# utils/cache.py
self._redis = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    password='your_strong_password_here',  # 添加密码
    decode_responses=True,
    socket_connect_timeout=1
)
```

### 2. 监控和告警

- 监控Redis内存使用率
- 监控连接数
- 设置内存使用告警（例如>80%）

### 3. 备份（如果启用了持久化）

```bash
# 手动备份
redis-cli save
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb
```

## 总结

### 快速部署（最简单）

```bash
# 1. 安装
sudo apt install redis-server -y

# 2. 启动
sudo systemctl start redis-server
sudo systemctl enable redis-server

# 3. 验证
redis-cli ping

# 4. 重启应用
sudo systemctl restart oddsmind
```

### 不部署Redis的影响

- ✅ 系统仍可正常工作（使用内存缓存）
- ⚠️ 多进程环境下缓存无法共享
- ⚠️ 应用重启后缓存丢失
- ⚠️ 性能略低于Redis

### 推荐

**对于生产环境，强烈推荐部署Redis**，因为：
1. 安装简单（几分钟）
2. 资源占用小（通常<100MB内存）
3. 显著提升缓存效果（多进程共享）
4. 更好的性能和稳定性












