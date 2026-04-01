const {
  fetchMatchDetail,
  fetchMatchDetailBasic,
  fetchMatchDetailPage,
  fetchPoissonPrediction
} = require("../../utils/match-service.js");
const { fetchMatchAlerts } = require("../../utils/alert-service.js");
const util = require("../../utils/util.js");
const oddsLookup = require("../../utils/odds-lookup.js");
Page({
  data: {
    loading: false,
    loadingMore: false,
    matchId: "",
    matchDetail: {},
    companies: [],
    matchTime: "",
    statusText: "",
    recommendationText: "",
    companyOptions: [],
    selectedCompanyIndex: 0,
    selectedCompany: null,
    fundamentalItems: [],
    expandedOddsRanges: {}, // 记录哪些项的合理开盘区间是展开的
    collapsedModules: {
      reasonable: false,
      fundamental: false,
      odds: false,
      poisson: false,
      ruleMatch: true,
      asianHandicap: false,
      attitude: false,
      drawSystem: false
    },
    reasonableOddsTable: [], // 合理开盘区间表格数据
    asianHandicapRows: [], // 亚盘对比数据
    poissonPrediction: null,
    poissonLoading: false,
    poissonError: null,
    poissonLoaded: false,
    poissonSummary: {
      home: "--",
      draw: "--",
      away: "--"
    },
    oddsRows: [],
    pagination: {
      page: 1,
      pageSize: 10,
      totalCompanies: 0,
      totalPages: 0,
      hasMore: false,
      hasPrev: false
    },
    poissonModalVisible: false,
    poissonModalData: {
      expectedHome: "--",
      expectedAway: "--",
      expectedTotal: "--",
      homeProb: "--",
      drawProb: "--",
      awayProb: "--",
      method: "--",
      ouList: [],
      scoreTable: []
    },
    // 公司态度汇总数据
    companySummary: null,
    attitudeViewMode: 'initial', // 'initial' 或 'current'，默认显示初盘
    expandedAttitude: {}, // 记录哪个态度项被展开 { home: false, draw: false, away: false }
    ruleMatchLoading: false,
    ruleMatchError: null,
    hasRuleMatch: false,
    handicapTeam: "",
    receiverTeam: "",
    ruleHomeTeam: "",
    ruleAwayTeam: "",
    target: "",
    targetMode: "",
    targetMain: "",
    targetSub: "",
    ruleFeatures: null,
    alerts: [],
    hasDrawSystem: false,
    drawSystem: {}
  },
  onLoad(options) {
    console.log("\u6BD4\u8D5B\u8BE6\u60C5\u9875\u52A0\u8F7D", options);
    if (options.matchId) {
      this.setData({ matchId: options.matchId });
      this.loadMatchDetail();
      this.loadMatchAlerts(options.matchId);
    } else {
      util.showToast("\u7F3A\u5C11\u6BD4\u8D5BID", "error");
      setTimeout(() => {
        wx.navigateBack();
      }, 1500);
    }
  },
  onPullDownRefresh() {
    console.log("\u6BD4\u8D5B\u8BE6\u60C5\u9875\u4E0B\u62C9\u5237\u65B0");
    Promise.all([this.loadMatchDetail(), this.loadMatchAlerts()]).finally(() => {
      wx.stopPullDownRefresh();
    });
  },
  resetPoissonState() {
    this.setData({
      poissonPrediction: null,
      poissonLoading: false,
      poissonError: null,
      poissonLoaded: false,
      poissonModalVisible: false,
      poissonSummary: this.buildPoissonSummary(null),
      poissonModalData: {
        expectedHome: "--",
        expectedAway: "--",
        expectedTotal: "--",
        homeProb: "--",
        drawProb: "--",
        awayProb: "--",
        method: "--",
        ouList: [],
        scoreTable: []
      }
    });
  },
  async loadMatchDetail() {
    try {
      this.setData({
        loading: true,
        loadingMore: false,
        companies: [],
        pagination: this.getDefaultPagination()
      });
      this.resetPoissonState();

      // Fast path: use new pagination endpoint to reduce payload
      try {
        const paged = await fetchMatchDetailBasic(this.data.matchId);
        if (paged && paged.success && paged.data) {
          this.preparePaginatedDetail(paged.data);
          return;
        }
      } catch (err) {
        console.warn("Pagination basic detail failed, falling back to legacy detail.", err);
      }

      // Fallback to legacy full detail
      const response = await fetchMatchDetail(this.data.matchId);
      if (response && response.success && response.data) {
        this.prepareMatchDetail(response.data);
      } else {
        throw new Error((response == null ? void 0 : response.error) || "\u6BD4\u8D5B\u8BE6\u60C5\u52A0\u8F7D\u5931\u8D25");
      }
    } catch (error) {
      console.error("\u52A0\u8F7D\u6BD4\u8D5B\u8BE6\u60C5\u5931\u8D25:", error);
      util.showToast("\u6BD4\u8D5B\u8BE6\u60C5\u52A0\u8F7D\u5931\u8D25", "none");
      setTimeout(() => {
        wx.navigateBack();
      }, 2e3);
    } finally {
      this.setData({ loading: false });
    }
  },
  async loadMatchAlerts(matchId) {
    const targetMatchId = matchId || this.data.matchId;
    if (!targetMatchId) {
      return;
    }
    this.setData({
      ruleMatchLoading: true,
      ruleMatchError: null,
      hasRuleMatch: false
    });
    try {
      const res = await fetchMatchAlerts(targetMatchId, { showLoading: false, suppressToast: true });
      const payload = res && res.success && res.data ? res.data : null;
      const alerts = payload && Array.isArray(payload.alerts) ? payload.alerts : [];
      const hasAlertFlag = payload && (payload.has_alert === false || payload.hasAlert === false);
      if (!payload || hasAlertFlag || alerts.length === 0) {
        this.setData({
          ruleMatchLoading: false,
          hasRuleMatch: false,
          target: "",
          targetMode: "",
          targetMain: "",
          targetSub: "",
          alerts: [],
          ruleFeatures: null
        });
        return;
      }
      const state = this.buildRuleMatchState(payload);
      this.setData({
        ruleMatchLoading: false,
        ruleMatchError: null,
        ...state
      });
    } catch (err) {
      console.warn("loadMatchAlerts failed:", err);
      this.setData({
        ruleMatchLoading: false,
        ruleMatchError: (err && err.message) || "\u89C4\u5219\u5339\u914D\u6570\u636E\u52A0\u8F7D\u5931\u8D25",
        hasRuleMatch: false,
        target: "",
        targetMode: "",
        targetMain: "",
        targetSub: "",
        alerts: [],
        ruleFeatures: null
      });
    }
  },
  buildRuleMatchState(payload) {
    const getRuleFeatures = (source) => {
      if (!source) return {};
      if (typeof source === "string") {
        try {
          const parsed = JSON.parse(source);
          return parsed && typeof parsed === "object" ? parsed : {};
        } catch (err) {
          return {};
        }
      }
      return typeof source === "object" ? source : {};
    };

    const alerts = Array.isArray(payload.alerts) ? payload.alerts : (Array.isArray(payload.rules) ? payload.rules : []);
    const decoratedAlerts = alerts.map((alert) => {
      const target = (alert && (alert.target || alert.prediction)) || "";
      const accuracyText = alert && (alert.accuracy_pct || alert.accuracyPct)
        ? (alert.accuracy_pct || alert.accuracyPct)
        : typeof (alert && alert.accuracy) === "number"
          ? `${Math.round(alert.accuracy * 100)}%`
          : "--";
      return Object.assign({}, alert, { target, accuracyText });
    });
    const firstAlert = decoratedAlerts[0] || {};
    const handicapTeam = payload.handicap_team || payload.handicapTeam || firstAlert.handicap_team || firstAlert.handicapTeam || "";
    const ruleHomeTeam = payload.home_team || payload.homeTeam || firstAlert.home_team || firstAlert.homeTeam || "";
    const ruleAwayTeam = payload.away_team || payload.awayTeam || firstAlert.away_team || firstAlert.awayTeam || "";
    const targets = decoratedAlerts.map((item) => item && item.target).filter(Boolean);
    const hasHandicap = targets.some((item) => (
      item === "\u8BA9\u65B9\u4E0D\u8F93"
      || item === "\u8BA9\u65B9\u5FC5\u8D62"
      || item === "\u8BA9\u65B9\u5FC5\u80DC"
    ));
    const hasReceiver = targets.some((item) => item === "\u53D7\u8BA9\u65B9\u4E0D\u8F93");
    const hasDrawHint = hasHandicap && hasReceiver;
    const receiverTeamFromPayload = payload.receiver_team || payload.receiverTeam || firstAlert.receiver_team || firstAlert.receiverTeam || "";
    const receiverTeam = receiverTeamFromPayload || (
      handicapTeam && ruleHomeTeam && ruleAwayTeam
        ? (handicapTeam === ruleHomeTeam ? ruleAwayTeam : ruleHomeTeam)
        : ""
    );
    const primaryTarget = decoratedAlerts[0] ? decoratedAlerts[0].target : "";
    let targetMode = "handicap";
    if (hasDrawHint) {
      targetMode = "draw";
    } else if (primaryTarget === "\u53D7\u8BA9\u65B9\u4E0D\u8F93") {
      targetMode = "receiver";
    }
    let targetMain = "";
    let targetSub = "";
    if (targetMode === "draw") {
      targetMain = "\u2696\uFE0F \u89C4\u5219\u4FE1\u53F7\u51B2\u5408";
      targetSub = "\u540C\u65F6\u547D\u4E2D\u8BA9\u65B9\u4E0D\u8F93\u4E0E\u53D7\u8BA9\u65B9\u4E0D\u8F93";
    } else if (targetMode === "receiver") {
      targetMain = receiverTeam ? `\uD83C\uDFAF ${receiverTeam} \u4E0D\u8F93` : "\uD83C\uDFAF \u53D7\u8BA9\u65B9\u4E0D\u8F93";
      targetSub = handicapTeam && receiverTeam
        ? `\u65B9\u5411: ${handicapTeam}(\u8BA9\u7403\u65B9) \u5F97\u5206 \u2264 ${receiverTeam}(\u53D7\u8BA9\u65B9)`
        : "\u65B9\u5411: \u8BA9\u7403\u65B9 \u5F97\u5206 \u2264 \u53D7\u8BA9\u65B9";
    } else {
      const isMustWin = primaryTarget === "\u8BA9\u65B9\u5FC5\u8D62" || primaryTarget === "\u8BA9\u65B9\u5FC5\u80DC";
      targetMain = handicapTeam
        ? `\uD83C\uDFAF ${handicapTeam} ${isMustWin ? "\u5FC5\u80DC" : "\u4E0D\u8F93"}`
        : `\uD83C\uDFAF \u8BA9\u65B9${isMustWin ? "\u5FC5\u80DC" : "\u4E0D\u8F93"}`;
      targetSub = handicapTeam && receiverTeam
        ? `\u65B9\u5411: ${handicapTeam}(\u8BA9\u7403\u65B9) \u5F97\u5206 ${isMustWin ? ">" : "\u2265"} ${receiverTeam}(\u53D7\u8BA9\u65B9)`
        : `\u65B9\u5411: \u8BA9\u7403\u65B9 \u5F97\u5206 ${isMustWin ? ">" : "\u2265"} \u53D7\u8BA9\u65B9`;
    }
    const rawFeatures = (() => {
      const fromPayload = getRuleFeatures(payload.features || payload.rule_features || payload.ruleFeatures);
      if (Object.keys(fromPayload).length) return fromPayload;
      for (let i = 0; i < decoratedAlerts.length; i += 1) {
        const item = decoratedAlerts[i] || {};
        const parsed = getRuleFeatures(item.features || item.rule_features || item.ruleFeatures);
        if (Object.keys(parsed).length) return parsed;
      }
      return {};
    })();
    const ruleFeatures = {
      power: rawFeatures.power_v2 || rawFeatures.power,
      init_h: rawFeatures.init_h || rawFeatures.initH,
      curr_h: rawFeatures.curr_h || rawFeatures.currH,
      curr_r: rawFeatures.curr_r || rawFeatures.currR,
      h_change: rawFeatures.h_change_simple || rawFeatures.h_change || rawFeatures.hChange,
      r_change: rawFeatures.r_change_simple || rawFeatures.r_change || rawFeatures.rChange
    };
    const getChangeClass = (value) => {
      if (!value) return "";
      if (value.includes("\u5347")) return "up";
      if (value.includes("\u964D")) return "down";
      return "stable";
    };
    ruleFeatures.hChangeClass = getChangeClass(ruleFeatures.h_change);
    ruleFeatures.rChangeClass = getChangeClass(ruleFeatures.r_change);
    const hasFeatureValue = !!(ruleFeatures.power || ruleFeatures.init_h || ruleFeatures.curr_h || ruleFeatures.curr_r || ruleFeatures.h_change || ruleFeatures.r_change);
    return {
      hasRuleMatch: true,
      handicapTeam,
      receiverTeam,
      ruleHomeTeam,
      ruleAwayTeam,
      target: primaryTarget,
      targetMode,
      targetMain,
      targetSub,
      alerts: decoratedAlerts,
      ruleFeatures: hasFeatureValue ? ruleFeatures : null
    };
  },
  pickFirstValue(values = [], fallback = null) {
    for (let i = 0; i < values.length; i += 1) {
      const value = values[i];
      if (value !== undefined && value !== null && value !== "") {
        return value;
      }
    }
    return fallback;
  },
  parseSuggestions(value) {
    if (Array.isArray(value)) {
      return value.filter(Boolean);
    }
    if (typeof value === "string") {
      const text = value.trim();
      if (!text) return [];
      try {
        const parsed = JSON.parse(text);
        if (Array.isArray(parsed)) {
          return parsed.filter(Boolean);
        }
      } catch (err) {
        // ignore parse failure and fallback to split
      }
      return text
        .split(/[、,，;；|/]/)
        .map((item) => item.trim())
        .filter(Boolean);
    }
    return [];
  },
  normalizeOddsSection(section) {
    const source = section && typeof section === "object" ? section : {};
    const odds = source.odds && typeof source.odds === "object" ? source.odds : {};
    const home = this.pickFirstValue([
      odds.home,
      odds.homeWin,
      odds.win,
      source.home,
      source.homeWin,
      source.win,
      source.home_odds,
      source.home_win_odds
    ], null);
    const draw = this.pickFirstValue([
      odds.draw,
      source.draw,
      source.drawOdds,
      source.draw_odds
    ], null);
    const away = this.pickFirstValue([
      odds.away,
      odds.awayWin,
      odds.lose,
      source.away,
      source.awayWin,
      source.lose,
      source.away_odds,
      source.away_win_odds,
      source.lose_odds
    ], null);
    return Object.assign({}, source, {
      homeRange: this.pickFirstValue([source.homeRange, source.home_range], null),
      drawRange: this.pickFirstValue([source.drawRange, source.draw_range], null),
      awayRange: this.pickFirstValue([source.awayRange, source.away_range], null),
      homeRuleValue: this.pickFirstValue([source.homeRuleValue, source.home_rule_value], null),
      drawRuleValue: this.pickFirstValue([source.drawRuleValue, source.draw_rule_value], null),
      awayRuleValue: this.pickFirstValue([source.awayRuleValue, source.away_rule_value], null),
      ruleDiff: this.pickFirstValue([source.ruleDiff, source.rule_diff], null),
      recommendedOutcome: this.pickFirstValue([source.recommendedOutcome, source.recommended_outcome], null),
      odds: Object.assign({}, odds, {
        home,
        draw,
        away,
        homeWin: this.pickFirstValue([odds.homeWin, home], null),
        awayWin: this.pickFirstValue([odds.awayWin, away], null),
        win: this.pickFirstValue([odds.win, home], null),
        lose: this.pickFirstValue([odds.lose, away], null)
      }),
      home,
      draw,
      away,
      homeWin: this.pickFirstValue([source.homeWin, home], null),
      awayWin: this.pickFirstValue([source.awayWin, away], null),
      win: this.pickFirstValue([source.win, home], null),
      lose: this.pickFirstValue([source.lose, away], null)
    });
  },
  normalizeCompanyAnalysis(company) {
    if (!company || typeof company !== "object") {
      return null;
    }
    const source = company;
    const initialSource = this.pickFirstValue([
      source.initial,
      source.initial_odds,
      source.opening,
      source.opening_odds
    ], {});
    const currentSource = this.pickFirstValue([
      source.current,
      source.current_odds,
      source.instant,
      source.instant_odds,
      source.latest
    ], {});
    return Object.assign({}, source, {
      companyId: this.pickFirstValue([source.companyId, source.company_id, source.id], ""),
      companyName: this.pickFirstValue([source.companyName, source.company_name, source.name], ""),
      homePowerLevel: this.pickFirstValue([source.homePowerLevel, source.home_power_level], null),
      awayPowerLevel: this.pickFirstValue([source.awayPowerLevel, source.away_power_level], null),
      homeTierLevel: this.pickFirstValue([source.homeTierLevel, source.home_tier_level], null),
      awayTierLevel: this.pickFirstValue([source.awayTierLevel, source.away_tier_level], null),
      homeTeamStrength: this.pickFirstValue([source.homeTeamStrength, source.home_team_strength], null),
      awayTeamStrength: this.pickFirstValue([source.awayTeamStrength, source.away_team_strength], null),
      analyzedAt: this.pickFirstValue([source.analyzedAt, source.analyzed_at], null),
      recommendedOutcome: this.pickFirstValue([source.recommendedOutcome, source.recommended_outcome], null),
      initial: this.normalizeOddsSection(initialSource),
      current: this.normalizeOddsSection(currentSource)
    });
  },
  normalizeCompanyList(companies) {
    if (!Array.isArray(companies)) {
      return [];
    }
    return companies
      .map((company) => this.normalizeCompanyAnalysis(company))
      .filter(Boolean);
  },
  normalizeFundamentalEntry(entry, topLevelSuggestions) {
    const source = entry && typeof entry === "object" ? entry : {};
    const suggestions = this.parseSuggestions(
      this.pickFirstValue([source.oddsSuggestions, source.odds_suggestions, topLevelSuggestions], [])
    );
    const normalized = {
      score: this.pickFirstValue([source.score, source.maxScore, source.max_score], null),
      confidenceLevel: this.pickFirstValue([source.confidenceLevel, source.confidence_level], null),
      confidenceInterval: this.pickFirstValue([source.confidenceInterval, source.confidence_interval], null),
      oddsSuggestions: suggestions
    };
    const hasValue = normalized.score != null
      || normalized.confidenceLevel
      || normalized.confidenceInterval
      || normalized.oddsSuggestions.length > 0;
    return hasValue ? normalized : null;
  },
  normalizeFundamentalAnalysis(analysis) {
    const source = analysis && typeof analysis === "object" ? analysis : {};
    const homeTop = this.parseSuggestions(
      this.pickFirstValue([source.homeOddsSuggestions, source.home_odds_suggestions], [])
    );
    const drawTop = this.parseSuggestions(
      this.pickFirstValue([source.drawOddsSuggestions, source.draw_odds_suggestions], [])
    );
    const awayTop = this.parseSuggestions(
      this.pickFirstValue([source.awayOddsSuggestions, source.away_odds_suggestions], [])
    );
    return Object.assign({}, source, {
      recommendedOutcome: this.pickFirstValue([source.recommendedOutcome, source.recommended_outcome, source.recommendation], null),
      confidenceLevel: this.pickFirstValue([source.confidenceLevel, source.confidence_level, source.recommendation_confidence], null),
      maxScore: this.pickFirstValue([source.maxScore, source.max_score], null),
      homeOddsSuggestions: homeTop,
      drawOddsSuggestions: drawTop,
      awayOddsSuggestions: awayTop,
      homeWin: this.normalizeFundamentalEntry(this.pickFirstValue([source.homeWin, source.home_win], null), homeTop),
      draw: this.normalizeFundamentalEntry(this.pickFirstValue([source.draw, source.draw_data], null), drawTop),
      awayWin: this.normalizeFundamentalEntry(this.pickFirstValue([source.awayWin, source.away_win], null), awayTop),
      pullDirection: this.pickFirstValue([source.pullDirection, source.pull_direction], null),
      pullDescription: this.pickFirstValue([source.pullDescription, source.pull_description], null),
      prompts: this.pickFirstValue([source.prompts], []),
      absentPlayers: this.pickFirstValue([source.absentPlayers, source.absent_players], {home: [], away: []}),
      briefing: this.pickFirstValue([source.briefing], ""),
      distributionNode: this.pickFirstValue([source.distributionNode, source.distribution_node], null)
    });
  },
  normalizeStandings(standings) {
    const source = standings && typeof standings === "object" ? standings : {};
    const normalizeTeam = (team) => {
      const data = team && typeof team === "object" ? team : {};
      return {
        position: this.pickFirstValue([data.position, data.rank], null),
        points: this.pickFirstValue([data.points, data.point], null),
        played: this.pickFirstValue([data.played, data.matches_played], null),
        wins: this.pickFirstValue([data.wins, data.win], null),
        draws: this.pickFirstValue([data.draws, data.draw], null),
        losses: this.pickFirstValue([data.losses, data.lose], null),
        team_id: this.pickFirstValue([data.team_id, data.teamId], null)
      };
    };
    return {
      home: normalizeTeam(this.pickFirstValue([source.home, source.home_team, source.homeTeam], {})),
      away: normalizeTeam(this.pickFirstValue([source.away, source.away_team, source.awayTeam], {}))
    };
  },
  normalizeMatchDetail(detail) {
    const source = detail && typeof detail === "object" ? detail : {};
    const companies = this.normalizeCompanyList(
      this.pickFirstValue([source.companyAnalyses, source.company_analyses], [])
    );
    const topCompany = this.normalizeCompanyAnalysis(
      this.pickFirstValue([source.topCompany, source.top_company, source.oddsAnalysis, source.odds_analysis], null)
    );
    const mergedCompanies = this.mergeCompanies([
      ...(topCompany ? [topCompany] : []),
      ...companies
    ]);
    const companySummary = this.pickFirstValue([source.companySummary, source.company_summary], null);
    return Object.assign({}, source, {
      matchId: this.pickFirstValue([source.matchId, source.match_id, source.id, this.data.matchId], ""),
      leagueName: this.pickFirstValue([source.leagueName, source.league_name], ""),
      matchTime: this.pickFirstValue([source.matchTime, source.match_time], null),
      homeTeam: this.pickFirstValue([source.homeTeam, source.home_team], ""),
      awayTeam: this.pickFirstValue([source.awayTeam, source.away_team], ""),
      homeTeamLogo: this.pickFirstValue([source.homeTeamLogo, source.home_team_logo], null),
      awayTeamLogo: this.pickFirstValue([source.awayTeamLogo, source.away_team_logo], null),
      matchStatus: this.pickFirstValue([source.matchStatus, source.match_status], ""),
      homeScore: this.pickFirstValue([source.homeScore, source.home_score], null),
      awayScore: this.pickFirstValue([source.awayScore, source.away_score], null),
      roundNumber: this.pickFirstValue([source.roundNumber, source.round_number, source.round], null),
      totalRounds: this.pickFirstValue([source.totalRounds, source.total_rounds], null),
      season: this.pickFirstValue([source.season], null),
      groupName: this.pickFirstValue([source.groupName, source.group_name], null),
      standings: this.normalizeStandings(source.standings),
      fundamentalAnalysis: this.normalizeFundamentalAnalysis(
        this.pickFirstValue([source.fundamentalAnalysis, source.fundamental_analysis], {})
      ),
      companySummary,
      totalCompanyCount: Number(this.pickFirstValue([
        source.totalCompanyCount,
        source.total_company_count,
        source.totalCompanies,
        source.total_companies,
        companySummary && (companySummary.total_companies || companySummary.totalCompanies || companySummary.total),
        mergedCompanies.length
      ], 0)) || 0,
      companyAnalyses: mergedCompanies,
      topCompany,
      oddsAnalysis: this.pickFirstValue([source.oddsAnalysis, source.odds_analysis], null),
      poissonPrediction: this.pickFirstValue([source.poissonPrediction, source.poisson_prediction], null),
      asianHandicap: this.pickFirstValue([source.asianHandicap, source.asian_handicap], null),
      drawSystemAnalysis: this.pickFirstValue([source.drawSystemAnalysis, source.draw_system_analysis], null)
    });
  },
  prepareMatchDetail(detail) {
    const normalizedDetail = this.normalizeMatchDetail(detail);
    const matchTime = util.formatMatchTime(normalizedDetail.matchTime);
    const statusText = util.getMatchStatusText(normalizedDetail.matchStatus);
    const recommendationText = this.getRecommendationText(normalizedDetail);
    const fundamentalItems = this.buildFundamentalItems(normalizedDetail);
    const cleanedDetail = Object.assign({}, normalizedDetail);
    delete cleanedDetail.poissonPrediction;
    delete cleanedDetail.poisson_prediction;
    wx.setNavigationBarTitle({
      title: `${normalizedDetail.homeTeam || "\u4E3B\u961F"} VS ${normalizedDetail.awayTeam || "\u5BA2\u961F"}`
    });
    cleanedDetail.homeTeamShort = this.getTeamShort(normalizedDetail.homeTeam);
    cleanedDetail.awayTeamShort = this.getTeamShort(normalizedDetail.awayTeam);
    
    // 处理积分排名数据
    const standings = normalizedDetail.standings || {};
    cleanedDetail.homeRank = standings.home ? standings.home.position : null;
    cleanedDetail.homePoints = standings.home ? standings.home.points : null;
    cleanedDetail.awayRank = standings.away ? standings.away.position : null;
    cleanedDetail.awayPoints = standings.away ? standings.away.points : null;
    
    // 调试：输出比分和排名数据
    console.log('[prepareMatchDetail] 比分数据:', {
      homeScore: normalizedDetail.homeScore,
      awayScore: normalizedDetail.awayScore,
      homeRank: cleanedDetail.homeRank,
      awayRank: cleanedDetail.awayRank,
      matchStatus: normalizedDetail.matchStatus
    });
    
    // 处理公司态度汇总数据
    const companySummary = this.buildCompanySummaryDisplay(normalizedDetail.companySummary, normalizedDetail.totalCompanyCount);
    
    // 处理泊松预测数据（如果API已返回，兼容多种字段名）
    const poissonPrediction = this.extractPoissonData(normalizedDetail);
    const hasPoissonData = this.validatePoissonData(poissonPrediction);
    
    console.log('[prepareMatchDetail] 泊松数据检测:', hasPoissonData ? '已找到' : '未找到', poissonPrediction);
    
    // 临场基本面分析数据
    const fa = normalizedDetail.fundamentalAnalysis || {};
    const nonAbsentPrompts = (fa.prompts || []).filter(p => !p.includes('缺阵'));
    const absentPlayers = fa.absentPlayers || {home: [], away: []};
    const hasPreMatch = !!(fa.pullDirection || fa.distributionNode || nonAbsentPrompts.length > 0 ||
      (absentPlayers.home && absentPlayers.home.length > 0) ||
      (absentPlayers.away && absentPlayers.away.length > 0) ||
      fa.briefing);

    const drawSystemState = this.buildDrawSystemDisplay(normalizedDetail.drawSystemAnalysis);

    this.setData({
      matchDetail: cleanedDetail,
      companies: normalizedDetail.companyAnalyses || [],
      matchTime,
      statusText,
      recommendationText,
      fundamentalItems,
      hasPreMatch,
      pullDirection: fa.pullDirection || '',
      pullDescription: fa.pullDescription || '',
      distributionNode: fa.distributionNode || null,
      preMatchPrompts: nonAbsentPrompts,
      absentPlayersHome: absentPlayers.home || [],
      absentPlayersAway: absentPlayers.away || [],
      briefing: fa.briefing || '',
      poissonPrediction: hasPoissonData ? poissonPrediction : null,
      poissonLoaded: hasPoissonData,
      poissonLoading: false,
      poissonError: null,
      poissonSummary: this.buildPoissonSummary(hasPoissonData ? poissonPrediction : null),
      companySummary,
      attitudeViewMode: 'initial',
      expandedAttitude: {},
      hasDrawSystem: drawSystemState.hasData,
      drawSystem: drawSystemState.data
    });
    
    // 如果已有泊松数据，直接更新弹窗数据
    if (hasPoissonData) {
      this.updatePoissonModal(poissonPrediction);
    } else {
      this.updatePoissonModal({});
    }
    
    this.setupCompanies(normalizedDetail.companyAnalyses || []);
    this.calculateReasonableOdds(normalizedDetail);
    this.buildAsianHandicapDisplay(normalizedDetail);
  },
  preparePaginatedDetail(detail) {
    const normalizedDetail = this.normalizeMatchDetail(detail);
    const pagination = this.normalizePagination(
      (detail && detail.pagination) || normalizedDetail.pagination || {}
    );
    const hydrated = Object.assign({}, normalizedDetail, {
      matchId: normalizedDetail.matchId || this.data.matchId
    });

    this.prepareMatchDetail(hydrated);
    this.setData({
      pagination,
      companies: hydrated.companyAnalyses || [],
      loading: false
    });
  },
  normalizePagination(pagination = {}) {
    const page = Number(pagination.page) || 1;
    const pageSize = Number(pagination.pageSize || pagination.page_size) || 20;
    const totalCompanies = Number(pagination.total_companies || pagination.totalCompanies || pagination.total) || 0;
    const totalPages = Number(pagination.total_pages || pagination.totalPages) || (pageSize > 0 ? Math.ceil(totalCompanies / pageSize) : 0);
    return {
      page,
      pageSize,
      totalCompanies,
      totalPages,
      hasMore: pagination.has_more != null ? !!pagination.has_more : page < totalPages,
      hasPrev: pagination.has_prev != null ? !!pagination.has_prev : page > 1
    };
  },
  getDefaultPagination() {
    return {
      page: 1,
      pageSize: 10,
      totalCompanies: 0,
      totalPages: 0,
      hasMore: false,
      hasPrev: false
    };
  },
  mergeCompanies(companies = []) {
    const seen = new Set();
    const result = [];
    companies.forEach((company) => {
      if (!company) return;
      const key = (company.companyId || company.company_id || company.companyName || company.company_name || company.id || company.name || `idx-${result.length}`).toString();
      if (seen.has(key)) return;
      seen.add(key);
      result.push(company);
    });
    return result;
  },
  calculateReasonableOdds(detail, companyOverride = null) {
    // 获取当前选中的公司（如果传入了companyOverride则使用它）
    const company = companyOverride || this.data.selectedCompany;
    if (!company) {
      this.setData({ reasonableOddsTable: [] });
      return;
    }
    
    // 获取广义实力（从公司数据中获取）
    const homeStrength = company.homeTierLevel;
    const awayStrength = company.awayTierLevel;
    
    if (!homeStrength || !awayStrength) {
      this.setData({ reasonableOddsTable: [] });
      return;
    }
    
    // 根据公司ID或名称获取体系（优先使用ID）
    const system = oddsLookup.getSystemByCompany(company.companyName, company.companyId);
    
    // 查找合理开盘区间
    const result = oddsLookup.lookupOdds(homeStrength, awayStrength, system);
    
    if (!result || !result.success) {
      console.warn('查找合理开盘区间失败:', result && result.error ? result.error : '未知错误');
      this.setData({ reasonableOddsTable: [] });
      return;
    }
    
    // 获取公司的初始和即时赔率
    const getOddsDisplay = (section, label) => {
      if (!section) {
        console.log(`[getOddsDisplay] ${label} section为空`);
        return { homeWin: '--', draw: '--', awayWin: '--' };
      }
      
      // 调试日志：输出section的关键信息（避免JSON.stringify可能的问题）
      try {
        console.log(`[getOddsDisplay] ${label} section类型:`, typeof section, 'keys:', section ? Object.keys(section).slice(0, 10) : 'null');
      } catch (e) {
        console.log(`[getOddsDisplay] ${label} section检查失败:`, e.message);
      }
      
      // 尝试多种可能的字段名来提取赔率
      // 主胜可能字段：win, homeWin, home, homeOdds, winOdds, homeWinOdds
      let homeWin = this.extractOddsValue(section, 'win');
      if (!homeWin) {
        homeWin = this.extractOddsValue(section, 'homeWin') || 
                  this.extractOddsValue(section, 'home') ||
                  (section.odds && (section.odds.homeWin || section.odds.home)) ||
                  section.homeWin || section.home || section.homeWinOdds || section.winOdds;
      }
      
      // 平局字段：draw, drawOdds
      const draw = this.extractOddsValue(section, 'draw') || 
                   section.draw || 
                   section.drawOdds ||
                   (section.odds && section.odds.draw);
      
      // 客胜可能字段：lose, awayWin, away, loseOdds, awayWinOdds
      let awayWin = this.extractOddsValue(section, 'lose');
      if (!awayWin) {
        awayWin = this.extractOddsValue(section, 'awayWin') || 
                  this.extractOddsValue(section, 'away') ||
                  (section.odds && (section.odds.awayWin || section.odds.away)) ||
                  section.awayWin || section.away || section.awayWinOdds || section.loseOdds;
      }
      
      console.log(`[getOddsDisplay] ${label} 提取结果:`, { 
        homeWin: homeWin, 
        draw: draw, 
        awayWin: awayWin,
        sectionKeys: Object.keys(section),
        oddsKeys: section.odds ? Object.keys(section.odds) : null
      });
      
      return {
        homeWin: this.formatOddsValue(homeWin),
        draw: this.formatOddsValue(draw),
        awayWin: this.formatOddsValue(awayWin),
        // 保存原始数值用于计算升降
        homeWinRaw: homeWin,
        drawRaw: draw,
        awayWinRaw: awayWin
      };
    };
    
    const initialOdds = getOddsDisplay(company.initial, '初盘');
    const currentOdds = getOddsDisplay(company.current, '即时');
    
    // 计算升降标识
    const getOddsTrend = (initial, current) => {
      if (initial == null || current == null || initial === '--' || current === '--') {
        return { arrow: '', colorClass: '' };
      }
      const initVal = parseFloat(initial);
      const currVal = parseFloat(current);
      if (isNaN(initVal) || isNaN(currVal)) {
        return { arrow: '', colorClass: '' };
      }
      if (currVal > initVal) {
        return { arrow: '↑', colorClass: 'odds-up' }; // 升 - 红色
      } else if (currVal < initVal) {
        return { arrow: '↓', colorClass: 'odds-down' }; // 降 - 绿色
      }
      return { arrow: '', colorClass: '' }; // 持平
    };
    
    // 计算各项赔率的升降趋势
    const homeWinTrend = getOddsTrend(initialOdds.homeWinRaw, currentOdds.homeWinRaw);
    const drawTrend = getOddsTrend(initialOdds.drawRaw, currentOdds.drawRaw);
    const awayWinTrend = getOddsTrend(initialOdds.awayWinRaw, currentOdds.awayWinRaw);
    
    // 将趋势信息添加到currentOdds
    const currentOddsWithTrend = {
      ...currentOdds,
      homeWinArrow: homeWinTrend.arrow,
      homeWinClass: homeWinTrend.colorClass,
      drawArrow: drawTrend.arrow,
      drawClass: drawTrend.colorClass,
      awayWinArrow: awayWinTrend.arrow,
      awayWinClass: awayWinTrend.colorClass
    };
    
    // 格式化表格数据
    const tableRows = [];
    const so = result.standardOdds;
    if (so) {
      tableRows.push({
        section: result.section || '',
        zoneLabel: (result.zone || '') + ' (' + (result.handicap || '') + ')',
        homeWin: so.H != null ? so.H.toFixed(2) : '--',
        draw: so.D != null ? so.D.toFixed(2) : '--',
        awayWin: so.A != null ? so.A.toFixed(2) : '--',
        initialOdds: initialOdds,
        currentOdds: currentOddsWithTrend,
      });
    }
    
    this.setData({ 
      reasonableOddsTable: tableRows,
      reasonableOddsSystem: system
    });
  },
  buildDrawSystemDisplay(raw) {
    if (!raw || !raw.draw_system_name) {
      return { hasData: false, data: {} };
    }
    const fmt = (v) => (v != null ? Number(v).toFixed(2) : '--');
    const fmtDur = (v) => (v != null ? Number(v).toFixed(1) : null);
    const fmtLine = (v) => (v != null && v !== '' ? Number(v).toFixed(2) : '--');
    const fmtTime = (v) => {
      if (!v) return '--';
      const s = String(v);
      return s.length > 16 ? s.substring(5, 16) : s;
    };

    // 水位级别 → CSS class 辅助
    const waterClass = (wl) => {
      if (!wl) return '';
      if (wl.includes('高')) return 'water-high';
      if (wl.includes('低')) return 'water-low';
      return 'water-mid';
    };
    const normalizeOuSnapshot = (snapshot, fallbackPhaseLabel) => {
      if (!snapshot || typeof snapshot !== 'object') {
        return null;
      }
      const phaseLabel = snapshot.phase_label || fallbackPhaseLabel || '--';
      const line = fmtLine(snapshot.line != null ? snapshot.line : raw.ou_line);
      const over = fmt(snapshot.over);
      const under = fmt(snapshot.under);
      const biasLabel = snapshot.bias_label || (
        snapshot.bias_side === 'over'
          ? '大球'
          : snapshot.bias_side === 'under'
            ? '小球'
            : '均水'
      );
      const waterLabel = snapshot.water_band_label || '';
      return {
        phaseLabel,
        line,
        over,
        under,
        biasLabel,
        waterLabel,
        waterText: waterLabel || (biasLabel === '均水' ? '均水' : '--'),
        summary: snapshot.summary || (waterLabel ? `${biasLabel}${waterLabel}` : biasLabel),
        reason: snapshot.reason || '',
        display: snapshot.display || `${phaseLabel} ${line}球 大${over} / 小${under}`
      };
    };

    const buildNodeDisplay = (node) => {
      if (!node) {
        return null;
      }
      const home94Num = node.home94 != null ? Number(node.home94) : null;
      const away94Num = node.away94 != null ? Number(node.away94) : null;
      const homeNum = node.home != null ? Number(node.home) : null;
      const awayNum = node.away != null ? Number(node.away) : null;
      let waterSide = '';
      if (node.waterLevel) {
        if (home94Num != null && away94Num != null && !Number.isNaN(home94Num) && !Number.isNaN(away94Num)) {
          waterSide = home94Num <= away94Num ? 'home' : 'away';
        } else if (homeNum != null && awayNum != null && !Number.isNaN(homeNum) && !Number.isNaN(awayNum)) {
          waterSide = homeNum <= awayNum ? 'home' : 'away';
        }
      }
      const waterSideLabel = waterSide === 'home'
        ? '主队'
        : waterSide === 'away'
          ? '客队'
          : '';
      const waterLevel = node.waterLevel || '';
      return {
        home: fmt(node.home),
        draw: fmt(node.draw),
        away: fmt(node.away),
        home94: fmt(node.home94),
        draw94: fmt(node.draw94),
        away94: fmt(node.away94),
        duration: node.duration != null ? fmtDur(node.duration) : null,
        time: node.time ? fmtTime(node.time) : null,
        waterLevel,
        waterClass: waterClass(waterLevel),
        homeWaterLevel: waterSide === 'home' ? waterLevel : '',
        homeWaterClass: waterSide === 'home' ? waterClass(waterLevel) : '',
        awayWaterLevel: waterSide === 'away' ? waterLevel : '',
        awayWaterClass: waterSide === 'away' ? waterClass(waterLevel) : '',
        waterSide,
        waterSideLabel,
        waterSideText: waterSideLabel ? `${waterSideLabel}低赔` : '',
        zoneName: node.zoneName || '',
        standardDraw: node.standardDraw != null ? fmt(node.standardDraw) : '--',
        ouSnapshot: node.ouSnapshot || null
      };
    };

    const openOuSnapshot = normalizeOuSnapshot(raw.ou_open_snapshot, '初指');
    const currentOuSnapshot = normalizeOuSnapshot(raw.ou_current_snapshot, '即时');
    const referenceOuSnapshot = raw.ou_reference_phase === 'current'
      ? (currentOuSnapshot || openOuSnapshot)
      : (openOuSnapshot || currentOuSnapshot);
    const drawSystemName = String(raw.draw_system_name || '')
      .replace('（估算）', '')
      .replace('(估算)', '');

    const longNode = raw.odds_source === 'long_node'
      ? buildNodeDisplay({
        home: raw.raw_home,
        draw: raw.raw_draw,
        away: raw.raw_away,
        home94: raw.home_94,
        draw94: raw.draw_94 != null ? raw.draw_94 : raw.actual_draw_94,
        away94: raw.away_94,
        duration: raw.long_node_duration_hours,
        time: raw.long_node_time,
        waterLevel: raw.water_level || '',
        zoneName: raw.zone_name || '',
        standardDraw: raw.standard_draw,
        ouSnapshot: openOuSnapshot
      })
      : null;

    let controlNode = null;
    if (raw.control_home != null) {
      controlNode = buildNodeDisplay({
        home: raw.control_home,
        draw: raw.control_draw,
        away: raw.control_away,
        home94: raw.control_home_94,
        draw94: raw.control_draw_94,
        away94: raw.control_away_94,
        time: raw.control_time,
        waterLevel: raw.control_water_level || '',
        zoneName: raw.control_zone_name || '',
        standardDraw: raw.control_standard_draw,
        ouSnapshot: openOuSnapshot
      });
    }

    let currentNode = null;
    if (raw.current_home != null) {
      currentNode = buildNodeDisplay({
        home: raw.current_home,
        draw: raw.current_draw,
        away: raw.current_away,
        home94: raw.current_home_94,
        draw94: raw.current_draw_94,
        away94: raw.current_away_94,
        time: raw.current_time,
        waterLevel: raw.current_water_level || '',
        zoneName: raw.current_zone_name || '',
        standardDraw: raw.current_standard_draw,
        ouSnapshot: currentOuSnapshot || openOuSnapshot
      });
    }

    const dev = raw.deviation;
    let deviationClass = '';
    let deviationText = '--';
    let conclusion = '';
    if (dev != null) {
      deviationText = (dev > 0 ? '+' : '') + dev.toFixed(3);
      if (raw.deviation_direction === '高') {
        deviationClass = 'deviation-high';
        conclusion = '实际平赔高于标准值';
      } else if (raw.deviation_direction === '低') {
        deviationClass = 'deviation-low';
        conclusion = '实际平赔低于标准值';
      } else {
        deviationClass = 'deviation-ok';
        conclusion = '实际平赔与标准值吻合';
      }
    }

    return {
      hasData: true,
      data: {
        drawSystemName,
        oddsSource: raw.odds_source === 'long_node' ? '长节点' : '初盘回退',
        longNode,
        controlNode,
        currentNode,
        favorite: raw.favorite_side === 'home' ? '主队' : '客队',
        ouLine: raw.ou_line != null ? String(raw.ou_line) : '--',
        ouOverOpen: raw.ou_over_open != null ? fmt(raw.ou_over_open) : '--',
        ouUnderOpen: raw.ou_under_open != null ? fmt(raw.ou_under_open) : '--',
        ouOverCurrent: raw.ou_over_current != null ? fmt(raw.ou_over_current) : '--',
        ouUnderCurrent: raw.ou_under_current != null ? fmt(raw.ou_under_current) : '--',
        ouReferencePhaseLabel: raw.ou_reference_phase_label || '',
        ouReferenceReason: raw.ou_reference_reason || '',
        ouDecisionMode: raw.ou_decision_mode || '',
        openOuSnapshot,
        currentOuSnapshot,
        referenceOuSnapshot,
        standardDraw: fmt(raw.standard_draw),
        actualDraw94: fmt(raw.actual_draw_94),
        deviation: dev,
        deviationClass,
        deviationText,
        conclusion,
        zoneName: raw.zone_name || ''
      }
    };
  },
  buildAsianHandicapDisplay(detail) {
    const ah = detail.asianHandicap;
    const companies = detail.companyAnalyses || [];
    const macau = companies.find(c => c.companyId == 80);

    let theoreticalHandicap = null;
    let theoreticalValue = null;
    if (macau && macau.homeTierLevel && macau.awayTierLevel) {
      const initOdds = (macau.initial && macau.initial.odds) || {};
      const openH = initOdds.home || 0;
      const openD = initOdds.draw || 0;
      const openA = initOdds.away || 0;
      const result = oddsLookup.lookupOdds(
        macau.homeTierLevel, macau.awayTierLevel,
        openH, openD, openA
      );
      if (result && result.success) {
        theoreticalHandicap = result.handicap || null;
        theoreticalValue = result.handicapValue != null ? result.handicapValue : null;
      }
    }

    if (!ah && theoreticalHandicap === null) {
      this.setData({ asianHandicapRows: [] });
      return;
    }

    const getMatchClass = (ahLine, theoVal) => {
      if (ahLine == null || theoVal == null) return '';
      const diff = Math.abs(ahLine - theoVal);
      if (diff < 0.01) return 'ah-match';
      if (diff <= 0.25) return 'ah-close';
      return 'ah-diff';
    };

    const rows = [];
    if (theoreticalHandicap !== null) {
      rows.push({
        label: '理论盘口',
        text: theoreticalHandicap,
        value: theoreticalValue != null ? String(theoreticalValue) : '--',
        homeOdds: '--',
        awayOdds: '--',
        matchClass: 'ah-theory'
      });
    }
    if (ah && ah.initial && ah.initial.handicapLine != null) {
      rows.push({
        label: '澳门初盘',
        text: ah.initial.handicapText || '--',
        value: String(ah.initial.handicapLine),
        homeOdds: ah.initial.homeOdds != null ? String(ah.initial.homeOdds) : '--',
        awayOdds: ah.initial.awayOdds != null ? String(ah.initial.awayOdds) : '--',
        matchClass: getMatchClass(ah.initial.handicapLine, theoreticalValue)
      });
    }
    if (ah && ah.current && ah.current.handicapLine != null) {
      rows.push({
        label: '澳门即时',
        text: ah.current.handicapText || '--',
        value: String(ah.current.handicapLine),
        homeOdds: ah.current.homeOdds != null ? String(ah.current.homeOdds) : '--',
        awayOdds: ah.current.awayOdds != null ? String(ah.current.awayOdds) : '--',
        matchClass: getMatchClass(ah.current.handicapLine, theoreticalValue)
      });
    }

    this.setData({ asianHandicapRows: rows });
  },
  setupCompanies(companies, preserveSelection = false) {
    console.log('[setupCompanies] 开始设置公司列表，公司数量:', companies ? companies.length : 0);
    if (!companies || companies.length === 0) {
      console.warn('[setupCompanies] 公司列表为空，清空相关数据');
      this.setData({
        companyOptions: [],
        selectedCompany: null,
        selectedCompanyIndex: -1,
        oddsRows: []
      });
      return;
    }
    const options = companies.map((c) => c.companyName || `\u516C\u53F8 ${c.companyId || ""}`);
    let targetIndex = 0;
    if (preserveSelection && this.data.selectedCompanyIndex >= 0 && this.data.selectedCompanyIndex < companies.length) {
      targetIndex = this.data.selectedCompanyIndex;
    }
    const initialCompany = companies[targetIndex] || companies[0] || null;
    const decorated = this.decorateCompany(initialCompany);
    console.log('[setupCompanies] 初始公司:', initialCompany ? initialCompany.companyName : 'null', '装饰后:', decorated ? '成功' : '失败');
    this.setData({
      companyOptions: options,
      selectedCompany: decorated,
      selectedCompanyIndex: initialCompany ? targetIndex : -1
    });
    console.log('[setupCompanies] 数据已设置，selectedCompany:', this.data.selectedCompany ? '存在' : 'null');
    this.refreshOddsTable(initialCompany);
    // 重新计算合理开盘区间，传入原始公司对象（确保有完整的initial和current数据）
    if (this.data.matchDetail) {
      this.calculateReasonableOdds(this.data.matchDetail, initialCompany);
    }
  },
  refreshOddsTable(company) {
    console.log('[refreshOddsTable] 刷新赔率表格，公司:', company ? company.companyName : 'null');
    if (!company) {
      console.warn('[refreshOddsTable] 公司为空，清空表格');
      this.setData({ oddsRows: [] });
      return;
    }
    const buildRow = (label, payload) => {
      const homeTier = (payload == null ? void 0 : payload.homeTierLevel) || company.homeTierLevel;
      const awayTier = (payload == null ? void 0 : payload.awayTierLevel) || company.awayTierLevel;
      const homeStrengthValue = (payload != null && payload.homeStrength != null) ? payload.homeStrength : 
                                 ((payload != null && payload.homePowerLevel != null) ? payload.homePowerLevel : company.homePowerLevel);
      const awayStrengthValue = (payload != null && payload.awayStrength != null) ? payload.awayStrength : 
                                ((payload != null && payload.awayPowerLevel != null) ? payload.awayPowerLevel : company.awayPowerLevel);
      const isInitial = label === "\u521D\u76D8";
      return {
        label,
        homeStrength: this.formatPowerValue(homeStrengthValue, homeTier, isInitial),
        homeRange: (payload == null ? void 0 : payload.homeRange) || "--",
        homeRangeClass: util.getRuleColorClass(payload == null ? void 0 : payload.homeRuleValue),
        homePressure: this.formatRuleValue(payload == null ? void 0 : payload.homeRuleValue),
        drawRange: (payload == null ? void 0 : payload.drawRange) || "--",
        drawRangeClass: util.getRuleColorClass(payload == null ? void 0 : payload.drawRuleValue),
        awayStrength: this.formatPowerValue(awayStrengthValue, awayTier, isInitial),
        awayRange: (payload == null ? void 0 : payload.awayRange) || "--",
        awayRangeClass: util.getRuleColorClass(payload == null ? void 0 : payload.awayRuleValue),
        awayPressure: this.formatRuleValue(payload == null ? void 0 : payload.awayRuleValue),
        ruleDiff: (payload == null ? void 0 : payload.ruleDiff) != null ? payload.ruleDiff.toFixed(1) : "--",
        recommendation: (payload == null ? void 0 : payload.recommendedOutcome) || "--"
      };
    };
    const rows = [];
    if (company.initial) {
      rows.push(buildRow("\u521D\u76D8", company.initial));
    }
    if (company.current) {
      rows.push(buildRow("\u5373\u65F6", company.current));
    }
    console.log('[refreshOddsTable] 生成的表格行数:', rows.length, 'rows:', rows);
    this.setData({ oddsRows: rows });
  },
  formatRuleValue(value) {
    if (value == null || Number.isNaN(value)) {
      return "--";
    }
    return value.toFixed(2);
  },
  updatePoissonModal(prediction) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _i;
    const payload = (prediction == null ? void 0 : prediction.prediction) || prediction || {};
    const expected = payload.expected_goals || {};
    const methodLabel = payload.method || (prediction == null ? void 0 : prediction.method) || "Poisson";
    const totalGoals = payload.total_goals_probs || payload.total_goals_probabilities || {};
    const scoreSource = payload.score_probabilities || payload.score_probs || payload.probabilities || [];
    const scoreTable = scoreSource.slice(0, 10).map((item) => {
      var _a2, _b2, _c2;
      return {
        score: item.score || item.label || item.score_label || "--",
        probability: (_c2 = (_b2 = (_a2 = item.probability) != null ? _a2 : item.value) != null ? _b2 : item.prob) != null ? _c2 : 0,
        odds: item.odds || item.odds_value || "--"
      };
    });
    const ouList = [];
    if (totalGoals.le3 != null) {
      ouList.push({ label: "\u22643\u7403", value: `${Math.round(totalGoals.le3)}%` });
    }
    if (totalGoals.gt3 != null) {
      ouList.push({ label: ">3\u7403", value: `${Math.round(totalGoals.gt3)}%` });
    }
    this.setData({
      poissonModalData: {
        expectedHome: (_a = expected.home) != null ? _a : "--",
        expectedAway: (_b = expected.away) != null ? _b : "--",
        expectedTotal: (_c = expected.total) != null ? _c : "--",
        homeProb: ((_e = (_d = payload.home_win_prob) == null ? void 0 : _d.toFixed) == null ? void 0 : _e.call(_d, 1)) ? `${payload.home_win_prob.toFixed(1)}%` : payload.home_win_prob ? `${Math.round(payload.home_win_prob)}%` : "--",
        drawProb: ((_g = (_f = payload.draw_prob) == null ? void 0 : _f.toFixed) == null ? void 0 : _g.call(_f, 1)) ? `${payload.draw_prob.toFixed(1)}%` : payload.draw_prob ? `${Math.round(payload.draw_prob)}%` : "--",
        awayProb: ((_i = (_h = payload.away_win_prob) == null ? void 0 : _h.toFixed) == null ? void 0 : _i.call(_h, 1)) ? `${payload.away_win_prob.toFixed(1)}%` : payload.away_win_prob ? `${Math.round(payload.away_win_prob)}%` : "--",
        method: methodLabel,
        ouList,
        scoreTable
      }
    });
  },
  openPoissonModal() {
    if (!this.data.poissonLoaded) {
      this.onLoadPoissonTap();
      return;
    }
    this.setData({ poissonModalVisible: true });
  },
  closePoissonModal() {
    this.setData({ poissonModalVisible: false });
  },
  stopPropagation() {
    return false;
  },
  onCompanyChange(e) {
    const index = Number(e.detail.value);
    const companies = this.data.matchDetail.companyAnalyses || [];
    const selected = companies[index] || null;
    const decorated = this.decorateCompany(selected);
    
    // 确保decorated包含所有原始数据（decorateCompany使用Object.assign，应该已经包含了）
    console.log('[onCompanyChange] 切换公司:', selected && selected.companyName, 'decorated包含initial:', !!(decorated && decorated.initial), 'decorated包含current:', !!(decorated && decorated.current));
    
    this.setData({
      selectedCompanyIndex: index,
      selectedCompany: decorated
    });
    this.refreshOddsTable(selected);
    // 重新计算合理开盘区间，传入新的公司对象（使用原始selected，因为decorated可能没有完整数据）
    if (this.data.matchDetail) {
      // 使用selected而不是decorated，确保有完整的initial和current数据
      this.calculateReasonableOdds(this.data.matchDetail, selected);
    }
  },
  getRecommendationText(detail) {
    if (!detail.fundamentalAnalysis || !detail.fundamentalAnalysis.recommendedOutcome) {
      return "";
    }
    return util.translateRecommendation(detail.fundamentalAnalysis.recommendedOutcome) || "";
  },
  buildFundamentalItems(detail) {
    const analysis = detail.fundamentalAnalysis || {};
    const definitions = [
      { key: "homeWin", label: "主胜", topLevelKey: "homeOddsSuggestions" },
      { key: "draw", label: "平局", topLevelKey: "drawOddsSuggestions" },
      { key: "awayWin", label: "客胜", topLevelKey: "awayOddsSuggestions" }
    ];
    const items = [];
    definitions.forEach((def) => {
      const entry = analysis[def.key];
      if (entry) {
        const score = entry.score != null ? entry.score : "--";
        const scoreText = typeof score === "number" ? score.toFixed(1) : score;
        const rawConfidence = entry.confidenceLevel || "未知";
        const confidence = rawConfidence.replace(/^信心/, "");
        // 获取合理开盘区间 - 优先从entry.oddsSuggestions获取，如果没有则从顶层获取
        // oddsSuggestions是字符串数组，如["实开盘高水", "实开盘中高水"]等
        let oddsRange = "--";
        let oddsSuggestions = entry.oddsSuggestions;
        // 如果entry中没有，尝试从顶层获取
        if ((!oddsSuggestions || !Array.isArray(oddsSuggestions) || oddsSuggestions.length === 0) && def.topLevelKey) {
          oddsSuggestions = analysis[def.topLevelKey];
        }
        // 平局不显示合理开盘区间
        if (def.key !== "draw" && oddsSuggestions && Array.isArray(oddsSuggestions) && oddsSuggestions.length > 0) {
          // oddsSuggestions是字符串数组，保存原始数组用于展开显示
          oddsRange = oddsSuggestions;
        } else {
          oddsRange = null;
        }
        items.push({
          label: def.label,
          score: scoreText,
          confidence,
          oddsRange: oddsRange, // 保存为数组，用于展开显示
          oddsRangeText: oddsRange && oddsRange.length > 0 ? oddsRange.join("、") : null // 用于折叠时显示前几个
        });
      }
    });
    return items;
  },
  buildPoissonSummary(prediction) {
    const payload = (prediction == null ? void 0 : prediction.prediction) || prediction || {};
    return {
      home: this.formatPercent(payload.home_win_prob),
      draw: this.formatPercent(payload.draw_prob),
      away: this.formatPercent(payload.away_win_prob)
    };
  },
  async loadPoissonPrediction() {
    const matchId = this.data.matchId || (this.data.matchDetail && this.data.matchDetail.matchId);
    if (!matchId) {
      console.error("\u65e0\u6cd5\u52a0\u8f7d\u6cca\u677e\u9884\u6d4b\uff1a\u7f3a\u5c11\u6bd4\u8d5bID");
      return;
    }
    if (this.data.poissonLoaded || this.data.poissonLoading) {
      return;
    }
    try {
      this.setData({
        poissonLoading: true,
        poissonError: null
      });
      const response = await fetchPoissonPrediction(matchId);
      if (response && response.success && response.data) {
        const prediction = response.data;
        this.setData({
          poissonPrediction: prediction,
          poissonLoaded: true,
          poissonLoading: false,
          poissonSummary: this.buildPoissonSummary(prediction)
        });
        this.updatePoissonModal(prediction);
      } else {
        throw new Error((response == null ? void 0 : response.error) || "\u52a0\u8f7d\u6cca\u677e\u9884\u6d4b\u5931\u8d25");
      }
    } catch (error) {
      console.error("\u52a0\u8f7d\u6cca\u677e\u9884\u6d4b\u5931\u8d25:", error);
      this.setData({
        poissonLoading: false,
        poissonError: (error == null ? void 0 : error.message) || "\u52a0\u8f7d\u6cca\u677e\u9884\u6d4b\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5"
      });
      util.showToast("\u52a0\u8f7d\u9884\u6d4b\u5931\u8d25", "none");
    }
  },
  onLoadPoissonTap() {
    this.loadPoissonPrediction();
  },
  onPoissonSectionVisible(e) {
    const ratio = e && e.detail && typeof e.detail.intersectionRatio === "number" ? e.detail.intersectionRatio : 0;
    if (ratio > 0 && !this.data.poissonLoaded && !this.data.poissonLoading) {
      this.loadPoissonPrediction();
    }
  },
  onRefresh() {
    Promise.all([this.loadMatchDetail(), this.loadMatchAlerts()]);
  },
  async loadMoreCompanies() {
    const { loadingMore, pagination, matchId, matchDetail } = this.data;
    if (loadingMore || !pagination.hasMore) {
      return;
    }
    this.setData({ loadingMore: true });
    const nextPage = pagination.page + 1;
    try {
      const response = await fetchMatchDetailPage(matchId, nextPage, pagination.pageSize || 20);
      if (response && response.success && response.data) {
        const pageData = response.data;
        const normalizedPageData = this.normalizeMatchDetail(pageData);
        const mergedCompanies = this.mergeCompanies([
          ...(matchDetail.companyAnalyses || []),
          ...(normalizedPageData.companyAnalyses || [])
        ]);
        const nextPagination = this.normalizePagination(pageData.pagination || { page: nextPage, page_size: pagination.pageSize });
        const updatedDetail = Object.assign({}, matchDetail, { companyAnalyses: mergedCompanies });
        this.setData({
          matchDetail: updatedDetail,
          companies: mergedCompanies,
          pagination: nextPagination,
          loadingMore: false
        });
        this.setupCompanies(mergedCompanies, true);
        if (mergedCompanies.length) {
          const currentIndex = this.data.selectedCompanyIndex >= 0 ? this.data.selectedCompanyIndex : 0;
          this.calculateReasonableOdds(updatedDetail, mergedCompanies[currentIndex]);
        }
        if (!nextPagination.hasMore) {
          util.showToast("\u5df2\u52a0\u8f7d\u5168\u90e8\u516c\u53f8", "success");
        }
      } else {
        util.showToast("\u52a0\u8f7d\u66f4\u591a\u5931\u8d25", "none");
        this.setData({ loadingMore: false });
      }
    } catch (err) {
      console.error("加载更多公司失败:", err);
      util.showToast("\u52a0\u8f7d\u66f4\u591a\u5931\u8d25", "none");
      this.setData({ loadingMore: false });
    }
  },
  onShareAppMessage() {
    const { homeTeam, awayTeam } = this.data.matchDetail;
    const title = homeTeam && awayTeam ? `${homeTeam} VS ${awayTeam}` : "\u6BD4\u8D5B\u8BE6\u60C5";
    return util.getShareConfig(title, `/pages/match-detail/match-detail?matchId=${this.data.matchId}`);
  },
  onShareTimeline() {
    const { homeTeam, awayTeam } = this.data.matchDetail;
    const title = homeTeam && awayTeam ? `${homeTeam} VS ${awayTeam}` : "\u6BD4\u8D5B\u8BE6\u60C5";
    return {
      title,
      query: `matchId=${this.data.matchId}`,
      imageUrl: ""
    };
  },
  getTeamShort(teamName) {
    if (!teamName) return "??";
    if (/[\u4e00-\u9fa5]/.test(teamName)) {
      return teamName.substring(0, 2);
    }
    const words = teamName.split(" ");
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return teamName.substring(0, 2).toUpperCase();
  },
  getPoissonValue(target, prediction) {
    const payload = (prediction == null ? void 0 : prediction.prediction) || prediction;
    if (!payload || !payload.expected_goals) return "--";
    const score = payload.expected_goals[target];
    if (typeof score === "number") {
      return score.toFixed(1);
    }
    return score != null ? score : "--";
  },
  getTotalGoalsProbability(label, prediction) {
    const payload = (prediction == null ? void 0 : prediction.prediction) || prediction;
    if (!payload) return "--";
    const stats = payload.total_goals_probs || payload.total_goals_probabilities || {};
    const value = stats[label];
    if (typeof value === "number") {
      return `${Math.round(value)}%`;
    }
    return value ? `${value}%` : "--";
  },
  formatPercent(value) {
    if (value == null) return "--";
    const num = typeof value === "number" ? value : parseFloat(value);
    if (Number.isNaN(num)) return "--";
    const pct = num > 1 ? num : num * 100;
    if (!Number.isFinite(pct)) {
      return "--";
    }
    return pct >= 10 ? `${pct.toFixed(0)}%` : `${pct.toFixed(1)}%`;
  },
  getOddsValue(sectionKey, outcomeKey) {
    const company = this.data.selectedCompany || {};
    const section = company[sectionKey];
    if (!section) {
      return "--";
    }
    const oddsValue = this.extractOddsValue(section, outcomeKey);
    return this.formatOddsValue(oddsValue);
  },
  getOddsRange(sectionKey, rangeKey) {
    const company = this.data.selectedCompany || {};
    const section = company[sectionKey];
    if (section && section[rangeKey] != null && section[rangeKey] !== "") {
      return section[rangeKey];
    }
    return "--";
  },
  getRangeClass(sectionKey, ruleKey) {
    const company = this.data.selectedCompany || {};
    const section = company[sectionKey] || {};
    return util.getRuleColorClass(section[ruleKey]);
  },
  decorateCompany(company) {
    if (!company) {
      return null;
    }
    // 公司级别的实力显示使用初盘逻辑（显示分值）
    return Object.assign({}, company, {
      displayHomeStrength: this.formatPowerValue(company.homePowerLevel, company.homeTierLevel, true),
      displayAwayStrength: this.formatPowerValue(company.awayPowerLevel, company.awayTierLevel, true)
    });
  },
  extractOddsValue(section, key) {
    if (section.odds && section.odds[key] != null) {
      return section.odds[key];
    }
    if (section[key] != null) {
      return section[key];
    }
    const namedKey = `${key}Odds`;
    if (section[namedKey] != null) {
      return section[namedKey];
    }
    return null;
  },
  formatOddsValue(value) {
    if (value == null || value === "") {
      return "--";
    }
    const num = typeof value === "number" ? value : parseFloat(value);
    if (Number.isNaN(num)) {
      return value;
    }
    return num % 1 === 0 ? num.toFixed(0) : num.toFixed(2);
  },
  toggleOddsRange(e) {
    const index = e.currentTarget.dataset.index;
    const expanded = this.data.expandedOddsRanges || {};
    expanded[index] = !expanded[index];
    this.setData({
      expandedOddsRanges: expanded
    });
  },
  toggleModule(e) {
    const module = e.currentTarget.dataset.module;
    const collapsedModules = this.data.collapsedModules || {};
    collapsedModules[module] = !collapsedModules[module];
    this.setData({
      collapsedModules
    });
  },
  formatPowerValue(power, tier, isInitial = true) {
    // 初盘显示广义实力分值，即时盘显示实力的描述
    if (isInitial) {
      // 初盘：显示分值
      if (power != null && !Number.isNaN(power)) {
        return parseFloat(power).toFixed(1);
      }
      return "--";
    } else {
      // 即时盘：显示描述（tier）
      return tier || "--";
    }
  },
  
  // ========== 泊松数据提取方法 ==========
  
  /**
   * 从API返回数据中提取泊松预测数据（兼容多种字段名）
   */
  extractPoissonData(detail) {
    if (!detail) return null;
    
    // 尝试多种可能的字段名
    const possibleKeys = [
      'poissonPrediction',
      'poisson_prediction',
      'poisson',
      'poissonData',
      'poisson_data',
      'prediction',
      'poissonAnalysis',
      'poisson_analysis'
    ];
    
    for (const key of possibleKeys) {
      if (detail[key] && typeof detail[key] === 'object') {
        console.log('[extractPoissonData] 找到泊松数据字段:', key);
        return detail[key];
      }
    }
    
    // 检查是否泊松数据直接在顶层
    if (detail.home_win_prob != null || detail.homeWinProb != null) {
      console.log('[extractPoissonData] 泊松数据在顶层');
      return detail;
    }
    
    return null;
  },
  
  /**
   * 验证泊松数据是否有效
   */
  validatePoissonData(data) {
    if (!data) return false;
    
    // 检查prediction嵌套结构
    const payload = data.prediction || data;
    
    // 检查是否有关键字段
    const hasProbs = (
      payload.home_win_prob != null ||
      payload.homeWinProb != null ||
      payload.draw_prob != null ||
      payload.drawProb != null ||
      payload.away_win_prob != null ||
      payload.awayWinProb != null
    );
    
    const hasExpectedGoals = (
      payload.expected_goals != null ||
      payload.expectedGoals != null
    );
    
    const hasScoreProbs = (
      payload.score_probabilities != null ||
      payload.score_probs != null ||
      payload.scoreProbabilities != null
    );
    
    return hasProbs || hasExpectedGoals || hasScoreProbs;
  },
  
  // ========== 公司态度汇总相关方法 ==========
  
  /**
   * 构建公司态度汇总展示数据
   */
  buildCompanySummaryDisplay(summary, totalCount) {
    if (!summary) {
      return null;
    }
    const toNumber = (value) => {
      const num = Number(value);
      return Number.isFinite(num) ? num : 0;
    };
    
    const buildTimePointData = (timePoint) => {
      if (!timePoint) return null;
      
      const total = toNumber(
        this.pickFirstValue([timePoint.total, timePoint.total_companies, totalCount], 0)
      );
      const homeData = this.pickFirstValue([timePoint.home, timePoint.home_win, timePoint.homeWin], {});
      const drawData = this.pickFirstValue([timePoint.draw, timePoint.draw_win, timePoint.drawWin], {});
      const awayData = this.pickFirstValue([timePoint.away, timePoint.away_win, timePoint.awayWin], {});
      const homePct = toNumber(this.pickFirstValue([homeData.percentage, homeData.percent], 0));
      const drawPct = toNumber(this.pickFirstValue([drawData.percentage, drawData.percent], 0));
      const awayPct = toNumber(this.pickFirstValue([awayData.percentage, awayData.percent], 0));
      
      return {
        total,
        home: {
          label: '主胜',
          count: toNumber(this.pickFirstValue([homeData.count, homeData.total], 0)),
          percentage: homePct,
          companies: this.pickFirstValue([homeData.companies, homeData.company_list], []),
          color: '#FF6B35', // 主题橙色
          barWidth: Math.min(homePct, 100)
        },
        draw: {
          label: '平局',
          count: toNumber(this.pickFirstValue([drawData.count, drawData.total], 0)),
          percentage: drawPct,
          companies: this.pickFirstValue([drawData.companies, drawData.company_list], []),
          color: '#F7B731', // 警告黄色
          barWidth: Math.min(drawPct, 100)
        },
        away: {
          label: '客胜',
          count: toNumber(this.pickFirstValue([awayData.count, awayData.total], 0)),
          percentage: awayPct,
          companies: this.pickFirstValue([awayData.companies, awayData.company_list], []),
          color: '#004E89', // 深蓝色
          barWidth: Math.min(awayPct, 100)
        }
      };
    };
    
    return {
      current: buildTimePointData(this.pickFirstValue([summary.current, summary.current_summary], null)),
      initial: buildTimePointData(this.pickFirstValue([summary.initial, summary.initial_summary], null)),
      totalCount: toNumber(this.pickFirstValue([
        totalCount,
        summary.total_companies,
        summary.totalCompanies,
        summary.total,
        summary.current && (summary.current.total || summary.current.total_companies)
      ], 0))
    };
  },
  
  /**
   * 切换态度视图模式（初盘/即时）
   */
  onAttitudeViewModeChange(e) {
    const mode = e.currentTarget.dataset.mode;
    if (mode && (mode === 'current' || mode === 'initial')) {
      this.setData({ attitudeViewMode: mode });
    }
  },
  
  /**
   * 展开/折叠态度详情（显示公司列表）
   */
  toggleAttitudeDetail(e) {
    const key = e.currentTarget.dataset.key; // 'home', 'draw', 'away'
    if (!key) return;
    
    const expanded = this.data.expandedAttitude || {};
    expanded[key] = !expanded[key];
    this.setData({ expandedAttitude: expanded });
  },
  
  /**
   * 获取当前态度视图数据
   */
  getCurrentAttitudeData() {
    const { companySummary, attitudeViewMode } = this.data;
    if (!companySummary) return null;
    return attitudeViewMode === 'initial' ? companySummary.initial : companySummary.current;
  }
});
