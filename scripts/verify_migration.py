#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
迁移验证脚本
用于验证数据库和应用迁移是否成功
"""

import sys
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import json

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

try:
    from database.connection import get_connection
    from core.logger import get_logger
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保在正确的环境中运行此脚本")
    sys.exit(1)

logger = get_logger(__name__)

class MigrationVerifier:
    def __init__(self):
        self.results = {
            'database': {},
            'application': {},
            'services': {},
            'functionality': {}
        }
        
    def print_header(self, title):
        """打印标题"""
        print("\n" + "="*60)
        print(f" {title}")
        print("="*60)
    
    def print_result(self, test_name, success, details=None):
        """打印测试结果"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
    
    def verify_database_connection(self):
        """验证数据库连接"""
        self.print_header("数据库连接验证")
        
        try:
            db = get_connection()
            result = db.execute_query("SELECT 1 as test", fetch='one')
            success = result and result['test'] == 1
            db.close()
            
            self.print_result("数据库连接", success)
            self.results['database']['connection'] = success
            return success
            
        except Exception as e:
            self.print_result("数据库连接", False, f"错误: {e}")
            self.results['database']['connection'] = False
            return False
    
    def verify_database_structure(self):
        """验证数据库结构"""
        self.print_header("数据库结构验证")
        
        expected_tables = [
            'leagues', 'teams', 'matches', 'companies',
            'european_odds', 'odds_changes', 'over_under_odds_changes', 'odds_analysis_results',
            'fundamental_analysis', 'team_power_ratings', 'standings'
        ]
        
        try:
            db = get_connection()
            
            # 获取所有表
            result = db.execute_query("SHOW TABLES", fetch='all')
            existing_tables = [list(row.values())[0] for row in result]
            
            missing_tables = []
            for table in expected_tables:
                if table not in existing_tables:
                    missing_tables.append(table)
            
            if missing_tables:
                self.print_result("表结构完整性", False, f"缺失表: {missing_tables}")
                self.results['database']['structure'] = False
            else:
                self.print_result("表结构完整性", True, f"所有 {len(expected_tables)} 个表都存在")
                self.results['database']['structure'] = True
            
            # 检查关键字段
            critical_checks = [
                ("matches", "match_id"),
                ("odds_analysis_results", "analyzed_at"),
                ("odds_changes", "last_updated"),
                ("over_under_odds_changes", "last_updated")
            ]
            
            for table, column in critical_checks:
                try:
                    db.execute_query(f"SELECT {column} FROM {table} LIMIT 1", fetch='one')
                    self.print_result(f"{table}.{column}", True)
                except Exception as e:
                    self.print_result(f"{table}.{column}", False, str(e))
            
            db.close()
            return not missing_tables
            
        except Exception as e:
            self.print_result("数据库结构验证", False, f"错误: {e}")
            self.results['database']['structure'] = False
            return False
    
    def verify_data_integrity(self):
        """验证数据完整性"""
        self.print_header("数据完整性验证")
        
        try:
            db = get_connection()
            
            # 数据量检查
            data_checks = {
                'matches': 'SELECT COUNT(*) as count FROM matches',
                'teams': 'SELECT COUNT(*) as count FROM teams',
                'leagues': 'SELECT COUNT(*) as count FROM leagues',
                'companies': 'SELECT COUNT(*) as count FROM companies',
                'odds_analysis_results': 'SELECT COUNT(*) as count FROM odds_analysis_results',
                'odds_changes': 'SELECT COUNT(*) as count FROM odds_changes',
                'over_under_odds_changes': 'SELECT COUNT(*) as count FROM over_under_odds_changes'
            }
            
            all_good = True
            for table, query in data_checks.items():
                try:
                    result = db.execute_query(query, fetch='one')
                    count = result['count'] if result else 0
                    
                    if count > 0:
                        self.print_result(f"{table} 数据", True, f"{count:,} 条记录")
                    else:
                        self.print_result(f"{table} 数据", False, "无数据")
                        if table in ['matches', 'teams']:  # 关键表
                            all_good = False
                            
                except Exception as e:
                    self.print_result(f"{table} 数据检查", False, str(e))
                    all_good = False
            
            # 数据时间范围检查
            time_checks = [
                ("matches", "match_time", "����ʱ��"),
                ("odds_analysis_results", "analyzed_at", "����ʱ��"),
                ("odds_changes", "last_updated", "���ʸ���ʱ��"),
                ("over_under_odds_changes", "last_updated", "��С�����ʱ��")
            ]
            
            for table, time_field, desc in time_checks:
                try:
                    query = f"SELECT MIN({time_field}) as earliest, MAX({time_field}) as latest FROM {table} WHERE {time_field} IS NOT NULL"
                    result = db.execute_query(query, fetch='one')
                    
                    if result and result['earliest'] and result['latest']:
                        earliest = result['earliest']
                        latest = result['latest']
                        
                        # 检查时间范围是否合理
                        if isinstance(earliest, datetime) and isinstance(latest, datetime):
                            days_span = (latest - earliest).days
                            self.print_result(f"{desc}范围", True, 
                                           f"{earliest} 到 {latest} ({days_span} 天)")
                        else:
                            self.print_result(f"{desc}范围", True, f"{earliest} 到 {latest}")
                    else:
                        self.print_result(f"{desc}范围", False, "无有效时间数据")
                        
                except Exception as e:
                    self.print_result(f"{desc}范围检查", False, str(e))
            
            # 数据关联性检查
            association_checks = [
                ("比赛-队伍关联", "SELECT COUNT(*) FROM matches m JOIN teams h ON m.home_team_id = h.team_id JOIN teams a ON m.away_team_id = a.team_id"),
                ("分析结果-比赛关联", "SELECT COUNT(*) FROM odds_analysis_results oar JOIN matches m ON oar.match_id = m.match_id"),
                ("赔率变化-比赛关联", "SELECT COUNT(*) FROM odds_changes oc JOIN matches m ON oc.match_id = m.match_id")
            ]
            
            for desc, query in association_checks:
                try:
                    result = db.execute_query(query, fetch='one')
                    count = list(result.values())[0] if result else 0
                    
                    if count > 0:
                        self.print_result(desc, True, f"{count:,} 条关联记录")
                    else:
                        self.print_result(desc, False, "无关联数据")
                        
                except Exception as e:
                    self.print_result(desc, False, str(e))
            
            db.close()
            self.results['database']['integrity'] = all_good
            return all_good
            
        except Exception as e:
            self.print_result("数据完整性验证", False, f"错误: {e}")
            self.results['database']['integrity'] = False
            return False
    
    def verify_application_startup(self):
        """验证应用启动"""
        self.print_header("应用启动验证")
        
        # 检查Python环境
        try:
            import flask, mysql.connector, requests, apscheduler
            self.print_result("Python依赖", True)
            self.results['application']['dependencies'] = True
        except ImportError as e:
            self.print_result("Python依赖", False, f"缺失依赖: {e}")
            self.results['application']['dependencies'] = False
        
        # 检查配置文件
        config_files = [
            PROJECT_ROOT / ".env.production",
            PROJECT_ROOT / "config" / "database_config.py"
        ]
        
        config_ok = True
        for config_file in config_files:
            if config_file.exists():
                self.print_result(f"配置文件 {config_file.name}", True)
            else:
                self.print_result(f"配置文件 {config_file.name}", False, "文件不存在")
                config_ok = False
        
        self.results['application']['config'] = config_ok
        
        # 检查关键模块导入
        try:
            from odds_analysis.main_analyzer import MainAnalyzer
            from monitoring.odds_monitor import OddsChangeMonitor
            from database.manager import DatabaseManager
            
            self.print_result("核心模块导入", True)
            self.results['application']['modules'] = True
            
        except ImportError as e:
            self.print_result("核心模块导入", False, str(e))
            self.results['application']['modules'] = False
    
    def verify_web_service(self):
        """验证Web服务"""
        self.print_header("Web服务验证")
        
        test_urls = [
            ("主页", "http://localhost:8889/"),
            ("健康检查", "http://localhost:8889/health"),
            ("API状态", "http://localhost:8889/api/matches/recent")
        ]
        
        all_good = True
        for desc, url in test_urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    self.print_result(f"Web服务 - {desc}", True, f"状态码: {response.status_code}")
                else:
                    self.print_result(f"Web服务 - {desc}", False, f"状态码: {response.status_code}")
                    all_good = False
                    
            except requests.exceptions.RequestException as e:
                self.print_result(f"Web服务 - {desc}", False, str(e))
                all_good = False
        
        self.results['services']['web'] = all_good
        return all_good
    
    def verify_system_services(self):
        """验证系统服务"""
        self.print_header("系统服务验证")
        
        services = ['oddsmind', 'nginx', 'mysql']
        
        all_good = True
        for service in services:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', service],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout.strip() == 'active':
                    self.print_result(f"服务 {service}", True, "运行中")
                else:
                    self.print_result(f"服务 {service}", False, "未运行")
                    all_good = False
                    
            except Exception as e:
                self.print_result(f"服务 {service}", False, str(e))
                all_good = False
        
        self.results['services']['system'] = all_good
        return all_good
    
    def verify_functionality(self):
        """验证功能性"""
        self.print_header("功能性验证")
        
        try:
            # 测试数据分析功能
            from odds_analysis.main_analyzer import MainAnalyzer
            
            analyzer = MainAnalyzer()
            
            # 找一个有数据的比赛进行测试
            db = get_connection()
            test_match = db.execute_query(
                "SELECT match_id FROM matches WHERE match_id IN (SELECT DISTINCT match_id FROM odds_changes) LIMIT 1",
                fetch='one'
            )
            
            if test_match:
                match_id = test_match['match_id']
                
                # 测试分析功能
                try:
                    # 这里不实际执行分析，只测试能否调用
                    match_info = analyzer.repository.get_match_info(match_id)
                    if match_info:
                        self.print_result("分析功能测试", True, f"成功获取比赛 {match_id} 信息")
                        self.results['functionality']['analysis'] = True
                    else:
                        self.print_result("分析功能测试", False, "无法获取比赛信息")
                        self.results['functionality']['analysis'] = False
                        
                except Exception as e:
                    self.print_result("分析功能测试", False, str(e))
                    self.results['functionality']['analysis'] = False
            else:
                self.print_result("分析功能测试", False, "没有可测试的比赛数据")
                self.results['functionality']['analysis'] = False
            
            analyzer.close()
            db.close()
            
        except Exception as e:
            self.print_result("功能性验证", False, str(e))
            self.results['functionality']['analysis'] = False
    
    def generate_report(self):
        """生成验证报告"""
        self.print_header("迁移验证报告")
        
        # 统计结果
        total_tests = 0
        passed_tests = 0
        
        def count_results(section):
            nonlocal total_tests, passed_tests
            for key, value in section.items():
                total_tests += 1
                if value:
                    passed_tests += 1
        
        count_results(self.results['database'])
        count_results(self.results['application'])
        count_results(self.results['services'])
        count_results(self.results['functionality'])
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n📊 总体结果: {passed_tests}/{total_tests} 测试通过 ({success_rate:.1f}%)")
        
        # 分类结果
        categories = [
            ("数据库", self.results['database']),
            ("应用", self.results['application']),
            ("服务", self.results['services']),
            ("功能", self.results['functionality'])
        ]
        
        for category_name, category_results in categories:
            category_passed = sum(1 for v in category_results.values() if v)
            category_total = len(category_results)
            category_rate = (category_passed / category_total * 100) if category_total > 0 else 0
            
            status_icon = "✅" if category_passed == category_total else "⚠️" if category_passed > 0 else "❌"
            print(f"{status_icon} {category_name}: {category_passed}/{category_total} ({category_rate:.1f}%)")
        
        # 建议
        print("\n💡 建议:")
        if success_rate >= 90:
            print("✅ 迁移成功！系统可以正常使用。")
        elif success_rate >= 70:
            print("⚠️  迁移基本成功，但有一些问题需要解决。")
        else:
            print("❌ 迁移存在重大问题，需要检查和修复。")
        
        # 保存报告
        report_file = PROJECT_ROOT / f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'success_rate': success_rate
                },
                'results': self.results
            }
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n📋 详细报告已保存到: {report_file}")
        
        return success_rate >= 80  # 80%以上通过率认为迁移成功

def main():
    """主函数"""
    print("🔍 OddsMind 迁移验证工具")
    print("=" * 60)
    print("此工具将验证数据库迁移和应用部署是否成功")
    
    verifier = MigrationVerifier()
    
    # 执行验证步骤
    steps = [
        verifier.verify_database_connection,
        verifier.verify_database_structure,
        verifier.verify_data_integrity,
        verifier.verify_application_startup,
        verifier.verify_web_service,
        verifier.verify_system_services,
        verifier.verify_functionality
    ]
    
    for step in steps:
        try:
            step()
        except Exception as e:
            print(f"❌ 验证步骤失败: {e}")
    
    # 生成最终报告
    success = verifier.generate_report()
    
    # 返回退出代码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()