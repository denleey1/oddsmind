#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compatibility shim for legacy imports."""

from __future__ import annotations

from application.services.web_ai_formatting import extract_final_judgment, format_analysis_text

__all__ = ["format_analysis_text", "extract_final_judgment"]
