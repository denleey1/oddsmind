#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Lazy singleton provider for legacy ``MatchDetailService``."""

from __future__ import annotations

import threading
from typing import Optional

from application.services.match_detail_service import MatchDetailService

_service_lock = threading.Lock()
_service_instance: Optional[MatchDetailService] = None


def get_match_detail_service() -> MatchDetailService:
    """Get a process-local singleton of ``MatchDetailService``."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = MatchDetailService()
    return _service_instance


__all__ = ["get_match_detail_service"]
