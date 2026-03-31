# AI分析接口说明

## 一、服务重启问题

### 需要重启的情况
- ✅ **修改了Python代码**（路由、函数逻辑等）- **必须重启**
- ✅ **修改了环境变量**（如GEMINI_API_KEY）- **需要重启**
- ✅ **修改了数据库结构** - **需要重启并执行迁移**

### 不需要重启的情况
- ❌ 修改了前端代码（HTML/JS/CSS）
- ❌ 修改了静态资源
- ❌ 修改了数据库数据（不涉及结构）

**当前状态**：如果修改了prompt内容，需要重启Flask服务才能生效。

---

## 二、微信小程序调用

### 权限设计
- ✅ **查看接口**：`GET /api/matches/<match_id>/ai-analysis/check` - **小程序可以使用**
  - 功能：查看数据库中已有的AI分析结果
  - 权限：小程序和Web端都可以使用
  - 使用场景：点开比赛，如果有分析就显示，没有就不显示

- ❌ **分析接口**：`POST /api/matches/<match_id>/ai-analysis` - **小程序不允许使用**
  - 功能：触发AI分析（调用Google AI）
  - 权限：仅限Web端使用
  - 限制：如果检测到JWT token或小程序User-Agent，会拒绝访问

### 小程序使用方式

**小程序只能查看已有结果，不能触发分析：**

```javascript
// 小程序代码示例
// 点开比赛详情页时，检查是否有AI分析
async function checkAIAnalysis(matchId) {
  try {
    const response = await wx.request({
      url: `https://oddsmind.top/api/matches/${matchId}/ai-analysis/check`,
      method: 'GET',
      header: {
        'Authorization': `Bearer ${token}` // JWT token
      }
    });
    
    if (response.data.success && response.data.exists) {
      // 有分析结果，显示
      showAIAnalysis(response.data.data);
    } else {
      // 没有分析结果，不显示AI分析入口
      hideAIAnalysisButton();
    }
  } catch (error) {
    console.error('检查AI分析失败:', error);
  }
}
```

### 后端实现

**POST接口（触发分析）** - 拒绝小程序：
```python
@web_bp.route('/api/matches/<int:match_id>/ai-analysis', methods=['POST'])
def get_ai_analysis(match_id: int):
    # 检查是否来自小程序
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        # 有JWT token，可能是小程序，拒绝访问
        return jsonify({
            'success': False,
            'error': '此接口仅限Web端使用，小程序请使用查看接口获取已有分析结果'
        }), 403
    # ... 继续处理
```

**GET接口（查看结果）** - 允许小程序：
```python
@web_bp.route('/api/matches/<int:match_id>/ai-analysis/check', methods=['GET'])
def check_ai_analysis_exists(match_id: int):
    # 小程序和Web端都可以使用
    # ... 查询数据库并返回结果
```

---

## 三、并发处理问题

### 当前实现
- ❌ **同步处理**：每个请求会阻塞等待AI分析完成（30-60秒）
- ❌ **单线程**：Flask默认单线程处理请求，会排队
- ❌ **问题**：30场比赛同时请求 = **排队处理**，最后一个可能要等30-60分钟

### 并发方案

#### 方案1：异步任务（推荐 - 使用Celery）
```python
# 1. 创建Celery任务
@celery_app.task
def analyze_match_async(match_id: int, user_id: int):
    # AI分析逻辑
    pass

# 2. 接口改为异步
@web_bp.route('/api/matches/<int:match_id>/ai-analysis', methods=['POST'])
def get_ai_analysis(match_id: int):
    # 提交任务到队列
    task = analyze_match_async.delay(match_id, user_id)
    return jsonify({
        'success': True,
        'task_id': task.id,
        'status': 'queued'
    })

# 3. 查询任务状态
@web_bp.route('/api/ai-analysis/task/<task_id>', methods=['GET'])
def get_task_status(task_id: str):
    task = analyze_match_async.AsyncResult(task_id)
    return jsonify({
        'status': task.status,
        'result': task.result if task.ready() else None
    })
```

**优势**：
- ✅ 30场比赛可以并发处理
- ✅ 不阻塞HTTP请求
- ✅ 可以设置并发数量（如同时处理5个）

#### 方案2：线程池（简单但有限制）
```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=5)  # 最多5个并发

@web_bp.route('/api/matches/<int:match_id>/ai-analysis', methods=['POST'])
def get_ai_analysis(match_id: int):
    # 提交到线程池
    future = executor.submit(analyze_match, match_id)
    return jsonify({
        'success': True,
        'status': 'processing'
    })
```

**限制**：
- ⚠️ 受限于服务器资源
- ⚠️ 重启服务会丢失任务
- ⚠️ 无法持久化任务状态

#### 方案3：队列 + 后台任务（折中方案）
```python
import queue
import threading

analysis_queue = queue.Queue()
worker_threads = []

def worker():
    while True:
        match_id = analysis_queue.get()
        if match_id is None:
            break
        analyze_match(match_id)
        analysis_queue.task_done()

# 启动5个工作线程
for i in range(5):
    t = threading.Thread(target=worker)
    t.start()
    worker_threads.append(t)

@web_bp.route('/api/matches/<int:match_id>/ai-analysis', methods=['POST'])
def get_ai_analysis(match_id: int):
    analysis_queue.put(match_id)
    return jsonify({
        'success': True,
        'status': 'queued'
    })
```

---

## 四、推荐方案

### 短期方案（快速实现）
使用**线程池**，限制并发数量（如5个），简单快速。

### 长期方案（推荐）
使用**Celery异步任务**：
1. 30场比赛提交到队列
2. Celery Worker并发处理（可配置并发数）
3. 前端轮询或WebSocket获取结果
4. 任务状态持久化，重启不丢失

---

## 五、实施建议

### 优先级1：添加JWT验证
- 确保只有登录用户可以使用
- 防止未授权访问

### 优先级2：实现异步处理
- 使用Celery或线程池
- 支持并发分析

### 优先级3：优化用户体验
- 前端显示分析进度
- 支持批量分析
- 结果通知（WebSocket或轮询）

