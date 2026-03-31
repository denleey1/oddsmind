// 前端交互增强脚本

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    
    // 添加平滑滚动效果
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // 优化加载状态显示
    const originalFetch = window.fetch;
    let activeRequests = 0;
    
    window.fetch = function(...args) {
        activeRequests++;
        showLoadingIndicator();
        
        return originalFetch.apply(this, args)
            .finally(() => {
                activeRequests--;
                if (activeRequests === 0) {
                    hideLoadingIndicator();
                }
            });
    };
    
    function showLoadingIndicator() {
        const indicator = document.getElementById('loading');
        if (indicator) {
            indicator.classList.add('show');
        }
    }
    
    function hideLoadingIndicator() {
        const indicator = document.getElementById('loading');
        if (indicator) {
            setTimeout(() => {
                indicator.classList.remove('show');
            }, 300);
        }
    }
    
    // 添加卡片动画效果
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const cardObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, index * 50);
                cardObserver.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // 监听所有比赛卡片
    function observeCards() {
        document.querySelectorAll('.match-card, .detail-card').forEach((card, index) => {
            // 只对match-card应用动画，避免破坏detail-card的grid布局
            if (card.classList.contains('match-card')) {
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                cardObserver.observe(card);
            }
        });
    }
    
    // 初始观察
    observeCards();
    
    // 在数据更新后重新观察
    const originalRenderMatchesList = window.renderMatchesList;
    if (originalRenderMatchesList) {
        window.renderMatchesList = function() {
            originalRenderMatchesList.apply(this, arguments);
            setTimeout(observeCards, 100);
        };
    }
    
    // 添加键盘快捷键支持
    document.addEventListener('keydown', function(e) {
        // ESC键返回列表页
        if (e.key === 'Escape') {
            const detailPage = document.getElementById('detailPage');
            const listPage = document.getElementById('listPage');
            if (detailPage && detailPage.classList.contains('active')) {
                if (typeof showList === 'function') {
                    showList();
                }
            }
        }
        
        // Ctrl/Cmd + R 刷新数据
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            if (typeof fetchMatches === 'function') {
                fetchMatches();
            }
        }
    });
    
    // 添加提示工具
    function addTooltips() {
        document.querySelectorAll('[title]').forEach(element => {
            element.addEventListener('mouseenter', function(e) {
                const tooltip = document.createElement('div');
                tooltip.className = 'custom-tooltip';
                tooltip.textContent = this.getAttribute('title');
                tooltip.style.cssText = `
                    position: absolute;
                    background: rgba(0, 0, 0, 0.9);
                    color: white;
                    padding: 8px 12px;
                    border-radius: 6px;
                    font-size: 12px;
                    z-index: 10000;
                    pointer-events: none;
                    max-width: 250px;
                    word-wrap: break-word;
                `;
                document.body.appendChild(tooltip);
                
                const rect = this.getBoundingClientRect();
                tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
                tooltip.style.top = rect.bottom + 10 + 'px';
                
                this.setAttribute('data-original-title', this.getAttribute('title'));
                this.removeAttribute('title');
                
                element._tooltip = tooltip;
            });
            
            element.addEventListener('mouseleave', function() {
                if (element._tooltip) {
                    element._tooltip.remove();
                    element._tooltip = null;
                }
                if (this.hasAttribute('data-original-title')) {
                    this.setAttribute('title', this.getAttribute('data-original-title'));
                    this.removeAttribute('data-original-title');
                }
            });
        });
    }
    
    // 初始化提示工具
    setTimeout(addTooltips, 500);
    
    // 添加表格行高亮效果
    document.addEventListener('mouseover', function(e) {
        if (e.target.tagName === 'TD') {
            const row = e.target.parentElement;
            if (row) {
                row.style.backgroundColor = 'rgba(102, 126, 234, 0.05)';
            }
        }
    });
    
    document.addEventListener('mouseout', function(e) {
        if (e.target.tagName === 'TD') {
            const row = e.target.parentElement;
            if (row) {
                row.style.backgroundColor = '';
            }
        }
    });
    
    // 优化筛选器交互
    const filters = document.querySelectorAll('.filter-select, .filter-input');
    filters.forEach(filter => {
        filter.addEventListener('focus', function() {
            this.style.transform = 'scale(1.02)';
        });
        
        filter.addEventListener('blur', function() {
            this.style.transform = 'scale(1)';
        });
    });
    
    // 添加返回顶部按钮
    const backToTop = document.createElement('button');
    backToTop.innerHTML = '↑';
    backToTop.style.cssText = `
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        font-size: 24px;
        cursor: pointer;
        opacity: 0;
        transition: all 0.3s ease;
        z-index: 999;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    `;
    document.body.appendChild(backToTop);
    
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTop.style.opacity = '1';
            backToTop.style.pointerEvents = 'auto';
        } else {
            backToTop.style.opacity = '0';
            backToTop.style.pointerEvents = 'none';
        }
    });
    
    backToTop.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
    
    backToTop.addEventListener('mouseenter', function() {
        this.style.transform = 'scale(1.1) translateY(-5px)';
        this.style.boxShadow = '0 6px 20px rgba(102, 126, 234, 0.5)';
    });
    
    backToTop.addEventListener('mouseleave', function() {
        this.style.transform = 'scale(1)';
        this.style.boxShadow = '0 4px 15px rgba(102, 126, 234, 0.4)';
    });
    
    console.log('✨ 前端增强功能已加载');
});

// 错误处理增强
window.addEventListener('error', function(e) {
    console.error('页面错误:', e.error);
    // 可以在这里添加错误上报逻辑
});

// 未处理的Promise拒绝
window.addEventListener('unhandledrejection', function(e) {
    console.error('未处理的Promise拒绝:', e.reason);
});
