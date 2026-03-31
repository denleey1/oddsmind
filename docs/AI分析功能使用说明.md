# AI分析功能使用说明

## 功能概述

AI分析功能允许在比赛开赛前40分钟内，调用Google AI（Gemini）对比赛进行专业的盘口分析，并将分析结果保存到数据库中。

## 功能特点

1. **时间限制**：仅在开赛前40分钟内允许分析
2. **防重复**：每个比赛只能分析一次，结果保存到数据库
3. **专业分析**：使用《足球盘口分析教程》全本内容作为System Role
4. **结果保存**：AI分析结果和最终判断都会保存到数据库

## 安装步骤

### 1. 安装依赖

```bash
pip install google-genai
```

或者更新requirements.txt后：

```bash
pip install -r requirements.txt
```

### 2. 创建数据库表

执行SQL脚本创建表：

```bash
mysql -u your_username -p your_database < scripts/create_ai_analysis_table.sql
```

或者直接在MySQL中执行：

```sql
CREATE TABLE IF NOT EXISTS `match_ai_analysis` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `match_id` VARCHAR(50) NOT NULL COMMENT '比赛ID',
    `analysis_text` TEXT NOT NULL COMMENT 'AI分析完整文本',
    `final_judgment` VARCHAR(500) DEFAULT NULL COMMENT 'AI最终判断结果（提取的关键结论）',
    `analysis_data` JSON DEFAULT NULL COMMENT '分析时使用的原始数据（JSON格式）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_match_id` (`match_id`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='比赛AI分析结果表';
```

### 3. 配置API Key

在环境变量中设置Google AI API Key：

```bash
# 在 oddsmind.env 文件中添加
export GEMINI_API_KEY="your-google-ai-api-key"
```

或者：

```bash
export GOOGLE_AI_API_KEY="your-google-ai-api-key"
```

## 使用方法

### 前端使用

1. 访问比赛详情页面
2. 如果比赛在开赛前40分钟内，会显示"🤖 AI智能分析"按钮
3. 点击按钮触发AI分析
4. 分析完成后，结果会显示在模态框中
5. 如果已有分析结果，按钮会变为"查看分析结果"

### API接口

#### 1. 检查是否已有分析结果

```
GET /api/matches/<match_id>/ai-analysis/check
```

**响应示例：**

```json
{
    "success": true,
    "exists": true,
    "data": {
        "analysis": "完整的AI分析文本...",
        "finalJudgment": "最终判断结果...",
        "createdAt": "2024-01-01T12:00:00"
    }
}
```

#### 2. 触发AI分析

```
POST /api/matches/<match_id>/ai-analysis
```

**请求体（可选）：**

```json
{
    "apiKey": "your-api-key",  // 可选，如果不提供则使用环境变量
    "promptTemplate": "自定义提示词..."  // 可选，使用默认System Role
}
```

**响应示例：**

```json
{
    "success": true,
    "data": {
        "analysis": "完整的AI分析文本...",
        "finalJudgment": "最终判断结果...",
        "matchInfo": {
            "matchId": "123456",
            "leagueName": "英超",
            "homeTeam": "主队名称",
            "awayTeam": "客队名称"
        }
    }
}
```

## 功能限制

1. **时间限制**：只能在开赛前40分钟内进行分析
2. **单次限制**：每个比赛只能分析一次，结果保存后不允许重复分析
3. **API限制**：受Google AI API的调用频率限制

## 数据库表结构

### match_ai_analysis

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| match_id | VARCHAR(50) | 比赛ID（唯一） |
| analysis_text | TEXT | AI分析完整文本 |
| final_judgment | VARCHAR(500) | AI最终判断结果 |
| analysis_data | JSON | 分析时使用的原始数据 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

## 注意事项

1. 确保Google AI API Key有效且有足够的配额
2. 分析过程可能需要几秒到几十秒，请耐心等待
3. 如果分析失败，可以查看服务器日志获取详细错误信息
4. 数据库表使用唯一约束，确保每个比赛只有一条分析记录

## 故障排查

### 1. 按钮不显示

- 检查比赛时间是否在开赛前40分钟内
- 检查比赛状态是否为'scheduled'
- 查看浏览器控制台是否有错误

### 2. 分析失败

- 检查API Key是否正确配置
- 检查网络连接是否正常
- 查看服务器日志获取详细错误

### 3. 数据库错误

- 确认数据库表已创建
- 检查数据库连接配置
- 查看数据库日志

