// 标准欧赔查找模块 v2.0
// 按实力等级对战矩阵 + 实际返还率自动匹配89/92/94体系
(function() {
'use strict';

let _data = null;

function loadData() {
    if (_data) return _data;
    // 数据由页面内联或通过 fetch 加载
    if (window._standardOddsV2) {
        _data = window._standardOddsV2;
        return _data;
    }
    console.warn('标准赔率表 v2 未加载');
    return null;
}

function toCoarseTier(fineTier) {
    const data = loadData();
    if (!data) return fineTier;
    const mapping = data.tier_mapping || {};
    if (mapping[fineTier]) return mapping[fineTier];
    if ((data.strength_levels || []).includes(fineTier)) return fineTier;
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

/**
 * 查找标准赔率（v2.0）
 * 
 * @param {string} homeStrength - 主队实力等级（细分或粗）
 * @param {string} awayStrength - 客队实力等级
 * @param {number} openH - 初盘主胜赔率
 * @param {number} openD - 初盘平局赔率
 * @param {number} openA - 初盘客胜赔率
 * @returns {object} 查找结果
 */
function lookupOdds(homeStrength, awayStrength, openH, openD, openA) {
    const data = loadData();
    if (!data) {
        return { success: false, error: '标准赔率表未加载' };
    }

    // 1. 粗等级
    const homeTier = toCoarseTier(homeStrength);
    const awayTier = toCoarseTier(awayStrength);

    // 2. 对战矩阵
    const section = ((data.matrix || {})[homeTier] || {})[awayTier];
    if (!section) {
        return {
            success: false,
            error: `找不到 ${homeTier} vs ${awayTier} 的对战矩阵映射`,
        };
    }

    // 3. 区间标识 → zone + 让球 + swap
    const zoneInfo = (data.zones || {})[section];
    if (!zoneInfo) {
        return {
            success: false,
            error: `区间标识 ${section} 不在 zones 表中`,
        };
    }

    const zoneKey = zoneInfo.zone;
    const handicap = zoneInfo.handicap;
    const handicapValue = zoneInfo.value;
    const swap = zoneInfo.swap_odds;

    // 4. 计算返还率 → 匹配体系
    const returnRate = calcReturnRate(openH || 0, openD || 0, openA || 0);
    const system = matchSystemByReturnRate(returnRate);

    // 5. 取该zone的赔率行
    const oddsRows = (data.odds || {})[zoneKey] || [];
    if (!oddsRows.length) {
        return {
            success: false,
            error: `zone=${zoneKey} 无赔率数据`,
        };
    }

    // 6. 从多行中选最接近实际初盘的
    let bestRow = null;
    let bestDist = Infinity;

    oddsRows.forEach(row => {
        const triple = row[system];
        if (!triple || triple.length !== 3) return;

        let refH = triple[0], refD = triple[1], refA = triple[2];
        if (swap) { const tmp = refH; refH = refA; refA = tmp; }

        let dist = 0;
        if (openH > 0) dist += Math.abs(openH - refH) / Math.max(refH, 0.01);
        if (openD > 0) dist += Math.abs(openD - refD) / Math.max(refD, 0.01);
        if (openA > 0) dist += Math.abs(openA - refA) / Math.max(refA, 0.01);

        if (dist < bestDist) {
            bestDist = dist;
            bestRow = { H: refH, D: refD, A: refA };
        }
    });

    if (!bestRow) {
        return {
            success: false,
            error: `zone=${zoneKey} 体系=${system} 无可用赔率`,
        };
    }

    return {
        success: true,
        handicap: handicap,
        handicapValue: handicapValue,
        system: system,
        returnRate: Math.round(returnRate * 10) / 10,
        standardOdds: bestRow,
        homeTier: homeTier,
        awayTier: awayTier,
        section: section,
        zone: zoneKey,
        swap: swap,
    };
}

/**
 * 兼容旧接口：lookupOdds(homeStrength, awayStrength, system)
 * 新接口需要传初盘赔率，旧接口只传体系名，用默认赔率
 */
function lookupOddsLegacy(homeStrength, awayStrength, system) {
    return lookupOdds(homeStrength, awayStrength, 0, 0, 0);
}

// 暴露到全局
window.OddsLookup = {
    lookupOdds: lookupOdds,
    lookupOddsLegacy: lookupOddsLegacy,
    matchSystemByReturnRate: matchSystemByReturnRate,
    calcReturnRate: calcReturnRate,
    toCoarseTier: toCoarseTier,
};

console.log('OddsLookup v2.0 加载成功');

})();
