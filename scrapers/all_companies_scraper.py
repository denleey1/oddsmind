#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
All Companies Odds Scraper - 解析所有庄家公司的赔率数据
"""

from .odds_scraper import OddsScraperModern
from typing import Dict, Any, Optional, List
from core.logger import get_logger
from config.companies_config import CompanyInfo
from concurrent.futures import ThreadPoolExecutor


class AllCompaniesOddsScraper(OddsScraperModern):
    """
    解析所有庄家公司的赔率爬虫
    继承自OddsScraperModern，但强制解析所有公司的数据
    统一使用scrape()方法，自动优化监控场景
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, executor: Optional[ThreadPoolExecutor] = None):
        """
        初始化全公司赔率爬虫
        
        Args:
            config: 可选的配置覆盖
            executor: 可选的外部线程池执行器
        """
        # 调用父类，但设置parse_all_companies=True
        super().__init__(
            company_filter=None,
            target_companies=None, 
            parse_all_companies=True,  # 关键参数：解析所有公司
            config=config,
            executor=executor  # 传递executor
        )
        
        self.logger = get_logger(self.__class__.__name__)
        self.logger.info("All companies odds scraper initialized - will parse ALL bookmaker companies")
    
    def scrape(
        self,
        match_ids: List[int],
        max_workers: Optional[int] = None,
        skip_existing: bool = True,
        force_refresh_for_monitoring: bool = False,
        **kwargs
    ):
        """
        重写scrape方法，支持监控优化
        
        Args:
            match_ids: 比赛ID列表
            max_workers: 最大并发数
            skip_existing: 是否跳过已存在的数据
            force_refresh_for_monitoring: 是否强制刷新（监控模式）
            **kwargs: 其他参数
            
        Returns:
            包含所有公司赔率数据的ScrapingResult
        """
        # 监控模式：强制重新抓取最新数据
        if force_refresh_for_monitoring:
            skip_existing = False
            self.logger.info(f"监控模式：强制刷新 {len(match_ids)} 场比赛的所有公司赔率数据")
        else:
            self.logger.info(f"开始爬取 {len(match_ids)} 场比赛的所有公司赔率数据")
        
        # 调用父类的scrape方法
        result = super().scrape(
            match_ids=match_ids,
            max_workers=max_workers,
            skip_existing=skip_existing,
            **kwargs
        )
        
        # 统计解析到的公司数量（保持原有功能）
        if result.success and result.data:
            all_companies = set()
            total_odds_records = 0
            
            for match_id, match_result in result.data.items():
                if hasattr(match_result, 'data'):
                    odds_data = match_result.data
                else:
                    odds_data = match_result
                
                if isinstance(odds_data, dict) and 'odds' in odds_data:
                    for odds_record in odds_data['odds']:
                        if 'company_id' in odds_record:
                            all_companies.add(odds_record['company_id'])
                            total_odds_records += 1
            
            self.logger.info(
                f"解析完成 - 发现 {len(all_companies)} 个不同的庄家公司，"
                f"共 {total_odds_records} 条赔率记录"
            )
            if all_companies:
                self.logger.info(f"庄家公司ID列表: {sorted(all_companies)}")
        
        return result
    
    def get_expected_companies_info(self) -> str:
        """返回期望解析的公司信息"""
        return (
            "此爬虫将解析赔率页面中的所有庄家公司数据，"
            "包括但不限于：香港马会、威廉希尔、Bet365、易胜博、"
            "BWIN、Ladbrokes、12BET等所有提供赔率的公司"
        )
    
    def scrape_with_all_companies(
        self,
        match_ids: List[int],
        max_workers: Optional[int] = None,
        **kwargs
    ):
        """
        爬取指定比赛的所有公司赔率数据
        [兼容方法] 现在直接调用统一的scrape()方法
        
        Args:
            match_ids: 比赛ID列表
            max_workers: 最大并发数
            **kwargs: 其他参数
            
        Returns:
            包含所有公司赔率数据的ScrapingResult
        """
        # 使用监控优化模式调用统一的scrape方法
        return self.scrape(
            match_ids=match_ids,
            max_workers=max_workers,
            force_refresh_for_monitoring=True,  # 监控模式
            **kwargs
        )


def create_all_companies_scraper(config: Optional[Dict[str, Any]] = None) -> AllCompaniesOddsScraper:
    """
    创建全公司赔率爬虫的工厂函数
    
    Args:
        config: 可选配置
        
    Returns:
        AllCompaniesOddsScraper实例
    """
    return AllCompaniesOddsScraper(config=config)