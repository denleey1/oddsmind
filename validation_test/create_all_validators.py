#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
为所有准备好的联赛创建验证器
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from check_all_leagues import check_all_leagues

def create_league_validator(league_info):
    """为单个联赛创建验证器 - 基于英超验证器修改"""
    
    league_id = league_info['id']
    league_name = league_info['name']
    league_code = league_info['code']
    start_round = league_info['start']
    end_round = league_info['end']
    
    # 读取英超验证器作为模板
    premier_file = Path(__file__).parent / 'premier_league_validator.py'
    if not premier_file.exists():
        raise FileNotFoundError("找不到英超验证器文件")
    
    with open(premier_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换关键参数
    replacements = [
        ('英超历史数据验证器', f'{league_name}历史数据验证器'),
        ('使用已完成的英超38轮比赛数据验证模型准确率', f'使用已完成的{league_name}比赛数据验证模型准确率'),
        ('class PremierLeagueValidator:', f'class {get_class_name(league_name)}Validator:'),
        ('"""英超历史数据验证器"""', f'"""{league_name}历史数据验证器"""'),
        ('self.league_id = 36  # 英超联赛ID', f'self.league_id = {league_id}  # {league_name}联赛ID'),
        ('def validate_premier_league(self, start_round: int = 10, end_round: int = 38)', f'def validate_{league_code}(self, start_round: int = {start_round}, end_round: int = {end_round})'),
        ('"""验证英超比赛数据"""', f'"""验证{league_name}比赛数据"""'),
        ('self.logger.info(f"开始验证英超第{start_round}-{end_round}轮比赛")', f'self.logger.info(f"开始验证{league_name}第{{start_round}}-{{end_round}}轮比赛")'),
        ('table_name: str = \'premier_league_validation_results\'', f'table_name: str = \'{league_code}_validation_results\''),
        ('COMMENT=\'英超验证结果表\'', f'COMMENT=\'{league_name}验证结果表\''),
        ('validator = PremierLeagueValidator()', f'validator = {get_class_name(league_name)}Validator()'),
        ('# 验证第10-38轮比赛', f'# 验证第{start_round}-{end_round}轮比赛'),
        ('results = validator.validate_premier_league(start_round=10, end_round=38)', f'results = validator.validate_{league_code}(start_round={start_round}, end_round={end_round})'),
        ('print(f"\\n英超验证完成！")', f'print(f"\\n{league_name}验证完成！")'),
    ]
    
    # 执行替换
    for old, new in replacements:
        content = content.replace(old, new)
    
    return content

def get_class_name(league_name):
    """生成类名"""
    name_map = {
        '德甲': 'Bundesliga',
        '法甲': 'Ligue1', 
        '韩国K联赛': 'KLeague',
        '日职联': 'JLeague',
        '西甲': 'LaLiga',
        '意甲': 'SerieA',
        '英超': 'PremierLeague'
    }
    return name_map.get(league_name, league_name.replace(' ', ''))

def create_batch_script(ready_leagues):
    """创建批量验证脚本"""
    
    script_content = '''@echo off
echo ========================================
echo 七大联赛验证批量执行脚本
echo ========================================
echo.

'''
    
    for league in ready_leagues:
        script_content += f'''echo 开始验证{league["name"]}...
python {league["code"]}_validator.py
echo {league["name"]}验证完成
echo.

'''
    
    script_content += '''echo ========================================
echo 所有联赛验证完成！
echo ========================================
pause
'''
    
    return script_content

def main():
    """主函数"""
    print("检查联赛数据状态...")
    ready_leagues = check_all_leagues()
    
    if not ready_leagues:
        print("没有可验证的联赛，退出。")
        return
    
    print(f"\n开始为 {len(ready_leagues)} 个联赛创建验证器...")
    
    # 创建各联赛验证器
    for league in ready_leagues:
        validator_code = create_league_validator(league)
        filename = f"{league['code']}_validator.py"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(validator_code)
        
        print(f"✅ 已创建: {filename}")
    
    # 创建批量执行脚本
    batch_script = create_batch_script(ready_leagues)
    with open('validate_all_leagues.bat', 'w', encoding='utf-8') as f:
        f.write(batch_script)
    
    print("✅ 已创建: validate_all_leagues.bat")
    
    # 创建Python批量执行脚本
    python_batch = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Python版本的批量验证脚本
"""

import subprocess
import sys
from datetime import datetime

def run_validator(script_name, league_name):
    """运行单个验证器"""
    print(f"\\n{'='*50}")
    print(f"开始验证{league_name}...")
    print(f"执行: python {script_name}")
    print(f"{'='*50}")
    
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print(f"✅ {league_name}验证成功")
            print("输出:")
            print(result.stdout)
        else:
            print(f"❌ {league_name}验证失败")
            print("错误:")
            print(result.stderr)
        
    except Exception as e:
        print(f"❌ {league_name}验证异常: {e}")

def main():
    """主函数"""
    start_time = datetime.now()
    print("七大联赛验证批量执行脚本 (Python版)")
    print(f"开始时间: {start_time}")
    
'''
    
    for league in ready_leagues:
        python_batch += f'    run_validator("{league["code"]}_validator.py", "{league["name"]}")\n'
    
    python_batch += '''
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\\n{'='*50}")
    print("所有联赛验证完成！")
    print(f"结束时间: {end_time}")
    print(f"总耗时: {duration}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
'''
    
    with open('validate_all_leagues.py', 'w', encoding='utf-8') as f:
        f.write(python_batch)
    
    print("✅ 已创建: validate_all_leagues.py")
    
    print(f"\n🎉 所有验证脚本已创建完成！")
    print(f"共创建 {len(ready_leagues)} 个联赛验证器 + 2个批量执行脚本")
    print("\n使用方法:")
    print("1. Windows: 双击运行 validate_all_leagues.bat")
    print("2. Python: python validate_all_leagues.py")
    print("3. 单独运行: python [联赛代码]_validator.py")

if __name__ == "__main__":
    main()