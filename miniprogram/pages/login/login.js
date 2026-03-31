// pages/login/login.js
// 登录页面

const auth = require('../../utils/auth.js')

Page({
  data: {
    needActivate: false,        // 是否需要激活
    isExpired: false,           // 是否过期（过期续费）
    inviteCode: '',             // 邀请码
    loading: false,             // 加载状态
    errorMessage: ''            // 错误信息
  },

  onLoad(options) {
    console.log('登录页 onLoad')
    
    // ⭐ 检查本地登录状态
    const isLoggedIn = auth.isLoggedIn()
    const isActivated = auth.isActivated()
    
    console.log('本地状态 - 已登录:', isLoggedIn, '已激活:', isActivated)
    
    // 如果已经登录且已激活，直接跳转
    if (isLoggedIn && isActivated) {
      console.log('已登录且已激活，直接跳转首页')
      
      wx.showToast({
        title: '欢迎回来',
        icon: 'success',
        duration: 1000
      })
      
      setTimeout(() => {
        this.redirectToHome()
      }, 1000)
      return
    }

    // ⭐ 如果 token 存在但未激活，可能是数据异常，清除后重新登录
    if (isLoggedIn && !isActivated) {
      console.log('Token 存在但未激活，清除数据后重新登录')
      auth.logout()
    }

    // 自动尝试登录
    console.log('开始自动登录')
    this.autoLogin()
  },

  /**
   * 自动登录
   */
  async autoLogin() {
    console.log('===== autoLogin 开始 =====')
    this.setData({ loading: true, errorMessage: '' })

    try {
      console.log('调用 auth.login()')
      const result = await auth.login()
      console.log('auth.login() 返回结果:', result)

      if (result.success) {
        const app = getApp()
        if (app && typeof app.preloadMatches === 'function') {
          app.preloadMatches()
        }

        // 登录成功，跳转到首页
        console.log('✅ 登录成功，准备跳转首页')
        console.log('用户信息:', result.user)
        console.log('Token:', result.token ? '已获取' : '未获取')
        
        wx.showToast({
          title: '登录成功',
          icon: 'success',
          duration: 1500
        })
        setTimeout(() => {
          this.redirectToHome()
        }, 1500)
      } else if (result.needActivate) {
        // 需要激活（或已过期需要续费）
        console.log(result.isExpired ? '⏰ 已过期，需要续费' : '❌ 需要激活')
        this.setData({
          needActivate: true,
          isExpired: result.isExpired || false,
          loading: false
        })
        if (result.isExpired) {
          wx.showToast({
            title: '账号已过期，请续费',
            icon: 'none',
            duration: 3000
          })
        }
      } else {
        // 登录失败
        console.error('❌ 登录失败:', result.error)
        this.setData({
          loading: false,
          errorMessage: result.error || '登录失败，请稍后重试'
        })
        
        wx.showToast({
          title: result.error || '登录失败',
          icon: 'none',
          duration: 3000
        })
      }
    } catch (error) {
      console.error('❌ autoLogin 异常:', error)
      this.setData({
        loading: false,
        errorMessage: error.message || '登录失败，请稍后重试'
      })
      
      wx.showToast({
        title: error.message || '登录失败',
        icon: 'none',
        duration: 3000
      })
    }
    
    console.log('===== autoLogin 结束 =====')
  },

  /**
   * 输入邀请码
   */
  onInviteCodeInput(e) {
    this.setData({
      inviteCode: e.detail.value.trim().toUpperCase()
    })
  },

  /**
   * 提交激活
   */
  async onSubmitActivate() {
    const inviteCode = this.data.inviteCode.trim()

    if (!inviteCode) {
      wx.showToast({
        title: '请输入邀请码',
        icon: 'none',
        duration: 2000
      })
      return
    }

    this.setData({ loading: true, errorMessage: '' })

    try {
      console.log('开始激活，邀请码:', inviteCode)
      const result = await auth.activate(inviteCode)
      console.log('激活结果:', result)

      if (result.success) {
        const app = getApp()
        if (app && typeof app.preloadMatches === 'function') {
          app.preloadMatches()
        }

        // ✅ 验证 token 是否已保存
        const token = auth.getToken()
        const userInfo = auth.getUserInfoSync()

        console.log('激活后验证 - Token:', token ? '已保存' : '未保存')
        console.log('激活后验证 - 用户信息:', userInfo)
        console.log('激活后验证 - 是否激活:', userInfo?.is_activated)

        if (!token || !userInfo) {
          console.error('激活后数据未保存，重新登录')
          // 数据未保存，重新登录
          setTimeout(() => {
            this.autoLogin()
          }, 1000)
          return
        }

        // ✅ 验证用户是否已激活
        if (!userInfo.is_activated) {
          console.error('激活后用户状态未更新，重新登录')
          setTimeout(() => {
            this.autoLogin()
          }, 1000)
          return
        }

        wx.showToast({
          title: '激活成功',
          icon: 'success',
          duration: 1500
        })

        // ✅ 激活成功，直接跳转（不需要重新登录）
        // 原因：激活接口已经返回了token和用户信息，并且已经保存成功
        // 重新登录可能因为code过期导致失败（微信code只能使用一次）
        setTimeout(() => {
          console.log('激活成功，直接跳转首页')
          this.redirectToHome()
        }, 1500)
      } else {
        // ❌ 激活失败 - 显示后端返回的具体错误信息
        const errorMsg = this.getFriendlyErrorMessage(result.error)
        
        // ⭐ 特殊处理：如果账号已激活，自动调用登录接口
        if (result.error && result.error.includes('账号已激活')) {
          wx.showToast({
            title: '账号已激活，正在登录...',
            icon: 'none',
            duration: 2000
          })
          
          setTimeout(() => {
            console.log('账号已激活，转为调用登录接口')
            this.setData({ needActivate: false })
            this.autoLogin()
          }, 1500)
          return
        }
        
        // ⭐ 特殊处理：如果是登录凭证问题，自动重新登录
        if (result.error && result.error.includes('登录凭证已失效')) {
          wx.showToast({
            title: '登录已过期，正在重新登录...',
            icon: 'none',
            duration: 2000
          })
          
          setTimeout(() => {
            this.autoLogin()
          }, 1500)
          return
        }
        
        // 其他错误：显示错误信息
        this.setData({
          loading: false,
          errorMessage: errorMsg
        })
        
        wx.showToast({
          title: errorMsg,
          icon: 'none',
          duration: 3000
        })
      }
    } catch (error) {
      console.error('激活异常:', error)
      const errorMsg = this.getFriendlyErrorMessage(error.message)
      
      // ⭐ 特殊处理：如果账号已激活，自动调用登录接口
      if (error.message && error.message.includes('账号已激活')) {
        wx.showToast({
          title: '账号已激活，正在登录...',
          icon: 'none',
          duration: 2000
        })
        
        setTimeout(() => {
          console.log('账号已激活，转为调用登录接口')
          this.setData({ needActivate: false })
          this.autoLogin()
        }, 1500)
        return
      }
      
      // ⭐ 特殊处理：如果是登录凭证问题，自动重新登录
      if (error.message && error.message.includes('登录凭证已失效')) {
        wx.showToast({
          title: '登录已过期，正在重新登录...',
          icon: 'none',
          duration: 2000
        })
        
        setTimeout(() => {
          this.autoLogin()
        }, 1500)
        return
      }
      
      // 其他错误：显示错误信息
      this.setData({
        loading: false,
        errorMessage: errorMsg
      })
      
      wx.showToast({
        title: errorMsg,
        icon: 'none',
        duration: 3000
      })
    }
  },

  /**
   * 获取友好的错误提示信息
   */
  getFriendlyErrorMessage(backendMessage) {
    if (!backendMessage) {
      return '操作失败，请稍后重试'
    }

    // 错误消息映射 - 让提示更友好
    const errorMap = {
      '激活码无效或已失效': '激活码无效，请检查后重试\n或联系管理员获取新的激活码',
      '账号已激活，请直接登录': '账号已激活，正在为您登录...',
      '账号已激活': '账号已激活，正在为您登录...',
      '登录凭证已失效，请重新登录': '登录已过期，正在重新登录...',
      '登录凭证已失效': '登录已过期，正在重新登录...',
      '微信登录失败': '微信登录失败，请重试',
      '账号已过期，请联系管理员': '您的会员已到期\n请获取新的激活码续费',
      '账号已过期，请使用新的激活码续费': '您的会员已到期\n请获取新的激活码续费',
      '账号已过期': '您的会员已到期\n请获取新的激活码续费',
      '请求过于频繁': '操作过于频繁\n请稍后再试',
      '请求缺少字段': '请求参数错误，请重试',
      '请求缺少有效的 JSON 数据': '请求格式错误，请重试'
    }

    // 精确匹配
    if (errorMap[backendMessage]) {
      return errorMap[backendMessage]
    }

    // 模糊匹配
    for (const [key, value] of Object.entries(errorMap)) {
      if (backendMessage.includes(key)) {
        return value
      }
    }

    // 返回原始消息
    return backendMessage
  },

  /**
   * 查看产品说明和使用方法
   */
  onViewGuide() {},
  onPurchaseCode() {
    wx.showToast({ title: '请联系管理员获取激活码', icon: 'none', duration: 2000 })
  },

    /**
   * 重新登录
   */
  onRetryLogin() {
    this.setData({ needActivate: false })
    this.autoLogin()
  },

  /**
   * 跳转到首页
   */
  redirectToHome() {
    console.log('准备跳转到首页...')
    // 使用 reLaunch 跳转，清除所有页面栈，确保从首页开始
    wx.reLaunch({
      url: '/pages/index/index',
      success: () => {
        console.log('跳转首页成功')
      },
      fail: (err) => {
        console.error('跳转首页失败:', err)
        // 如果 reLaunch 失败，尝试使用 redirectTo
        wx.redirectTo({
          url: '/pages/index/index',
          success: () => {
            console.log('使用 redirectTo 跳转成功')
          },
          fail: (err2) => {
            console.error('redirectTo 也失败:', err2)
            wx.showToast({
              title: '跳转失败，请手动返回',
              icon: 'none'
            })
          }
        })
      }
    })
  }
})

