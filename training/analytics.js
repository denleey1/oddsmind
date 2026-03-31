/**
 * 培训系统Analytics数据追踪
 * 功能: 学习时长、完成率、用户路径、设备统计
 */

class TrainingAnalytics {
    constructor() {
        this.sessionId = this.generateSessionId();
        this.startTime = Date.now();
        this.moduleStartTime = null;
        this.currentModule = null;
        this.analytics = this.loadAnalytics();
        
        this.init();
    }
    
    /**
     * 初始化
     */
    init() {
        // 记录会话开始
        this.trackEvent('session_start', {
            device: this.getDeviceInfo(),
            browser: this.getBrowserInfo(),
            screen: `${window.screen.width}x${window.screen.height}`,
            timestamp: new Date().toISOString()
        });
        
        // 页面卸载时保存数据
        window.addEventListener('beforeunload', () => {
            this.trackEvent('session_end', {
                duration: Date.now() - this.startTime,
                timestamp: new Date().toISOString()
            });
            this.saveAnalytics();
        });
        
        // 定期自动保存
        setInterval(() => {
            this.saveAnalytics();
        }, 30000); // 每30秒保存一次
        
        console.log('📊 Analytics已启动 - Session ID:', this.sessionId);
    }
    
    /**
     * 生成会话ID
     */
    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    /**
     * 加载历史数据
     */
    loadAnalytics() {
        try {
            const data = localStorage.getItem('trainingAnalytics');
            return data ? JSON.parse(data) : this.createEmptyAnalytics();
        } catch (e) {
            console.error('加载Analytics失败:', e);
            return this.createEmptyAnalytics();
        }
    }
    
    /**
     * 创建空的Analytics对象
     */
    createEmptyAnalytics() {
        return {
            totalSessions: 0,
            totalTime: 0, // 总学习时长(毫秒)
            modules: {}, // 每个模块的详细数据
            events: [], // 事件日志
            devices: {}, // 设备统计
            completionRate: 0,
            lastVisit: null,
            firstVisit: new Date().toISOString(),
            streak: 0 // 连续学习天数
        };
    }
    
    /**
     * 保存数据
     */
    saveAnalytics() {
        try {
            // 更新总会话数
            this.analytics.totalSessions++;
            
            // 更新最后访问时间
            this.analytics.lastVisit = new Date().toISOString();
            
            // 计算连续学习天数
            this.analytics.streak = this.calculateStreak();
            
            // 保存到localStorage
            localStorage.setItem('trainingAnalytics', JSON.stringify(this.analytics));
        } catch (e) {
            console.error('保存Analytics失败:', e);
        }
    }
    
    /**
     * 跟踪事件
     */
    trackEvent(eventName, data = {}) {
        const event = {
            name: eventName,
            sessionId: this.sessionId,
            timestamp: Date.now(),
            data: data
        };
        
        // 添加到事件列表(只保留最近1000条)
        this.analytics.events.push(event);
        if (this.analytics.events.length > 1000) {
            this.analytics.events = this.analytics.events.slice(-1000);
        }
        
        console.log('📊 Event:', eventName, data);
    }
    
    /**
     * 开始学习模块
     */
    startModule(moduleId, moduleName) {
        // 结束上一个模块
        if (this.currentModule) {
            this.endModule(this.currentModule);
        }
        
        this.currentModule = moduleId;
        this.moduleStartTime = Date.now();
        
        // 初始化模块数据
        if (!this.analytics.modules[moduleId]) {
            this.analytics.modules[moduleId] = {
                name: moduleName,
                visits: 0,
                totalTime: 0,
                completed: false,
                lastVisit: null,
                firstVisit: new Date().toISOString()
            };
        }
        
        this.analytics.modules[moduleId].visits++;
        this.analytics.modules[moduleId].lastVisit = new Date().toISOString();
        
        this.trackEvent('module_start', {
            moduleId: moduleId,
            moduleName: moduleName
        });
    }
    
    /**
     * 结束学习模块
     */
    endModule(moduleId) {
        if (!this.moduleStartTime) return;
        
        const duration = Date.now() - this.moduleStartTime;
        
        // 更新模块学习时长
        if (this.analytics.modules[moduleId]) {
            this.analytics.modules[moduleId].totalTime += duration;
        }
        
        // 更新总学习时长
        this.analytics.totalTime += duration;
        
        this.trackEvent('module_end', {
            moduleId: moduleId,
            duration: duration,
            durationMinutes: (duration / 60000).toFixed(2)
        });
        
        this.moduleStartTime = null;
        this.currentModule = null;
    }
    
    /**
     * 标记模块完成
     */
    completeModule(moduleId) {
        if (this.analytics.modules[moduleId]) {
            this.analytics.modules[moduleId].completed = true;
        }
        
        // 计算完成率
        const totalModules = 8;
        const completedCount = Object.values(this.analytics.modules).filter(m => m.completed).length;
        this.analytics.completionRate = (completedCount / totalModules * 100).toFixed(1);
        
        this.trackEvent('module_completed', {
            moduleId: moduleId,
            completionRate: this.analytics.completionRate
        });
        
        this.saveAnalytics();
    }
    
    /**
     * 获取设备信息
     */
    getDeviceInfo() {
        const ua = navigator.userAgent;
        
        if (/mobile/i.test(ua)) return 'Mobile';
        if (/tablet|ipad/i.test(ua)) return 'Tablet';
        return 'Desktop';
    }
    
    /**
     * 获取浏览器信息
     */
    getBrowserInfo() {
        const ua = navigator.userAgent;
        
        if (ua.includes('Chrome')) return 'Chrome';
        if (ua.includes('Firefox')) return 'Firefox';
        if (ua.includes('Safari') && !ua.includes('Chrome')) return 'Safari';
        if (ua.includes('Edge')) return 'Edge';
        return 'Unknown';
    }
    
    /**
     * 计算连续学习天数
     */
    calculateStreak() {
        const today = new Date().toDateString();
        const lastVisit = this.analytics.lastVisit ? new Date(this.analytics.lastVisit).toDateString() : null;
        
        if (!lastVisit) return 1;
        
        const daysDiff = Math.floor((new Date(today) - new Date(lastVisit)) / (1000 * 60 * 60 * 24));
        
        if (daysDiff === 0) {
            // 今天已经访问过
            return this.analytics.streak || 1;
        } else if (daysDiff === 1) {
            // 连续访问
            return (this.analytics.streak || 0) + 1;
        } else {
            // 中断了,重新开始
            return 1;
        }
    }
    
    /**
     * 获取统计摘要
     */
    getSummary() {
        const completedModules = Object.values(this.analytics.modules).filter(m => m.completed).length;
        const totalMinutes = (this.analytics.totalTime / 60000).toFixed(1);
        const avgTimePerModule = completedModules > 0 ? 
            (this.analytics.totalTime / completedModules / 60000).toFixed(1) : 0;
        
        return {
            totalSessions: this.analytics.totalSessions,
            totalTime: totalMinutes + ' 分钟',
            completedModules: `${completedModules}/8`,
            completionRate: this.analytics.completionRate + '%',
            avgTimePerModule: avgTimePerModule + ' 分钟/模块',
            streak: this.analytics.streak + ' 天',
            device: this.getDeviceInfo(),
            browser: this.getBrowserInfo()
        };
    }
    
    /**
     * 打印统计报告
     */
    printReport() {
        console.log('\n📊 ===== 学习数据统计报告 =====');
        console.table(this.getSummary());
        
        console.log('\n📚 模块详情:');
        const moduleStats = {};
        Object.entries(this.analytics.modules).forEach(([id, data]) => {
            moduleStats[id] = {
                名称: data.name,
                访问次数: data.visits,
                学习时长: (data.totalTime / 60000).toFixed(1) + '分钟',
                完成状态: data.completed ? '✓' : '○'
            };
        });
        console.table(moduleStats);
        
        console.log('\n📈 最近10条事件:');
        console.table(
            this.analytics.events.slice(-10).map(e => ({
                事件: e.name,
                时间: new Date(e.timestamp).toLocaleString('zh-CN'),
                数据: JSON.stringify(e.data)
            }))
        );
    }
    
    /**
     * 导出数据(用于分析)
     */
    exportData() {
        return {
            analytics: this.analytics,
            summary: this.getSummary(),
            exportTime: new Date().toISOString()
        };
    }
    
    /**
     * 清除所有数据
     */
    clearData() {
        if (confirm('确定要清除所有学习数据吗?此操作不可恢复!')) {
            localStorage.removeItem('trainingAnalytics');
            this.analytics = this.createEmptyAnalytics();
            console.log('✓ 数据已清除');
        }
    }
}

// 全局Analytics实例
window.analytics = new TrainingAnalytics();

// 暴露给控制台的快捷方法
window.showAnalytics = () => window.analytics.printReport();
window.exportAnalytics = () => {
    const data = window.analytics.exportData();
    console.log('导出数据:', data);
    
    // 创建下载链接
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `training_analytics_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
};
window.clearAnalytics = () => window.analytics.clearData();

console.log('\n💡 Analytics命令:');
console.log('  showAnalytics()   - 查看学习统计');
console.log('  exportAnalytics() - 导出数据');
console.log('  clearAnalytics()  - 清除数据\n');
