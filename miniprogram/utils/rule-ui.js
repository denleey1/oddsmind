var __defProp = Object.defineProperty;
var __defProps = Object.defineProperties;
var __getOwnPropDescs = Object.getOwnPropertyDescriptors;
var __getOwnPropSymbols = Object.getOwnPropertySymbols;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __propIsEnum = Object.prototype.propertyIsEnumerable;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __spreadValues = (a, b) => {
  for (var prop in b || (b = {}))
    if (__hasOwnProp.call(b, prop))
      __defNormalProp(a, prop, b[prop]);
  if (__getOwnPropSymbols)
    for (var prop of __getOwnPropSymbols(b)) {
      if (__propIsEnum.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    }
  return a;
};
var __spreadProps = (a, b) => __defProps(a, __getOwnPropDescs(b));
const matchColorMap = {
  "\u5339\u914D": "#4ade80",
  "\u4E0D\u5339\u914D": "#ef4444",
  "\u672A\u8BBE": "#9ca3af"
};
const quickStyles = [
  {
    predicate: (qp) => ["\u4E0D\u9002\u5408\u5FEB\u901F\u5224\u65AD", "\u6570\u636E\u4E0D\u8DB3"].includes(qp.level || qp.outcome),
    icon: "\u{1F4CB}",
    color: "#9ca3af"
  },
  {
    predicate: (qp) => qp.outcome === "\u8B66\u60D5",
    icon: "\u26A0\uFE0F",
    color: "#f59e0b"
  },
  {
    predicate: (qp) => /必胜/.test(qp.level || ""),
    icon: "\u{1F525}",
    color: "#ef4444"
  },
  {
    predicate: (qp) => qp.level === "\u6781\u5927\u6982\u7387\u80DC",
    icon: "\u{1F4AA}",
    color: "#f97316"
  },
  {
    predicate: (qp) => qp.level === "\u5927\u6982\u7387\u4E0D\u8D25",
    icon: "\u{1F4CA}",
    color: "#3b82f6"
  }
];
function formatQuickPrediction(quick) {
  const defaultStyle = {
    icon: "\u{1F4CA}",
    color: "#3b82f6"
  };
  const style = quickStyles.find((s) => s.predicate(quick)) || defaultStyle;
  const textColor = style.color;
  const borderColor = style.color;
  const bgColor = `${style.color}1A`;
  return __spreadProps(__spreadValues({}, quick), {
    icon: style.icon,
    textColor,
    borderColor,
    bgColor
  });
}
function formatRuleBlock(title, rule, matchStatus, actualZone) {
  const zoneText = Array.isArray(rule.zone) ? rule.zone.join("/") : rule.zone || "--";
  return {
    title,
    status: matchStatus,
    statusColor: matchColorMap[matchStatus] || "#9ca3af",
    zoneText,
    actualZone: actualZone || "--",
    description: rule.text || "--"
  };
}
function formatDetails(debug = {}) {
  const safeNumber = (value, decimals = 2) => {
    if (value == null) return "--";
    return typeof value === "number" ? value.toFixed(decimals) : value;
  };
  return [
    { label: "\u5E7F\u4E49\u5B9E\u529B(\u4E3B)", value: safeNumber(debug.genHome) },
    { label: "\u5E7F\u4E49\u5B9E\u529B(\u5BA2)", value: safeNumber(debug.genAway) },
    { label: "\u5B9E\u529B\u7EA7(\u4E3B)", value: debug.tierHome || "--" },
    { label: "\u5B9E\u529B\u7EA7(\u5BA2)", value: debug.tierAway || "--" },
    { label: "\u57FA\u672C\u9762(\u4E3B)", value: safeNumber(debug.teamConfHome) },
    { label: "\u57FA\u672C\u9762(\u5BA2)", value: safeNumber(debug.teamConfAway) },
    { label: "\u8BA9\u65B9\u4FE1\u5FC3", value: `${safeNumber(debug.confLet)} (${debug.confLetLevel || "--"})` },
    { label: "\u5E73\u5C40\u4FE1\u5FC3", value: `${safeNumber(debug.confDraw)} (${debug.confDrawLevel || "--"})` },
    { label: "\u53D7\u65B9\u4FE1\u5FC3", value: `${safeNumber(debug.confTake)} (${debug.confTakeLevel || "--"})` },
    { label: "\u5F00\u76D8\u7C7B\u578B", value: debug.openType || "--" }
  ];
}
function buildRulePanel(analysisResult) {
  var _a, _b, _c, _d;
  if (!analysisResult || !analysisResult.success) {
    return {
      ready: false,
      error: (analysisResult == null ? void 0 : analysisResult.error) || "\u89C4\u5219\u5206\u6790\u4E0D\u53EF\u7528"
    };
  }
  const data = analysisResult.data || {};
  const quick = formatQuickPrediction(data.quickPrediction || {});
  return {
    ready: true,
    quick,
    strong: formatRuleBlock("\u8BA9\u65B9\u89C4\u5219", data.ruleStrong || {}, (_a = data.ruleMatch) == null ? void 0 : _a.one, (_b = data.debug) == null ? void 0 : _b.macaoOne),
    weak: formatRuleBlock("\u53D7\u65B9\u89C4\u5219", data.ruleWeak || {}, (_c = data.ruleMatch) == null ? void 0 : _c.three, (_d = data.debug) == null ? void 0 : _d.hkThree),
    recommendation: data.recommendation || {},
    details: formatDetails(data.debug || {})
  };
}
module.exports = {
  buildRulePanel
};
