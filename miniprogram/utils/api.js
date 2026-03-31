// utils/api.js
// API请求封装
// 自动添加 Token、处理 401、自动刷新 Token

const config = require('./config.js')
const auth = require('./auth.js')
const pendingRequests = new Map()
const memoryCache = new Map()
const networkDiagnostics = {
  running: false,
  lastRun: 0
}

function getHeaderValue(headers, name) {
  if (!headers) return ''
  const lowerName = name.toLowerCase()
  return headers[name] || headers[lowerName] || headers[name.toUpperCase()] || ''
}

function logPerformance(method, fullUrl, duration, headers) {
  const serverTime = getHeaderValue(headers, 'X-Response-Time')
  const dbTime = getHeaderValue(headers, 'X-DB-Time')
  const serverPart = serverTime ? `server ${serverTime}` : 'server n/a'
  const dbPart = dbTime ? `db ${dbTime}` : 'db n/a'
  console.log(`[API] ${method} ${fullUrl} ${duration}ms (${serverPart}, ${dbPart})`)
  if (duration > 2000) {
    console.warn(`[API] slow request ${method} ${fullUrl} ${duration}ms`)
  }
}

function classifyRequestError(errMsg = '') {
  const msg = String(errMsg || '').toLowerCase()
  if (msg.includes('domain list') || msg.includes('not in domain list') || msg.includes('url not in domain list')) {
    return {
      code: 'DOMAIN',
      hint: 'request合法域名未配置，请在小程序后台添加，并检查开发者工具的合法域名校验设置'
    }
  }
  if (msg.includes('ssl') || msg.includes('tls') || msg.includes('certificate') || msg.includes('cert')) {
    return {
      code: 'TLS',
      hint: '可能是HTTPS证书或TLS版本不被信任，请检查证书链/TLS>=1.2'
    }
  }
  if (msg.includes('timeout')) {
    return {
      code: 'TIMEOUT',
      hint: '请求超时，可能是网络不可达、代理阻断或服务端响应慢'
    }
  }
  if (msg.includes('fail')) {
    return {
      code: 'FAIL',
      hint: '网络请求失败，请检查网络/代理/域名配置'
    }
  }
  return null
}

function runNetworkDiagnostics(reason = '') {
  const now = Date.now()
  if (networkDiagnostics.running || now - networkDiagnostics.lastRun < 60000) {
    return
  }
  networkDiagnostics.running = true
  networkDiagnostics.lastRun = now

  try {
    wx.getNetworkType({
      success: (res) => {
        console.log('[API] network type:', res.networkType, 'reason:', reason)
      },
      fail: (err) => {
        console.warn('[API] network type check failed:', err)
      }
    })
  } catch (err) {
    console.warn('[API] network type check exception:', err)
  }

  const healthPath = (config.api && config.api.endpoints && config.api.endpoints.health) || '/health'
  const healthUrl = healthPath.startsWith('http') ? healthPath : config.api.baseUrl + healthPath

  wx.request({
    url: healthUrl,
    method: 'GET',
    timeout: 5000,
    success: (res) => {
      console.log('[API] health check ok:', res.statusCode, 'reason:', reason)
    },
    fail: (err) => {
      console.warn('[API] health check failed:', err, 'reason:', reason)
    },
    complete: () => {
      networkDiagnostics.running = false
    }
  })
}

function readMemoryCache(cacheKey, cacheTime) {
  const cached = memoryCache.get(cacheKey)
  if (!cached || !cached.timestamp) {
    return null
  }
  if (Date.now() - cached.timestamp < cacheTime) {
    return cached.data
  }
  return null
}

function readCache(cacheKey, cacheTime, persist) {
  const cached = readMemoryCache(cacheKey, cacheTime)
  if (cached !== null && cached !== undefined) {
    return cached
  }
  if (!persist) {
    return null
  }
  try {
    const stored = wx.getStorageSync(cacheKey)
    if (stored && stored.timestamp && Date.now() - stored.timestamp < cacheTime) {
      memoryCache.set(cacheKey, stored)
      return stored.data
    }
  } catch (err) {
    console.warn('Cache read failed:', err)
  }
  return null
}

function readCacheFallback(cacheKey, persist) {
  const cached = memoryCache.get(cacheKey)
  if (cached && cached.data) {
    return cached.data
  }
  if (!persist) {
    return null
  }
  try {
    const stored = wx.getStorageSync(cacheKey)
    if (stored && stored.data) {
      memoryCache.set(cacheKey, stored)
      return stored.data
    }
  } catch (err) {
    console.warn('Cache fallback failed:', err)
  }
  return null
}

function writeCache(cacheKey, data, persist) {
  const payload = { data, timestamp: Date.now() }
  memoryCache.set(cacheKey, payload)
  if (!persist) {
    return
  }
  try {
    wx.setStorageSync(cacheKey, payload)
  } catch (err) {
    console.warn('Cache set failed:', err)
  }
}


/**
 * 处理 401 错误（未授权）
 */
function handle401() {
  // 清除本地 Token
  auth.logout()

  // 显示提示
  wx.showToast({
    title: '登录已过期，请重新登录',
    icon: 'none',
    duration: 2000
  })

  // 延迟跳转到登录页（避免与当前页面冲突）
  setTimeout(() => {
    wx.reLaunch({
      url: '/pages/login/login'
    })
  }, 2000)
}

/**
 * 通用请求方法
 * @param {string} url 请求URL
 * @param {string} method 请求方法
 * @param {Object} data 请求数据
 * @param {Object} options 选项 { headers, needAuth, showLoading }
 */
function request(url, method = 'GET', data = {}, options = {}) {
  const {
    headers = {},
    needAuth = true,  // 是否需要认证
    showLoading = true,  // ????????
    suppressToast = false
  } = options

  return new Promise((resolve, reject) => {
    // 显示加载提示
    if (showLoading) {
      wx.showLoading({
        title: '加载中...',
        mask: true
      })
    }

    // 构建完整URL
    const fullUrl = url.startsWith('http') ? url : config.api.baseUrl + url

    // 添加 Token
    const requestHeaders = {
      'Content-Type': 'application/json',
      ...headers
    }

    if (needAuth) {
      const token = auth.getToken()
      if (token) {
        requestHeaders['Authorization'] = `Bearer ${token}`
      }
    }

    const startTime = Date.now()
    wx.request({
      url: fullUrl,
      method: method,
      data: data,
      header: requestHeaders,
      timeout: config.api.timeout,
      success: (res) => {
        if (showLoading) {
          wx.hideLoading()
        }
        logPerformance(method, fullUrl, Date.now() - startTime, res.header)

        if (res.statusCode === 200) {
          if (res.data && res.data.success !== false) {
            resolve(res.data)
            return
          }
          const payloadError = res.data?.message || res.data?.error || '请求失败'
          if (!suppressToast) {
          wx.showToast({ title: payloadError, icon: 'none', duration: 2000 })
          }
          console.error('API 200 payload error:', fullUrl, res.data)
          reject(new Error(payloadError))
          return
        }

        if (res.statusCode === 401) {
          if (needAuth) {
            handle401()
          }
          const errorMsg = '未登录或登录已过期'
          if (!suppressToast) {
          wx.showToast({ title: errorMsg, icon: 'none', duration: 2000 })
          }
          console.error('API 401:', fullUrl, res.data)
          reject(new Error(errorMsg))
          return
        }

        if (res.statusCode === 403) {
          const errorMsg = res.data?.message || res.data?.error || '访问被拒绝'
          if (!suppressToast) {
          wx.showToast({ title: errorMsg, icon: 'none', duration: 2000 })
          }
          console.error('API 403:', fullUrl, res.data)
          reject(new Error(errorMsg))
          return
        }

        if (res.statusCode === 404) {
          const errorMsg = '请求的资源不存在'
          if (!suppressToast) {
          wx.showToast({ title: errorMsg, icon: 'none', duration: 2000 })
          }
          console.error('API 404:', fullUrl, res.data)
          reject(new Error(errorMsg))
          return
        }

        if (res.statusCode === 429) {
          const retryAfter = res.data?.rate_limit?.retry_after
          const errorMsg = res.data?.message || res.data?.error || '请求过于频繁，请稍后重试'
          const fullMsg = retryAfter ? `${errorMsg}（${retryAfter}秒后重试）` : errorMsg
          if (!suppressToast) {
          wx.showToast({ title: fullMsg, icon: 'none', duration: 2000 })
          }
          console.error('API 429:', fullUrl, res.data)
          reject(new Error(fullMsg))
          return
        }

        const errorMsg = res.data?.message || res.data?.error || `请求失败: ${res.statusCode}`
        if (!suppressToast) {
          wx.showToast({ title: errorMsg, icon: 'none', duration: 2000 })
          }
        console.error(`API ${res.statusCode}:`, fullUrl, res.data)
        reject(new Error(errorMsg))
      },
      fail: (err) => {
        if (showLoading) {
          wx.hideLoading()
        }
        logPerformance(method, fullUrl, Date.now() - startTime, {})
        console.error('请求失败:', err)
        const errMsg = err && err.errMsg ? err.errMsg : ''
        const hint = classifyRequestError(errMsg)
        if (hint) {
          console.warn('[API] network hint:', hint.code, hint.hint, 'errMsg:', errMsg, 'url:', fullUrl)
          runNetworkDiagnostics(hint.code)
        }
        
        // 显示错误提示
        if (!suppressToast) {
          wx.showToast({
          title: '网络请求失败',
          icon: 'none',
          duration: 2000
        })
        
        }

        
        reject(err)
      }
    })
  })
}

/**
 * GET请求
 * @param {string} url 请求URL
 * @param {Object} data 请求参数（会转换为 query string）
 * @param {Object} optionsOrHeaders 选项 { headers, needAuth, showLoading } 或 headers 对象（向后兼容）
 */
function get(url, data = {}, optionsOrHeaders = {}) {
  if (Object.keys(data).length > 0) {
    const queryString = Object.keys(data)
      .sort()
      .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(data[key])}`)
      .join('&')
    url = `${url}?${queryString}`
  }

  let options = optionsOrHeaders || {}
  const hasOptionField = (key) => Object.prototype.hasOwnProperty.call(optionsOrHeaders, key)
  if (optionsOrHeaders && !optionsOrHeaders.headers &&
      !hasOptionField('needAuth') && !hasOptionField('showLoading') && !hasOptionField('cache') &&
      !hasOptionField('cacheTime') && !hasOptionField('cachePersist') && !hasOptionField('retry') && !hasOptionField('retryDelay') &&
      !hasOptionField('dedupe') && !hasOptionField('bypassCache') && !hasOptionField('useCacheOnFail') &&
      !hasOptionField('suppressToast')) {
    options = { headers: optionsOrHeaders }
  }

  const needAuth = options.needAuth !== false
  const token = needAuth ? auth.getToken() : ''
  const fullUrl = url.startsWith('http') ? url : config.api.baseUrl + url
  const cacheKey = options.cacheKey || `GET:${fullUrl}:${token || 'public'}`
  const cacheTime = typeof options.cacheTime === 'number' ? options.cacheTime : 0
  const useCache = options.cache === true && cacheTime > 0
  const cachePersist = options.cachePersist === true
  const bypassCache = options.bypassCache === true
  const dedupe = options.dedupe !== false
  const retries = typeof options.retry === 'number' ? options.retry : 0
  const retryDelay = typeof options.retryDelay === 'number' ? options.retryDelay : 500
  const useCacheOnFail = options.useCacheOnFail === true

  if (useCache && !bypassCache) {
    const cached = readCache(cacheKey, cacheTime, cachePersist)
    if (cached !== null && cached !== undefined) {
      return Promise.resolve(cached)
    }
  }

  if (dedupe && pendingRequests.has(cacheKey)) {
    return pendingRequests.get(cacheKey)
  }

  const runRequest = (attempt, delay) => {
    const requestOptions = { ...options }
    if (retries > 0) {
      requestOptions.suppressToast = true
    }
    if (attempt > 0) {
      requestOptions.showLoading = false
      requestOptions.suppressToast = true
    }
    return request(url, 'GET', {}, requestOptions).catch((err) => {
      if (attempt < retries) {
        return new Promise((resolve) => setTimeout(resolve, delay))
          .then(() => runRequest(attempt + 1, delay * 2))
      }
      throw err
    })
  }

  const requestPromise = runRequest(0, retryDelay)
    .then((resData) => {
      if (useCache) {
        writeCache(cacheKey, resData, cachePersist)
      }
      return resData
    })
    .catch((err) => {
      if (useCache && useCacheOnFail) {
        const cached = readCacheFallback(cacheKey, cachePersist)
        if (cached !== null && cached !== undefined) {
          return cached
        }
      }
      if (retries > 0 && !options.suppressToast) {
        wx.showToast({ title: err && err.message ? err.message : 'Request failed', icon: 'none', duration: 2000 })
      }
      throw err
    })

  pendingRequests.set(cacheKey, requestPromise)
  requestPromise.then(() => pendingRequests.delete(cacheKey)).catch(() => pendingRequests.delete(cacheKey))
  return requestPromise
}

/**
 * POST request
 * @param {string} url 请求URL
 * @param {Object} data 请求数据
 * @param {Object} options 选项 { headers, needAuth, showLoading }
 */
function post(url, data = {}, options = {}) {
  return request(url, 'POST', data, options)
}

/**
 * API接口封装
 */
const api = {
  /**
   * 获取今日比赛列表（公共API）
   * @param {String} status - 比赛状态筛选（可选：finished）
   */
  getPublicMatchesToday(status = '', paging = {}, options = {}) {
    const params = status ? { status } : {}
    if (paging.page) {
      params.page = paging.page
    }
    if (paging.pageSize) {
      params.page_size = paging.pageSize
    }
    return get(config.api.endpoints.publicMatchesToday, params, {
      cache: true,
      cacheTime: 15000,
      dedupe: true,
      retry: 0,
      retryDelay: 500,
      useCacheOnFail: true,
      ...options,
      needAuth: false
    })
  },

  /**
   * 获取比赛详情（公共API）
   * @param {Number} matchId - 比赛ID
   */
  getPublicMatchDetail(matchId, options = {}) {
    const url = config.api.endpoints.publicMatchDetail.replace('{id}', matchId)
    return get(url, {}, {
      needAuth: false,
      ...options
    })
  },

  /**
   * 获取今日比赛列表（需要认证 - 暂未启用）
   * @param {String} status - 比赛状态筛选
   */
  getMatchesToday(status = '', paging = {}, options = {}) {
    const params = status ? { status } : {}
    if (paging.page) {
      params.page = paging.page
    }
    if (paging.pageSize) {
      params.page_size = paging.pageSize
    }
    return get(config.api.endpoints.matchesToday, params, {
      cache: true,
      cacheTime: 15000,
      dedupe: true,
      retry: 0,
      retryDelay: 500,
      useCacheOnFail: true,
      ...options
    })
  },

  /**
   * 获取比赛详情（需要认证 - 暂未启用）
   * @param {Number} matchId - 比赛ID
   */
  getMatchDetail(matchId, options = {}) {
    const url = config.api.endpoints.matchDetail.replace('{id}', matchId)
    return get(url, {}, options)
  },

  /**
   * 获取比赛泊松预测（需要认证）
   * @param {Number} matchId - 比赛ID
   */
  getMatchPoissonPrediction(matchId, options = {}) {
    const url = `/api/matches/${matchId}/poisson`
    return get(url, {}, options)
  },

  /**
   * 获取比赛泊松预测（公共接口）
   * @param {Number} matchId - 比赛ID
   */
  getPublicMatchPoissonPrediction(matchId, options = {}) {
    const url = `/api/public/matches/${matchId}/poisson`
    return get(url, {}, {
      needAuth: false,
      ...options
    })
  },

  /**
   * 获取比赛的所有赔率分析（公共API）
   * @param {Number} matchId - 比赛ID
   */
  getPublicMatchAnalyses(matchId, options = {}) {
    // 注意：这个接口实际上需要登录，但我们先尝试调用
    // 如果失败，详情页会优雅降级
    const url = `/api/matches/${matchId}/all_analyses`
    return get(url, {}, options)
  },

  /**
   * 获取比赛的所有分析（需要认证 - 暂未启用）
   * @param {Number} matchId - 比赛ID
   */
  getMatchAnalyses(matchId, options = {}) {
    const url = config.api.endpoints.matchAnalyses.replace('{id}', matchId)
    return get(url, {}, options)
  },

  /**
   * 健康检查
   */
  healthCheck(options = {}) {
    return get(config.api.endpoints.health, {}, options)
  }
}

module.exports = {
  request,
  get,
  post,
  api,
  handle401  // 导出供外部使用
}
