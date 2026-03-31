// components/match-card/match-card.js
const util = require('../../utils/util.js')

const SIGNAL_CONFIG = {
  '\u91CD\u4ED3': {
    key: 'heavy',
    icon: '\ud83d\udd34',
    label: '\u91CD\u4ED3'
  },
  '\u5F3A\u70C8': {
    key: 'strong',
    icon: '\ud83d\udfe0',
    label: '\u5F3A\u70C8'
  },
  '\u53C2\u8003': {
    key: 'reference',
    icon: '\ud83d\udfe1',
    label: '\u53C2\u8003'
  }
}

const SIGNAL_LEVEL_ALIASES = {
  heavy: '\u91CD\u4ED3',
  heavy_bet: '\u91CD\u4ED3',
  heavybet: '\u91CD\u4ED3',
  strong: '\u5F3A\u70C8',
  strongly: '\u5F3A\u70C8',
  reference: '\u53C2\u8003',
  ref: '\u53C2\u8003'
}

Component({
  properties: {
    match: {
      type: Object,
      value: {},
      observer: function(newVal) {
        if (newVal) {
          this.processMatchData(newVal)
        }
      }
    },
    alertInfo: {
      type: Object,
      value: null,
      observer: function(newVal) {
        this.processAlertInfo(newVal)
      }
    }
  },

  data: {
    matchTime: '',
    statusText: '',
    statusColor: '',
    homeTeamShort: '',
    awayTeamShort: '',
    signalDisplay: {
      visible: false,
      key: '',
      icon: '',
      label: '',
      gradeSummary: '',
      crossConfirm: false,
      cardClass: ''
    },
    isAlertExpanded: false
  },

  methods: {
    /**
     * 处理比赛数据
     */
    processMatchData(match) {
      // 格式化比赛时间
      const matchTime = util.formatMatchTime(match.matchTime)
      
      // 获取状态文本和颜色
      const statusText = util.getMatchStatusText(match.matchStatus)
      const statusColor = util.getMatchStatusColor(match.matchStatus)

      // 获取球队简称（取前2个字符）
      const homeTeamShort = this.getTeamShort(match.homeTeam)
      const awayTeamShort = this.getTeamShort(match.awayTeam)

      this.setData({
        matchTime,
        statusText,
        statusColor,
        homeTeamShort,
        awayTeamShort
      })
    },

    normalizeSignalLevel(level) {
      const raw = String(level || '').trim()
      if (!raw) return ''
      if (SIGNAL_CONFIG[raw]) return raw
      const mapped = SIGNAL_LEVEL_ALIASES[raw.toLowerCase()]
      return mapped || raw
    },

    toBoolean(value) {
      if (typeof value === 'boolean') return value
      if (typeof value === 'number') return value === 1
      if (typeof value === 'string') {
        const normalized = value.trim().toLowerCase()
        return normalized === '1' || normalized === 'true' || normalized === 'yes'
      }
      return false
    },

    processAlertInfo(alertInfo) {
      this.setData({ isAlertExpanded: false })
      if (!alertInfo || typeof alertInfo !== 'object') {
        this.setData({
          signalDisplay: {
            visible: false,
            key: '',
            icon: '',
            label: '',
            gradeSummary: '',
            crossConfirm: false,
            cardClass: ''
          }
        })
        return
      }

      const level = this.normalizeSignalLevel(alertInfo.signalLevel || alertInfo.signal_level)
      if (!level || !SIGNAL_CONFIG[level]) {
        this.setData({
          signalDisplay: {
            visible: false,
            key: '',
            icon: '',
            label: '',
            gradeSummary: '',
            crossConfirm: false,
            cardClass: ''
          }
        })
        return
      }

      const config = SIGNAL_CONFIG[level]
      const crossConfirmRaw = alertInfo.crossConfirm != null ? alertInfo.crossConfirm : alertInfo.cross_confirm
      const gradeSummary = alertInfo.gradeSummary || alertInfo.grade_summary || ''

      this.setData({
        signalDisplay: {
          visible: true,
          key: config.key,
          icon: alertInfo.signalIcon || alertInfo.signal_icon || config.icon,
          label: config.label,
          gradeSummary,
          crossConfirm: this.toBoolean(crossConfirmRaw),
          cardClass: config.key === 'reference' ? 'match-card-reference' : ''
        }
      })
    },

    getPrimaryRule(alertInfo) {
      if (!alertInfo || !Array.isArray(alertInfo.rules) || !alertInfo.rules.length) {
        return null
      }
      return alertInfo.rules[0] || null
    },

    getQuickSuggestion(alertInfo) {
      const primary = this.getPrimaryRule(alertInfo)
      if (!primary) return '--'
      const target = primary.target || '--'
      const suggestion = primary.bet_suggestion || primary.betSuggestion || '--'
      return `${target} → ${suggestion}`
    },

    toggleAlertDetails() {
      if (!this.properties.alertInfo || !this.properties.alertInfo.ruleCount) {
        return
      }
      this.setData({ isAlertExpanded: !this.data.isAlertExpanded })
    },

    /**
     * 获取球队简称
     */
    getTeamShort(teamName) {
      if (!teamName) return '?'
      
      // 如果是中文，取前2个字符
      if (/[\u4e00-\u9fa5]/.test(teamName)) {
        return teamName.substring(0, 2)
      }
      
      // 如果是英文，取首字母
      const words = teamName.split(' ')
      if (words.length >= 2) {
        return (words[0][0] + words[1][0]).toUpperCase()
      }
      return teamName.substring(0, 2).toUpperCase()
    },

    /**
     * 点击事件
     */
    onTap() {
      this.triggerEvent('matchtap', { match: this.properties.match })
    }
  }
})


