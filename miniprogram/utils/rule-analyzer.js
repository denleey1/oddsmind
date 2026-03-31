"use strict";
const CONFIG = {
  COMPANY_IDS: {
    MACAO: 80,
    // 澳门
    HK: 432,
    // 马会
    WILLIAM: 115
    // 威廉希尔
  },
  // 区间核心关键词（用于模糊匹配）
  RANGE_KEYWORDS: {
    "\u97EC\u5149": /韬光/,
    "\u9AD8\u5F00": /高开/,
    "\u5B9E\u5F00": /实开/,
    "\u4F4E\u5F00": /低开/,
    "\u8D85\u5B9E": /超实/
  },
  // 信心区间划分（重要！）
  CONFIDENCE_RANGES: {
    MEDIUM_LOW: 4.4,
    // 中庸下限
    MEDIUM_HIGH: 5.6
    // 中庸上限（>5.6为中上）
  }
};
function getCompanyAnalysis(companyAnalyses, preferredIds) {
  if (!companyAnalyses || !Array.isArray(companyAnalyses)) {
    return null;
  }
  for (const id of preferredIds) {
    const analysis = companyAnalyses.find((c) => c.companyId == id);
    if (analysis) return analysis;
  }
  return null;
}
function getConfidenceLevel(confidence) {
  if (confidence == null) return "\u672A\u77E5";
  if (confidence < CONFIG.CONFIDENCE_RANGES.MEDIUM_LOW) {
    return "\u4F4E";
  } else if (confidence >= CONFIG.CONFIDENCE_RANGES.MEDIUM_LOW && confidence <= CONFIG.CONFIDENCE_RANGES.MEDIUM_HIGH) {
    return "\u4E2D\u5EB8";
  } else {
    return "\u4E2D\u4E0A";
  }
}
function isInMediumRange(confidence) {
  return confidence >= CONFIG.CONFIDENCE_RANGES.MEDIUM_LOW && confidence <= CONFIG.CONFIDENCE_RANGES.MEDIUM_HIGH;
}
function isAboveMedium(confidence) {
  return confidence > CONFIG.CONFIDENCE_RANGES.MEDIUM_HIGH;
}
function isBelowMedium(confidence) {
  return confidence < CONFIG.CONFIDENCE_RANGES.MEDIUM_LOW;
}
function isStrongTier(tier, isAway, teamConf) {
  if (!tier) return false;
  if (tier.includes("\u5F3A")) {
    if (tier === "\u4E2D\u5F3A" && isAway && !isAboveMedium(teamConf)) {
      return false;
    }
    return true;
  }
  return false;
}
function extractRangeCore(rangeText) {
  if (!rangeText) return null;
  for (const [key, regex] of Object.entries(CONFIG.RANGE_KEYWORDS)) {
    if (regex.test(rangeText)) {
      return key;
    }
  }
  return null;
}
function isValidRange(range) {
  return extractRangeCore(range) !== null;
}
function rangeMatches(range1, zone) {
  const core1 = extractRangeCore(range1);
  if (!core1) return false;
  if (Array.isArray(zone)) {
    return zone.some((z) => {
      const core22 = extractRangeCore(z);
      return core22 && core1 === core22;
    });
  }
  const core2 = extractRangeCore(zone);
  return core2 && core1 === core2;
}
function analyzeMatch(apiData) {
  var _a, _b, _c, _d, _e, _f, _g, _h, _i, _j, _k, _l, _m, _n, _o, _p, _q, _r, _s, _t, _u, _v, _w, _x;
  try {
    console.log("[\u89C4\u5219\u5206\u6790] \u5F00\u59CB\u5206\u6790\u6BD4\u8D5B");
    console.log("[\u89C4\u5219\u5206\u6790] \u516C\u53F8\u603B\u6570:", ((_a = apiData.companyAnalyses) == null ? void 0 : _a.length) || 0);
    if (apiData.companyAnalyses && apiData.companyAnalyses.length > 0) {
      console.log("[\u89C4\u5219\u5206\u6790] \u524D3\u5BB6\u516C\u53F8ID:", apiData.companyAnalyses.slice(0, 3).map((c) => ({
        id: c.companyId,
        type: typeof c.companyId,
        name: c.companyName
      })));
    }
    const macaoAnalysis = getCompanyAnalysis(
      apiData.companyAnalyses,
      [CONFIG.COMPANY_IDS.MACAO]
    );
    console.log("[\u89C4\u5219\u5206\u6790] \u6FB3\u95E8\u516C\u53F8\u67E5\u627E\u7ED3\u679C:", macaoAnalysis ? "\u627E\u5230" : "\u672A\u627E\u5230");
    if (macaoAnalysis) {
      const homeRangeCore = extractRangeCore((_b = macaoAnalysis.initial) == null ? void 0 : _b.homeRange);
      const awayRangeCore = extractRangeCore((_c = macaoAnalysis.initial) == null ? void 0 : _c.awayRange);
      console.log("[\u89C4\u5219\u5206\u6790] \u6FB3\u95E8\u6570\u636E:", {
        companyId: macaoAnalysis.companyId,
        homePowerLevel: macaoAnalysis.homePowerLevel,
        awayPowerLevel: macaoAnalysis.awayPowerLevel,
        initialHomeRange: (_d = macaoAnalysis.initial) == null ? void 0 : _d.homeRange,
        initialHomeRangeCore: homeRangeCore,
        initialAwayRange: (_e = macaoAnalysis.initial) == null ? void 0 : _e.awayRange,
        initialAwayRangeCore: awayRangeCore
      });
    }
    const hkAnalysis = getCompanyAnalysis(
      apiData.companyAnalyses,
      [CONFIG.COMPANY_IDS.HK, CONFIG.COMPANY_IDS.MACAO, CONFIG.COMPANY_IDS.WILLIAM]
    );
    if (!macaoAnalysis) {
      const availableIds = ((_f = apiData.companyAnalyses) == null ? void 0 : _f.map((c) => c.companyId).join(", ")) || "\u65E0";
      throw new Error(`\u7F3A\u5C11\u6FB3\u95E8\u516C\u53F8\u6570\u636E (ID: 80)\u3002\u53EF\u7528\u516C\u53F8ID: ${availableIds}`);
    }
    const genHome = macaoAnalysis.homePowerLevel;
    const genAway = macaoAnalysis.awayPowerLevel;
    const tierHome = macaoAnalysis.homeTierLevel;
    const tierAway = macaoAnalysis.awayTierLevel;
    const teamConfHome = (_h = (_g = apiData.fundamentalAnalysis) == null ? void 0 : _g.homeWin) == null ? void 0 : _h.score;
    const teamConfAway = (_j = (_i = apiData.fundamentalAnalysis) == null ? void 0 : _i.awayWin) == null ? void 0 : _j.score;
    if (genHome == null || genAway == null || teamConfHome == null || teamConfAway == null) {
      throw new Error("\u7F3A\u5C11\u5FC5\u8981\u7684\u5E7F\u4E49\u5B9E\u529B\u6216\u57FA\u672C\u9762\u6570\u636E");
    }
    const betSide = genHome + 1.5 > genAway ? "\u4E3B" : "\u5BA2";
    const confLet = betSide === "\u4E3B" ? (_l = (_k = apiData.fundamentalAnalysis) == null ? void 0 : _k.homeWin) == null ? void 0 : _l.score : (_n = (_m = apiData.fundamentalAnalysis) == null ? void 0 : _m.awayWin) == null ? void 0 : _n.score;
    const confDraw = (_p = (_o = apiData.fundamentalAnalysis) == null ? void 0 : _o.draw) == null ? void 0 : _p.score;
    const confTake = betSide === "\u4E3B" ? (_r = (_q = apiData.fundamentalAnalysis) == null ? void 0 : _q.awayWin) == null ? void 0 : _r.score : (_t = (_s = apiData.fundamentalAnalysis) == null ? void 0 : _s.homeWin) == null ? void 0 : _t.score;
    const macaoOne = betSide === "\u4E3B" ? (_u = macaoAnalysis.initial) == null ? void 0 : _u.homeRange : (_v = macaoAnalysis.initial) == null ? void 0 : _v.awayRange;
    const hkThree = betSide === "\u4E3B" ? (_w = hkAnalysis == null ? void 0 : hkAnalysis.initial) == null ? void 0 : _w.awayRange : (_x = hkAnalysis == null ? void 0 : hkAnalysis.initial) == null ? void 0 : _x.homeRange;
    if (!isValidRange(macaoOne) || !isValidRange(hkThree)) {
      throw new Error(`\u8D54\u7387\u533A\u95F4\u65E0\u6548: macaoOne=${macaoOne}, hkThree=${hkThree}`);
    }
    const directions = [
      { name: "\u8BA9", value: confLet },
      { name: "\u5E73", value: confDraw },
      { name: "\u53D7", value: confTake }
    ].sort((a, b) => b.value - a.value);
    const pullDirection = directions[0].name;
    const firstDispersion = pullDirection === "\u8BA9" ? directions[1].name : directions[0].name;
    const secondDispersion = pullDirection === "\u8BA9" ? directions[2].name : directions[1].name;
    const homeStrong = isStrongTier(tierHome, false, teamConfHome);
    const awayStrong = isStrongTier(tierAway, true, teamConfAway);
    let openType;
    if (homeStrong && awayStrong) {
      openType = "\u5F3A\u5F3A";
    } else if (homeStrong || awayStrong) {
      openType = "\u5F3A\u5F31";
    } else {
      openType = "\u5F31\u5F31";
    }
    let ruleStrong = { code: null, zone: null, text: "" };
    if (isAboveMedium(confLet)) {
      ruleStrong = {
        code: "C",
        zone: "\u8D85\u5B9E",
        text: `\u5F3A\u961F${confLet.toFixed(1)}(\u4E2D\u4E0A)\uFF0C\u5FC5\u987B\u8D85\u5B9E\u76D8\uFF1B\u521D\u8D54\u4F4E\u5F00\u4E3A\u8BA4\u53EF\uFF0C\u53D8\u76D8\u964D\u81F3\u8D85\u5B9E=\u6B63\u8DEF`
      };
    } else {
      if (isAboveMedium(confTake)) {
        ruleStrong = {
          code: "A",
          zone: "\u5B9E\u5F00",
          text: `\u5F31\u961F${confTake.toFixed(1)}(\u597D)\uFF0C\u5F3A\u961F${confLet.toFixed(1)}(\u4E2D\u5EB8\u53CA\u4EE5\u4E0B)\u53EF\u5F00\u5B9E\u76D8\uFF0C\u53D8\u76D8\u53EF\u7565\u5FAE\u5347\u6C34`
        };
      } else {
        ruleStrong = {
          code: "B",
          zone: ["\u5B9E\u5F00", "\u4F4E\u5F00"],
          text: `\u5F31\u961F${confTake.toFixed(1)}(\u4E00\u822C)\uFF0C\u5F3A\u961F${confLet.toFixed(1)}(\u4E2D\u5EB8\u53CA\u4EE5\u4E0B)\u9700\u5B9E\u76D8/\u4F4E\u5F00+\u5E73\u5206\u6563\uFF0C\u53D8\u76D8\u4EE5\u964D\u8D54\u4E3A\u4E3B`
        };
      }
    }
    let ruleWeak = { code: null, zone: null, text: "" };
    if (!isAboveMedium(confTake)) {
      ruleWeak = {
        code: "D",
        zone: "\u5B9E\u5F00",
        text: `\u5F31\u961F${confTake.toFixed(1)}(\u4E2D\u5EB8\u4EE5\u4E0B)\uFF0C\u5B9E\u5F00\u76D8\u9644\u8FD1\uFF1B\u540E\u671F\u5347\u81F3\u9AD8\u6C34+\u5BF9\u624B\u533A\u95F4\u964D\u4F4E=\u51B7\u95E8\u6B63\u8DEF`
      };
    } else {
      if (confLet < confTake) {
        ruleWeak = {
          code: "F",
          zone: "\u8D85\u5B9E",
          text: `\u5F31\u961F${confTake.toFixed(1)}\u5F3A\u4E8E\u5F3A\u961F${confLet.toFixed(1)}\uFF0C\u8D85\u5B9E\u76D8\uFF1B\u521D\u8D54\u5B9E\u5F00/\u4F4E\u5F00\u8BA4\u53EF\u2192\u53D8\u76D8\u8D85\u5B9E\uFF1B\u5E73\u8D54\u5728\u5E73\u4E2D\u5EB8/\u5E73\u5B9E\u4F4E/\u4F4E\u5F00\u5E73=\u7A33`
        };
      } else {
        ruleWeak = {
          code: "E",
          zone: "\u5B9E\u5F00",
          text: `\u5F31\u961F${confTake.toFixed(1)}\u4E0E\u5F3A\u961F${confLet.toFixed(1)}\u76F8\u5F53\uFF0C\u5B9E\u5F00\u76D8+\u5E73\u5206\u6563\uFF1B\u540E\u671F\u65E0\u8BBA\u5347/\u964D\u6C34\u90FD\u662F\u51B7\u95E8\u6B63\u8DEF`
        };
      }
    }
    const ruleMatch = {
      one: rangeMatches(macaoOne, ruleStrong.zone) ? "\u5339\u914D" : ruleStrong.zone ? "\u4E0D\u5339\u914D" : "\u672A\u8BBE",
      three: rangeMatches(hkThree, ruleWeak.zone) ? "\u5339\u914D" : ruleWeak.zone ? "\u4E0D\u5339\u914D" : "\u672A\u8BBE"
    };
    const recommendation = {
      outcome: betSide,
      // 推荐投注方向
      confidence: ruleMatch.one === "\u5339\u914D" ? "high" : "medium",
      // 信心等级
      rule: ruleStrong.code,
      // 应用的规则
      zone: Array.isArray(ruleStrong.zone) ? ruleStrong.zone.join("/") : ruleStrong.zone,
      // 需要的区间（格式化为字符串）
      zoneArray: ruleStrong.zone,
      // 原始zone（可能是数组）
      reason: ruleStrong.text
      // 推荐理由
    };
    const quickPrediction = generateQuickPrediction(confLet, confTake, macaoOne, hkThree, betSide);
    return {
      success: true,
      data: {
        // 输出字段
        betSide,
        pullDirection,
        firstDispersion,
        secondDispersion,
        openType,
        ruleStrong,
        ruleWeak,
        ruleMatch,
        recommendation,
        quickPrediction,
        // 调试信息
        debug: {
          genHome,
          genAway,
          tierHome,
          tierAway,
          teamConfHome,
          teamConfAway,
          confLet,
          confLetLevel: getConfidenceLevel(confLet),
          confDraw,
          confDrawLevel: getConfidenceLevel(confDraw),
          confTake,
          confTakeLevel: getConfidenceLevel(confTake),
          macaoOne,
          macaoOneCore: extractRangeCore(macaoOne),
          hkThree,
          hkThreeCore: extractRangeCore(hkThree),
          ruleStrongZone: Array.isArray(ruleStrong.zone) ? ruleStrong.zone.join("/") : ruleStrong.zone,
          ruleWeakZone: Array.isArray(ruleWeak.zone) ? ruleWeak.zone.join("/") : ruleWeak.zone,
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
function generateQuickPrediction(confLet, confTake, macaoOne, hkThree, betSide) {
  const result = {
    ruleNumber: 0,
    outcome: "\u4E0D\u9002\u5408\u5FEB\u901F\u5224\u65AD",
    level: "\u76D8\u53E3\u590D\u6742",
    betSide: betSide || "\u672A\u77E5"
  };
  if (confLet == null || confTake == null) {
    result.outcome = "\u6570\u636E\u4E0D\u8DB3";
    result.level = "\u65E0\u6CD5\u5224\u65AD";
    return result;
  }
  const letCore = extractRangeCore(macaoOne);
  const hkCore = extractRangeCore(hkThree);
  const matches = (core, target) => core === target;
  if (confTake < confLet && matches(hkCore, "\u8D85\u5B9E")) {
    result.ruleNumber = 1;
    result.outcome = "\u53D7\u65B9";
    result.level = "\u5FC5\u80DC";
  } else if (confLet < confTake && matches(letCore, "\u8D85\u5B9E")) {
    result.ruleNumber = 2;
    result.outcome = "\u8BA9\u65B9";
    result.level = "\u51E0\u4E4E\u5FC5\u80DC";
  } else if (confLet > confTake && matches(letCore, "\u8D85\u5B9E")) {
    result.ruleNumber = 3;
    result.outcome = "\u8BA9\u65B9";
    result.level = "\u6781\u5927\u6982\u7387\u80DC";
  } else if (confLet < confTake && matches(letCore, "\u97EC\u5149")) {
    result.ruleNumber = 4;
    result.outcome = "\u8BA9\u65B9";
    result.level = "\u6781\u5927\u6982\u7387\u80DC";
  } else if (confLet > confTake && matches(letCore, "\u97EC\u5149")) {
    result.ruleNumber = 5;
    result.outcome = "\u8B66\u60D5";
    result.level = "\u76D8\u53E3\u4E0D\u592A\u8BA4\u53EF\u8BA9\u65B9";
  } else if (confLet > confTake && matches(letCore, "\u5B9E\u5F00")) {
    result.ruleNumber = 6;
    result.outcome = "\u8BA9\u65B9";
    result.level = "\u5927\u6982\u7387\u4E0D\u8D25";
  }
  return result;
}
module.exports = {
  analyzeMatch,
  generateQuickPrediction,
  CONFIG
};
