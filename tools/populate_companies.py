#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动填充companies表 - 从赔率数据中发现的新公司
"""

from database.connection import get_connection
from core.logger import get_logger
from typing import Dict, Set, List

logger = get_logger("populate_companies")

def extract_companies_from_odds_data() -> Dict[int, Dict[str, str]]:
    """
    从赔率数据中提取公司信息
    通过临时爬取一些赔率数据来获取公司ID和名称的映射
    """
    from scrapers.all_companies_scraper import AllCompaniesOddsScraper
    
    logger.info("正在从赔率数据中提取公司信息...")
    
    # 获取一些测试比赛
    db = get_connection()
    test_matches = db.execute_query("""
        SELECT match_id FROM matches 
        WHERE league_id = 36 AND match_status = 'finished'
        LIMIT 2
    """, fetch='all')
    
    if not test_matches:
        logger.error("没有找到测试比赛")
        return {}
    
    match_ids = [m['match_id'] for m in test_matches]
    
    # 使用全公司爬虫获取数据
    scraper = AllCompaniesOddsScraper()
    result = scraper.scrape_with_all_companies(match_ids, max_workers=2)
    
    companies_info = {}
    
    if result.success:
        for match_result in result.data.values():
            if hasattr(match_result, 'data'):
                odds_data = match_result.data
            else:
                odds_data = match_result
            
            if 'odds' in odds_data:
                for odds in odds_data['odds']:
                    company_id = odds.get('company_id')
                    if company_id:
                        companies_info[company_id] = {
                            'name_en': odds.get('company_name', f'Company_{company_id}'),
                            'name_cn': odds.get('company_name_cn', f'公司_{company_id}'),
                            'website': '',
                            'country': 'Unknown',
                            'is_active': True
                        }
    
    logger.info(f"从赔率数据中提取到 {len(companies_info)} 个公司信息")
    return companies_info

def populate_companies_table():
    """填充companies表"""
    
    print("="*60)
    print("自动填充companies表")
    print("="*60)
    
    db = get_connection()
    
    # 1. 检查现有companies数量
    existing_count = db.execute_query("""
        SELECT COUNT(*) as count FROM companies
    """, fetch='one')
    
    print(f"\n1. 当前companies表中有 {existing_count['count']} 个公司")
    
    # 2. 提取公司信息
    print(f"\n2. 从赔率数据中提取公司信息...")
    companies_info = extract_companies_from_odds_data()
    
    if not companies_info:
        print("没有提取到公司信息")
        return
    
    # 3. 检查哪些公司不存在
    existing_companies = db.execute_query("""
        SELECT company_id FROM companies
    """, fetch='all')
    
    existing_ids = {c['company_id'] for c in existing_companies}
    new_company_ids = set(companies_info.keys()) - existing_ids
    
    print(f"\n3. 发现 {len(new_company_ids)} 个新公司需要添加:")
    for company_id in sorted(new_company_ids):
        info = companies_info[company_id]
        print(f"  - 公司ID {company_id}: {info['name_cn']} ({info['name_en']})")
    
    # 4. 插入新公司
    if new_company_ids:
        print(f"\n4. 正在插入新公司到companies表...")
        
        for company_id in sorted(new_company_ids):
            info = companies_info[company_id]
            
            try:
                db.execute_query("""
                    INSERT INTO companies (
                        company_id, name_en, name_cn, website, country, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    company_id,
                    info['name_en'],
                    info['name_cn'],
                    info['website'],
                    info['country'],
                    info['is_active']
                ))
                
                logger.info(f"插入公司: {company_id} - {info['name_cn']}")
                
            except Exception as e:
                logger.error(f"插入公司 {company_id} 失败: {e}")
        
        print(f"成功插入 {len(new_company_ids)} 个新公司")
    else:
        print(f"\n4. 没有新公司需要添加")
    
    # 5. 最终验证
    final_count = db.execute_query("""
        SELECT COUNT(*) as count FROM companies
    """, fetch='one')
    
    print(f"\n5. 最终companies表中有 {final_count['count']} 个公司")
    print(f"增加了 {final_count['count'] - existing_count['count']} 个公司")
    
    print("\n" + "="*60)
    print("填充完成!")
    print("="*60)

if __name__ == "__main__":
    populate_companies_table()