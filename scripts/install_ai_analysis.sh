#!/bin/bash
# AI分析功能安装脚本
# 自动安装依赖并创建数据库表

set -e

echo "=========================================="
echo "AI分析功能安装脚本"
echo "=========================================="

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "1. 安装Python依赖..."
cd "$PROJECT_DIR"

# 检查虚拟环境
if [ -d "venv" ]; then
    echo "   激活虚拟环境: venv"
    source venv/bin/activate
else
    echo "   警告: 未找到虚拟环境 venv，将使用系统Python"
fi

# 安装google-genai
echo "   安装 google-genai..."
pip install google-genai

echo ""
echo "2. 创建数据库表..."

# 读取数据库配置
if [ -f "oddsmind.env" ]; then
    source oddsmind.env
    DB_HOST="${MYSQL_HOST:-localhost}"
    DB_USER="${MYSQL_USER:-root}"
    DB_PASSWORD="${MYSQL_PASSWORD:-}"
    DB_NAME="${MYSQL_DATABASE:-oddsmind}"
    DB_PORT="${MYSQL_PORT:-3306}"
else
    echo "   错误: 未找到 oddsmind.env 文件"
    echo "   请手动设置数据库配置或创建 oddsmind.env 文件"
    exit 1
fi

# 执行SQL创建表
echo "   连接数据库: $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
mysql -u "$DB_USER" -p"$DB_PASSWORD" -h "$DB_HOST" -P "$DB_PORT" "$DB_NAME" <<EOF
CREATE TABLE IF NOT EXISTS \`match_ai_analysis\` (
    \`id\` INT AUTO_INCREMENT PRIMARY KEY,
    \`match_id\` VARCHAR(50) NOT NULL COMMENT '比赛ID',
    \`analysis_text\` TEXT NOT NULL COMMENT 'AI分析完整文本',
    \`final_judgment\` VARCHAR(500) DEFAULT NULL COMMENT 'AI最终判断结果（提取的关键结论）',
    \`analysis_data\` JSON DEFAULT NULL COMMENT '分析时使用的原始数据（JSON格式）',
    \`created_at\` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    \`updated_at\` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY \`uk_match_id\` (\`match_id\`),
    KEY \`idx_created_at\` (\`created_at\`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='比赛AI分析结果表';
EOF

if [ $? -eq 0 ]; then
    echo "   ✓ 数据库表创建成功"
else
    echo "   ✗ 数据库表创建失败"
    exit 1
fi

echo ""
echo "=========================================="
echo "安装完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 在 oddsmind.env 中设置 GEMINI_API_KEY 环境变量"
echo "2. 重启应用以使配置生效"
echo ""

