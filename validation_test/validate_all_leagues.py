#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Python版本的批量验证脚本
"""

import subprocess
import sys
from datetime import datetime

def run_validator(script_name, league_name):
    """运行单个验证器"""
    print(f"\n{'='*50}")
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
    
    run_validator("bundesliga_validator.py", "德甲")
    run_validator("ligue1_validator.py", "法甲")
    run_validator("kleague_validator.py", "韩国K联赛")
    run_validator("jleague_validator.py", "日职联")
    run_validator("laliga_validator.py", "西甲")
    run_validator("seriea_validator.py", "意甲")
    run_validator("premier_validator.py", "英超")

    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{'='*50}")
    print("所有联赛验证完成！")
    print(f"结束时间: {end_time}")
    print(f"总耗时: {duration}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
