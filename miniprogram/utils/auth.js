// utils/auth.js
// 认证工具类
// 负责微信登录、Token管理、用户状态管理

// 延迟加载 api.js 避免循环依赖
// const api = require('./api.js')  // ❌ 移除顶部导入
const storage = require('./storage.js')

// 存储键名
const TOKEN_KEY = 'jwt_token'
const USER_INFO_KEY = 'user_info'

class Auth {
  constructor() {
    this._loginPromise = null
  }

  /**
   * 获取 api 实例（延迟加载，避免循环依赖）
   * @returns {Object} api 实例，包含 post, get, request 等方法
   */
  _getApi() {
    // 延迟加载，避免循环依赖
    // api.js 导出的是 { request, get, post, api, handle401 }
    return require('./api.js')
  }

  async login() {
    if (this._loginPromise) {
      return this._loginPromise
    }

    this._loginPromise = this._loginInternal()
    try {
      return await this._loginPromise
    } finally {
      this._loginPromise = null
    }
  }

  /**
   * 微信登录
   * @returns {Promise<Object>} 登录结果
   */
  async _loginInternal() {
    try {
      console.log('===== auth.login() 开始 =====')
      
      // 1. 调用 wx.login() 获取 code
      console.log('1. 调用 wx.login() 获取 code')
      const loginRes = await this.wxLogin()
      const code = loginRes.code
      console.log('获取到 code:', code ? '成功' : '失败')

      // 2. 调用后端登录接口（延迟加载 api）
      console.log('2. 调用后端登录接口')
      const api = this._getApi()
      const response = await api.post('/api/miniprogram/login', { code }, { needAuth: false })
      console.log('后端响应:', response)

      if (!response.success) {
        console.error('❌ 登录接口返回失败:', response)
        throw new Error(response.message || response.error || '登录失败')
      }

      const data = response.data
      console.log('登录数据:', data)
      console.log('data.is_activated:', data.is_activated)
      console.log('data.user:', data.user)
      console.log('data.user.is_activated:', data.user?.is_activated)

      // 3. 如果未激活，返回需要激活的状态
      // ⭐ 修复：is_activated 在 user 对象里，不在 data 根层级
      const isActivated = data.user?.is_activated || data.is_activated
      console.log('最终判断 isActivated:', isActivated)
      
      if (!isActivated) {
        // 区分"未激活"和"已过期"
        const isExpired = data.status === 'EXPIRED'
        console.log(isExpired ? '⏰ 账号已过期，需要续费' : '❌ 账号未激活，需要激活')
        // 清除旧的本地缓存（过期的 token 和用户信息）
        storage.remove(TOKEN_KEY)
        storage.remove(USER_INFO_KEY)
        return {
          success: false,
          needActivate: true,
          isExpired: isExpired,
          openid: data.user?.openid || data.openid,
          message: data.message || (isExpired ? '账号已过期，请使用新的激活码续费' : '需要激活账号')
        }
      }

      // 4. 已激活，保存 Token 和用户信息
      console.log('✅ 账号已激活，保存 Token 和用户信息')
      if (data.token) {
        storage.set(TOKEN_KEY, data.token)
        console.log('Token 已保存，长度:', data.token.length)
      } else {
        console.error('⚠️ 警告：后端未返回 token')
      }
      
      if (data.user) {
        storage.set(USER_INFO_KEY, data.user)
        console.log('用户信息已保存:', data.user)
      } else {
        console.error('⚠️ 警告：后端未返回用户信息')
      }

      // 同步到全局状态
      this.syncAppState(data.user)
      console.log('已同步到全局状态')

      const result = {
        success: true,
        user: data.user,
        token: data.token
      }
      console.log('✅ 登录成功，返回结果:', result)
      console.log('===== auth.login() 结束 =====')
      
      return result
    } catch (error) {
      console.error('❌ 登录异常:', error)
      console.error('错误详情:', error.message)
      console.log('===== auth.login() 异常结束 =====')
      
      return {
        success: false,
        error: error.message || '登录失败，请稍后重试'
      }
    }
  }

  /**
   * 激活账号（验证邀请码）
   * @param {string} inviteCode 邀请码
   * @returns {Promise<Object>} 激活结果
   */
  async activate(inviteCode) {
    try {
      console.log('开始激活，邀请码:', inviteCode)

      // 1. 获取 code
      const loginRes = await this.wxLogin()
      const code = loginRes.code
      console.log('获取到微信code:', code ? '成功' : '失败')

      // 2. 调用激活接口（延迟加载 api）
      console.log('调用激活接口...')
      const api = this._getApi()
      const response = await api.post('/api/miniprogram/activate', {
        code,
        invite_code: inviteCode
      }, { needAuth: false })

      console.log('激活接口响应:', response)
      console.log('响应success:', response.success)
      console.log('响应data:', response.data)

      if (!response.success) {
        console.error('激活失败:', response.error)
        throw new Error(response.error || '激活失败')
      }

      const data = response.data
      console.log('激活接口数据:', data)
      console.log('Token存在:', !!data.token)
      console.log('用户信息存在:', !!data.user)

      // 3. 保存 Token 和用户信息
      if (data.token) {
        storage.set(TOKEN_KEY, data.token)
        console.log('Token已保存，长度:', data.token.length)
      } else {
        console.error('激活接口未返回token!')
        throw new Error('激活失败：未返回token')
      }

      if (data.user) {
        storage.set(USER_INFO_KEY, data.user)
        console.log('用户信息已保存:', data.user)
      } else {
        console.error('激活接口未返回用户信息!')
        throw new Error('激活失败：未返回用户信息')
      }

      // 4. 验证保存是否成功
      const savedToken = storage.get(TOKEN_KEY)
      const savedUser = storage.get(USER_INFO_KEY)
      console.log('验证保存结果 - Token:', savedToken ? '已保存' : '未保存')
      console.log('验证保存结果 - 用户信息:', savedUser ? '已保存' : '未保存')

      // 同步到全局状态
      this.syncAppState(data.user)

      return {
        success: true,
        user: data.user,
        token: data.token
      }
    } catch (error) {
      console.error('激活失败:', error)
      return {
        success: false,
        error: error.message || '激活失败，请检查邀请码是否正确'
      }
    }
  }

  /**
   * 获取当前用户信息
   * @returns {Promise<Object>} 用户信息
   */
  async getUserInfo() {
    try {
      // 延迟加载 api，避免循环依赖
      const api = this._getApi()
      const response = await api.get('/api/miniprogram/user', {}, {
        cache: true,
        cacheTime: 60000,
        useCacheOnFail: true,
        suppressToast: true
      })
      
      if (!response.success) {
        throw new Error(response.error || '获取用户信息失败')
      }

      // 更新本地存储的用户信息
      if (response.data) {
        storage.set(USER_INFO_KEY, response.data)
        this.syncAppState(response.data)
      }

      return {
        success: true,
        user: response.data
      }
    } catch (error) {
      console.error('获取用户信息失败:', error)
      return {
        success: false,
        error: error.message
      }
    }
  }

  /**
   * 检查登录状态
   * @returns {boolean} 是否已登录
   */
  isLoggedIn() {
    const token = storage.get(TOKEN_KEY)
    return !!token
  }

  /**
   * 检查是否已激活
   * @returns {boolean} 是否已激活
   */
  isActivated() {
    const userInfo = storage.get(USER_INFO_KEY)
    return userInfo && userInfo.is_activated === true
  }

  /**
   * 获取 Token
   * @returns {string|null} Token
   */
  getToken() {
    return storage.get(TOKEN_KEY)
  }

  /**
   * 获取用户信息（同步）
   * @returns {Object|null} 用户信息
   */
  getUserInfoSync() {
    return storage.get(USER_INFO_KEY)
  }

  /**
   * 登出
   */
  logout() {
    storage.remove(TOKEN_KEY)
    storage.remove(USER_INFO_KEY)
    this.syncAppState({})
  }

  /**
   * 微信登录（封装 wx.login）
   * @returns {Promise<Object>} 登录结果
   */
  wxLogin() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: resolve,
        fail: reject
      })
    })
  }

  /**
   * 检查账号是否过期
   * @returns {boolean} 是否过期
   */
  isExpired() {
    const userInfo = this.getUserInfoSync()
    if (!userInfo || !userInfo.expires_at) {
      return false
    }

    const expiresAt = new Date(userInfo.expires_at)
    return expiresAt < new Date()
  }

  /**
   * 同步到全局状态（兼容旧代码）
   * @param {Object} user 用户信息
   */
  syncAppState(user = {}) {
    const app = getApp()
    if (app) {
      app.globalData.userInfo = user || {}
    }
  }

  /**
   * 初始化会话（兼容旧代码）
   * @returns {Promise<Object>} 用户信息
   */
  initializeSession() {
    const user = this.getUserInfoSync()
    this.syncAppState(user)
    return Promise.resolve(user)
  }

  /**
   * 读取用户（兼容旧代码）
   * @returns {Object} 用户信息
   */
  readUser() {
    return this.getUserInfoSync() || {}
  }

  /**
   * 持久化用户（兼容旧代码）
   * @param {Object} user 用户信息
   */
  persistUser(user = {}) {
    storage.set(USER_INFO_KEY, user)
    this.syncAppState(user)
  }

  /**
   * 清除用户（兼容旧代码）
   */
  clearUser() {
    this.logout()
  }

  /**
   * 调试：检查登录状态
   * @returns {Object} 登录状态信息
   */
  debugLoginStatus() {
    const token = this.getToken()
    const userInfo = this.getUserInfoSync()

    console.log('=== 登录状态调试 ===')
    console.log('Token:', token ? `存在 (${token.length}字符)` : '不存在')
    console.log('用户信息:', userInfo)
    console.log('是否登录:', this.isLoggedIn())
    console.log('是否激活:', this.isActivated())
    console.log('是否过期:', this.isExpired())
    console.log('==================')

    return {
      hasToken: !!token,
      hasUserInfo: !!userInfo,
      isLoggedIn: this.isLoggedIn(),
      isActivated: this.isActivated(),
      isExpired: this.isExpired(),
      token: token,
      userInfo: userInfo
    }
  }
}

// 导出单例
module.exports = new Auth()
