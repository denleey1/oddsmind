const util = require("../../utils/util.js");
const config = require("../../utils/config.js");
const auth = require("../../utils/auth.js");
Page({
  data: {
    version: config.app.version,
    userInfo: {},
    isActivated: false,
    expiresAt: null,
    loading: false,
    expirationReminderEnabled: true,
    collapsedModules: {
      menu: false,
      system: false
    },
    renewCode: '',
    renewLoading: false
  },
  onLoad() {
    console.log("个人中心页加载");
  },
  onShow() {
    console.log("个人中心页显示");
    this.loadUserInfo();
    // 读取续费提醒开关状态
    const disableReminder = wx.getStorageSync('disableExpirationReminder');
    this.setData({
      expirationReminderEnabled: !disableReminder
    });
  },
  /**
   * 加载用户信息
   */
  async loadUserInfo() {
    this.setData({ loading: true });

    try {
      // 先从本地获取
      const localUserInfo = auth.getUserInfoSync();
      if (localUserInfo) {
        this.setData({
          userInfo: localUserInfo,
          isActivated: localUserInfo.is_activated || false,
          expiresAt: localUserInfo.expires_at,
          loading: false
        });
      }

      // 从服务器获取最新信息
      const result = await auth.getUserInfo();
      if (result.success && result.user) {
        this.setData({
          userInfo: result.user,
          isActivated: result.user.is_activated || false,
          expiresAt: result.user.expires_at,
          loading: false
        });
      } else {
        this.setData({ loading: false });
      }
    } catch (error) {
      console.error('加载用户信息失败:', error);
      // 如果获取失败，使用本地数据
      const localUserInfo = auth.getUserInfoSync();
      this.setData({
        userInfo: localUserInfo || {},
        isActivated: localUserInfo?.is_activated || false,
        expiresAt: localUserInfo?.expires_at,
        loading: false
      });
    }
  },
  /**
   * 显示过期时间详情
   */
  showExpiresDetail() {
    if (!this.data.expiresAt) {
      wx.showToast({
        title: '账号永久有效',
        icon: 'none'
      })
      return
    }

    const date = new Date(this.data.expiresAt)
    const now = new Date()
    const diff = date - now

    if (diff < 0) {
      wx.showModal({
        title: '账号已过期',
        content: `过期时间：${date.toLocaleString('zh-CN')}\n\n您的账号已过期，请获取新的激活码续费。`,
        showCancel: false,
        confirmText: '知道了'
      })
      return
    }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

    let detailText = `过期时间：${date.toLocaleString('zh-CN')}\n\n`

    if (days > 0) {
      detailText += `剩余时间：${days}天`
      if (hours > 0) {
        detailText += `${hours}小时`
      }
      if (minutes > 0 && days === 0) {
        detailText += `${minutes}分钟`
      }
    } else if (hours > 0) {
      detailText += `剩余时间：${hours}小时${minutes}分钟`
    } else if (minutes > 0) {
      detailText += `剩余时间：${minutes}分钟`
    } else {
      detailText += `剩余时间：即将过期`
    }

    wx.showModal({
      title: '账号过期时间',
      content: detailText,
      showCancel: false,
      confirmText: '知道了'
    })
  },

  /**
   * 刷新用户信息
   */
  async refreshUserInfo() {
    wx.showLoading({
      title: '刷新中...',
      mask: true
    })

    try {
      await this.loadUserInfo()
      wx.hideLoading()
      wx.showToast({
        title: '刷新成功',
        icon: 'success'
      })
    } catch (error) {
      wx.hideLoading()
      wx.showToast({
        title: '刷新失败',
        icon: 'none'
      })
    }
  },

  /**
   * 格式化过期时间
   * @returns {string} 格式化的过期时间文本
   */
  formatExpiresAt(expiresAt) {
    if (!expiresAt) return '永久有效';

    const date = new Date(expiresAt);
    const now = new Date();
    const diff = date - now;

    if (diff < 0) {
      return '已过期';
    }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    // 如果超过30天，显示具体日期
    if (days > 30) {
      return `${date.toLocaleDateString('zh-CN')} (剩余${days}天)`;
    }
    // 如果超过1天，显示剩余天数
    else if (days > 0) {
      if (days === 1 && hours > 0) {
        return `剩余${days}天${hours}小时`;
      }
      return `剩余${days}天`;
    }
    // 如果不足1天但超过1小时，显示剩余小时
    else if (hours > 0) {
      return `剩余${hours}小时${minutes}分钟`;
    }
    // 如果不足1小时，显示剩余分钟
    else if (minutes > 0) {
      return `剩余${minutes}分钟`;
    }
    // 即将过期
    else {
      return '即将过期';
    }
  },
  /**
   * 续费激活码输入
   */
  onRenewCodeInput(e) {
    this.setData({ renewCode: e.detail.value.trim().toUpperCase() })
  },

  /**
   * 提交续费
   */
  async onSubmitRenew() {
    const code = this.data.renewCode.trim()
    if (!code) {
      wx.showToast({ title: '请输入激活码', icon: 'none' })
      return
    }

    this.setData({ renewLoading: true })

    try {
      const api = require('../../utils/api.js')
      const response = await api.post('/api/miniprogram/renew', { invite_code: code })

      if (response.success && response.data) {
        // 更新本地 token 和用户信息
        const auth = require('../../utils/auth.js')
        const storage = require('../../utils/storage.js')
        if (response.data.token) {
          storage.set('jwt_token', response.data.token)
        }
        if (response.data.user) {
          storage.set('user_info', response.data.user)
          auth.syncAppState(response.data.user)
        }

        wx.showToast({
          title: response.data.message || '续费成功',
          icon: 'success',
          duration: 2000
        })

        this.setData({ renewCode: '', renewLoading: false })

        // 刷新页面数据
        setTimeout(() => { this.loadUserInfo() }, 1000)
      } else {
        wx.showToast({
          title: response.message || response.error || '续费失败',
          icon: 'none',
          duration: 3000
        })
        this.setData({ renewLoading: false })
      }
    } catch (error) {
      console.error('续费失败:', error)
      wx.showToast({
        title: error.message || '续费失败，请稍后重试',
        icon: 'none',
        duration: 3000
      })
      this.setData({ renewLoading: false })
    }
  },

  onPurchaseOrRenew() {
    wx.showToast({ title: '请联系管理员获取激活码', icon: 'none', duration: 2000 })
  },

    /**
   * 导航到比赛列表
   */
  navigateToMatches() {
    wx.navigateTo({
      url: "/pages/matches/matches"
    });
  },
  /**
   * 显示已完成比赛
   */
  showFinishedMatches() {
    wx.navigateTo({
      url: "/pages/matches/matches?status=finished"
    });
  },
  /**
   * 产品说明
   */
  onViewGuide() {},
  onViewUsage() {},

    /**
   * 检查更新
   */
  checkUpdate() {
    const updateManager = wx.getUpdateManager();
    updateManager.onCheckForUpdate((res) => {
      if (res.hasUpdate) {
        util.showToast("\u53D1\u73B0\u65B0\u7248\u672C", "success");
        updateManager.onUpdateReady(() => {
          wx.showModal({
            title: "\u66F4\u65B0\u63D0\u793A",
            content: "\u65B0\u7248\u672C\u5DF2\u7ECF\u51C6\u5907\u597D\uFF0C\u662F\u5426\u91CD\u542F\u5E94\u7528\uFF1F",
            success: (res2) => {
              if (res2.confirm) {
                updateManager.applyUpdate();
              }
            }
          });
        });
        updateManager.onUpdateFailed(() => {
          util.showToast("\u65B0\u7248\u672C\u4E0B\u8F7D\u5931\u8D25", "error");
        });
      } else {
        util.showToast("\u5F53\u524D\u5DF2\u662F\u6700\u65B0\u7248\u672C", "success");
      }
    });
  },
  /**
   * 清除缓存
   */
  clearCache() {
    wx.showModal({
      title: "\u6E05\u9664\u7F13\u5B58",
      content: "\u786E\u5B9A\u8981\u6E05\u9664\u6240\u6709\u7F13\u5B58\u6570\u636E\u5417\uFF1F",
      success: (res) => {
        if (res.confirm) {
          util.cache.clear();
          util.showToast("\u7F13\u5B58\u6E05\u9664\u6210\u529F", "success");
        }
      }
    });
  },
  /**
   * 关于我们
   */
  showAbout() {
    wx.showModal({
      title: "OddsMind",
      content: `\u7248\u672C\uFF1A${this.data.version}

OddsMind\u662F\u4E00\u6B3E\u4E13\u4E1A\u7684\u8DB3\u7403\u8D54\u7387\u5206\u6790\u5DE5\u5177\uFF0C\u4E3A\u60A8\u63D0\u4F9B\u5B9E\u65F6\u6BD4\u8D5B\u6570\u636E\u3001\u4E13\u4E1A\u5206\u6790\u63A8\u8350\u548C\u8D54\u7387\u8D8B\u52BF\u3002

\u6211\u4EEC\u81F4\u529B\u4E8E\u5E2E\u52A9\u8DB3\u7403\u7231\u597D\u8005\u505A\u51FA\u66F4\u660E\u667A\u7684\u51B3\u7B56\u3002`,
      showCancel: false,
      confirmText: "\u77E5\u9053\u4E86"
    });
  },
  /**
   * 联系客服
   */
  contactUs() {
    wx.showModal({
      title: "\u8054\u7CFB\u6211\u4EEC",
      content: "\u5982\u9700\u5E2E\u52A9\u6216\u53CD\u9988\u95EE\u9898\uFF0C\u8BF7\u901A\u8FC7\u4EE5\u4E0B\u65B9\u5F0F\u8054\u7CFB\u6211\u4EEC\uFF1A\n\n\u656C\u8BF7\u671F\u5F85...",
      showCancel: true,
      cancelText: "\u53D6\u6D88",
      confirmText: "\u590D\u5236"
    });
  },
  /**
   * 退出登录
   */
  logout() {
    wx.showModal({
      title: '提示',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          auth.logout();
          util.showToast("已退出登录", "success");
          this.setData({
            userInfo: {},
            isActivated: false,
            expiresAt: null
          });
          // 跳转到登录页
          setTimeout(() => {
            wx.reLaunch({
              url: '/pages/login/login'
            });
          }, 1000);
        }
      }
    });
  },
  toggleModule(e) {
    const module = e.currentTarget.dataset.module;
    const collapsedModules = Object.assign({}, this.data.collapsedModules || {});
    collapsedModules[module] = !collapsedModules[module];
    this.setData({
      collapsedModules
    });
  },

  /**
   * 切换续费提醒开关
   */
  toggleExpirationReminder(e) {
    const enabled = e.detail.value;
    this.setData({ expirationReminderEnabled: enabled });
    
    if (enabled) {
      // 开启提醒：移除禁用标记
      wx.removeStorageSync('disableExpirationReminder');
      wx.showToast({
        title: '已开启提醒',
        icon: 'success',
        duration: 1500
      });
    } else {
      // 关闭提醒：设置禁用标记
      wx.setStorageSync('disableExpirationReminder', true);
      wx.showToast({
        title: '已关闭提醒',
        icon: 'none',
        duration: 1500
      });
    }
  },
  /**
   * 分享配置
   */
  onShareAppMessage() {
    return util.getShareConfig("OddsMind - \u4E13\u4E1A\u8DB3\u7403\u8D54\u7387\u5206\u6790", "/pages/index/index");
  },
  /**
   * 分享到朋友圈
   */
  onShareTimeline() {
    return {
      title: "OddsMind - \u4E13\u4E1A\u8DB3\u7403\u8D54\u7387\u5206\u6790",
      query: "",
      imageUrl: ""
    };
  }
});
