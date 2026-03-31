#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库完整导出脚本
用于迁移前的数据备份
"""

import subprocess
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger

logger = get_logger(__name__)

class DatabaseExporter:
    def __init__(self):
        self.backup_dir = PROJECT_ROOT / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # 从现有连接获取数据库配置
        self.db = get_connection()
        self.config = self.db.config
        
    def export_complete_database(self):
        """导出完整数据库（结构+数据）"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"oddsmind_complete_{timestamp}.sql"
        
        logger.info(f"开始导出完整数据库到: {backup_file}")
        
        # 构建mysqldump命令
        cmd = [
            "mysqldump",
            f"-h{self.config['host']}",
            f"-P{self.config['port']}",
            f"-u{self.config['user']}",
            f"-p{self.config['password']}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--set-gtid-purged=OFF",
            "--databases",
            self.config['database']
        ]
        
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
                
            if result.returncode == 0:
                file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
                logger.info(f"✅ 数据库导出成功!")
                logger.info(f"   文件: {backup_file}")
                logger.info(f"   大小: {file_size:.2f} MB")
                return str(backup_file)
            else:
                logger.error(f"❌ 数据库导出失败: {result.stderr}")
                if backup_file.exists():
                    backup_file.unlink()
                return None
                
        except Exception as e:
            logger.error(f"❌ 导出过程异常: {e}")
            if backup_file.exists():
                backup_file.unlink()
            return None
    
    def export_schema_only(self):
        """仅导出数据库结构"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        schema_file = self.backup_dir / f"oddsmind_schema_{timestamp}.sql"
        
        logger.info(f"导出数据库结构到: {schema_file}")
        
        cmd = [
            "mysqldump",
            f"-h{self.config['host']}",
            f"-P{self.config['port']}",
            f"-u{self.config['user']}",
            f"-p{self.config['password']}",
            "--no-data",
            "--routines",
            "--triggers",
            "--set-gtid-purged=OFF",
            self.config['database']
        ]
        
        try:
            with open(schema_file, 'w', encoding='utf-8') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
                
            if result.returncode == 0:
                logger.info(f"✅ 数据库结构导出成功: {schema_file}")
                return str(schema_file)
            else:
                logger.error(f"❌ 结构导出失败: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 结构导出异常: {e}")
            return None
    
    def export_data_only(self):
        """仅导出数据"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_file = self.backup_dir / f"oddsmind_data_{timestamp}.sql"
        
        logger.info(f"导出数据到: {data_file}")
        
        cmd = [
            "mysqldump",
            f"-h{self.config['host']}",
            f"-P{self.config['port']}",
            f"-u{self.config['user']}",
            f"-p{self.config['password']}",
            "--no-create-info",
            "--single-transaction",
            "--set-gtid-purged=OFF",
            self.config['database']
        ]
        
        try:
            with open(data_file, 'w', encoding='utf-8') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
                
            if result.returncode == 0:
                logger.info(f"✅ 数据导出成功: {data_file}")
                return str(data_file)
            else:
                logger.error(f"❌ 数据导出失败: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 数据导出异常: {e}")
            return None
    
    def verify_database_content(self):
        """验证数据库内容"""
        logger.info("Verifying database content...")
        
        # 关键统计信息
        stats_queries = {
            'matches': 'SELECT COUNT(*) as count FROM matches',
            'odds_analysis_results': 'SELECT COUNT(*) as count FROM odds_analysis_results', 
            'odds_changes': 'SELECT COUNT(*) as count FROM odds_changes',
            'over_under_odds_changes': 'SELECT COUNT(*) as count FROM over_under_odds_changes',
            'european_odds': 'SELECT COUNT(*) as count FROM european_odds',
            'teams': 'SELECT COUNT(*) as count FROM teams',
            'leagues': 'SELECT COUNT(*) as count FROM leagues',
            'companies': 'SELECT COUNT(*) as count FROM companies'
        }
        
        stats = {}
        for table, query in stats_queries.items():
            try:
                result = self.db.execute_query(query, fetch='one')
                stats[table] = result['count'] if result else 0
            except Exception as e:
                logger.warning(f"无法获取表 {table} 的统计: {e}")
                stats[table] = 'ERROR'
        
        # 数据时间范围
        time_queries = {
            'matches_time_range': '''
                SELECT 
                    MIN(match_time) as earliest,
                    MAX(match_time) as latest
                FROM matches
            ''',
            'analysis_time_range': '''
                SELECT 
                    MIN(analyzed_at) as earliest,
                    MAX(analyzed_at) as latest  
                FROM odds_analysis_results
            ''',
            'odds_changes_time_range': '''
                SELECT 
                    MIN(last_updated) as earliest,
                    MAX(last_updated) as latest
                FROM odds_changes
            ''',
            'over_under_time_range': '''
                SELECT 
                    MIN(last_updated) as earliest,
                    MAX(last_updated) as latest
                FROM over_under_odds_changes
            '''
        }
        
        time_ranges = {}
        for name, query in time_queries.items():
            try:
                result = self.db.execute_query(query, fetch='one')
                if result:
                    time_ranges[name] = {
                        'earliest': result['earliest'],
                        'latest': result['latest']
                    }
                else:
                    time_ranges[name] = {'earliest': None, 'latest': None}
            except Exception as e:
                logger.warning(f"无法获取时间范围 {name}: {e}")
                time_ranges[name] = {'earliest': 'ERROR', 'latest': 'ERROR'}
        
        # 输出验证报告
        logger.info("Database Content Verification Report:")
        logger.info("=" * 50)
        
        logger.info("Table Statistics:")
        for table, count in stats.items():
            logger.info(f"   {table}: {count:,}")
        
        logger.info("\nData Time Ranges:")
        for name, time_range in time_ranges.items():
            if time_range['earliest'] and time_range['latest']:
                logger.info(f"   {name}:")
                logger.info(f"     最早: {time_range['earliest']}")
                logger.info(f"     最新: {time_range['latest']}")
            else:
                logger.info(f"   {name}: 无数据")
        
        return {
            'stats': stats,
            'time_ranges': time_ranges
        }
    
    def create_verification_report(self, backup_file):
        """创建验证报告"""
        if not backup_file:
            return None
            
        report_file = Path(backup_file).with_suffix('.report.txt')
        
        # 获取验证信息
        db_stats = self.verify_database_content()
        
        # 获取文件信息
        backup_path = Path(backup_file)
        file_size = backup_path.stat().st_size / (1024 * 1024)  # MB
        
        # 生成报告
        report_content = f"""
OddsMind 数据库备份验证报告
============================================
备份文件: {backup_file}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
文件大小: {file_size:.2f} MB

数据库配置:
- 主机: {self.config['host']}:{self.config['port']}
- 数据库: {self.config['database']}
- 用户: {self.config['user']}

表数据统计:
"""
        
        for table, count in db_stats['stats'].items():
            report_content += f"- {table}: {count:,}\n"
        
        report_content += "\n数据时间范围:\n"
        for name, time_range in db_stats['time_ranges'].items():
            if time_range['earliest'] and time_range['latest']:
                report_content += f"- {name}:\n"
                report_content += f"  最早: {time_range['earliest']}\n"
                report_content += f"  最新: {time_range['latest']}\n"
        
        # 写入报告文件
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"📋 验证报告已生成: {report_file}")
        return str(report_file)
    
    def cleanup_old_backups(self, keep_days=30):
        """清理旧备份文件"""
        logger.info(f"🧹 清理 {keep_days} 天前的备份文件...")
        
        current_time = datetime.now()
        removed_count = 0
        
        for backup_file in self.backup_dir.glob("oddsmind_*.sql"):
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
            age_days = (current_time - file_time).days
            
            if age_days > keep_days:
                backup_file.unlink()
                # 同时删除对应的报告文件
                report_file = backup_file.with_suffix('.report.txt')
                if report_file.exists():
                    report_file.unlink()
                removed_count += 1
                logger.info(f"   删除旧备份: {backup_file.name} (已存在 {age_days} 天)")
        
        if removed_count > 0:
            logger.info(f"✅ 已清理 {removed_count} 个旧备份文件")
        else:
            logger.info("✅ 没有需要清理的旧备份文件")

def main():
    """主函数"""
    print("OddsMind Database Export Tool")
    print("=" * 50)
    
    exporter = DatabaseExporter()
    
    # 先验证当前数据库状态
    exporter.verify_database_content()
    
    # 导出完整数据库
    backup_file = exporter.export_complete_database()
    
    if backup_file:
        # 生成验证报告
        exporter.create_verification_report(backup_file)
        
        # 清理旧备份
        exporter.cleanup_old_backups()
        
        print("\n" + "=" * 50)
        print("[SUCCESS] Database export completed!")
        print(f"Backup file: {backup_file}")
        print(f"Report file: {backup_file.replace('.sql', '.report.txt')}")
        print("\nMigration steps:")
        print("1. Copy backup file to target server")
        print("2. Create database and user on target server")
        print("3. Import backup: mysql -u user -p database < backup_file.sql")
        print("4. Verify import results")
        
    else:
        print("\n[ERROR] Database export failed!")
        print("Please check MySQL configuration and permissions")
        sys.exit(1)

if __name__ == "__main__":
    main()