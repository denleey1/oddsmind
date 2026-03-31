// 颜色修复补丁 - 可以直接在控制台运行
// 或添加到 app_modern.js 的末尾

function applyOddsRangeColors() {
    console.log('应用开盘区间颜色...');
    
    // 确保必要的数据存在
    if (!window.currentMatchData || !window.currentMatchData.fundamentalAnalysis) {
        console.log('没有基本面分析数据，跳过颜色应用');
        return;
    }
    
    const fundamentalAnalysis = window.currentMatchData.fundamentalAnalysis;
    const companyAnalyses = window.currentMatchData.companyAnalyses;
    
    if (!companyAnalyses || companyAnalyses.length === 0) {
        console.log('没有公司分析数据，跳过颜色应用');
        return;
    }
    
    // 获取当前显示的公司索引
    const companySelect = document.getElementById('companySelect');
    const currentIndex = companySelect ? parseInt(companySelect.value) : 0;
    const currentCompany = companyAnalyses[currentIndex];
    
    if (!currentCompany) {
        console.log('未找到当前公司数据');
        return;
    }
    
    // 辅助函数：判断区间是否合理
    function isRangeValid(oddsRange, suggestions) {
        if (!oddsRange || oddsRange === '--' || !suggestions) {
            return null;
        }
        
        // 解析建议列表
        let suggestionsList = [];
        try {
            if (typeof suggestions === 'string') {
                suggestionsList = JSON.parse(suggestions);
            } else if (Array.isArray(suggestions)) {
                suggestionsList = suggestions;
            }
        } catch (e) {
            return null;
        }
        
        // 解析赔率区间
        const rangeParts = oddsRange.split('-');
        if (rangeParts.length !== 2) return null;
        
        const rangeMin = parseFloat(rangeParts[0]);
        const rangeMax = parseFloat(rangeParts[1]);
        
        if (isNaN(rangeMin) || isNaN(rangeMax)) return null;
        
        // 检查是否有交集
        for (const suggestion of suggestionsList) {
            const sugParts = suggestion.split('-');
            if (sugParts.length !== 2) continue;
            
            const sugMin = parseFloat(sugParts[0]);
            const sugMax = parseFloat(sugParts[1]);
            
            if (isNaN(sugMin) || isNaN(sugMax)) continue;
            
            // 检查是否有交集
            if (rangeMin <= sugMax && rangeMax >= sugMin) {
                return true; // 合理
            }
        }
        
        return false; // 不合理
    }
    
    // 应用颜色到表格行
    const tableRows = document.querySelectorAll('#oddsTableBody tr');
    
    tableRows.forEach((row, index) => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 7) return;
        
        const isInitial = index === 0; // 第一行是初盘
        const data = isInitial ? currentCompany.initial : currentCompany.current;
        
        if (!data) return;
        
        // 主队区间 (第3列，索引2)
        const homeRangeCell = cells[2];
        if (homeRangeCell && data.homeRange && data.homeRange !== '--') {
            const isValid = isRangeValid(data.homeRange, fundamentalAnalysis.homeWin?.oddsSuggestions);
            
            if (isValid === true) {
                homeRangeCell.style.background = '#e8f5e8';
                homeRangeCell.style.color = '#2e7d32';
                homeRangeCell.title = '合理：主队开盘在建议范围内';
            } else if (isValid === false) {
                homeRangeCell.style.background = '#ffeaa7';
                homeRangeCell.style.color = '#d63031';
                homeRangeCell.title = '不合理：主队开盘不在建议范围内';
            }
            
            homeRangeCell.style.padding = '4px 8px';
            homeRangeCell.style.borderRadius = '4px';
            homeRangeCell.style.cursor = 'pointer';
        }
        
        // 客队区间 (第7列，索引6)
        const awayRangeCell = cells[6];
        if (awayRangeCell && data.awayRange && data.awayRange !== '--') {
            const isValid = isRangeValid(data.awayRange, fundamentalAnalysis.awayWin?.oddsSuggestions);
            
            if (isValid === true) {
                awayRangeCell.style.background = '#e8f5e8';
                awayRangeCell.style.color = '#2e7d32';
                awayRangeCell.title = '合理：客队开盘在建议范围内';
            } else if (isValid === false) {
                awayRangeCell.style.background = '#ffeaa7';
                awayRangeCell.style.color = '#d63031';
                awayRangeCell.title = '不合理：客队开盘不在建议范围内';
            }
            
            awayRangeCell.style.padding = '4px 8px';
            awayRangeCell.style.borderRadius = '4px';
            awayRangeCell.style.cursor = 'pointer';
        }
    });
    
    console.log('颜色应用完成');
}

// 监听公司选择变化
const existingSelect = document.getElementById('companySelect');
if (existingSelect) {
    existingSelect.addEventListener('change', function() {
        setTimeout(applyOddsRangeColors, 100); // 延迟100ms确保表格已更新
    });
}

// 立即应用一次
applyOddsRangeColors();

// 导出到全局
window.applyOddsRangeColors = applyOddsRangeColors;

console.log('颜色修复补丁已加载。可以手动调用 applyOddsRangeColors() 来应用颜色。');