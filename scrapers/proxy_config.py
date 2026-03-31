#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Central proxy configuration for all scrapers.
Reads tunnel proxy settings from environment variables and provides
a unified interface for applying proxy to requests sessions.
"""

import os
from typing import Dict, Optional


def get_proxy_config() -> Optional[Dict[str, str]]:
    """
    Read proxy configuration from environment variables.

    Expected env vars:
        PROXY_HOST  – tunnel hostname  (e.g. q927.kdltps.com)
        PROXY_PORT  – tunnel port      (e.g. 15818)
        PROXY_USER  – auth username
        PROXY_PASS  – auth password

    Returns:
        Dict with 'http' and 'https' proxy URLs, or None if not configured.
    """
    host = os.environ.get('PROXY_HOST', '').strip()
    port = os.environ.get('PROXY_PORT', '').strip()
    user = os.environ.get('PROXY_USER', '').strip()
    pwd = os.environ.get('PROXY_PASS', '').strip()

    if not host or not port:
        return None

    if user and pwd:
        proxy_url = f"http://{user}:{pwd}@{host}:{port}/"
    else:
        proxy_url = f"http://{host}:{port}/"

    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def apply_proxy_to_session(session) -> None:
    """
    Apply the configured proxy to a *requests.Session* instance.
    No-op when proxy env vars are not set.
    """
    proxies = get_proxy_config()
    if proxies:
        session.proxies.update(proxies)
