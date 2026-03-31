#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OddsMind 综合分析预测系统主启动脚本
整合所有服务组件，提供统一的启动入口
"""
import sys
import signal
import argparse
from pathlib import Path
from datetime import datetime
import threading
import time

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

from app_environment import get_environment_manager
from core.logger import get_logger, setup_logging
from services.prediction_api import PredictionAPI
from services.scheduled_tasks import ScheduledTasks
from services.daily_update_service import DailyUpdateService

_ENV_MANAGER = get_environment_manager()
setup_logging(_ENV_MANAGER.config.logging)
logger = get_logger(__name__)

class OddsMindSystem:
    """OddsMind综合分析预测系统"""
    
    def __init__(self):
        """初始化系统"""
        self.api_service = None
        self.scheduler = None
        self.running = False
        self.start_time = None
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("OddsMind系统初始化完成")
    
    def start_api_service(self, host: str = '0.0.0.0', port: int = 8888, debug: bool = False):
        """启动API服务"""
        try:
            self.api_service = PredictionAPI(host=host, port=port)
            
            # 在单独线程中启动API服务
            api_thread = threading.Thread(
                target=self.api_service.run,
                kwargs={'debug': debug},
                daemon=True,
                name="API-Service"
            )
            api_thread.start()
            
            logger.info(f"API服务已在线程中启动: {host}:{port}")
            return api_thread
            
        except Exception as e:
            logger.error(f"启动API服务失败: {e}")
            raise
    
    def start_scheduler(self):
        """启动定时任务调度器"""
        try:
            self.scheduler = ScheduledTasks()
            self.scheduler.setup_default_tasks()
            self.scheduler.start()
            
            logger.info("定时任务调度器已启动")
            
        except Exception as e:
            logger.error(f"启动定时任务调度器失败: {e}")
            raise
    
    def run_full_system(self, api_host: str = '0.0.0.0', api_port: int = 8888, 
                       enable_scheduler: bool = True, debug: bool = False):
        """运行完整系统"""
        try:
            logger.info("="*60)
            logger.info("启动 OddsMind 综合分析预测系统")
            logger.info("="*60)
            
            self.start_time = datetime.utcnow()
            self.running = True
            
            # 启动API服务
            api_thread = self.start_api_service(host=api_host, port=api_port, debug=debug)
            
            # 启动定时任务调度器
            if enable_scheduler:
                self.start_scheduler()
            
            logger.info("系统启动完成！")
            logger.info("-"*60)
            logger.info("服务状态:")
            logger.info(f"  📡 API服务: http://{api_host}:{api_port}")
            logger.info(f"  ⏰ 定时任务: {'启用' if enable_scheduler else '禁用'}")
            logger.info(f"  🕐 启动时间: {self.start_time.isoformat()}")
            logger.info("-"*60)
            logger.info("可用API端点:")
            logger.info("  GET  /api/health                       - 健康检查")
            logger.info("  GET  /api/analyze/<match_id>           - 分析比赛")
            logger.info("  POST /api/monitor/start/<match_id>     - 开始监控")
            logger.info("  GET  /api/monitor/status               - 监控状态")
            logger.info("  GET  /api/matches/recent               - 最近比赛")
            logger.info("  GET  /api/stats                        - 系统统计")
            logger.info("-"*60)
            logger.info("按 Ctrl+C 停止系统")
            
            # 主循环
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("收到停止信号...")
            
            self.shutdown()
            
        except Exception as e:
            logger.error(f"运行系统失败: {e}")
            self.shutdown()
            raise
    
    def run_api_only(self, host: str = '0.0.0.0', port: int = 8888, debug: bool = False):
        """仅运行API服务"""
        try:
            logger.info("启动API服务模式")
            
            self.api_service = PredictionAPI(host=host, port=port)
            self.api_service.run(debug=debug)
            
        except KeyboardInterrupt:
            logger.info("API服务停止")
        except Exception as e:
            logger.error(f"API服务异常: {e}")
            raise
    
    def run_update_only(self):
        """仅运行数据更新任务"""
        try:
            logger.info("启动数据更新模式")
            
            update_service = DailyUpdateService()
            update_service.daily_update_job()
            
            logger.info("数据更新完成")
            
        except Exception as e:
            logger.error(f"数据更新失败: {e}")
            raise
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，准备停止系统...")
        self.running = False
    
    def shutdown(self):
        """关闭系统"""
        logger.info("正在关闭系统...")
        
        try:
            # 停止定时任务调度器
            if self.scheduler:
                self.scheduler.stop()
                logger.info("定时任务调度器已停止")
            
            # 停止API服务
            if self.api_service:
                self.api_service.stop()
                logger.info("API服务已停止")
            
            self.running = False
            
            if self.start_time:
                runtime = datetime.utcnow() - self.start_time
                logger.info(f"系统运行时长: {runtime}")
            
            logger.info("OddsMind系统已完全关闭")
            
        except Exception as e:
            logger.error(f"关闭系统时出错: {e}")
    
    def get_system_status(self) -> dict:
        """获取系统状态"""
        status = {
            'running': self.running,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'api_service': self.api_service is not None,
            'scheduler': self.scheduler is not None
        }
        
        if self.start_time:
            runtime = datetime.utcnow() - self.start_time
            status['runtime_seconds'] = runtime.total_seconds()
        
        if self.scheduler:
            status['scheduler_status'] = self.scheduler.get_status()
        
        return status


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="OddsMind综合分析预测系统")
    
    parser.add_argument('--mode', type=str, 
                       choices=['full', 'api-only', 'update-only'], 
                       default='full',
                       help='运行模式: full=完整系统, api-only=仅API服务, update-only=仅数据更新')
    
    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='API服务主机地址 (默认: 0.0.0.0)')
    
    parser.add_argument('--port', type=int, default=8888,
                       help='API服务端口 (默认: 8888)')
    
    parser.add_argument('--debug', action='store_true',
                       help='启用调试模式')
    
    parser.add_argument('--no-scheduler', action='store_true',
                       help='禁用定时任务调度器')
    
    parser.add_argument('--log-level', type=str, 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO',
                       help='日志级别 (默认: INFO)')
    
    args = parser.parse_args()
    
    # 设置日志级别
    setup_logging(_ENV_MANAGER.config.logging, level=args.log_level)
    
    # 创建系统实例
    system = OddsMindSystem()
    
    try:
        if args.mode == 'full':
            system.run_full_system(
                api_host=args.host,
                api_port=args.port,
                enable_scheduler=not args.no_scheduler,
                debug=args.debug
            )
        elif args.mode == 'api-only':
            system.run_api_only(
                host=args.host,
                port=args.port,
                debug=args.debug
            )
        elif args.mode == 'update-only':
            system.run_update_only()
        
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"系统运行异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
