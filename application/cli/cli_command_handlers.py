#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extracted command handlers for OddsMind CLI."""

from __future__ import annotations

from typing import Any, Dict, List

from config.leagues_config import LEAGUES_CONFIG, get_league_group_codes
from scrapers import OddsScraperModern
from scrapers.all_companies_scraper import AllCompaniesOddsScraper
from fundamental_analysis import (
    FundamentalDataFetcher,
    FundamentalCalculator,
    get_league_name,
)
from calculation.mysql_general_strength_calculator import MySQLGeneralStrengthCalculator


def handle_scrape_odds(cli, args) -> int:
    """Handle odds scraping command."""
    cli.logger.info("Starting odds scraping...")

    if args.match_ids:
        match_ids_to_scrape = [int(mid.strip()) for mid in args.match_ids.split(',')]
    else:
        cli.logger.info("Finding all matches that need odds data...")

        league_ids_to_process = []
        if args.league_group:
            import re

            league_codes = get_league_group_codes(args.league_group)
            for code in league_codes:
                if code in LEAGUES_CONFIG:
                    league_info = LEAGUES_CONFIG[code]
                    match = re.match(r's(\d+)', league_info.league_filename)
                    if match:
                        league_id = int(match.group(1))
                        if league_id not in league_ids_to_process:
                            league_ids_to_process.append(league_id)
            cli.logger.info(
                "Processing league group '%s' with %s leagues.",
                args.league_group,
                len(league_ids_to_process),
            )

        elif args.league_id:
            league_ids_to_process.append(args.league_id)

        if league_ids_to_process:
            all_matches = []
            for league_id in league_ids_to_process:
                all_matches.extend(
                    cli.db_manager.get_matches_needing_odds(
                        league_id=league_id,
                        only_finished=True,
                    )
                )
            match_ids_to_scrape = all_matches
        else:
            match_ids_to_scrape = cli.db_manager.get_matches_needing_odds(
                league_id=None,
                only_finished=True,
            )

    if not match_ids_to_scrape:
        cli.logger.info("No matches found that require odds scraping.")
        return 0

    total_matches = len(match_ids_to_scrape)
    cli.logger.info("Found a total of %s matches to process.", total_matches)

    target_companies = None
    if args.company_ids:
        company_ids = [int(cid.strip()) for cid in args.company_ids.split(',')]
        target_companies = cli._get_companies_by_ids(company_ids)
        cli.logger.info("Using custom company IDs: %s", company_ids)
    elif args.company_names:
        company_names = [name.strip() for name in args.company_names.split(',')]
        target_companies = cli._get_companies_by_names(company_names)
        cli.logger.info("Using custom company names: %s", company_names)
    elif args.company_group:
        from config.companies_config import get_companies_info_from_group

        target_companies = get_companies_info_from_group(args.company_group)
    elif args.company_filter != 'all':
        from config.companies_config import get_companies_by_region

        target_companies = get_companies_by_region(args.company_filter)

    if args.company_filter == 'all':
        cli.logger.info("Company filter is 'all', using AllCompaniesOddsScraper to capture everything.")
        scraper = AllCompaniesOddsScraper()
    else:
        cli.logger.info(
            "Using company filter '%s' with OddsScraperModern.",
            args.company_filter,
        )
        scraper = OddsScraperModern(
            company_filter=args.company_filter,
            target_companies=target_companies,
        )

    for i in range(0, total_matches, args.batch_size):
        batch_ids = match_ids_to_scrape[i:i + args.batch_size]
        start_num = i + 1
        end_num = min(i + args.batch_size, total_matches)
        cli.logger.info("--- Processing batch %s-%s of %s ---", start_num, end_num, total_matches)

        with cli.performance_monitor.monitor_operation("scrape_odds_batch"):
            result = scraper.scrape(
                match_ids=batch_ids,
                max_workers=args.max_workers,
                skip_existing=args.skip_existing,
            )

        if result.success and result.data:
            stored_count = 0
            for match_id, match_result in result.data.items():
                if match_result.success and match_result.data:
                    try:
                        company_map = match_result.data.get('company_map')
                        count = cli.db_manager.store_odds_data(
                            match_id,
                            match_result.data,
                            company_map=company_map,
                        )
                        stored_count += count
                    except Exception as exc:
                        cli.logger.error("Error storing odds for match %s: %s", match_id, exc)

            cli.logger.info(
                "Batch complete. Stored %s total odds records for this batch.",
                stored_count,
            )

    cli.logger.info("--- Full odds scraping process finished ---")
    return 0


def handle_analyze_odds(cli, args) -> int:
    """Handle odds analysis command via unified CLI (single or batch)."""
    try:
        from odds_analysis.main_analyzer import MainAnalyzer
        from database import get_connection

        match_ids: List[int] = []
        if args.match_ids:
            match_ids = [int(x.strip()) for x in args.match_ids.split(',') if x.strip()]
        elif args.match_id:
            match_ids = [int(args.match_id)]
        elif args.league_id:
            db = get_connection()
            rows: List[Dict[str, Any]] = []
            if args.data_source == 'odds_changes':
                rows = db.execute_query(
                    """
                    SELECT DISTINCT oc.match_id, m.match_time
                    FROM odds_changes oc
                    JOIN matches m ON m.match_id = oc.match_id
                    WHERE m.league_id = %s
                    ORDER BY m.match_time DESC
                    LIMIT %s
                    """,
                    (args.league_id, args.limit),
                    fetch='all',
                ) or []
            if not rows:
                rows = db.execute_query(
                    """
                    SELECT DISTINCT eo.match_id, m.match_time
                    FROM european_odds eo
                    JOIN matches m ON m.match_id = eo.match_id
                    WHERE m.league_id = %s
                    ORDER BY m.match_time DESC
                    LIMIT %s
                    """,
                    (args.league_id, args.limit),
                    fetch='all',
                ) or []
            match_ids = [int(row['match_id']) for row in rows]
        else:
            cli.logger.error("Please provide --match-id or --match-ids or --league-id")
            return 1

        if not match_ids:
            cli.logger.info("No matches to analyze.")
            return 0

        cli.logger.info("Starting odds analysis for %s match(es)...", len(match_ids))
        analyzer = MainAnalyzer()
        setattr(analyzer, 'data_source', args.data_source)
        ok, fail = 0, 0
        for match_id in match_ids:
            try:
                analyzer.analyze_match(match_id)
                ok += 1
            except Exception as exc:
                fail += 1
                cli.logger.error("Analyze match %s failed: %s", match_id, exc)
        analyzer.close()

        cli.logger.info("Odds analysis completed. Success: %s, Failed: %s", ok, fail)
        return 0 if fail == 0 else 1
    except Exception as exc:
        cli.logger.error("Odds analysis failed: %s", exc, exc_info=True)
        return 1


def handle_analyze_fundamental(cli, args) -> int:
    """Handle fundamental analysis command."""
    cli.logger.info("Starting fundamental analysis for match %s", args.match_id)

    try:
        cli.logger.info("Fetching match data...")
        fetcher = FundamentalDataFetcher()
        parsed_data = fetcher.fetch_and_parse(args.match_id)

        if not parsed_data:
            cli.logger.error("Failed to fetch match data")
            return 1

        basic_info = parsed_data.get('basic_info', {})
        home_team = basic_info.get('home_team', '未知')
        away_team = basic_info.get('away_team', '未知')

        league_name = get_league_name(
            match_id=args.match_id,
            league_input=basic_info.get('league'),
            match_data=parsed_data,
        )

        cli.logger.info("Analyzing match: %s vs %s (League: %s)", home_team, away_team, league_name)

        calculator = FundamentalCalculator()
        result = calculator.calculate_analysis_with_storage(
            parsed_data,
            match_id=args.match_id,
            save_to_db=True,
        )

        if not result:
            cli.logger.error("Failed to calculate analysis scores")
            return 1

        scores = result.get('final_scores', {})
        confidence_data = result.get('confidence_analysis', {})

        print(f"\n{'='*60}")
        print(f"基本面分析结果 - 比赛 {args.match_id}")
        print(f"{'='*60}")
        print(f"比赛: {home_team} vs {away_team}")
        print(f"联赛: {league_name or '未知'}")

        print("\n📊 最终评分:")
        outcomes = ['home_win', 'draw', 'away_win']
        outcome_names = {'home_win': '🏠 主胜', 'draw': '🤝 平局', 'away_win': '🛣️ 客胜'}

        for outcome in outcomes:
            score = scores.get(outcome, 0)
            confidence_info = confidence_data.get(outcome, {})
            confidence_level = confidence_info.get('level', '未知')
            confidence_interval = confidence_info.get('interval', '未知')
            odds_suggestions = confidence_info.get('odds_suggestions', [])

            print(f"   {outcome_names[outcome]}: {score:.1f}/10")
            print(f"      └─ 信心等级: {confidence_level}")
            print(f"      └─ 信心区间: {confidence_interval}")
            if odds_suggestions:
                print(f"      └─ 开盘建议(共{len(odds_suggestions)}条):")
                for i, suggestion in enumerate(odds_suggestions, 1):
                    print(f"          {i}. {suggestion}")
            else:
                print("      └─ 开盘建议: 无")
            print()

        print(f"🎯 推荐结果: {result.get('recommended_outcome', '未知')}")
        print(f"🔒 整体信心等级: {result.get('confidence_level', '未知')}")

        recommended = result.get('recommended_outcome', '')
        if recommended in ['主胜', 'home_win']:
            target_outcome = 'home_win'
        elif recommended in ['平局', 'draw']:
            target_outcome = 'draw'
        elif recommended in ['客胜', 'away_win']:
            target_outcome = 'away_win'
        else:
            target_outcome = None

        if target_outcome and target_outcome in confidence_data:
            target_suggestions = confidence_data[target_outcome].get('odds_suggestions', [])
            if target_suggestions:
                print("\n💡 推荐结果开盘建议:")
                for i, suggestion in enumerate(target_suggestions, 1):
                    print(f"   {i}. {suggestion}")

        if result.get('saved_to_db'):
            print("\n✅ 结果已保存到数据库")
        else:
            print("\n❌ 数据库保存失败")

        if args.save_to_db:
            print("   (详细模式已启用)")

        print(f"{'='*60}")
        return 0

    except Exception as exc:
        cli.logger.error("Fundamental analysis failed: %s", exc, exc_info=True)
        return 1

def handle_calculate_strength(cli, args) -> int:
    """Handle strength calculation command.

    对于分区赛制联赛（如日职J1东/西区），自动执行：
    1. 每个分区内部的实力排名（仅含区内比赛）
    2. 全局合并排名（合并全部分区比赛，用于跨区比赛或季后赛参考）
    """
    import re
    from config.leagues_config import DIVISIONAL_LEAGUES

    league_ids = []

    if args.all:
        for _, league_info in LEAGUES_CONFIG.items():
            match = re.match(r's(\d+)', league_info.league_filename)
            if match:
                league_id = int(match.group(1))
                if league_id not in league_ids:
                    league_ids.append(league_id)
        cli.logger.info("Calculating strength for ALL %s leagues", len(league_ids))

    elif args.league_group:
        league_codes = get_league_group_codes(args.league_group)
        for code in league_codes:
            if code in LEAGUES_CONFIG:
                league_info = LEAGUES_CONFIG[code]
                match = re.match(r's(\d+)', league_info.league_filename)
                if match:
                    league_id = int(match.group(1))
                    if league_id not in league_ids:
                        league_ids.append(league_id)
        cli.logger.info(
            "Calculating strength for %s group (%s leagues)",
            args.league_group,
            len(league_ids),
        )

    elif args.league_ids:
        try:
            league_ids = [int(league_id.strip()) for league_id in args.league_ids.split(',')]
        except ValueError:
            cli.logger.error("Invalid league IDs format. Use comma-separated numbers (e.g., 25,15,36)")
            return 1
    else:
        cli.logger.error("Must specify either --all, --league-group, or --league-ids")
        return 1

    # ──────────────────────────────────────────────────────
    # 构建计算任务列表：(league_id, division_or_None)
    # 对于分区赛制联赛，拆分成 N 个分区任务 + 1 个全局任务
    # ──────────────────────────────────────────────────────
    calc_tasks = []  # list of (league_id, division)
    for league_id in league_ids:
        div_cfg = DIVISIONAL_LEAGUES.get(league_id)
        if div_cfg:
            divisions = list(div_cfg['divisions'].keys())
            cli.logger.info(
                "League %s is a divisional league with divisions: %s — "
                "will calculate per-division + global rankings",
                league_id, divisions,
            )
            # 每个分区单独计算
            for div_key in divisions:
                calc_tasks.append((league_id, div_key))
            # 全局合并计算（division=None → 加载全部比赛）
            calc_tasks.append((league_id, None))
        else:
            calc_tasks.append((league_id, None))

    cli.logger.info(
        "Starting strength calculation: %s total tasks (leagues=%s, divisional_extra=%s)",
        len(calc_tasks), len(league_ids), len(calc_tasks) - len(league_ids),
    )

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 避免外层"按联赛并发"和内层"按公司并发"叠加过高导致数据库压力抖动。
        outer_workers = max(int(args.max_workers or 1), 1)
        company_workers = max(1, min(4, 8 // outer_workers))
        cli.logger.info(
            "Strength concurrency plan: league_workers=%s, company_workers_per_league=%s",
            outer_workers,
            company_workers,
        )

        def calculate_league_strength(league_id, division):
            calculator = MySQLGeneralStrengthCalculator(
                league_id=league_id,
                season=args.season,
                division=division,
            )
            summary = calculator.calculate(max_workers=company_workers)
            return league_id, division, summary

        failed_tasks = []
        partial_tasks = []
        skipped_tasks = []

        with ThreadPoolExecutor(max_workers=outer_workers) as executor:
            futures = {
                executor.submit(calculate_league_strength, lid, div): (lid, div)
                for lid, div in calc_tasks
            }

            for future in as_completed(futures):
                lid, div = futures[future]
                task_label = f"League {lid}" + (f" [div={div}]" if div else "")
                try:
                    _, _, summary = future.result()
                    status = summary.get('status', 'ok') if isinstance(summary, dict) else 'ok'

                    if status == 'error':
                        failed_tasks.append(task_label)
                        cli.logger.error(
                            "%s strength calculation failed: %s",
                            task_label,
                            summary.get('errors'),
                        )
                    elif status == 'partial':
                        partial_tasks.append(task_label)
                        cli.logger.error(
                            "%s strength calculation partially failed: failed_companies=%s, errors=%s",
                            task_label,
                            summary.get('failed_companies'),
                            summary.get('errors'),
                        )
                    elif status == 'skipped':
                        skipped_tasks.append(task_label)
                        cli.logger.warning(
                            "%s strength calculation skipped: %s",
                            task_label,
                            summary.get('errors'),
                        )
                    else:
                        cli.logger.info("%s strength calculation completed", task_label)
                except Exception as exc:
                    failed_tasks.append(task_label)
                    cli.logger.error("%s calculation failed: %s", task_label, exc)

        cli.logger.info(
            "Strength calculation summary: success=%s, partial=%s, skipped=%s, failed=%s",
            len(calc_tasks) - len(partial_tasks) - len(skipped_tasks) - len(failed_tasks),
            len(partial_tasks),
            len(skipped_tasks),
            len(failed_tasks),
        )

        if partial_tasks or failed_tasks:
            cli.logger.error(
                "Strength calculations completed with errors. partial=%s failed=%s",
                partial_tasks,
                failed_tasks,
            )
            return 1

        cli.logger.info("All strength calculations completed")
        return 0

    except Exception as exc:
        cli.logger.error("Strength calculation failed: %s", exc, exc_info=True)
        return 1

__all__ = [
    "handle_scrape_odds",
    "handle_analyze_odds",
    "handle_analyze_fundamental",
    "handle_calculate_strength",
]
