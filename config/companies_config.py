#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bookmaker companies configuration.
Comprehensive configuration for all supported betting companies.
"""

from typing import Dict, List, NamedTuple


class CompanyInfo(NamedTuple):
    """Company information structure."""
    company_id: int
    name_en: str
    name_cn: str
    country: str
    website: str
    is_main: bool = False
    is_asian: bool = False
    priority: int = 100
    is_active: bool = True


# All supported companies
COMPANIES_CONFIG: Dict[str, CompanyInfo] = {
    
    # Tier 1 - Premier bookmakers (highest priority)
    "hkjc": CompanyInfo(
        company_id=432,
        name_en="HKJC",
        name_cn="香港马*(中国香港)",
        country="Hong Kong",
        website="https://bet.hkjc.com",
        is_main=True,
        is_asian=True,
        priority=1
    ),
    
    "williamhill": CompanyInfo(
        company_id=115,
        name_en="William Hill", 
        name_cn="威廉希尔",
        country="United Kingdom",
        website="https://williamhill.com",
        is_main=True,
        is_asian=False,
        priority=2
    ),
    
    "bet365": CompanyInfo(
        company_id=188,
        name_en="Bet365",
        name_cn="bet365",
        country="United Kingdom", 
        website="https://bet365.com",
        is_main=True,
        is_asian=False,
        priority=3
    ),
    
    # Tier 2 - Major bookmakers
    "easybets": CompanyInfo(
        company_id=90,
        name_en="Easybets",
        name_cn="易胜博",
        country="Philippines",
        website="https://easybets.com",
        is_main=True,
        is_asian=True,
        priority=10
    ),
    
    "pinnacle": CompanyInfo(
        company_id=281,
        name_en="Pinnacle",
        name_cn="平博",
        country="Malta",
        website="https://pinnacle.com",
        is_main=True, 
        is_asian=False,
        priority=11
    ),
    
    "crown": CompanyInfo(
        company_id=545,
        name_en="Crown",
        name_cn="皇冠",
        country="China",
        website="",
        is_main=True,
        is_asian=True,
        priority=5,
        is_active=True
    ),
    "macau": CompanyInfo(
        company_id=80,
        name_en="Macau",
        name_cn="澳门",
        country="Macau",
        website="",
        is_main=False,
        is_asian=True,
        priority=12
    ),
    
    "bwin": CompanyInfo(
        company_id=255,
        name_en="BWIN",
        name_cn="BWIN",
        country="Austria",
        website="https://bwin.com",
        is_main=True,
        is_asian=False,
        priority=13
    ),
    
    # Tier 3 - Regional/specialized bookmakers
    "weide": CompanyInfo(
        company_id=81,
        name_en="Weide",
        name_cn="伟德",
        country="Isle of Man", 
        website="https://weide.com",
        is_main=False,
        is_asian=True,
        priority=20
    ),
    
    "sbobet": CompanyInfo(
        company_id=474,
        name_en="SB",
        name_cn="利记",
        country="Philippines",
        website="",
        is_main=False,
        is_asian=True,
        priority=21
    ),
    
    "ladbrokes": CompanyInfo(
        company_id=181,
        name_en="Ladbrokes",
        name_cn="立博",
        country="United Kingdom",
        website="https://ladbrokes.com",
        is_main=True,
        is_asian=False,
        priority=22
    ),
    
    "interwetten": CompanyInfo(
        company_id=190,
        name_en="Interwetten",
        name_cn="inter",
        country="Austria",
        website="https://interwetten.com",
        is_main=False,
        is_asian=False,
        priority=30
    ),
    
    "nordicbet": CompanyInfo(
        company_id=4,
        name_en="Nordicbet", 
        name_cn="Nordicbet",
        country="Malta",
        website="https://nordicbet.com",
        is_main=False,
        is_asian=False,
        priority=40
    ),
    
    "18bet": CompanyInfo(
        company_id=976,
        name_en="18BET",
        name_cn="18BET",
        country="Curacao",
        website="",
        is_main=False,
        is_asian=True,
        priority=50
    ),
    
    "betisn": CompanyInfo(
        company_id=937,
        name_en="BetISn",
        name_cn="BetISn", 
        country="Malta",
        website="",
        is_main=False,
        is_asian=False,
        priority=60
    ),
    
    "iddaa": CompanyInfo(
        company_id=657,
        name_en="iddaa",
        name_cn="iddaa",
        country="Turkey",
        website="",
        is_main=False,
        is_asian=False,
        priority=70
    ),
}


# Pre-defined company groups for different scraping strategies
COMPANY_GROUPS = {
    
    # Most important single company
    "hkjc_only": ["hkjc"],
    
    # Big 3 European bookmakers
    "big3_european": ["williamhill", "bet365", "ladbrokes"],
    
    # Top 3 overall (mix of Asian and European)
    "top3_mixed": ["hkjc", "williamhill", "easybets"],
    
    # Asian bookmakers focus
    "asian_focus": ["hkjc", "easybets", "macau", "weide", "sbobet", "18bet"],
    
    # European bookmakers focus
    "european_focus": ["williamhill", "bet365", "pinnacle", "bwin", "ladbrokes"],
    
    # Main/Tier 1 bookmakers only
    "tier1_only": ["hkjc", "williamhill", "bet365", "easybets", "pinnacle", "bwin"],
    
    # All companies
    "all": list(COMPANIES_CONFIG.keys())
}


def get_companies_by_priority(max_priority: int = 50) -> Dict[str, CompanyInfo]:
    """Get companies up to a certain priority level (lower number = higher priority)."""
    return {
        code: info for code, info in COMPANIES_CONFIG.items()
        if info.priority <= max_priority and info.is_active
    }


def get_companies_by_region(region: str) -> Dict[str, CompanyInfo]:
    """Get companies by region: 'asian', 'european', 'all'."""
    if region == "asian":
        return {
            code: info for code, info in COMPANIES_CONFIG.items()
            if info.is_asian and info.is_active
        }
    elif region == "european":
        return {
            code: info for code, info in COMPANIES_CONFIG.items() 
            if not info.is_asian and info.is_active
        }
    else:  # 'all' or any other value
        return {
            code: info for code, info in COMPANIES_CONFIG.items()
            if info.is_active
        }


def get_main_companies() -> Dict[str, CompanyInfo]:
    """Get only main/tier 1 bookmakers."""
    return {
        code: info for code, info in COMPANIES_CONFIG.items()
        if info.is_main and info.is_active
    }


def get_company_ids_from_group(group_name: str) -> List[int]:
    """Get company IDs from a predefined group."""
    if group_name not in COMPANY_GROUPS:
        raise ValueError(f"Unknown company group: {group_name}")
    
    company_codes = COMPANY_GROUPS[group_name]
    return [
        COMPANIES_CONFIG[code].company_id 
        for code in company_codes 
        if code in COMPANIES_CONFIG and COMPANIES_CONFIG[code].is_active
    ]


def get_companies_info_from_group(group_name: str) -> Dict[str, CompanyInfo]:
    """Get company info objects from a predefined group."""
    if group_name not in COMPANY_GROUPS:
        raise ValueError(f"Unknown company group: {group_name}")
    
    company_codes = COMPANY_GROUPS[group_name]
    return {
        code: COMPANIES_CONFIG[code]
        for code in company_codes
        if code in COMPANIES_CONFIG and COMPANIES_CONFIG[code].is_active  
    }


# Legacy mapping for backward compatibility
LEGACY_TARGET_COMPANIES = {
    str(info.company_id): {
        "en": info.name_en,
        "cn": info.name_cn, 
        "priority": info.priority
    }
    for info in COMPANIES_CONFIG.values()
    if info.priority <= 20  # Only include high priority companies
}


# Quick access filters for backward compatibility
COMPANY_FILTERS = {
    "hkjc": get_companies_info_from_group("hkjc_only"),
    "main3": get_companies_info_from_group("top3_mixed"), 
    "asian": get_companies_info_from_group("asian_focus"),
    "all": COMPANIES_CONFIG
}
