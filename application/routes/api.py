#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API Blueprint placeholder
原来的API已迁移到其他模块
"""
from flask import Blueprint

api_bp = Blueprint('api', __name__)

# 注: API功能已分散到各专用蓝图:
# - miniprogram_bp: 小程序相关API
# - rule_api: 规则匹配API
