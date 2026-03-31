// utils/util.js
// 通用工具函数

/**
 * 格式化时间
 * @param {Date|String} date - 日期对象或日期字符串
 * @param {String} format - 格式化模板
 */
function formatTime(date, format = 'YYYY-MM-DD hh:mm:ss') {
  if (!date) return ''
  
  // 如果是字符串，转换为Date对象
  if (typeof date === 'string') {
    date = new Date(date)
  }

  const year = date.getFullYear()
  const month = date.getMonth() + 1
  const day = date.getDate()
  const hour = date.getHours()
  const minute = date.getMinutes()
  const second = date.getSeconds()

  const formatNumber = n => {
    n = n.toString()
    return n[1] ? n : '0' + n
  }

  return format
    .replace('YYYY', year)
    .replace('MM', formatNumber(month))
    .replace('DD', formatNumber(day))
    .replace('hh', formatNumber(hour))
    .replace('mm', formatNumber(minute))
    .replace('ss', formatNumber(second))
}

/**
 * 格式化比赛时间
 * @param {String} matchTime - 比赛时间字符串
 */
function formatMatchTime(matchTime) {
  if (!matchTime) return ''
  
  const date = new Date(matchTime)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000)
  const matchDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())

  let prefix = ''
  if (matchDate.getTime() === today.getTime()) {
    prefix = '今天 '
  } else if (matchDate.getTime() === tomorrow.getTime()) {
    prefix = '明天 '
  } else {
    prefix = formatTime(date, 'MM-DD ')
  }

  return prefix + formatTime(date, 'hh:mm')
}

/**
 * 获取比赛状态文本
 * @param {String} status - 比赛状态
 */
function getMatchStatusText(status) {
  const statusMap = {
    'scheduled': '未开始',
    'live': '进行中',
    'finished': '已结束',
    'halftime': '中场',
    'postponed': '推迟',
    'cancelled': '取消',
    '未开始': '未开始',
    '进行中': '进行中',
    '已结束': '已结束',
    '中场': '中场',
    '推迟': '推迟',
    '取消': '取消'
  }
  
  return statusMap[status] || status
}

/**
 * 获取比赛状态颜色
 * @param {String} status - 比赛状态
 */
function getMatchStatusColor(status) {
  const colorMap = {
    'scheduled': '#FF6B35',
    'live': '#2ECC71',
    'finished': '#7F8C8D',
    'halftime': '#F7B731',
    'postponed': '#E74C3C',
    'cancelled': '#E74C3C',
    '未开始': '#FF6B35',
    '进行中': '#2ECC71',
    '已结束': '#7F8C8D',
    '中场': '#F7B731',
    '推迟': '#E74C3C',
    '取消': '#E74C3C'
  }
  
  return colorMap[status] || '#7F8C8D'
}

/**
 * 节流函数
 * @param {Function} fn - 要执行的函数
 * @param {Number} delay - 延迟时间（毫秒）
 */
function throttle(fn, delay = 500) {
  let timer = null
  return function(...args) {
    if (timer) return
    timer = setTimeout(() => {
      fn.apply(this, args)
      timer = null
    }, delay)
  }
}

/**
 * 防抖函数
 * @param {Function} fn - 要执行的函数
 * @param {Number} delay - 延迟时间（毫秒）
 */
function debounce(fn, delay = 500) {
  let timer = null
  return function(...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      fn.apply(this, args)
    }, delay)
  }
}

/**
 * 数据缓存
 */
const cache = {
  /**
   * 设置缓存
   * @param {String} key - 键
   * @param {Any} data - 数据
   * @param {Number} expire - 过期时间（毫秒）
   */
  set(key, data, expire = 0) {
    const cacheData = {
      data: data,
      timestamp: Date.now(),
      expire: expire
    }
    try {
      wx.setStorageSync(key, JSON.stringify(cacheData))
      return true
    } catch (e) {
      console.error('缓存设置失败:', e)
      return false
    }
  },

  /**
   * 获取缓存
   * @param {String} key - 键
   */
  get(key) {
    try {
      const cacheStr = wx.getStorageSync(key)
      if (!cacheStr) return null

      const cacheData = JSON.parse(cacheStr)
      
      // 检查是否过期
      if (cacheData.expire > 0) {
        const now = Date.now()
        if (now - cacheData.timestamp > cacheData.expire) {
          this.remove(key)
          return null
        }
      }

      return cacheData.data
    } catch (e) {
      console.error('缓存获取失败:', e)
      return null
    }
  },

  /**
   * 删除缓存
   * @param {String} key - 键
   */
  remove(key) {
    try {
      wx.removeStorageSync(key)
      return true
    } catch (e) {
      console.error('缓存删除失败:', e)
      return false
    }
  },

  /**
   * 清空所有缓存
   */
  clear() {
    try {
      wx.clearStorageSync()
      return true
    } catch (e) {
      console.error('缓存清空失败:', e)
      return false
    }
  }
}

/**
 * 显示Toast提示
 * @param {String} title - 提示文本
 * @param {String} icon - 图标类型（success/error/loading/none）
 * @param {Number} duration - 显示时长（毫秒）
 */
function showToast(title, icon = 'none', duration = 2000) {
  wx.showToast({
    title: title,
    icon: icon,
    duration: duration
  })
}

/**
 * 显示确认对话框
 * @param {String} content - 内容
 * @param {String} title - 标题
 */
function showConfirm(content, title = '提示') {
  return new Promise((resolve, reject) => {
    wx.showModal({
      title: title,
      content: content,
      success: (res) => {
        if (res.confirm) {
          resolve(true)
        } else {
          reject(false)
        }
      }
    })
  })
}

/**
 * 复制到剪贴板
 * @param {String} data - 要复制的内容
 */
function copyToClipboard(data) {
  wx.setClipboardData({
    data: data,
    success: () => {
      showToast('复制成功', 'success')
    },
    fail: () => {
      showToast('复制失败', 'error')
    }
  })
}

/**
 * 分享配置
 */
function getShareConfig(title = 'OddsMind足球赔率分析', path = '/pages/index/index') {
  return {
    title: title,
    path: path,
    imageUrl: '' // 可以设置分享图片
  }
}

/**
 * 安全的数字格式化
 * @param {Any} value - 值
 * @param {Number} defaultValue - 默认值
 */
function safeNumber(value, defaultValue = 0) {
  const num = parseFloat(value)
  return isNaN(num) ? defaultValue : num
}

/**
 * 安全的字符串获取
 * @param {Any} value - 值
 * @param {String} defaultValue - 默认值
 */
function safeString(value, defaultValue = '') {
  return value ? String(value) : defaultValue
}

/**
 * 计算相对时间
 * @param {String|Date} date - 日期
 */
function getRelativeTime(date) {
  if (!date) return ''
  
  const now = new Date()
  const target = new Date(date)
  const diff = target.getTime() - now.getTime()
  
  if (diff < 0) {
    // 已经过去
    const absDiff = Math.abs(diff)
    const minutes = Math.floor(absDiff / (60 * 1000))
    const hours = Math.floor(absDiff / (60 * 60 * 1000))
    const days = Math.floor(absDiff / (24 * 60 * 60 * 1000))
    
    if (minutes < 1) return '刚刚'
    if (minutes < 60) return `${minutes}分钟前`
    if (hours < 24) return `${hours}小时前`
    return `${days}天前`
  } else {
    // 还未到来
    const minutes = Math.floor(diff / (60 * 1000))
    const hours = Math.floor(diff / (60 * 60 * 1000))
    const days = Math.floor(diff / (24 * 60 * 60 * 1000))
    
    if (minutes < 1) return '即将开始'
    if (minutes < 60) return `${minutes}分钟后`
    if (hours < 24) return `${hours}小时后`
    return `${days}天后`
  }
}

const RECOMMENDATION_DISPLAY_MAP = {
  'home': '主胜',
  'draw': '平局',
  'away': '客胜',
  '3': '主胜',
  '1': '平局',
  '0': '客胜'
}

function translateRecommendation(recommendation) {
  if (!recommendation) return '--'
  const normalized = String(recommendation).trim()
  if (!normalized) return '--'
  return RECOMMENDATION_DISPLAY_MAP[normalized] || normalized
}

function getRuleColorClass(value) {
  const numValue = parseFloat(value)
  if (!Number.isNaN(numValue)) {
    if (numValue >= 5) return 'rule-red'
    if (numValue >= 4.5) return 'rule-orange'
    if (numValue >= 3.5) return 'rule-yellow'
    if (numValue > 3) return 'rule-yellow'
    return 'rule-green'
  }
  return 'rule-green'
}

module.exports = {
  formatTime,
  formatMatchTime,
  getMatchStatusText,
  getMatchStatusColor,
  throttle,
  debounce,
  cache,
  showToast,
  showConfirm,
  copyToClipboard,
  getShareConfig,
  safeNumber,
  safeString,
  getRelativeTime,
  translateRecommendation,
  getRuleColorClass
}


