#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
J1(日职联) 批量验证桥接脚本

流程：
1) 从 main 入口批量执行赔率分析并写入数据库
2) 运行单联赛验证器，输出验证结果概览
"""

import argparse
import subprocess
import sys


def run_cmd(cmd: str) -> int:
    print(f"\n>>> {cmd}")
    return subprocess.call(cmd, shell=True)


def main():
    parser = argparse.ArgumentParser(description="J1(日职联) 批量验证")
    parser.add_argument("--limit", type=int, default=500, help="分析的最近比赛数量")
    parser.add_argument("--season", default="2025", help="实力计算赛季标记，仅展示")
    args = parser.parse_args()

    # 1) 批量赔率分析写库
    rc = run_cmd(f"python main.py analyze-odds --league-id 25 --limit {args.limit}")
    if rc != 0:
        print("批量赔率分析失败，停止后续步骤。")
        sys.exit(rc)

    # 2) 运行联赛验证器（固定J1=25）
    rc = run_cmd("python validation_test/optimized_validator_fixed.py --league-id 25")
    if rc != 0:
        print("联赛验证器运行失败。")
        sys.exit(rc)

    # 3) 生成Markdown报告（可选）
    rc = run_cmd("python validation_test/generate_md_report.py")
    if rc != 0:
        print("报告生成失败。")
        sys.exit(rc)

    print("\nJ1(日职联) 批量验证流程完成。")


if __name__ == "__main__":
    main()

