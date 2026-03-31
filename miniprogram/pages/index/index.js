const { fetchMatches } = require("../../utils/match-service.js");
const util = require("../../utils/util.js");
const auth = require("../../utils/auth.js");
Page({
  data: {
    loading: false,
    upcomingMatches: [],
    liveMatches: [],
    todayMatchCount: 0,
    liveMatchCount: 0,
    finishedMatchCount: 0,
    collapsedModules: {
      upcoming: false,
      live: false
    }
  },
  onLoad() {
    console.log("首页加载，检查登录状态...");

    // ✅ 检查登录状态
    const token = auth.getToken();
    const userInfo = auth.getUserInfoSync();

    console.log("首页 - Token:", token ? "存在" : "不存在");
    console.log("首页 - 用户信息:", userInfo);
    console.log("首页 - 是否激活:", userInfo?.is_activated);

    if (!token) {
      console.log("未找到Token，跳转到登录页");
      wx.redirectTo({
        url: "/pages/login/login"
      });
      return;
    }

    if (!userInfo) {
      console.log("未找到用户信息，跳转到登录页");
      wx.redirectTo({
        url: "/pages/login/login"
      });
      return;
    }

    if (!userInfo.is_activated) {
      console.log("用户未激活，跳转到登录页");
      wx.redirectTo({
        url: "/pages/login/login"
      });
      return;
    }

    console.log("登录状态验证通过，加载数据");
    // 已登录，加载数据
    this.loadData();
  },
  onShow() {
    console.log("\u9996\u9875\u663E\u793A");
  },
  onPullDownRefresh() {
    console.log("\u4E0B\u62C9\u5237\u65B0");
    this.loadData({ usePreload: false, forceRefresh: true }).then(() => {
      wx.stopPullDownRefresh();
      util.showToast("\u5237\u65B0\u6210\u529F", "success");
    }).catch(() => {
      wx.stopPullDownRefresh();
    });
  },
  /**
   * 加载数据
   */
  async loadData(options = {}) {
    const { usePreload = true, forceRefresh = false } = options;
    let usedPreload = false;
    try {
      const app = getApp();
      const preloaded = usePreload && app && app.globalData ? app.globalData.preloadedMatches : null;
      const preloadedTotal = usePreload && app && app.globalData ? app.globalData.preloadedTotal : 0;
      const preloadTime = usePreload && app && app.globalData ? app.globalData.preloadTime : 0;
      const preloadFresh = preloadTime && (Date.now() - preloadTime < 30 * 1000);
      if (preloaded && preloaded.length) {
        usedPreload = true;
        this.processMatches(preloaded, preloadedTotal);
      }
      if (usedPreload && preloadFresh && !forceRefresh) {
        this.setData({ loading: false });
        return;
      }
      if (!usedPreload) {
        this.setData({ loading: true });
      }
      const response = await fetchMatches("", {}, { showLoading: !usedPreload, bypassCache: forceRefresh });
      if (response && response.success && response.data) {
        const matches = response.data;
        this.processMatches(matches, response.total);
      } else {
        throw new Error((response == null ? void 0 : response.error) || "\u6570\u636E\u52A0\u8F7D\u5931\u8D25");
      }
    } catch (error) {
      console.error("\u52A0\u8F7D\u6570\u636E\u5931\u8D25:", error);
      util.showToast("\u6570\u636E\u52A0\u8F7D\u5931\u8D25", "none");
    } finally {
      this.setData({ loading: false });
    }
  },
  /**
   * 处理比赛数据
   */
  processMatches(matches, totalCount = 0) {
    let liveCount = 0;
    let finishedCount = 0;
    const upcoming = [];
    const live = [];
    
    // 调试：打印所有比赛状态
    const statusValues = [...new Set(matches.map(m => m.matchStatus))];
    console.log('[DEBUG] 所有比赛状态值:', statusValues);
    
    matches.forEach((match) => {
      const status = match.matchStatus;
      // 兼容更多状态值格式（忽略大小写）
      const statusLower = (status || '').toString().toLowerCase();
      if (status === "\u8FDB\u884C\u4E2D" || statusLower === "live" || statusLower === "playing" || statusLower === "in_progress") {
        liveCount++;
        live.push(match);
      } else if (status === "\u5DF2\u7ED3\u675F" || statusLower === "finished" || statusLower === "ended" || statusLower === "completed") {
        finishedCount++;
      }
      if (status === "\u672A\u5F00\u59CB" || status === "scheduled") {
        const matchTime = new Date(match.matchTime);
        const now = /* @__PURE__ */ new Date();
        const diffHours = (matchTime - now) / (1e3 * 60 * 60);
        if (diffHours > 0 && diffHours <= 2) {
          upcoming.push(match);
        }
      }
    });
    upcoming.sort((a, b) => new Date(a.matchTime) - new Date(b.matchTime));
    const upcomingMatches = upcoming.slice(0, 3);
    const total = typeof totalCount === "number" && totalCount > 0 ? totalCount : matches.length;
    this.setData({
      upcomingMatches,
      liveMatches: live,
      todayMatchCount: total,
      liveMatchCount: liveCount,
      finishedMatchCount: finishedCount
    });
  },
  /**
   * 刷新数据
   */
  onRefresh() {
    this.loadData({ usePreload: false, forceRefresh: true }).then(() => {
      util.showToast("\u5237\u65B0\u6210\u529F", "success");
    });
  },
  /**
   * 比赛卡片点击
   */
  onMatchTap(e) {
    const match = e && e.detail ? e.detail.match : null;
    if (!match || !match.matchId) {
      return;
    }
    wx.navigateTo({
      url: `/pages/match-detail/match-detail?matchId=${match.matchId}`
    });
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
  toggleModule(e) {
    const module = e && e.currentTarget && e.currentTarget.dataset ? e.currentTarget.dataset.module : "";
    if (!module) return;
    const collapsedModules = Object.assign({}, this.data.collapsedModules || {});
    collapsedModules[module] = !collapsedModules[module];
    this.setData({ collapsedModules });
  },
  /**
   * 导航到个人中心
   */
  navigateToProfile() {
    wx.navigateTo({
      url: "/pages/profile/profile"
    });
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
