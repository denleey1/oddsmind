/**
 * 规则匹配前端模块
 * 用于在比赛详情页显示规则匹配结果，以及在比赛列表显示火焰图标
 */

const RuleMatch = {
    // 缓存已加载的警报数据
    alertedMatches: new Set(),
    alertsData: {},

    /**
     * 初始化 - 加载今日所有规则匹配
     */
    init: function() {
        this.loadAlertedMatches();
    },

    /**
     * 加载今日所有规则匹配的比赛ID
     */
    loadAlertedMatches: async function() {
        try {
            const response = await fetch('/api/rule-alerts/today');
            if (!response.ok) return;
            
            const data = await response.json();
            if (!data.success) return;
            
            // 收集所有匹配的比赛ID
            const allMatches = [...(data.handicap_win || []), ...(data.receiver_not_lose || [])];
            allMatches.forEach(match => {
                this.alertedMatches.add(match.match_id);
                this.alertsData[match.match_id] = match;
            });
            
            console.log(`[RuleMatch] 已加载 ${this.alertedMatches.size} 场规则匹配`);
            
            // 渲染火焰图标
            this.renderFireIcons();
        } catch (error) {
            console.error('[RuleMatch] 加载规则匹配失败:', error);
        }
    },

    /**
     * 在比赛列表中渲染火焰图标
     */
    renderFireIcons: function() {
        if (this.alertedMatches.size === 0) return;
        
        // 查找所有比赛卡片
        const matchCards = document.querySelectorAll('.match-card, [data-match-id]');
        
        matchCards.forEach(card => {
            const matchId = card.dataset.matchId || card.getAttribute('data-match-id');
            if (!matchId) return;
            
            const numericId = parseInt(matchId);
            if (!this.alertedMatches.has(numericId)) return;
            
            // 已经有火焰图标则跳过
            if (card.querySelector('.rule-fire-badge')) return;
            
            const alertData = this.alertsData[numericId];
            const isHandicapWin = alertData && alertData.rules && 
                alertData.rules.some(r => r.prediction === '让方必赢');
            
            // 创建火焰徽章
            const badge = document.createElement('div');
            badge.className = 'rule-fire-badge';
            badge.innerHTML = isHandicapWin ? '🔥赢' : '🔥不输';
            badge.title = alertData ? `${alertData.rules.length}条规则命中` : '规则命中';
            badge.style.cssText = `
                position: absolute;
                top: 4px;
                right: 4px;
                background: linear-gradient(135deg, #ff6b35, #f72585);
                color: white;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                z-index: 10;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            `;
            
            // 确保父元素有定位
            if (getComputedStyle(card).position === 'static') {
                card.style.position = 'relative';
            }
            
            card.appendChild(badge);
        });
    },

    /**
     * 加载指定比赛的规则匹配详情
     */
    loadMatchAlerts: async function(matchId) {
        try {
            const response = await fetch(`/api/rule-alerts/match/${matchId}`);
            if (!response.ok) return null;
            
            const data = await response.json();
            return data;
        } catch (error) {
            console.error(`[RuleMatch] 加载比赛 ${matchId} 规则失败:`, error);
            return null;
        }
    },

    /**
     * 渲染比赛详情页的规则匹配模块
     */
    renderDetailModule: async function(matchId, container) {
        const data = await this.loadMatchAlerts(matchId);
        
        if (!data || !data.has_alert) {
            container.innerHTML = '<div class="no-rules">暂无规则匹配</div>';
            return;
        }
        
        const match = data.match_info;
        const rules = data.rules || [];
        
        let html = `
            <div class="rule-match-module">
                <div class="rule-header">
                    <span class="rule-icon">🎯</span>
                    <span class="rule-title">规则匹配</span>
                    <span class="rule-count">${rules.length}条命中</span>
                </div>
                <div class="rule-teams">
                    <span class="handicap-team">让方: ${match.handicap_team}</span>
                    <span class="receiver-team">受方: ${match.receiver_team}</span>
                </div>
                <div class="rule-list">
        `;
        
        rules.forEach(rule => {
            const predictionClass = rule.prediction === '让方必赢' ? 'prediction-win' : 'prediction-not-lose';
            html += `
                <div class="rule-item">
                    <div class="rule-name">${rule.rule_name}</div>
                    <div class="rule-prediction ${predictionClass}">${rule.prediction}</div>
                    <div class="rule-suggestion">${rule.bet_suggestion}</div>
                    <div class="rule-accuracy">历史命中: ${(rule.accuracy * 100).toFixed(0)}%</div>
                </div>
            `;
        });
        
        html += '</div></div>';
        container.innerHTML = html;
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    RuleMatch.init();
});

// 监听动态加载的比赛卡片
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.addedNodes.length > 0) {
            setTimeout(() => RuleMatch.renderFireIcons(), 100);
        }
    });
});

// 开始观察
observer.observe(document.body, { childList: true, subtree: true });

// 定时刷新火焰图标（应对异步加载）
setInterval(() => RuleMatch.renderFireIcons(), 2000);

console.log('✅ RuleMatch模块加载成功！');
