// utils/alert-service.js
const { get } = require('./api.js')

function parseRuleFeatures(raw) {
  if (!raw) {
    return null
  }
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      return parsed && typeof parsed === 'object' ? parsed : null
    } catch (err) {
      return null
    }
  }
  return typeof raw === 'object' ? raw : null
}

function normalizeRuleItem(rule = {}, match = {}, category = '') {
  const history = rule.history || {}
  const accuracy = typeof rule.accuracy === 'number'
    ? rule.accuracy
    : (typeof history.accuracy === 'number' ? history.accuracy : null)
  const accuracyPct = rule.accuracy_pct
    || rule.accuracyPct
    || history.accuracy_pct
    || history.accuracyPct
    || (accuracy != null ? `${Math.round(accuracy * 100)}%` : '')
  const fallbackTarget = category === 'handicap_win'
    ? '让方必赢'
    : (category === 'handicap_not_lose' ? '让方不输' : (category === 'receiver_not_lose' ? '受让方不输' : ''))
  const features = parseRuleFeatures(rule.features || rule.rule_features || rule.ruleFeatures)
  return {
    match_id: match.match_id || match.matchId,
    match_time: match.match_time || match.matchTime,
    league_name: match.league_name || match.leagueName,
    is_big5: match.is_big5 || match.isBig5,
    big5_name: match.big5_name || match.big5Name,
    home_team: match.home_team || match.homeTeam,
    away_team: match.away_team || match.awayTeam,
    handicap_team: match.handicap_team || match.handicapTeam,
    receiver_team: match.receiver_team || match.receiverTeam,
    rule_id: rule.rule_id || rule.id || rule.ruleId,
    rule_name: rule.rule_name || rule.name || rule.ruleName,
    target: rule.target || rule.prediction || fallbackTarget,
    bet_suggestion: rule.bet_suggestion || rule.betSuggestion,
    accuracy: accuracy != null ? accuracy : null,
    accuracy_pct: accuracyPct,
    sample: rule.sample != null ? rule.sample : history.sample,
    features
  }
}

function flattenTodayAlerts(payload = {}) {
  const alerts = []
  if (Array.isArray(payload.alerts)) {
    payload.alerts.forEach((alert) => alerts.push(alert))
  }
  const sections = [
    { key: 'handicap_win', category: 'handicap_win' },
    { key: 'handicap_not_lose', category: 'handicap_not_lose' },
    { key: 'receiver_not_lose', category: 'receiver_not_lose' }
  ]
  sections.forEach((section) => {
    const matches = Array.isArray(payload[section.key]) ? payload[section.key] : []
    matches.forEach((match) => {
      const rules = Array.isArray(match.rules) ? match.rules : []
      if (!rules.length) {
        return
      }
      rules.forEach((rule) => {
        alerts.push(normalizeRuleItem(rule, match, section.category))
      })
    })
  })
  return alerts
}

function normalizeMatchAlertResponse(payload = {}) {
  const matchInfo = payload.match_info || payload.matchInfo || {}
  const rules = Array.isArray(payload.rules) ? payload.rules : (Array.isArray(payload.alerts) ? payload.alerts : [])
  const normalizedRules = rules.map((rule) => normalizeRuleItem(rule, matchInfo))
  const topLevelFeatures = parseRuleFeatures(payload.features || payload.rule_features || payload.ruleFeatures)
  const firstRuleFeatures = normalizedRules.find((rule) => rule && rule.features)?.features || null
  const firstRule = normalizedRules[0] || {}
  return {
    match_id: payload.match_id || payload.matchId || matchInfo.match_id || matchInfo.matchId,
    has_alert: payload.has_alert != null ? payload.has_alert : payload.hasAlert,
    home_team: matchInfo.home_team || matchInfo.homeTeam || payload.home_team || payload.homeTeam,
    away_team: matchInfo.away_team || matchInfo.awayTeam || payload.away_team || payload.awayTeam,
    is_big5: matchInfo.is_big5 || matchInfo.isBig5 || payload.is_big5 || payload.isBig5,
    big5_name: matchInfo.big5_name || matchInfo.big5Name || payload.big5_name || payload.big5Name,
    match_time: matchInfo.match_time || matchInfo.matchTime || payload.match_time || payload.matchTime,
    handicap_team: payload.handicap_team || payload.handicapTeam || matchInfo.handicap_team || matchInfo.handicapTeam || firstRule.handicap_team,
    receiver_team: payload.receiver_team || payload.receiverTeam || matchInfo.receiver_team || matchInfo.receiverTeam || firstRule.receiver_team,
    features: topLevelFeatures || firstRuleFeatures || {},
    alerts: normalizedRules,
    rules: normalizedRules
  }
}

function fetchAlerts(hours = 168, options = {}) {
  return get('/api/rule-alerts/today', {}, {
    needAuth: false,
    showLoading: false,
    cache: true,
    cacheTime: 30000,
    useCacheOnFail: true,
    ...options
  }).then((res) => {
    if (res && res.success) {
      const payload = res.data || res
      const alerts = flattenTodayAlerts(payload)
      return Object.assign({}, res, {
        data: Object.assign({}, payload, { alerts })
      })
    }
    return res
  })
}

function fetchMatchAlerts(matchId, options = {}) {
  if (!matchId) {
    return Promise.resolve({ success: true, data: { alerts: [] } })
  }
  return get(`/api/rule-alerts/match/${matchId}`, {}, {
    needAuth: false,
    showLoading: false,
    cache: true,
    cacheTime: 20000,
    useCacheOnFail: true,
    ...options
  }).then((res) => {
    if (res && res.success) {
      const payload = res.data || res
      return Object.assign({}, res, { data: normalizeMatchAlertResponse(payload) })
    }
    return res
  })
}

module.exports = {
  fetchAlerts,
  fetchMatchAlerts
}
