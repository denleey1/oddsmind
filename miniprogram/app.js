// app.js
const auth = require('./utils/auth.js')
const { api } = require('./utils/api.js')

App({
  globalData: {
    userInfo: null,
    isVip: false,
    vipExpireDate: null,
    version: '1.0.0',
    preloadedMatches: null,
    preloadedTotal: 0,
    preloadTime: 0
  },

  onLaunch() {
    console.log('OddsMind小程序启动', this.globalData.version)
    
    // 检查小程序更新
    this.checkForUpdate()
    
    // 检查网络状态
    this.checkNetworkStatus()
    
    // 获取系统信息
    this.getSystemInfo()
    
    // 初始化应用
    this.initApp()

    // 恢复用户状态
    auth.initializeSession()
      .then((user) => {
        this.setUserInfo(user)
        console.log('用户状态恢复', user)
        // 检查临期提醒
        this.checkExpirationReminder(user)
      })
      .catch((err) => {
        console.warn('初始化用户信息失败', err)
      })

    // 检查登录状态
    this.checkLoginStatus()
      .then((canPreload) => {
        if (canPreload) {
          this.preloadMatches()
        }
      })
      .catch((err) => {
        console.warn('Login status check failed', err)
      })
  },

  onShow() {
    console.log('OddsMind小程序显示')
  },

  onHide() {
    console.log('OddsMind小程序隐藏')
  },

  /**
   * 检查网络状态
   */
  checkNetworkStatus() {
    wx.getNetworkType({
      success: (res) => {
        const networkType = res.networkType
        console.log('网络类型:', networkType)
        
        if (networkType === 'none') {
          wx.showToast({
            title: '网络未连接',
            icon: 'none',
            duration: 2000
          })
        }
      }
    })
  },

  /**
   * 获取系统信息
   */
  getSystemInfo() {
    wx.getSystemInfo({
      success: (res) => {
        this.globalData.systemInfo = res
        console.log('系统信息:', res)
      }
    })
  },

  /**
   * 初始化应用
   */
  initApp() {
    // 后续可以在这里添加初始化逻辑
  },

  /**
   * 检查小程序更新（强制更新）
   */
  checkForUpdate() {
    if (!wx.canIUse('getUpdateManager')) {
      console.log('当前微信版本不支持 getUpdateManager')
      return
    }

    const updateManager = wx.getUpdateManager()

    // 检查是否有新版本
    updateManager.onCheckForUpdate((res) => {
      console.log('检查更新结果:', res.hasUpdate ? '有新版本' : '已是最新版本')
    })

    // 新版本下载完成
    updateManager.onUpdateReady(() => {
      console.log('新版本已下载完成')
      wx.showModal({
        title: '更新提示',
        content: '新版本已准备好，是否立即重启应用？',
        confirmText: '立即更新',
        cancelText: '稍后更新',
        success: (res) => {
          if (res.confirm) {
            // 强制重启应用并应用新版本
            updateManager.applyUpdate()
          }
        }
      })
    })

    // 新版本下载失败
    updateManager.onUpdateFailed(() => {
      console.error('新版本下载失败')
      wx.showModal({
        title: '更新提示',
        content: '新版本下载失败，请检查网络后重试，或删除小程序重新搜索打开',
        showCancel: false
      })
    })
  },

  /**
   * 设置用户信息
   */
  setUserInfo(userInfo) {
    this.globalData.userInfo = userInfo
  },

  /**
   * 检查临期提醒（还有N天过期时提醒用户）
   * @param {Object} user 用户信息
   */
  checkExpirationReminder(user) {
    if (!user || !user.expires_at) {
      return // 没有过期时间，不提醒（可能是永久账号）
    }

    // 检查用户是否选择了"不再提醒"
    const disableReminder = wx.getStorageSync('disableExpirationReminder')
    if (disableReminder) {
      console.log('用户已关闭续费提醒')
      return
    }

    const expiresAt = new Date(user.expires_at)
    const now = new Date()
    const diffMs = expiresAt - now
    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

    // 已经过期的不在这里处理（checkLoginStatus 会处理）
    if (diffDays <= 0) {
      return
    }

    // 设置提醒阈值：还有几天时开始提醒
    const reminderThreshold = 3

    if (diffDays <= reminderThreshold) {
      // 检查今天是否已经提醒过，避免频繁打扰
      const today = new Date().toDateString()
      const lastReminderDate = wx.getStorageSync('lastExpirationReminderDate')
      
      if (lastReminderDate === today) {
        console.log('今日已提醒过，不再重复提醒')
        return
      }

      // 记录提醒日期
      wx.setStorageSync('lastExpirationReminderDate', today)

      // 构造提醒内容
      let content = ''
      if (diffDays === 1) {
        content = '您的账号将于明天到期，请及时联系管理员续费，以免影响使用。'
      } else if (diffDays === 0) {
        content = '您的账号今天到期，请尽快联系管理员续费！'
      } else {
        content = `您的账号还有 ${diffDays} 天到期，请提前联系管理员续费。`
      }

      // 弹窗提醒（带"不再提醒"选项）
      wx.showModal({
        title: '⏰ 续费提醒',
        content: content,
        confirmText: '知道了',
        cancelText: '不再提醒',
        showCancel: true,
        success: (res) => {
          if (res.cancel) {
            // 用户点击"不再提醒"，记录到本地存储
            wx.setStorageSync('disableExpirationReminder', true)
            wx.showToast({
              title: '已关闭提醒',
              icon: 'none',
              duration: 1500
            })
          }
        }
      })

      console.log(`临期提醒：还有 ${diffDays} 天到期`)
    }
  },

  /**
   * 设置VIP状态
   */
  setVipStatus(isVip, expireDate) {
    this.globalData.isVip = isVip
    this.globalData.vipExpireDate = expireDate
  },

  /**
   * 检查登录状态
   */
  async checkLoginStatus() {
    // 如果未登录，跳转到登录页
    if (!auth.isLoggedIn()) {
      console.log('未登录，跳转到登录页')
      wx.reLaunch({
        url: '/pages/login/login'
      })
      return false
    }

    // 如果已登录但未激活，跳转到登录页（激活）
    if (!auth.isActivated()) {
      console.log('未激活，跳转到登录页')
      wx.reLaunch({
        url: '/pages/login/login'
      })
      return false
    }

    // 检查账号是否过期
    if (auth.isExpired()) {
      console.log('账号已过期')
      wx.showModal({
        title: '提示',
        content: '您的账号已过期，请联系管理员',
        showCancel: false,
        success: () => {
          auth.logout()
          wx.reLaunch({
            url: '/pages/login/login'
          })
        }
      })
      return false
    }

    // 尝试刷新用户信息
    try {
      await auth.getUserInfo()
    } catch (error) {
      console.error('获取用户信息失败:', error)
    }

    console.log('登录状态正常')
    return true
  },

  /**
   * Preload matches list
   */
  preloadMatches() {
    api.getPublicMatchesToday('', { page: 1, pageSize: 20 }, { showLoading: false, suppressToast: true })
      .then((res) => {
        if (res && res.success && res.data) {
          this.globalData.preloadedMatches = res.data
          this.globalData.preloadedTotal = typeof res.total === 'number' ? res.total : res.data.length
          this.globalData.preloadTime = Date.now()
        }
      })
      .catch((err) => {
        console.warn('Preload matches failed', err)
      })
  },

})

