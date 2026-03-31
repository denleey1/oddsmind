#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OddsMind application entrypoint with refactored modular structure."""

from __future__ import annotations

# 加载环境变量
from dotenv import load_dotenv
load_dotenv('oddsmind.env')

from application.web import create_app, get_app_logger, run_application

app = create_app()
logger = get_app_logger()


if __name__ == '__main__':
    run_application(app)
