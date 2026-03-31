#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Backward-compatible entrypoint for the odds analyzer."""

from odds_analysis.main_analyzer import MainAnalyzer, main

__all__ = ["MainAnalyzer", "main"]


if __name__ == "__main__":
    main()
