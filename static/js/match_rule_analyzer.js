"use strict";

function _typeof(o) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (o) { return typeof o; } : function (o) { return o && "function" == typeof Symbol && o.constructor === Symbol && o !== Symbol.prototype ? "symbol" : typeof o; }, _typeof(o); }
function _slicedToArray(r, e) { return _arrayWithHoles(r) || _iterableToArrayLimit(r, e) || _unsupportedIterableToArray(r, e) || _nonIterableRest(); }
function _nonIterableRest() { throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); }
function _iterableToArrayLimit(r, l) { var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"]; if (null != t) { var e, n, i, u, a = [], f = !0, o = !1; try { if (i = (t = t.call(r)).next, 0 === l) { if (Object(t) !== t) return; f = !1; } else for (; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0); } catch (r) { o = !0, n = r; } finally { try { if (!f && null != t.return && (u = t.return(), Object(u) !== u)) return; } finally { if (o) throw n; } } return a; } }
function _arrayWithHoles(r) { if (Array.isArray(r)) return r; }
function _createForOfIteratorHelper(r, e) { var t = "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"]; if (!t) { if (Array.isArray(r) || (t = _unsupportedIterableToArray(r)) || e && r && "number" == typeof r.length) { t && (r = t); var _n = 0, F = function F() {}; return { s: F, n: function n() { return _n >= r.length ? { done: !0 } : { done: !1, value: r[_n++] }; }, e: function e(r) { throw r; }, f: F }; } throw new TypeError("Invalid attempt to iterate non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); } var o, a = !0, u = !1; return { s: function s() { t = t.call(r); }, n: function n() { var r = t.next(); return a = r.done, r; }, e: function e(r) { u = !0, o = r; }, f: function f() { try { a || null == t.return || t.return(); } finally { if (u) throw o; } } }; }
function _unsupportedIterableToArray(r, a) { if (r) { if ("string" == typeof r) return _arrayLikeToArray(r, a); var t = {}.toString.call(r).slice(8, -1); return "Object" === t && r.constructor && (t = r.constructor.name), "Map" === t || "Set" === t ? Array.from(r) : "Arguments" === t || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(t) ? _arrayLikeToArray(r, a) : void 0; } }
function _arrayLikeToArray(r, a) { (null == a || a > r.length) && (a = r.length); for (var e = 0, n = Array(a); e < a; e++) n[e] = r[e]; return n; }
/**
 * 比赛规则分析模块
 * 基于澳门、马会赔率和基本面分析，判断强队打出概率
 * 不侵入现有代码，可独立调用
 */

(function (window) {
  'use strict';

  // ========== 常量配置 ==========
  var CONFIG = {
    COMPANY_IDS: {
      MACAO: 80,
      // 澳门
      HK: 432,
      // 马会
      WILLIAM: 115 // 威廉希尔
    },
    // 区间核心关键词（用于模糊匹配）
    RANGE_KEYWORDS: {
      '韬光': /韬光/,
      '高开': /高开/,
      '实开': /实开/,
      '低开': /低开/,
      '超实': /超实/
    },
    // 信心区间划分（重要！）
    CONFIDENCE_RANGES: {
      MEDIUM_LOW: 4.4,
      // 中庸下限
      MEDIUM_HIGH: 5.6 // 中庸上限（>5.6为中上）
    }
  };

  // ========== 工具函数 ==========

  /**
   * 获取公司分析数据（带降级逻辑）
   */
  function getCompanyAnalysis(companyAnalyses, preferredIds) {
    if (!companyAnalyses || !Array.isArray(companyAnalyses)) {
      return null;
    }
    var _iterator = _createForOfIteratorHelper(preferredIds),
      _step;
    try {
      var _loop = function _loop() {
          var id = _step.value;
          // 使用宽松比较（==）来匹配数字和字符串
          var analysis = companyAnalyses.find(function (c) {
            return c.companyId == id;
          });
          if (analysis) return {
            v: analysis
          };
        },
        _ret;
      for (_iterator.s(); !(_step = _iterator.n()).done;) {
        _ret = _loop();
        if (_ret) return _ret.v;
      }
    } catch (err) {
      _iterator.e(err);
    } finally {
      _iterator.f();
    }
    return null;
  }

  /**
   * 获取信心等级
   * @param {number} confidence - 信心值
   * @returns {string} - 信心等级：'低'、'中庸'、'中上'、'高'
   */
  function getConfidenceLevel(confidence) {
    if (confidence == null) return '未知';
    if (confidence < CONFIG.CONFIDENCE_RANGES.MEDIUM_LOW) {
      return '低';
    } else if (confidence >= CONFIG.CONFIDENCE_RANGES.MEDIUM_LOW && confidence <= CONFIG.CONFIDENCE_RANGES.MEDIUM_HIGH) {
      return '中庸';
    } else {
      return '中上';
    }
  }

  /**
   * 判断信心是否在中庸区间
   */
  function isInMediumRange(confidence) {
    return confidence >= CONFIG.CONFIDENCE_RANGES.MEDIUM_LOW && confidence <= CONFIG.CONFIDENCE_RANGES.MEDIUM_HIGH;
  }

  /**
   * 判断信心是否超过中庸上限（中上及以上）
   */
  function isAboveMedium(confidence) {
    return confidence > CONFIG.CONFIDENCE_RANGES.MEDIUM_HIGH;
  }

  /**
   * 判断信心是否低于中庸下限
   */
  function isBelowMedium(confidence) {
    return confidence < CONFIG.CONFIDENCE_RANGES.MEDIUM_LOW;
  }

  /**
   * 判断球队是否为"强"队
   */
  function isStrongTier(tier, isAway, teamConf) {
    if (!tier) return false;
    if (tier.includes('强')) {
      // 特殊规则：客场中强且队伍信心在中庸以下时按弱处理
      if (tier === '中强' && isAway && !isAboveMedium(teamConf)) {
        return false;
      }
      return true;
    }
    return false;
  }

  /**
   * 提取区间核心类型（去除"盘"和水位信息）
   */
  function extractRangeCore(rangeText) {
    if (!rangeText) return null;
    for (var _i = 0, _Object$entries = Object.entries(CONFIG.RANGE_KEYWORDS); _i < _Object$entries.length; _i++) {
      var _Object$entries$_i = _slicedToArray(_Object$entries[_i], 2),
        key = _Object$entries$_i[0],
        regex = _Object$entries$_i[1];
      if (regex.test(rangeText)) {
        return key;
      }
    }
    return null;
  }

  /**
   * 验证赔率区间是否有效
   */
  function isValidRange(range) {
    return extractRangeCore(range) !== null;
  }

  /**
   * 比较两个区间是否匹配（核心类型匹配即可）
   * 支持zone为字符串或数组
   */
  function rangeMatches(range1, zone) {
    var core1 = extractRangeCore(range1);
    if (!core1) return false;

    // 如果zone是数组，检查core1是否在数组中
    if (Array.isArray(zone)) {
      return zone.some(function (z) {
        var core2 = extractRangeCore(z);
        return core2 && core1 === core2;
      });
    }

    // 如果zone是字符串，直接比较
    var core2 = extractRangeCore(zone);
    return core2 && core1 === core2;
  }

  // ========== 主分析函数 ==========

  /**
   * 分析比赛 - 强队打出逻辑
   * @param {Object} apiData - API返回的 response.data
   * @returns {Object} 分析结果
   */
  function analyzeMatch(apiData) {
    try {
      var _apiData$companyAnaly, _apiData$fundamentalA, _apiData$fundamentalA2, _apiData$fundamentalA3, _apiData$fundamentalA4, _apiData$fundamentalA5, _apiData$fundamentalA6, _apiData$fundamentalA7, _apiData$fundamentalA8, _apiData$fundamentalA9, _apiData$fundamentalA0, _apiData$fundamentalA1, _apiData$fundamentalA10, _apiData$fundamentalA11, _apiData$fundamentalA12, _macaoAnalysis$initia5, _macaoAnalysis$initia6, _hkAnalysis$initial, _hkAnalysis$initial2;
      // ========== 调试：查看实际数据 ==========
      console.log('[规则分析] 开始分析比赛');
      console.log('[规则分析] 公司总数:', ((_apiData$companyAnaly = apiData.companyAnalyses) === null || _apiData$companyAnaly === void 0 ? void 0 : _apiData$companyAnaly.length) || 0);
      if (apiData.companyAnalyses && apiData.companyAnalyses.length > 0) {
        console.log('[规则分析] 前3家公司ID:', apiData.companyAnalyses.slice(0, 3).map(function (c) {
          return {
            id: c.companyId,
            type: _typeof(c.companyId),
            name: c.companyName
          };
        }));
      }

      // ========== 第一步：提取公司数据 ==========
      var macaoAnalysis = getCompanyAnalysis(apiData.companyAnalyses, [CONFIG.COMPANY_IDS.MACAO]);
      console.log('[规则分析] 澳门公司查找结果:', macaoAnalysis ? '找到' : '未找到');
      if (macaoAnalysis) {
        var _macaoAnalysis$initia, _macaoAnalysis$initia2, _macaoAnalysis$initia3, _macaoAnalysis$initia4;
        var homeRangeCore = extractRangeCore((_macaoAnalysis$initia = macaoAnalysis.initial) === null || _macaoAnalysis$initia === void 0 ? void 0 : _macaoAnalysis$initia.homeRange);
        var awayRangeCore = extractRangeCore((_macaoAnalysis$initia2 = macaoAnalysis.initial) === null || _macaoAnalysis$initia2 === void 0 ? void 0 : _macaoAnalysis$initia2.awayRange);
        console.log('[规则分析] 澳门数据:', {
          companyId: macaoAnalysis.companyId,
          homePowerLevel: macaoAnalysis.homePowerLevel,
          awayPowerLevel: macaoAnalysis.awayPowerLevel,
          initialHomeRange: (_macaoAnalysis$initia3 = macaoAnalysis.initial) === null || _macaoAnalysis$initia3 === void 0 ? void 0 : _macaoAnalysis$initia3.homeRange,
          initialHomeRangeCore: homeRangeCore,
          initialAwayRange: (_macaoAnalysis$initia4 = macaoAnalysis.initial) === null || _macaoAnalysis$initia4 === void 0 ? void 0 : _macaoAnalysis$initia4.awayRange,
          initialAwayRangeCore: awayRangeCore
        });
      }
      var hkAnalysis = getCompanyAnalysis(apiData.companyAnalyses, [CONFIG.COMPANY_IDS.HK, CONFIG.COMPANY_IDS.MACAO, CONFIG.COMPANY_IDS.WILLIAM]);
      if (!macaoAnalysis) {
        var _apiData$companyAnaly2;
        // 列出所有可用的公司ID
        var availableIds = ((_apiData$companyAnaly2 = apiData.companyAnalyses) === null || _apiData$companyAnaly2 === void 0 ? void 0 : _apiData$companyAnaly2.map(function (c) {
          return c.companyId;
        }).join(', ')) || '无';
        throw new Error("\u7F3A\u5C11\u6FB3\u95E8\u516C\u53F8\u6570\u636E (ID: 80)\u3002\u53EF\u7528\u516C\u53F8ID: ".concat(availableIds));
      }

      // ========== 第二步：提取基础数据 ==========
      var genHome = macaoAnalysis.homePowerLevel;
      var genAway = macaoAnalysis.awayPowerLevel;
      var tierHome = macaoAnalysis.homeTierLevel;
      var tierAway = macaoAnalysis.awayTierLevel;
      var teamConfHome = (_apiData$fundamentalA = apiData.fundamentalAnalysis) === null || _apiData$fundamentalA === void 0 ? void 0 : (_apiData$fundamentalA2 = _apiData$fundamentalA.homeWin) === null || _apiData$fundamentalA2 === void 0 ? void 0 : _apiData$fundamentalA2.score;
      var teamConfAway = (_apiData$fundamentalA3 = apiData.fundamentalAnalysis) === null || _apiData$fundamentalA3 === void 0 ? void 0 : (_apiData$fundamentalA4 = _apiData$fundamentalA3.awayWin) === null || _apiData$fundamentalA4 === void 0 ? void 0 : _apiData$fundamentalA4.score;

      // 数据完整性检查
      if (genHome == null || genAway == null || teamConfHome == null || teamConfAway == null) {
        throw new Error('缺少必要的广义实力或基本面数据');
      }

      // ========== 第三步：确定让球方 ==========
      var betSide = genHome + 1.5 > genAway ? '主' : '客';

      // ========== 第四步：计算让/平/受信心 ==========
      var confLet = betSide === '主' ? (_apiData$fundamentalA5 = apiData.fundamentalAnalysis) === null || _apiData$fundamentalA5 === void 0 ? void 0 : (_apiData$fundamentalA6 = _apiData$fundamentalA5.homeWin) === null || _apiData$fundamentalA6 === void 0 ? void 0 : _apiData$fundamentalA6.score : (_apiData$fundamentalA7 = apiData.fundamentalAnalysis) === null || _apiData$fundamentalA7 === void 0 ? void 0 : (_apiData$fundamentalA8 = _apiData$fundamentalA7.awayWin) === null || _apiData$fundamentalA8 === void 0 ? void 0 : _apiData$fundamentalA8.score;
      var confDraw = (_apiData$fundamentalA9 = apiData.fundamentalAnalysis) === null || _apiData$fundamentalA9 === void 0 ? void 0 : (_apiData$fundamentalA0 = _apiData$fundamentalA9.draw) === null || _apiData$fundamentalA0 === void 0 ? void 0 : _apiData$fundamentalA0.score;
      var confTake = betSide === '主' ? (_apiData$fundamentalA1 = apiData.fundamentalAnalysis) === null || _apiData$fundamentalA1 === void 0 ? void 0 : (_apiData$fundamentalA10 = _apiData$fundamentalA1.awayWin) === null || _apiData$fundamentalA10 === void 0 ? void 0 : _apiData$fundamentalA10.score : (_apiData$fundamentalA11 = apiData.fundamentalAnalysis) === null || _apiData$fundamentalA11 === void 0 ? void 0 : (_apiData$fundamentalA12 = _apiData$fundamentalA11.homeWin) === null || _apiData$fundamentalA12 === void 0 ? void 0 : _apiData$fundamentalA12.score;

      // ========== 第五步：提取赔率区间 ==========
      // 澳门一赔区间（让方的初盘区间）
      var macaoOne = betSide === '主' ? (_macaoAnalysis$initia5 = macaoAnalysis.initial) === null || _macaoAnalysis$initia5 === void 0 ? void 0 : _macaoAnalysis$initia5.homeRange : (_macaoAnalysis$initia6 = macaoAnalysis.initial) === null || _macaoAnalysis$initia6 === void 0 ? void 0 : _macaoAnalysis$initia6.awayRange;

      // 马会三赔区间（受方的初盘区间）
      var hkThree = betSide === '主' ? hkAnalysis === null || hkAnalysis === void 0 ? void 0 : (_hkAnalysis$initial = hkAnalysis.initial) === null || _hkAnalysis$initial === void 0 ? void 0 : _hkAnalysis$initial.awayRange : hkAnalysis === null || hkAnalysis === void 0 ? void 0 : (_hkAnalysis$initial2 = hkAnalysis.initial) === null || _hkAnalysis$initial2 === void 0 ? void 0 : _hkAnalysis$initial2.homeRange;

      // 区间有效性验证
      if (!isValidRange(macaoOne) || !isValidRange(hkThree)) {
        throw new Error("\u8D54\u7387\u533A\u95F4\u65E0\u6548: macaoOne=".concat(macaoOne, ", hkThree=").concat(hkThree));
      }

      // ========== 第六步：计算拉力方向 ==========
      var directions = [{
        name: '让',
        value: confLet
      }, {
        name: '平',
        value: confDraw
      }, {
        name: '受',
        value: confTake
      }].sort(function (a, b) {
        return b.value - a.value;
      });
      var pullDirection = directions[0].name;
      var firstDispersion = pullDirection === '让' ? directions[1].name : directions[0].name;
      var secondDispersion = pullDirection === '让' ? directions[2].name : directions[1].name;

      // ========== 第七步：判断开盘类型 ==========
      var homeStrong = isStrongTier(tierHome, false, teamConfHome);
      var awayStrong = isStrongTier(tierAway, true, teamConfAway);
      var openType;
      if (homeStrong && awayStrong) {
        openType = '强强';
      } else if (homeStrong || awayStrong) {
        openType = '强弱';
      } else {
        openType = '弱弱';
      }

      // ========== 第八步：应用强队打出规则（核心）==========
      // 规则逻辑说明：
      // 1. 强队信心>5.6（中上）→ 必须超实盘（规则C）
      // 2. 强队信心≤5.6 且 弱队信心>5.6（好）→ 实盘，可略微升水（规则A）
      // 3. 强队信心≤5.6 且 弱队信心≤5.6（一般）→ 实盘/低开+平分散（规则B，低开也是看好能打出的）

      var ruleStrong = {
        code: null,
        zone: null,
        text: ''
      };
      if (isAboveMedium(confLet)) {
        // 规则C：强队信心>5.6（中上），无论弱队如何，必须超实盘
        ruleStrong = {
          code: 'C',
          zone: '超实',
          text: "\u5F3A\u961F".concat(confLet.toFixed(1), "(\u4E2D\u4E0A)\uFF0C\u5FC5\u987B\u8D85\u5B9E\u76D8\uFF1B\u521D\u8D54\u4F4E\u5F00\u4E3A\u8BA4\u53EF\uFF0C\u53D8\u76D8\u964D\u81F3\u8D85\u5B9E=\u6B63\u8DEF")
        };
      } else {
        // 强队信心≤5.6（中庸及以下）
        if (isAboveMedium(confTake)) {
          // 规则A：弱队信心好（>5.6），强队中庸及以下可开实盘
          ruleStrong = {
            code: 'A',
            zone: '实开',
            text: "\u5F31\u961F".concat(confTake.toFixed(1), "(\u597D)\uFF0C\u5F3A\u961F").concat(confLet.toFixed(1), "(\u4E2D\u5EB8\u53CA\u4EE5\u4E0B)\u53EF\u5F00\u5B9E\u76D8\uFF0C\u53D8\u76D8\u53EF\u7565\u5FAE\u5347\u6C34")
          };
        } else {
          // 规则B：弱队信心一般（≤5.6），强队中庸及以下需实盘中水以下+平分散
          // 注意：低开也是看好能打出的
          ruleStrong = {
            code: 'B',
            zone: ['实开', '低开'],
            text: "\u5F31\u961F".concat(confTake.toFixed(1), "(\u4E00\u822C)\uFF0C\u5F3A\u961F").concat(confLet.toFixed(1), "(\u4E2D\u5EB8\u53CA\u4EE5\u4E0B)\u9700\u5B9E\u76D8/\u4F4E\u5F00+\u5E73\u5206\u6563\uFF0C\u53D8\u76D8\u4EE5\u964D\u8D54\u4E3A\u4E3B")
          };
        }
      }

      // ========== 第九步：弱队打出规则（参考）==========
      // 弱队打出规则：
      // D. 弱队信心≤5.6（中庸以下）→ 实开盘，后期升高水+对手区间降=正路
      // E. 弱队信心>5.6 且 强队相当 → 实开盘+平分散，升/降都可
      // F. 弱队信心>5.6 且 强队更差 → 超实盘，配合平赔

      var ruleWeak = {
        code: null,
        zone: null,
        text: ''
      };
      if (!isAboveMedium(confTake)) {
        // 规则D：弱队信心≤5.6（中庸以下），无论强队如何，开实开盘
        ruleWeak = {
          code: 'D',
          zone: '实开',
          text: "\u5F31\u961F".concat(confTake.toFixed(1), "(\u4E2D\u5EB8\u4EE5\u4E0B)\uFF0C\u5B9E\u5F00\u76D8\u9644\u8FD1\uFF1B\u540E\u671F\u5347\u81F3\u9AD8\u6C34+\u5BF9\u624B\u533A\u95F4\u964D\u4F4E=\u51B7\u95E8\u6B63\u8DEF")
        };
      } else {
        // 弱队信心>5.6（中上）
        if (confLet < confTake) {
          // 规则F：强队状态更差（强队<弱队），必然超实盘
          ruleWeak = {
            code: 'F',
            zone: '超实',
            text: "\u5F31\u961F".concat(confTake.toFixed(1), "\u5F3A\u4E8E\u5F3A\u961F").concat(confLet.toFixed(1), "\uFF0C\u8D85\u5B9E\u76D8\uFF1B\u521D\u8D54\u5B9E\u5F00/\u4F4E\u5F00\u8BA4\u53EF\u2192\u53D8\u76D8\u8D85\u5B9E\uFF1B\u5E73\u8D54\u5728\u5E73\u4E2D\u5EB8/\u5E73\u5B9E\u4F4E/\u4F4E\u5F00\u5E73=\u7A33")
          };
        } else {
          // 规则E：强队状态相当（强队≥弱队），实开盘+平分散
          ruleWeak = {
            code: 'E',
            zone: '实开',
            text: "\u5F31\u961F".concat(confTake.toFixed(1), "\u4E0E\u5F3A\u961F").concat(confLet.toFixed(1), "\u76F8\u5F53\uFF0C\u5B9E\u5F00\u76D8+\u5E73\u5206\u6563\uFF1B\u540E\u671F\u65E0\u8BBA\u5347/\u964D\u6C34\u90FD\u662F\u51B7\u95E8\u6B63\u8DEF")
          };
        }
      }

      // ========== 第十步：区间匹配验证 ==========
      var ruleMatch = {
        one: rangeMatches(macaoOne, ruleStrong.zone) ? '匹配' : ruleStrong.zone ? '不匹配' : '未设',
        three: rangeMatches(hkThree, ruleWeak.zone) ? '匹配' : ruleWeak.zone ? '不匹配' : '未设'
      };

      // ========== 第十一步：生成推荐结果 ==========
      var recommendation = {
        outcome: betSide,
        // 推荐投注方向
        confidence: ruleMatch.one === '匹配' ? 'high' : 'medium',
        // 信心等级
        rule: ruleStrong.code,
        // 应用的规则
        zone: Array.isArray(ruleStrong.zone) ? ruleStrong.zone.join('/') : ruleStrong.zone,
        // 需要的区间（格式化为字符串）
        zoneArray: ruleStrong.zone,
        // 原始zone（可能是数组）
        reason: ruleStrong.text // 推荐理由
      };

      // ========== 返回完整结果 ==========
      return {
        success: true,
        data: {
          // 输出字段
          betSide: betSide,
          pullDirection: pullDirection,
          firstDispersion: firstDispersion,
          secondDispersion: secondDispersion,
          openType: openType,
          ruleStrong: ruleStrong,
          ruleWeak: ruleWeak,
          ruleMatch: ruleMatch,
          recommendation: recommendation,
          // 调试信息
          debug: {
            genHome: genHome,
            genAway: genAway,
            tierHome: tierHome,
            tierAway: tierAway,
            teamConfHome: teamConfHome,
            teamConfAway: teamConfAway,
            confLet: confLet,
            confLetLevel: getConfidenceLevel(confLet),
            confDraw: confDraw,
            confDrawLevel: getConfidenceLevel(confDraw),
            confTake: confTake,
            confTakeLevel: getConfidenceLevel(confTake),
            macaoOne: macaoOne,
            macaoOneCore: extractRangeCore(macaoOne),
            hkThree: hkThree,
            hkThreeCore: extractRangeCore(hkThree),
            ruleStrongZone: Array.isArray(ruleStrong.zone) ? ruleStrong.zone.join('/') : ruleStrong.zone,
            ruleWeakZone: Array.isArray(ruleWeak.zone) ? ruleWeak.zone.join('/') : ruleWeak.zone,
            confidenceRanges: CONFIG.CONFIDENCE_RANGES
          }
        }
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  // ========== 导出到全局 ==========
  window.MatchRuleAnalyzer = {
    analyzeMatch: analyzeMatch,
    CONFIG: CONFIG
  };
})(window);
