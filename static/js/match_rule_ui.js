"use strict";

/**
 * 比赛规则分析UI组件
 * 用于在页面上展示分析结果
 */

(function (window) {
  'use strict';

  /**
   * 渲染规则分析结果HTML
   * @param {Object} analysisResult - MatchRuleAnalyzer.analyzeMatch() 的返回结果
   * @returns {string} HTML字符串
   */
  function renderRuleAnalysisCard(analysisResult) {
    var _data$debug$genHome, _data$debug$genAway, _data$debug$teamConfH, _data$debug$teamConfA, _data$debug$confLet, _data$debug$confDraw, _data$debug$confTake;
    if (!analysisResult || !analysisResult.success) {
      return "\n                <div class=\"detail-card\" style=\"background: rgba(255, 152, 0, 0.1); border-left: 4px solid #FF9800;\">\n                    <h3 style=\"color: #FF9800; margin-bottom: 1rem;\">\u26A0\uFE0F \u89C4\u5219\u5206\u6790\u4E0D\u53EF\u7528</h3>\n                    <p style=\"color: #eee;\">\u539F\u56E0: ".concat((analysisResult === null || analysisResult === void 0 ? void 0 : analysisResult.error) || '数据不完整', "</p>\n                </div>\n            ");
    }
    var data = analysisResult.data;
    var rec = data.recommendation;

    // 格式化zone（支持数组）
    var formatZone = function formatZone(zone) {
      if (!zone) return '';
      return Array.isArray(zone) ? zone.join('/') : zone;
    };

    // 信心颜色映射
    var confColors = {
      'high': '#4ade80',
      'medium': '#fbbf24',
      'low': '#f87171'
    };
    var confTexts = {
      'high': '高',
      'medium': '中',
      'low': '低'
    };

    // 匹配状态颜色
    var matchColors = {
      '匹配': '#4ade80',
      '不匹配': '#f87171',
      '未设': '#9ca3af'
    };

    // 快速预测结果颜色和图标
    var quickPredictionUI = data.quickPrediction ? function () {
      var qp = data.quickPrediction;
      var bgColor, borderColor, textColor, icon;
      if (qp.outcome === '不适合快速判断' || qp.outcome === '数据不足') {
        bgColor = 'rgba(156, 163, 175, 0.15)';
        borderColor = '#9ca3af';
        textColor = '#6b7280';
        icon = '📋';
      } else if (qp.outcome === '警惕') {
        bgColor = 'rgba(245, 158, 11, 0.15)';
        borderColor = '#f59e0b';
        textColor = '#f59e0b';
        icon = '⚠️';
      } else if (qp.level.includes('必胜') || qp.level.includes('几乎必胜')) {
        bgColor = 'rgba(239, 68, 68, 0.15)';
        borderColor = '#ef4444';
        textColor = '#ef4444';
        icon = '🔥';
      } else if (qp.level.includes('极大概率')) {
        bgColor = 'rgba(249, 115, 22, 0.15)';
        borderColor = '#f97316';
        textColor = '#f97316';
        icon = '💪';
      } else {
        bgColor = 'rgba(59, 130, 246, 0.15)';
        borderColor = '#3b82f6';
        textColor = '#3b82f6';
        icon = '📊';
      }
      return {
        bgColor: bgColor,
        borderColor: borderColor,
        textColor: textColor,
        icon: icon,
        qp: qp
      };
    }() : null;
    return "\n            <div style=\"background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%); border: 2px solid rgba(102, 126, 234, 0.3); box-shadow: 0 4px 20px rgba(102, 126, 234, 0.2); border-radius: 16px; padding: 1.5rem; animation: slideDown 0.3s ease;\">\n                <h3 style=\"color: #667eea; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.5rem;\">\n                    <span style=\"font-size: 1.5em;\">\uD83C\uDFAF</span>\n                    <span>\u667A\u80FD\u89C4\u5219\u5206\u6790</span>\n                </h3>\n                <style>\n                    @keyframes slideDown {\n                        from {\n                            opacity: 0;\n                            transform: translateY(-10px);\n                        }\n                        to {\n                            opacity: 1;\n                            transform: translateY(0);\n                        }\n                    }\n                </style>\n                \n                ".concat(quickPredictionUI ? "\n                <!-- \u5FEB\u901F\u9884\u6D4B\u7ED3\u679C -->\n                <div style=\"background: ".concat(quickPredictionUI.bgColor, "; border: 3px solid ").concat(quickPredictionUI.borderColor, "; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 4px 15px rgba(0,0,0,0.1);\">\n                    <div style=\"display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;\">\n                        <div style=\"display: flex; align-items: center; gap: 0.8rem;\">\n                            <span style=\"font-size: 2rem;\">").concat(quickPredictionUI.icon, "</span>\n                            <div>\n                                <div style=\"font-size: 0.85rem; color: #6b7280; margin-bottom: 0.3rem;\">\u5FEB\u901F\u9884\u6D4B - \u89C4\u5219").concat(quickPredictionUI.qp.ruleNumber, "</div>\n                                <div style=\"font-size: 1.5rem; font-weight: 800; color: ").concat(quickPredictionUI.textColor, ";\">").concat(quickPredictionUI.qp.outcome, "</div>\n                            </div>\n                        </div>\n                        <div style=\"text-align: right;\">\n                            <div style=\"font-size: 0.85rem; color: #6b7280; margin-bottom: 0.3rem;\">\u9884\u6D4B\u7B49\u7EA7</div>\n                            <div style=\"font-size: 1.1rem; font-weight: 700; color: ").concat(quickPredictionUI.textColor, ";\">").concat(quickPredictionUI.qp.level, "</div>\n                        </div>\n                    </div>\n                </div>\n                ") : '', "\n                \n                <!-- \u8BA9\u7403\u65B9\u4FE1\u606F -->\n                <div style=\"background: rgba(255,255,255,0.95); padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; box-shadow: 0 2px 10px rgba(0,0,0,0.05);\">\n                    <div style=\"text-align: center;\">\n                        <div style=\"font-size: 0.85rem; color: #6b7280; margin-bottom: 0.3rem;\">\u8BA9\u7403\u65B9</div>\n                        <div style=\"font-size: 1.3rem; font-weight: 700; color: #667eea;\">").concat(data.betSide === '主' ? '主队' : '客队', "</div>\n                    </div>\n                </div>\n                \n                <!-- \u53CC\u89C4\u5219\u5206\u6790 -->\n                <div style=\"display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;\">\n                    <!-- \u8BA9\u65B9\u6253\u51FA -->\n                    <div style=\"background: rgba(16, 185, 129, 0.08); padding: 1.5rem; border-radius: 12px; border: 2px solid rgba(16, 185, 129, 0.3); box-shadow: 0 2px 10px rgba(0,0,0,0.05);\">\n                        <div style=\"display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;\">\n                            <span style=\"font-size: 1.3em;\">\uD83D\uDCAA</span>\n                            <h4 style=\"color: #10b981; margin: 0; font-size: 1rem; font-weight: 700;\">\u8BA9\u65B9\u6253\u51FA</h4>\n                        </div>\n                        <div style=\"text-align: center; padding: 0.8rem; background: rgba(255,255,255,0.7); border-radius: 8px; margin-bottom: 1rem;\">\n                            <div style=\"font-size: 0.85rem; color: #6b7280; margin-bottom: 0.3rem;\">\u89C4\u5219\u7F16\u53F7</div>\n                            <div style=\"font-size: 1.3rem; font-weight: 700; color: #10b981;\">").concat(data.ruleStrong.code || '--', "</div>\n                        </div>\n                        ").concat(data.ruleStrong.zone ? "\n                        <div style=\"padding: 0.8rem; background: rgba(255,255,255,0.5); border-radius: 8px; margin-bottom: 1rem;\">\n                            <div style=\"font-size: 0.85rem; color: #6b7280; margin-bottom: 0.3rem;\">\u9700\u8981\u533A\u95F4</div>\n                            <div style=\"font-size: 1rem; font-weight: 600; color: #059669;\">".concat(formatZone(data.ruleStrong.zone), "</div>\n                        </div>\n                        <div style=\"padding: 1rem; background: rgba(255,255,255,0.5); border-radius: 8px; border-left: 3px solid #10b981;\">\n                            <div style=\"font-size: 0.85rem; color: #047857; line-height: 1.6;\">\n                                ").concat(data.ruleStrong.text, "\n                            </div>\n                        </div>\n                        ") : "\n                        <div style=\"padding: 1rem; background: rgba(255,255,255,0.5); border-radius: 8px; text-align: center; color: #9ca3af; font-size: 0.9rem;\">\n                            \u672A\u89E6\u53D1\u89C4\u5219\n                        </div>\n                        ", "\n                    </div>\n                    \n                    <!-- \u53D7\u65B9\u6253\u51FA -->\n                    <div style=\"background: rgba(239, 68, 68, 0.08); padding: 1.5rem; border-radius: 12px; border: 2px solid rgba(239, 68, 68, 0.3); box-shadow: 0 2px 10px rgba(0,0,0,0.05);\">\n                        <div style=\"display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;\">\n                            <span style=\"font-size: 1.3em;\">\uD83C\uDFB2</span>\n                            <h4 style=\"color: #ef4444; margin: 0; font-size: 1rem; font-weight: 700;\">\u53D7\u65B9\u6253\u51FA</h4>\n                        </div>\n                        <div style=\"text-align: center; padding: 0.8rem; background: rgba(255,255,255,0.7); border-radius: 8px; margin-bottom: 1rem;\">\n                            <div style=\"font-size: 0.85rem; color: #6b7280; margin-bottom: 0.3rem;\">\u89C4\u5219\u7F16\u53F7</div>\n                            <div style=\"font-size: 1.3rem; font-weight: 700; color: #ef4444;\">").concat(data.ruleWeak.code || '--', "</div>\n                        </div>\n                        ").concat(data.ruleWeak.zone ? "\n                        <div style=\"padding: 0.8rem; background: rgba(255,255,255,0.5); border-radius: 8px; margin-bottom: 1rem;\">\n                            <div style=\"font-size: 0.85rem; color: #6b7280; margin-bottom: 0.3rem;\">\u9700\u8981\u533A\u95F4</div>\n                            <div style=\"font-size: 1rem; font-weight: 600; color: #dc2626;\">".concat(formatZone(data.ruleWeak.zone), "</div>\n                        </div>\n                        <div style=\"padding: 1rem; background: rgba(255,255,255,0.5); border-radius: 8px; border-left: 3px solid #ef4444;\">\n                            <div style=\"font-size: 0.85rem; color: #b91c1c; line-height: 1.6;\">\n                                ").concat(data.ruleWeak.text, "\n                            </div>\n                        </div>\n                        ") : "\n                        <div style=\"padding: 1rem; background: rgba(255,255,255,0.5); border-radius: 8px; text-align: center; color: #9ca3af; font-size: 0.9rem;\">\n                            \u672A\u89E6\u53D1\u89C4\u5219\n                        </div>\n                        ", "\n                    </div>\n                </div>\n\n                <!-- \u533A\u95F4\u5339\u914D\u9A8C\u8BC1 -->\n                <div style=\"background: rgba(255,255,255,0.95); padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; box-shadow: 0 2px 10px rgba(0,0,0,0.05);\">\n                    <h4 style=\"color: #1f2937; margin-bottom: 1rem; font-size: 1rem; display: flex; align-items: center; gap: 0.5rem;\">\n                        <span>\uD83D\uDCCB</span>\n                        <span>\u533A\u95F4\u5339\u914D\u9A8C\u8BC1</span>\n                    </h4>\n                    <div style=\"display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;\">\n                        <!-- \u8BA9\u65B9\u89C4\u5219\u9A8C\u8BC1 -->\n                        <div style=\"padding: 1.2rem; background: rgba(16, 185, 129, 0.05); border-radius: 8px; border: 2px solid rgba(16, 185, 129, 0.2);\">\n                            <div style=\"font-size: 0.85rem; color: #6b7280; margin-bottom: 0.8rem; font-weight: 600;\">\uD83D\uDCAA \u8BA9\u65B9\u89C4\u5219\uFF08\u6FB3\u95E8\u4E00\u8D54\uFF09</div>\n                            <div style=\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;\">\n                                <span style=\"font-size: 0.9rem; color: #4b5563;\">\u5339\u914D\u72B6\u6001</span>\n                                <span style=\"font-size: 1rem; font-weight: 700; padding: 0.3rem 0.8rem; border-radius: 6px; background: ").concat(matchColors[data.ruleMatch.one], "; color: white;\">\n                                    ").concat(data.ruleMatch.one === '匹配' ? '✓ 匹配' : data.ruleMatch.one === '不匹配' ? '✗ 不匹配' : '○ 未设', "\n                                </span>\n                            </div>\n                            <div style=\"font-size: 0.85rem; color: #6b7280; padding: 0.8rem; background: rgba(255,255,255,0.7); border-radius: 6px;\">\n                                <div style=\"margin-bottom: 0.4rem;\">\u9700\u8981\u533A\u95F4: <span style=\"color: #10b981; font-weight: 600;\">").concat(formatZone(data.ruleStrong.zone) || '--', "</span></div>\n                                <div>\u5B9E\u9645\u533A\u95F4: <span style=\"color: #1f2937; font-weight: 600;\">").concat(data.debug.macaoOne || '--', "</span></div>\n                            </div>\n                        </div>\n                        \n                        <!-- \u53D7\u65B9\u89C4\u5219\u9A8C\u8BC1 -->\n                        <div style=\"padding: 1.2rem; background: rgba(239, 68, 68, 0.05); border-radius: 8px; border: 2px solid rgba(239, 68, 68, 0.2);\">\n                            <div style=\"font-size: 0.85rem; color: #6b7280; margin-bottom: 0.8rem; font-weight: 600;\">\uD83C\uDFB2 \u53D7\u65B9\u89C4\u5219\uFF08\u9A6C\u4F1A\u4E09\u8D54\uFF09</div>\n                            <div style=\"display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;\">\n                                <span style=\"font-size: 0.9rem; color: #4b5563;\">\u5339\u914D\u72B6\u6001</span>\n                                <span style=\"font-size: 1rem; font-weight: 700; padding: 0.3rem 0.8rem; border-radius: 6px; background: ").concat(matchColors[data.ruleMatch.three], "; color: white;\">\n                                    ").concat(data.ruleMatch.three === '匹配' ? '✓ 匹配' : data.ruleMatch.three === '不匹配' ? '✗ 不匹配' : '○ 未设', "\n                                </span>\n                            </div>\n                            <div style=\"font-size: 0.85rem; color: #6b7280; padding: 0.8rem; background: rgba(255,255,255,0.7); border-radius: 6px;\">\n                                <div style=\"margin-bottom: 0.4rem;\">\u9700\u8981\u533A\u95F4: <span style=\"color: #ef4444; font-weight: 600;\">").concat(formatZone(data.ruleWeak.zone) || '--', "</span></div>\n                                <div>\u5B9E\u9645\u533A\u95F4: <span style=\"color: #1f2937; font-weight: 600;\">").concat(data.debug.hkThree || '--', "</span></div>\n                            </div>\n                        </div>\n                    </div>\n                </div>\n\n                <!-- \u8BE6\u7EC6\u6570\u636E\uFF08\u53EF\u6298\u53E0\uFF09 -->\n                <details style=\"background: rgba(255,255,255,0.95); padding: 1rem; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);\">\n                    <summary style=\"cursor: pointer; font-weight: 600; color: #667eea; font-size: 0.95rem; user-select: none;\">\n                        \uD83D\uDCCA \u67E5\u770B\u8BE6\u7EC6\u6570\u636E\n                    </summary>\n                    <div style=\"margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(0,0,0,0.1);\">\n                        <div style=\"margin-bottom: 1rem;\">\n                            <h5 style=\"color: #4b5563; font-size: 0.9rem; margin-bottom: 0.5rem; font-weight: 600;\">\u4FE1\u5FC3\u7B49\u7EA7\u533A\u95F4\u8BF4\u660E</h5>\n                            <div style=\"font-size: 0.8rem; color: #6b7280; line-height: 1.6; background: rgba(102, 126, 234, 0.05); padding: 0.8rem; border-radius: 6px;\">\n                                \u4F4E: < 4.4 &nbsp;|&nbsp; \u4E2D\u5EB8: 4.4-5.6 &nbsp;|&nbsp; \u4E2D\u4E0A: > 5.6\n                            </div>\n                        </div>\n                        <div style=\"display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.8rem; font-size: 0.85rem;\">\n                            <div><span style=\"color: #6b7280;\">\u5E7F\u4E49\u5B9E\u529B(\u4E3B):</span> <span style=\"color: #1f2937; font-weight: 500;\">").concat(((_data$debug$genHome = data.debug.genHome) === null || _data$debug$genHome === void 0 ? void 0 : _data$debug$genHome.toFixed(2)) || '--', "</span></div>\n                            <div><span style=\"color: #6b7280;\">\u5E7F\u4E49\u5B9E\u529B(\u5BA2):</span> <span style=\"color: #1f2937; font-weight: 500;\">").concat(((_data$debug$genAway = data.debug.genAway) === null || _data$debug$genAway === void 0 ? void 0 : _data$debug$genAway.toFixed(2)) || '--', "</span></div>\n                            <div><span style=\"color: #6b7280;\">\u5B9E\u529B\u7EA7(\u4E3B):</span> <span style=\"color: #1f2937; font-weight: 500;\">").concat(data.debug.tierHome || '--', "</span></div>\n                            <div><span style=\"color: #6b7280;\">\u5B9E\u529B\u7EA7(\u5BA2):</span> <span style=\"color: #1f2937; font-weight: 500;\">").concat(data.debug.tierAway || '--', "</span></div>\n                            <div><span style=\"color: #6b7280;\">\u57FA\u672C\u9762(\u4E3B):</span> <span style=\"color: #1f2937; font-weight: 500;\">").concat(((_data$debug$teamConfH = data.debug.teamConfHome) === null || _data$debug$teamConfH === void 0 ? void 0 : _data$debug$teamConfH.toFixed(2)) || '--', "</span></div>\n                            <div><span style=\"color: #6b7280;\">\u57FA\u672C\u9762(\u5BA2):</span> <span style=\"color: #1f2937; font-weight: 500;\">").concat(((_data$debug$teamConfA = data.debug.teamConfAway) === null || _data$debug$teamConfA === void 0 ? void 0 : _data$debug$teamConfA.toFixed(2)) || '--', "</span></div>\n                            <div><span style=\"color: #6b7280;\">\u8BA9\u65B9\u4FE1\u5FC3:</span> <span style=\"color: #1f2937; font-weight: 600;\">").concat(((_data$debug$confLet = data.debug.confLet) === null || _data$debug$confLet === void 0 ? void 0 : _data$debug$confLet.toFixed(2)) || '--', "</span> <span style=\"color: #10b981; font-size: 0.8rem;\">(").concat(data.debug.confLetLevel || '--', ")</span></div>\n                            <div><span style=\"color: #6b7280;\">\u5E73\u5C40\u4FE1\u5FC3:</span> <span style=\"color: #1f2937; font-weight: 600;\">").concat(((_data$debug$confDraw = data.debug.confDraw) === null || _data$debug$confDraw === void 0 ? void 0 : _data$debug$confDraw.toFixed(2)) || '--', "</span> <span style=\"color: #f59e0b; font-size: 0.8rem;\">(").concat(data.debug.confDrawLevel || '--', ")</span></div>\n                            <div><span style=\"color: #6b7280;\">\u53D7\u65B9\u4FE1\u5FC3:</span> <span style=\"color: #1f2937; font-weight: 600;\">").concat(((_data$debug$confTake = data.debug.confTake) === null || _data$debug$confTake === void 0 ? void 0 : _data$debug$confTake.toFixed(2)) || '--', "</span> <span style=\"color: #ef4444; font-size: 0.8rem;\">(").concat(data.debug.confTakeLevel || '--', ")</span></div>\n                            <div><span style=\"color: #6b7280;\">\u5F00\u76D8\u7C7B\u578B:</span> <span style=\"color: #1f2937; font-weight: 500;\">").concat(data.openType, "</span></div>\n                        </div>\n                    </div>\n                </details>\n            </div>\n        ");
  }

  /**
   * 将分析结果插入到页面中
   * @param {string} containerId - 容器元素ID
   * @param {Object} analysisResult - 分析结果
   */
  function insertRuleAnalysis(containerId, analysisResult) {
    var container = document.getElementById(containerId);
    if (!container) {
      console.error("Container #".concat(containerId, " not found"));
      return;
    }
    var html = renderRuleAnalysisCard(analysisResult);
    container.insertAdjacentHTML('afterbegin', html);
  }

  // 导出到全局
  window.MatchRuleUI = {
    renderRuleAnalysisCard: renderRuleAnalysisCard,
    insertRuleAnalysis: insertRuleAnalysis
  };
})(window);
