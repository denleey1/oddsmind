// utils/config.js
// 应用配置文件

const API_HOST = 'https://lvyinshuzhi.cn'

const config = {
  // API配置
  api: {
    baseUrl: API_HOST,
    timeout: 30000,
    
    // API端点
    endpoints: {
      // 公共API（无需认证）
      publicMatchesToday: '/api/public/matches/today',
      publicMatchDetail: '/api/public/matches/{id}',
      
      // 认证API（需要登录 - 暂未启用）
      matchesToday: '/api/matches/today',
      matchDetail: '/api/matches/{id}',
      matchAnalyses: '/api/matches/{id}/all_analyses',
      
      // 健康检查
      health: '/health'
    }
  },

  // 应用配置
  app: {
    name: 'OddsMind',
    version: '1.0.0',
    description: '足球赔率分析小程序'
  },

  // 缓存配置
  cache: {
    matchListExpire: 5 * 60 * 1000, // 5分钟
    matchDetailExpire: 3 * 60 * 1000, // 3分钟
  },

  // UI配置
  ui: {
    // 比赛状态颜色
    matchStatusColor: {
      '未开始': '#FF6B35',
      '进行中': '#2ECC71',
      '已结束': '#7F8C8D',
      '中场': '#F7B731',
      '推迟': '#E74C3C',
      '取消': '#E74C3C'
    },
    
    // 比赛状态文本
    matchStatusText: {
      'scheduled': '未开始',
      'live': '进行中',
      'finished': '已结束',
      'halftime': '中场',
      'postponed': '推迟',
      'cancelled': '取消'
    }
  },

  // 联赛图标映射（可选）
  leagueIcons: {
    '英超': '⚽',
    '西甲': '⚽',
    '德甲': '⚽',
    '意甲': '⚽',
    '法甲': '⚽',
    '中超': '⚽'
  }
}

module.exports = config


