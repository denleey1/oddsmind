#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
时区工具模块
提供统一的时区感知datetime函数，确保整个应用使用一致的时区处理
默认时区：Asia/Shanghai (UTC+8)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import pytz

# 默认时区：Asia/Shanghai (UTC+8)
DEFAULT_TIMEZONE_NAME = "Asia/Shanghai"
DEFAULT_TIMEZONE = pytz.timezone(DEFAULT_TIMEZONE_NAME)
DEFAULT_UTC_OFFSET = timedelta(hours=8)


def get_app_timezone() -> pytz.BaseTzInfo:
    """
    获取应用配置的时区对象
    
    Returns:
        pytz.BaseTzInfo: 时区对象，默认为Asia/Shanghai
    """
    try:
        # 延迟导入，避免循环导入
        import config.settings
        if hasattr(config.settings, 'settings') and hasattr(config.settings.settings, 'timezone'):
            tz_name = config.settings.settings.timezone.timezone_name
            return pytz.timezone(tz_name)
    except Exception:
        # 如果无法加载配置，使用默认时区
        pass
    return DEFAULT_TIMEZONE


def get_mysql_timezone_offset() -> str:
    """
    获取MySQL时区偏移字符串（用于SET time_zone语句）
    
    Returns:
        str: MySQL时区偏移，例如 "+08:00"，默认为 "+08:00"
    """
    try:
        # 延迟导入，避免循环导入
        import config.settings
        if hasattr(config.settings, 'settings') and hasattr(config.settings.settings, 'timezone'):
            return config.settings.settings.timezone.mysql_timezone_offset
    except Exception:
        pass
    return "+08:00"


def now() -> datetime:
    """
    获取当前时间（时区感知，使用应用配置的时区）
    
    Returns:
        datetime: 当前时间，带时区信息（Asia/Shanghai）
    """
    tz = get_app_timezone()
    return datetime.now(tz)


def now_utc() -> datetime:
    """
    获取当前UTC时间（时区感知）
    
    Returns:
        datetime: 当前UTC时间，带时区信息
    """
    return datetime.now(timezone.utc)


def now_naive() -> datetime:
    """
    获取当前本地时间（无时区信息，不推荐使用）
    仅用于向后兼容或特殊场景
    
    Returns:
        datetime: 当前本地时间，无时区信息
    """
    return datetime.now()


def to_timezone_aware(dt: datetime, tz: Optional[pytz.BaseTzInfo] = None) -> datetime:
    """
    将datetime转换为时区感知对象
    
    Args:
        dt: 要转换的datetime对象
        tz: 目标时区，如果为None则使用应用配置的时区
        
    Returns:
        datetime: 时区感知的datetime对象
    """
    if dt.tzinfo is not None:
        # 已经是时区感知的，直接返回
        return dt
    
    # 如果没有指定时区，使用应用配置的时区
    if tz is None:
        tz = get_app_timezone()
    
    # 假设naive datetime是应用时区的本地时间
    return tz.localize(dt)


def to_utc(dt: datetime) -> datetime:
    """
    将datetime转换为UTC时间
    
    Args:
        dt: 要转换的datetime对象（可以是naive或aware）
        
    Returns:
        datetime: UTC时间的datetime对象
    """
    if dt.tzinfo is None:
        # 如果是naive，假设是应用时区的本地时间
        dt = to_timezone_aware(dt)
    
    return dt.astimezone(timezone.utc)


def to_local(dt: datetime, tz: Optional[pytz.BaseTzInfo] = None) -> datetime:
    """
    将datetime转换为应用配置的本地时区时间
    
    Args:
        dt: 要转换的datetime对象（可以是naive或aware）
        tz: 目标时区，如果为None则使用应用配置的时区
        
    Returns:
        datetime: 本地时区的datetime对象
    """
    if dt.tzinfo is None:
        # 如果是naive，假设是应用时区的本地时间
        dt = to_timezone_aware(dt)
    
    if tz is None:
        tz = get_app_timezone()
    
    return dt.astimezone(tz)


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化datetime为字符串
    
    Args:
        dt: 要格式化的datetime对象
        fmt: 格式化字符串
        
    Returns:
        str: 格式化后的时间字符串
    """
    return dt.strftime(fmt)


def parse_datetime(dt_str: str, fmt: str = "%Y-%m-%d %H:%M:%S", tz: Optional[pytz.BaseTzInfo] = None) -> datetime:
    """
    解析时间字符串为datetime对象（时区感知）
    
    Args:
        dt_str: 时间字符串
        fmt: 格式化字符串
        tz: 时区，如果为None则使用应用配置的时区
        
    Returns:
        datetime: 时区感知的datetime对象
    """
    dt = datetime.strptime(dt_str, fmt)
    return to_timezone_aware(dt, tz)


def get_timezone_info() -> dict:
    """
    获取当前时区配置信息
    
    Returns:
        dict: 包含时区信息的字典
    """
    tz = get_app_timezone()
    now_dt = now()
    utc_dt = now_utc()
    
    return {
        "timezone_name": tz.zone,
        "mysql_offset": get_mysql_timezone_offset(),
        "current_local": format_datetime(now_dt),
        "current_utc": format_datetime(utc_dt),
        "offset_hours": now_dt.utcoffset().total_seconds() / 3600,
    }

