const { fetchMatches } = require("../../utils/match-service.js");
const { fetchAlerts } = require("../../utils/alert-service.js");
const util = require("../../utils/util.js");
const DATE_FILTERS = [
  { label: "\u5168\u90E8", value: "" },
  { label: "\u4ECA\u5929", value: "today" },
  { label: "\u660E\u5929", value: "tomorrow" },
  { label: "\u672C\u5468", value: "week" }
];
const STATUS_TABS = [
  { label: "\u5168\u90E8", value: "" },
  { label: "\u8FDB\u884C\u4E2D", value: "live" },
  { label: "\u672A\u5F00\u59CB", value: "scheduled" },
  { label: "\u5DF2\u5B8C\u6210", value: "finished" }
];
const SIGNAL_ORDER = {
  "\u91CD\u4ED3": 0,
  "\u5F3A\u70C8": 1,
  "\u53C2\u8003": 2
};
const SIGNAL_LEVEL_ALIASES = {
  heavy: "\u91CD\u4ED3",
  heavy_bet: "\u91CD\u4ED3",
  heavybet: "\u91CD\u4ED3",
  strong: "\u5F3A\u70C8",
  strongly: "\u5F3A\u70C8",
  reference: "\u53C2\u8003",
  ref: "\u53C2\u8003"
};

// 联赛优先级配置：五大联赛 > 欧战 > 重要联赛 > 其他
const LEAGUE_PRIORITY = {
  // 五大联赛（最高优先级）
  '英超': 1, '西甲': 1, '德甲': 1, '意甲': 1, '法甲': 1,
  // 欧战
  '欧冠': 2, '欧冠杯': 2, '欧联杯': 2, '欧协联': 2,
  // 重要联赛
  '荷甲': 3, '葡超': 3, '苏超': 3, '土超': 3, '俄超': 3,
  '巴甲': 3, '阿甲': 3, '美职': 3, '日职': 3, '韩K': 3,
  '中超': 3, '澳超': 3, '墨超': 3, '瑞典超': 3, '挪超': 3,
  // 次级联赛
  '英冠': 4, '英甲': 4, '英乙': 4, '西乙': 4, '德乙': 4,
  '意乙': 4, '法乙': 4, '荷乙': 4, '巴西甲': 4, '巴西乙': 4,
  '墨西哥甲春': 4, '墨西哥甲秋': 4, '日乙': 4, '韩K2': 4,
};

function getLeaguePriority(name) {
  // 精确匹配
  if (LEAGUE_PRIORITY[name] !== undefined) return LEAGUE_PRIORITY[name];
  // 模糊匹配（联赛名包含关键词）
  for (const [key, val] of Object.entries(LEAGUE_PRIORITY)) {
    if (name.includes(key) || key.includes(name)) return val;
  }
  return 99;
}

Page({
  data: {
    loading: false,
    loadingMore: false,
    allMatches: [],
    filteredMatches: [],
    groupedMatches: [],
    page: 1,
    pageSize: 20,
    totalMatches: 0,
    hasMore: true,
    skeletonItems: [1, 2, 3, 4, 5],
    searchKeyword: "",
    selectedLeague: "",
    selectedDate: "",
    customDate: "",
    statusFilter: "",
    leagueOptions: [],
    quickLeagues: [],
    dateFilters: DATE_FILTERS,
    statusTabs: STATUS_TABS,
    activeStatusTab: "",
    preloadedUsed: false,
    alertMap: {},
    signalSummary: {
      heavy: 0,
      strong: 0,
      reference: 0
    },
    visibleSignalSummary: {
      heavy: 0,
      strong: 0,
      reference: 0
    },
    hasSignalSummary: false,
    selectedSignalLevel: "",
    alertHours: 168,
    collapsedModules: {
      filter: false
    }
  },
  onLoad(options) {
    console.log("\u6BD4\u8D5B\u5217\u8868\u9875\u52A0\u8F7D", options);
    if (options.status) {
      this.setData({ statusFilter: options.status, activeStatusTab: options.status });
    }
    const app = getApp();
    const preloaded = app && app.globalData ? app.globalData.preloadedMatches : null;
    const preloadedTotal = app && app.globalData ? app.globalData.preloadedTotal : 0;
    const preloadTime = app && app.globalData ? app.globalData.preloadTime : 0;
    const preloadFresh = preloadTime && (Date.now() - preloadTime < 30 * 1000);
    if (!options.status && preloaded && preloaded.length) {
      const total = preloadedTotal || preloaded.length;
      this.setData({
        allMatches: preloaded,
        page: 1,
        totalMatches: total,
        hasMore: preloaded.length < total,
        preloadedUsed: true
      });
      this.updateLeagueOptions(preloaded);
      this.filterAndGroupMatches();
      this.loadAlerts();
      if (!preloadFresh) {
        this.loadData({ silent: true, reset: false });
      }
      return;
    }
    this.loadData({ reset: true });
  },
  onPullDownRefresh() {
    console.log("\u4E0B\u62C9\u5237\u65B0");
    this.loadData({ forceRefresh: true, reset: true }).finally(() => {
      wx.stopPullDownRefresh();
    });
  },
  async loadData(options = {}) {
    const { forceRefresh = false, silent = false, reset = true } = options;
    try {
      if (!silent) {
        this.setData({ loading: true });
      }
      if (reset) {
        this.setData({
          allMatches: [],
          filteredMatches: [],
          groupedMatches: [],
          page: 1,
          totalMatches: 0,
          hasMore: true,
          loadingMore: false,
          alertMap: {},
          signalSummary: {
            heavy: 0,
            strong: 0,
            reference: 0
          },
          hasSignalSummary: false
        });
      }
      const paging = { page: 1, pageSize: this.data.pageSize };
      const response = await fetchMatches(
        this.data.statusFilter,
        paging,
        { bypassCache: forceRefresh, showLoading: !silent }
      );
      if (response && response.success && response.data) {
        const matches = response.data;
        const total = typeof response.total === "number" ? response.total : matches.length;
        this.setData({
          allMatches: matches,
          page: 1,
          totalMatches: total,
          hasMore: matches.length < total
        });
        this.updateLeagueOptions(matches);
        this.filterAndGroupMatches();
        this.loadAlerts();
      } else {
        throw new Error((response == null ? void 0 : response.error) || "\u6570\u636E\u52A0\u8F7D\u5931\u8D25");
      }
    } catch (error) {
      console.error("\u52A0\u8F7D\u6570\u636E\u5931\u8D25:", error);
      util.showToast("\u6BD4\u8D5B\u6570\u636E\u52A0\u8F7D\u5931\u8D25", "none");
    } finally {
      if (!silent) {
        this.setData({ loading: false });
      }
    }
  },
  async loadAlerts() {
    const hours = this.data.alertHours || 168;
    try {
      const res = await fetchAlerts(hours, { showLoading: false, suppressToast: true });
      const payload = res && res.success && res.data ? res.data : {};
      const matches = this.extractAlertMatches(payload);
      const summary = this.extractSignalSummary(payload, matches);
      if (!matches.length) {
        this.setData({
          alertMap: {},
          signalSummary: {
            heavy: summary.heavy,
            strong: summary.strong,
            reference: summary.reference
          },
          hasSignalSummary: summary.hasData
        });
        this.filterAndGroupMatches();
        return;
      }
      const alertMap = this.buildAlertMap(matches);
      this.setData({
        alertMap,
        signalSummary: {
          heavy: summary.heavy,
          strong: summary.strong,
          reference: summary.reference
        },
        hasSignalSummary: summary.hasData
      });
      this.filterAndGroupMatches();
    } catch (err) {
      console.warn("loadAlerts failed:", err);
    }
  },
  onSignalFilterTap(e) {
    const rawLevel = e && e.currentTarget && e.currentTarget.dataset ? e.currentTarget.dataset.level : "";
    const level = rawLevel === "" ? "" : this.normalizeSignalLevel(rawLevel);
    const nextLevel = this.data.selectedSignalLevel === level ? "" : level;
    this.setData({ selectedSignalLevel: nextLevel });
    this.filterAndGroupMatches();
  },
  getCategoryTarget(category) {
    if (category === "handicap_win") return "\u8BA9\u65B9\u5FC5\u80DC";
    if (category === "handicap_not_lose") return "\u8BA9\u65B9\u4E0D\u8F93";
    if (category === "receiver_not_lose") return "\u53D7\u8BA9\u65B9\u4E0D\u8F93";
    return "";
  },
  toAccuracyNumber(rule = {}) {
    if (typeof rule.accuracy === "number" && !Number.isNaN(rule.accuracy)) {
      return rule.accuracy <= 1 ? rule.accuracy : rule.accuracy / 100;
    }
    const pct = rule.accuracy_pct || rule.accuracyPct;
    if (pct) {
      const num = parseFloat(String(pct).replace("%", ""));
      if (!Number.isNaN(num)) {
        return num > 1 ? num / 100 : num;
      }
    }
    return 0;
  },
  toAccuracyPctText(rule = {}, fallbackNum = 0) {
    if (rule.accuracy_pct || rule.accuracyPct) {
      return rule.accuracy_pct || rule.accuracyPct;
    }
    const num = typeof rule.accuracy === "number" ? rule.accuracy : fallbackNum;
    if (!num) return "--";
    const pct = num <= 1 ? num * 100 : num;
    return pct.toFixed(1) + "%";
  },
  formatOddsText(value) {
    if (value === null || value === undefined || value === "") return "--";
    const num = Number(value);
    if (Number.isNaN(num)) return String(value);
    return num.toFixed(2);
  },
  toSafeCount(value) {
    const num = Number(value);
    if (!Number.isFinite(num) || num < 0) {
      return 0;
    }
    return Math.floor(num);
  },
  toBoolean(value) {
    if (typeof value === "boolean") return value;
    if (typeof value === "number") return value === 1;
    if (typeof value === "string") {
      const normalized = value.trim().toLowerCase();
      return normalized === "1" || normalized === "true" || normalized === "yes";
    }
    return false;
  },
  normalizeSignalLevel(level) {
    const raw = String(level || "").trim();
    if (!raw) return "";
    if (Object.prototype.hasOwnProperty.call(SIGNAL_ORDER, raw)) {
      return raw;
    }
    const mapped = SIGNAL_LEVEL_ALIASES[raw.toLowerCase()];
    return mapped || raw;
  },
  getSignalIconByLevel(level) {
    const normalized = this.normalizeSignalLevel(level);
    if (normalized === "\u91CD\u4ED3") return "\ud83d\udd34";
    if (normalized === "\u5F3A\u70C8") return "\ud83d\udfe0";
    if (normalized === "\u53C2\u8003") return "\ud83d\udfe1";
    return "";
  },
  getSignalOrder(level) {
    const normalized = this.normalizeSignalLevel(level);
    if (Object.prototype.hasOwnProperty.call(SIGNAL_ORDER, normalized)) {
      return SIGNAL_ORDER[normalized];
    }
    return 9;
  },
  toMatchTimestamp(matchTime) {
    if (!matchTime) return null;
    const ts = new Date(matchTime).getTime();
    return Number.isNaN(ts) ? null : ts;
  },
  compareMatchesBySignal(a = {}, b = {}) {
    const aAlert = this.data.alertMap[String(a.matchId || "")] || {};
    const bAlert = this.data.alertMap[String(b.matchId || "")] || {};
    const aOrder = this.getSignalOrder(aAlert.signalLevel || aAlert.signal_level);
    const bOrder = this.getSignalOrder(bAlert.signalLevel || bAlert.signal_level);
    if (aOrder !== bOrder) {
      return aOrder - bOrder;
    }
    const aTs = this.toMatchTimestamp(a.matchTime);
    const bTs = this.toMatchTimestamp(b.matchTime);
    if (aTs != null && bTs != null && aTs !== bTs) {
      return aTs - bTs;
    }
    const aTimeText = String(a.matchTime || "");
    const bTimeText = String(b.matchTime || "");
    const timeCmp = aTimeText.localeCompare(bTimeText);
    if (timeCmp !== 0) {
      return timeCmp;
    }
    return String(a.matchId || "").localeCompare(String(b.matchId || ""));
  },
  computeVisibleSignalSummary(matches = []) {
    const result = {
      heavy: 0,
      strong: 0,
      reference: 0
    };
    const alertMap = this.data.alertMap || {};
    matches.forEach((match) => {
      const key = String(match && match.matchId ? match.matchId : "");
      if (!key) return;
      const alert = alertMap[key];
      if (!alert) return;
      const level = this.normalizeSignalLevel(alert.signalLevel || alert.signal_level);
      if (level === "\u91CD\u4ED3") result.heavy += 1;
      else if (level === "\u5F3A\u70C8") result.strong += 1;
      else if (level === "\u53C2\u8003") result.reference += 1;
    });
    return result;
  },
  extractSignalSummary(payload = {}, matches = []) {
    const summary = payload.summary && typeof payload.summary === "object" ? payload.summary : {};
    const summaryKeys = ["heavy_bet_count", "strong_signal_count", "reference_count"];
    const hasSummaryField = summaryKeys.some((key) => Object.prototype.hasOwnProperty.call(summary, key));
    let heavy = this.toSafeCount(summary.heavy_bet_count);
    let strong = this.toSafeCount(summary.strong_signal_count);
    let reference = this.toSafeCount(summary.reference_count);

    if (!hasSummaryField) {
      const groupedCounts = {
        heavy: Array.isArray(payload.heavy_bets) ? payload.heavy_bets.length : 0,
        strong: Array.isArray(payload.strong_signals) ? payload.strong_signals.length : 0,
        reference: Array.isArray(payload.reference_signals) ? payload.reference_signals.length : 0
      };
      const groupedTotal = groupedCounts.heavy + groupedCounts.strong + groupedCounts.reference;
      if (groupedTotal > 0) {
        heavy = groupedCounts.heavy;
        strong = groupedCounts.strong;
        reference = groupedCounts.reference;
      } else if (matches.length) {
        const counted = new Set();
        matches.forEach((match) => {
          const matchKey = String(match.matchId || "");
          if (!matchKey || counted.has(matchKey)) {
            return;
          }
          counted.add(matchKey);
          const level = this.normalizeSignalLevel(match.signalLevel || match.signal_level);
          if (level === "\u91CD\u4ED3") heavy += 1;
          else if (level === "\u5F3A\u70C8") strong += 1;
          else if (level === "\u53C2\u8003") reference += 1;
        });
      }
    }

    const total = heavy + strong + reference;
    return {
      heavy,
      strong,
      reference,
      total,
      hasData: hasSummaryField || total > 0
    };
  },
  normalizeRule(rule = {}, category = "") {
    const accuracyNum = this.toAccuracyNumber(rule);
    return {
      rule_id: rule.rule_id || rule.ruleId || rule.id || "",
      rule_name: rule.rule_name || rule.ruleName || rule.name || "",
      target: rule.target || this.getCategoryTarget(category),
      accuracy: accuracyNum,
      accuracy_pct: this.toAccuracyPctText(rule, accuracyNum),
      sample: rule.sample != null ? rule.sample : "--",
      bet_suggestion: rule.bet_suggestion || rule.betSuggestion || ""
    };
  },
  normalizeAlertMatch(match = {}, category = "") {
    const rules = Array.isArray(match.rules) ? match.rules : [];
    const normalizedRules = rules
      .map((rule) => this.normalizeRule(rule, category))
      .sort((a, b) => b.accuracy - a.accuracy);
    const signalLevel = this.normalizeSignalLevel(match.signal_level || match.signalLevel);
    const signalIcon = match.signal_icon || match.signalIcon || this.getSignalIconByLevel(signalLevel);
    const crossConfirmRaw = match.cross_confirm != null ? match.cross_confirm : match.crossConfirm;
    const confidence = match.confidence || (normalizedRules[0] ? normalizedRules[0].accuracy_pct : "--");
    const ruleCount = typeof match.rule_count === "number" ? match.rule_count : normalizedRules.length;
    return {
      category,
      matchId: match.match_id || match.matchId,
      matchTime: match.match_time || match.matchTime || "",
      matchStatus: match.match_status || match.matchStatus || "scheduled",
      leagueName: match.league_name || match.leagueName || "",
      homeTeam: match.home_team || match.homeTeam || "",
      awayTeam: match.away_team || match.awayTeam || "",
      handicapTeam: match.handicap_team || match.handicapTeam || "",
      receiverTeam: match.receiver_team || match.receiverTeam || "",
      oddsStr: match.odds_str || match.oddsStr || "--",
      hOdds: match.h_odds != null ? match.h_odds : match.hOdds,
      rOdds: match.r_odds != null ? match.r_odds : match.rOdds,
      hOddsText: this.formatOddsText(match.h_odds != null ? match.h_odds : match.hOdds),
      rOddsText: this.formatOddsText(match.r_odds != null ? match.r_odds : match.rOdds),
      ranges: {
        handicap: (match.ranges && (match.ranges.handicap || match.ranges.handicap_team)) || "--",
        receiver: (match.ranges && (match.ranges.receiver || match.ranges.receive_team)) || "--",
        draw: (match.ranges && match.ranges.draw) || "--"
      },
      changes: {
        handicap: (match.changes && (match.changes.handicap || match.changes.handicap_team)) || "--",
        receiver: (match.changes && (match.changes.receiver || match.changes.receive_team)) || "--",
        draw: (match.changes && match.changes.draw) || "--"
      },
      power: match.power || "--",
      confidence: confidence || "--",
      ruleCount,
      signalLevel,
      signalIcon,
      crossConfirm: this.toBoolean(crossConfirmRaw),
      gradeSummary: match.grade_summary || match.gradeSummary || "",
      rules: normalizedRules
    };
  },
  extractAlertMatches(payload = {}) {
    const matches = [];
    const signalGroups = [
      { key: "heavy_bets", signalLevel: "\u91CD\u4ED3" },
      { key: "strong_signals", signalLevel: "\u5F3A\u70C8" },
      { key: "reference_signals", signalLevel: "\u53C2\u8003" }
    ];
    signalGroups.forEach(({ key, signalLevel }) => {
      const list = Array.isArray(payload[key]) ? payload[key] : [];
      list.forEach((match) => {
        const matchWithLevel = Object.assign({}, match, {
          signal_level: match.signal_level || match.signalLevel || signalLevel
        });
        const normalized = this.normalizeAlertMatch(matchWithLevel, match.category || "");
        if (normalized && normalized.matchId) {
          matches.push(normalized);
        }
      });
    });
    const categories = ["handicap_win", "handicap_not_lose", "receiver_not_lose"];
    categories.forEach((category) => {
      const list = Array.isArray(payload[category]) ? payload[category] : [];
      list.forEach((match) => {
        const normalized = this.normalizeAlertMatch(match, category);
        if (normalized && normalized.matchId) {
          matches.push(normalized);
        }
      });
    });
    return matches;
  },
  buildAlertMap(matches = []) {
    const alertMap = {};
    const seenRule = {};
    matches.forEach((match) => {
      const key = String(match.matchId || "");
      if (!key) return;
      if (!alertMap[key]) {
        alertMap[key] = Object.assign({}, match, { rules: [] });
        seenRule[key] = new Set();
      }
      const entry = alertMap[key];
      const currentConfidence = parseFloat(String(entry.confidence || "0").replace("%", "")) || 0;
      const incomingConfidence = parseFloat(String(match.confidence || "0").replace("%", "")) || 0;
      if (incomingConfidence > currentConfidence) {
        entry.confidence = match.confidence;
      }
      entry.ruleCount = Math.max(entry.ruleCount || 0, match.ruleCount || 0);
      const currentSignalOrder = this.getSignalOrder(entry.signalLevel || entry.signal_level);
      const incomingSignalOrder = this.getSignalOrder(match.signalLevel || match.signal_level);
      const shouldReplaceSignal = incomingSignalOrder < currentSignalOrder || !entry.signalLevel;
      if (shouldReplaceSignal) {
        entry.signalLevel = match.signalLevel || match.signal_level;
        entry.signalIcon = match.signalIcon || this.getSignalIconByLevel(entry.signalLevel);
        entry.gradeSummary = match.gradeSummary || "";
      }
      if (!entry.signalIcon && match.signalIcon) {
        entry.signalIcon = match.signalIcon;
      }
      if (!entry.gradeSummary && match.gradeSummary) {
        entry.gradeSummary = match.gradeSummary;
      }
      entry.crossConfirm = !!(entry.crossConfirm || match.crossConfirm);
      if (entry.oddsStr === "--" && match.oddsStr && match.oddsStr !== "--") entry.oddsStr = match.oddsStr;
      if (entry.hOddsText === "--" && match.hOddsText && match.hOddsText !== "--") entry.hOddsText = match.hOddsText;
      if (entry.rOddsText === "--" && match.rOddsText && match.rOddsText !== "--") entry.rOddsText = match.rOddsText;
      if (entry.power === "--" && match.power && match.power !== "--") entry.power = match.power;
      if (!entry.handicapTeam && match.handicapTeam) entry.handicapTeam = match.handicapTeam;
      if (!entry.receiverTeam && match.receiverTeam) entry.receiverTeam = match.receiverTeam;
      if (entry.ranges.handicap === "--" && match.ranges.handicap !== "--") entry.ranges.handicap = match.ranges.handicap;
      if (entry.ranges.receiver === "--" && match.ranges.receiver !== "--") entry.ranges.receiver = match.ranges.receiver;
      if (entry.ranges.draw === "--" && match.ranges.draw !== "--") entry.ranges.draw = match.ranges.draw;
      if (entry.changes.handicap === "--" && match.changes.handicap !== "--") entry.changes.handicap = match.changes.handicap;
      if (entry.changes.receiver === "--" && match.changes.receiver !== "--") entry.changes.receiver = match.changes.receiver;
      if (entry.changes.draw === "--" && match.changes.draw !== "--") entry.changes.draw = match.changes.draw;

      (match.rules || []).forEach((rule) => {
        const dedupeKey = (rule.rule_id || "") + "|" + (rule.target || "") + "|" + (rule.rule_name || "");
        if (seenRule[key].has(dedupeKey)) return;
        seenRule[key].add(dedupeKey);
        entry.rules.push(rule);
      });
    });

    Object.keys(alertMap).forEach((key) => {
      const entry = alertMap[key];
      entry.rules.sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0));
      entry.ruleCount = entry.rules.length || entry.ruleCount || 0;
      if (!entry.confidence || entry.confidence === "--") {
        entry.confidence = entry.rules[0] ? entry.rules[0].accuracy_pct : "--";
      }
      entry.signalLevel = this.normalizeSignalLevel(entry.signalLevel || entry.signal_level);
      if (!entry.signalIcon) {
        entry.signalIcon = this.getSignalIconByLevel(entry.signalLevel);
      }
      entry.gradeSummary = entry.gradeSummary || "";
      entry.crossConfirm = !!entry.crossConfirm;
      entry.count = entry.ruleCount;
    });
    return alertMap;
  },
  async loadMore() {
    if (this.data.loadingMore || !this.data.hasMore) {
      return;
    }
    this.setData({ loadingMore: true });
    const nextPage = this.data.page + 1;
    try {
      const paging = { page: nextPage, pageSize: this.data.pageSize };
      const response = await fetchMatches(this.data.statusFilter, paging, { showLoading: false });
      if (response && response.success && response.data) {
        const newMatches = response.data;
        const merged = this.data.allMatches.concat(newMatches);
        const total = typeof response.total === "number" ? response.total : this.data.totalMatches;
        this.setData({
          allMatches: merged,
          page: nextPage,
          totalMatches: total,
          hasMore: total ? merged.length < total : newMatches.length === this.data.pageSize,
          loadingMore: false
        });
        this.updateLeagueOptions(merged);
        this.filterAndGroupMatches();
      } else {
        throw new Error((response == null ? void 0 : response.error) || "\u52A0\u8F7D\u66F4\u591A\u5931\u8D25");
      }
    } catch (error) {
      console.error("\u52A0\u8F7D\u66F4\u591A\u5931\u8D25:", error);
      util.showToast("\u52A0\u8F7D\u66F4\u591A\u5931\u8D25", "none");
      this.setData({ loadingMore: false });
    }
  },
  updateLeagueOptions(matches) {
    const leagueNames = [];
    matches.forEach((match) => {
      if (match.leagueName && !leagueNames.includes(match.leagueName)) {
        leagueNames.push(match.leagueName);
      }
    });
    leagueNames.sort();
    this.setData({
      leagueOptions: ["\u5168\u90E8\u8054\u8D5B", ...leagueNames]
    });
    // 生成快捷联赛筛选
    this.updateQuickLeagues(leagueNames);
  },
  updateQuickLeagues(leagueNames) {
    // 按优先级排序，取前8个
    const sorted = leagueNames
      .map(name => ({ name, priority: getLeaguePriority(name) }))
      .sort((a, b) => a.priority - b.priority || a.name.localeCompare(b.name));
    // 最多显示8个快捷筛选
    const quickLeagues = sorted.slice(0, 8);
    this.setData({ quickLeagues });
  },
  filterAndGroupMatches() {
    const {
      allMatches,
      searchKeyword,
      statusFilter,
      selectedLeague,
      selectedDate,
      customDate,
      selectedSignalLevel
    } = this.data;
    let filtered = allMatches.slice();

    if (selectedLeague && selectedLeague !== "\u5168\u90E8\u8054\u8D5B") {
      filtered = filtered.filter((match) => match.leagueName === selectedLeague);
    }
    if (statusFilter) {
      filtered = filtered.filter((match) => {
        const status = match.matchStatus;
        if (statusFilter === "live") {
          return status === "\u8FDB\u884C\u4E2D" || status === "live";
        }
        if (statusFilter === "scheduled") {
          return status === "\u672A\u5F00\u59CB" || status === "scheduled";
        }
        if (statusFilter === "finished") {
          return status === "\u5DF2\u7ED3\u675F" || status === "finished";
        }
        return true;
      });
    }
    if (selectedDate || customDate) {
      filtered = filtered.filter((match) => {
        const matchDate = new Date(match.matchTime);
        if (customDate) {
          const target = new Date(customDate);
          target.setHours(0, 0, 0, 0);
          const nextDay = new Date(target);
          nextDay.setDate(nextDay.getDate() + 1);
          return matchDate >= target && matchDate < nextDay;
        }
        const today = /* @__PURE__ */ new Date();
        today.setHours(0, 0, 0, 0);
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);
        const weekAhead = new Date(today);
        weekAhead.setDate(weekAhead.getDate() + 7);
        switch (selectedDate) {
          case "today":
            return matchDate >= today && matchDate < tomorrow;
          case "tomorrow":
            return matchDate >= tomorrow && matchDate < new Date(tomorrow.getTime() + 24 * 60 * 60 * 1e3);
          case "week":
            return matchDate >= today && matchDate < weekAhead;
          default:
            return true;
        }
      });
    }
    if (searchKeyword) {
      const keyword = searchKeyword.toLowerCase();
      filtered = filtered.filter((match) => {
        return (match.homeTeam || "").toLowerCase().includes(keyword) || (match.awayTeam || "").toLowerCase().includes(keyword) || (match.leagueName || "").toLowerCase().includes(keyword);
      });
    }
    const visibleSignalSummary = this.computeVisibleSignalSummary(filtered);
    if (selectedSignalLevel && Object.keys(this.data.alertMap || {}).length) {
      filtered = filtered.filter((match) => {
        const alert = this.data.alertMap[String(match.matchId || "")];
        if (!alert) {
          return false;
        }
        const level = this.normalizeSignalLevel(alert.signalLevel || alert.signal_level);
        return level === selectedSignalLevel;
      });
    }
    this.setData({
      visibleSignalSummary,
      filteredMatches: filtered,
      groupedMatches: this.groupMatchesByDate(filtered)
    });
  },
  groupMatchesByDate(matches) {
    const groups = {};
    matches.forEach((match) => {
      const rawTime = match && match.matchTime ? match.matchTime : "";
      const date = rawTime ? new Date(rawTime) : null;
      const validDate = date && !Number.isNaN(date.getTime()) ? date : null;
      const key = validDate ? util.formatTime(validDate, "YYYY-MM-DD") : "\u672A\u77E5\u65E5\u671F";
      if (!groups[key]) {
        groups[key] = {
          date: key,
          dateText: validDate ? this.getDateText(validDate) : "\u65F6\u95F4\u5F85\u5B9A",
          matches: []
        };
      }
      groups[key].matches.push(match);
    });
    Object.keys(groups).forEach((key) => {
      groups[key].matches.sort((a, b) => this.compareMatchesBySignal(a, b));
    });
    const groupedArray = Object.values(groups);
    groupedArray.sort((a, b) => {
      if (this.data.statusFilter === "finished") {
        return b.date.localeCompare(a.date);
      }
      return a.date.localeCompare(b.date);
    });
    return groupedArray;
  },
  getDateText(date) {
    const now = /* @__PURE__ */ new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const matchDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    if (matchDate.getTime() === today.getTime()) {
      return "\u4ECA\u5929";
    } else if (matchDate.getTime() === tomorrow.getTime()) {
      return "\u660E\u5929";
    } else if (matchDate.getTime() === yesterday.getTime()) {
      return "\u6628\u5929";
    }
    return util.formatTime(date, "MM\u6708DD\u65E5");
  },
  onQuickLeagueTap(e) {
    const name = e.currentTarget.dataset.name;
    // 点击同一个联赛取消筛选
    const next = this.data.selectedLeague === name ? '' : name;
    this.setData({ selectedLeague: next });
    this.filterAndGroupMatches();
  },
  onClearLeagueFilter() {
    this.setData({ selectedLeague: '' });
    this.filterAndGroupMatches();
  },
  onLeagueChange(e) {
    const index = e.detail.value;
    const league = this.data.leagueOptions[index];
    this.setData({ selectedLeague: league === "\u5168\u90E8\u8054\u8D5B" ? "" : league });
    this.filterAndGroupMatches();
  },
  onDateFilterChange(e) {
    const value = e.currentTarget.dataset.value;
    this.setData({ selectedDate: value, customDate: "" });
    this.filterAndGroupMatches();
  },
  onStatusTabTap(e) {
    const value = e.currentTarget.dataset.value;
    this.setData({ statusFilter: value, activeStatusTab: value });
    this.loadData({ reset: true });
  },
  onCustomDateChange(e) {
    this.setData({ customDate: e.detail.value, selectedDate: "" });
    this.filterAndGroupMatches();
  },
  onSearchInput(e) {
    const keyword = e.detail.value;
    this.setData({ searchKeyword: keyword });
    if (this.searchTimer) {
      clearTimeout(this.searchTimer);
    }
    this.searchTimer = setTimeout(() => {
      this.filterAndGroupMatches();
    }, 300);
  },
  onSearch() {
    this.filterAndGroupMatches();
  },
  toggleModule(e) {
    const module = e.currentTarget.dataset.module;
    if (!module) return;
    const collapsedModules = Object.assign({}, this.data.collapsedModules || {});
    collapsedModules[module] = !collapsedModules[module];
    this.setData({ collapsedModules });
  },
  onReachBottom() {
    this.loadMore();
  },
  onRefresh() {
    this.loadData({ forceRefresh: true, reset: true });
  },
  onMatchTap(e) {
    const match = e && e.detail ? e.detail.match : null;
    if (!match || !match.matchId) {
      return;
    }
    wx.navigateTo({
      url: `/pages/match-detail/match-detail?matchId=${match.matchId}`
    });
  },
  onShareAppMessage() {
    return util.getShareConfig("OddsMind - \u6BD4\u8D5B\u5217\u8868", "/pages/matches/matches");
  },
  onShareTimeline() {
    return {
      title: "OddsMind - \u6BD4\u8D5B\u5217\u8868",
      query: "",
      imageUrl: ""
    };
  },
  onUnload() {
    if (this.searchTimer) {
      clearTimeout(this.searchTimer);
      this.searchTimer = null;
    }
  }
});
