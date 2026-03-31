// utils/odds-lookup.js
// 标准欧赔查找工具 v2.0 — 按实力等级对战矩阵 + 返还率自动匹配

const oddsData = require('./standard_odds_v2_data.js');

function toCoarseTier(fineTier) {
  const mapping = oddsData.tier_mapping || {};
  if (mapping[fineTier]) return mapping[fineTier];
  if ((oddsData.strength_levels || []).includes(fineTier)) return fineTier;
  return fineTier;
}

function matchSystemByReturnRate(returnRate) {
  if (returnRate <= 90.5) return '89';
  if (returnRate <= 93.0) return '92';
  return '94';
}

function calcReturnRate(h, d, a) {
  if (h <= 0 || d <= 0 || a <= 0) return 89;
  return 1 / (1/h + 1/d + 1/a) * 100;
}

var COMPANY_SYSTEM_MAP = {
  80: '89',    // 澳门
  115: '92',   // 威廉希尔
  188: '94',   // Bet365
  281: '94',   // 平博 Pinnacle
  90: '92',    // 易胜博
  432: '89',   // 香港马会
  545: '89',   // 皇冠
};

function getSystemByCompany(companyName, companyId) {
  if (companyId && COMPANY_SYSTEM_MAP[companyId]) {
    return COMPANY_SYSTEM_MAP[companyId];
  }
  var name = (companyName || '').toLowerCase();
  if (name.indexOf('澳门') >= 0 || name.indexOf('macau') >= 0) return '89';
  if (name.indexOf('威廉') >= 0 || name.indexOf('william') >= 0) return '92';
  if (name.indexOf('bet365') >= 0) return '94';
  if (name.indexOf('平博') >= 0 || name.indexOf('pinnacle') >= 0) return '94';
  if (name.indexOf('易胜博') >= 0 || name.indexOf('easybets') >= 0) return '92';
  if (name.indexOf('立博') >= 0 || name.indexOf('ladbrokes') >= 0) return '92';
  if (name.indexOf('香港') >= 0 || name.indexOf('hkjc') >= 0) return '89';
  return '94';
}

/**
 * 查找标准赔率
 * @param {string} homeStrength - 主队实力等级
 * @param {string} awayStrength - 客队实力等级
 * @param {string|number} systemOrOpenH - 体系字符串('89','92','94') 或初盘主胜赔率
 * @param {number} [openD] - 初盘平局（仅当第3参数为赔率时使用）
 * @param {number} [openA] - 初盘客胜（仅当第3参数为赔率时使用）
 */
function lookupOdds(homeStrength, awayStrength, systemOrOpenH, openD, openA) {
  var system;
  if (typeof systemOrOpenH === 'string') {
    system = systemOrOpenH;
  } else {
    var returnRate = calcReturnRate(systemOrOpenH || 0, openD || 0, openA || 0);
    system = matchSystemByReturnRate(returnRate);
  }

  const homeTier = toCoarseTier(homeStrength);
  const awayTier = toCoarseTier(awayStrength);

  const section = ((oddsData.matrix || {})[homeTier] || {})[awayTier];
  if (!section) {
    return { success: false, error: '找不到 ' + homeTier + ' vs ' + awayTier + ' 的映射' };
  }

  const zoneInfo = (oddsData.zones || {})[section];
  if (!zoneInfo) {
    return { success: false, error: '区间 ' + section + ' 不存在' };
  }

  const zoneKey = zoneInfo.zone;
  const handicap = zoneInfo.handicap;
  const handicapValue = zoneInfo.value;
  const swap = zoneInfo.swap_odds;

  const oddsRows = (oddsData.odds || {})[zoneKey] || [];
  if (!oddsRows.length) {
    return { success: false, error: 'zone=' + zoneKey + ' 无赔率数据' };
  }

  var bestRow = null;

  if (typeof systemOrOpenH !== 'string' && systemOrOpenH > 0 && openD > 0 && openA > 0) {
    var bestDist = Infinity;
    oddsRows.forEach(function(row) {
      var triple = row[system];
      if (!triple || triple.length !== 3) return;
      var refH = triple[0], refD = triple[1], refA = triple[2];
      if (swap) { var tmp = refH; refH = refA; refA = tmp; }
      var dist = Math.abs(systemOrOpenH - refH) / Math.max(refH, 0.01)
               + Math.abs(openD - refD) / Math.max(refD, 0.01)
               + Math.abs(openA - refA) / Math.max(refA, 0.01);
      if (dist < bestDist) { bestDist = dist; bestRow = { H: refH, D: refD, A: refA }; }
    });
  } else {
    var firstTriple = oddsRows[0] && oddsRows[0][system];
    if (firstTriple && firstTriple.length === 3) {
      var h = firstTriple[0], d = firstTriple[1], a = firstTriple[2];
      if (swap) { var t = h; h = a; a = t; }
      bestRow = { H: h, D: d, A: a };
    }
  }

  if (!bestRow) {
    return { success: false, error: 'zone=' + zoneKey + ' 体系=' + system + ' 无可用赔率' };
  }

  return {
    success: true,
    handicap: handicap,
    handicapValue: handicapValue,
    system: system,
    standardOdds: bestRow,
    homeTier: homeTier,
    awayTier: awayTier,
    section: section,
    zone: zoneKey,
    swap: swap,
  };
}

module.exports = {
  lookupOdds,
  matchSystemByReturnRate,
  calcReturnRate,
  toCoarseTier,
  getSystemByCompany,
};
