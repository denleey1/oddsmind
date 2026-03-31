"""
titan007 联赛数据批量获取工具
===============================
自动从 zq.titan007.com 获取所有联赛的 JS 数据文件 URL。

工作原理：
1. 从 leftData.js 解析出所有联赛ID和名称
2. 对每个联赛获取其HTML页面，从中提取 SubSclassID
3. 构造 JS 数据文件 URL: s{id}_{subId}.js 或 s{id}.js

用法：
  python titan007_batch_urls.py                    # 获取所有联赛当前赛季的URL
  python titan007_batch_urls.py --season 2024-2025 # 指定赛季
  python titan007_batch_urls.py --top5              # 只获取五大联赛
  python titan007_batch_urls.py --download          # 下载所有JS数据文件
  python titan007_batch_urls.py --list-leagues      # 列出所有联赛ID和名称
"""

import re
import json
import time
import argparse
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://zq.titan007.com"
LEFT_DATA_URL = f"{BASE_URL}/jsData/leftData/leftData.js"
SEASON_URL_TPL = f"{BASE_URL}/jsData/LeagueSeason/sea{{league_id}}.js"
# 联赛页面 HTML（包含 SubSclassID 变量）
LEAGUE_PAGE_TPL = f"{BASE_URL}/cn/SubLeague/{{season}}/{{league_id}}.html"
# JS数据文件
MATCH_DATA_URL_TPL = f"{BASE_URL}/jsData/matchResult/{{season}}/s{{league_id}}.js"
MATCH_DATA_SUB_URL_TPL = f"{BASE_URL}/jsData/matchResult/{{season}}/s{{league_id}}_{{sub_id}}.js"

# 五大联赛 ID
TOP5_IDS = {
    34: "意甲",
    36: "英超",
    31: "西甲",
    8: "德甲",
    11: "法甲",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://zq.titan007.com/",
}

# 全局session复用连接
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch_text(url, timeout=15):
    """获取URL文本内容"""
    try:
        resp = SESSION.get(url, timeout=timeout)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass  # 静默处理，避免刷屏
    return None


def parse_left_data(js_text):
    """
    解析 leftData.js，提取所有联赛信息。
    联赛格式: [ID, '简体名', '繁体名', '英文名', type]
    返回: [{id, name_cn, name_en, area, type}, ...]
    """
    leagues = []

    # 提取联赛: [数字, '中文名', '繁体', '英文名', 数字]
    league_pattern = r"\[(\d+),'([^']+)','([^']+)','([^']+)',(\d+)\]"

    # 分块提取，按 arrArea[n] 拆分
    blocks = re.split(r"arrArea\[\d+\]\s*=\s*", js_text)

    for block in blocks:
        if not block.strip():
            continue

        # 获取区域名
        area_match = re.search(r"\[\['([^']+)'", block)
        area_name = area_match.group(1) if area_match else "未知"

        matches = re.findall(league_pattern, block)
        for m in matches:
            league_id = int(m[0])
            leagues.append({
                "id": league_id,
                "name_cn": m[1],
                "name_tw": m[2],
                "name_en": m[3],
                "type": int(m[4]),  # 0=普通联赛, 1=热门联赛, 2=杯赛
                "area": area_name,
            })

    return leagues


def parse_seasons(js_text):
    """解析 sea{id}.js，返回赛季列表"""
    if not js_text:
        return []
    match = re.search(r"arrSeason\s*=\s*\[(.*?)\]", js_text)
    if match:
        return re.findall(r"'([^']+)'", match.group(1))
    return []


def get_sub_id_from_page(league_id, season):
    """
    从联赛HTML页面中提取 SubSclassID。
    页面中会定义: var SubSclassID = 2948;  或  var SubSclassID = 0;
    SubSclassID=0 表示不需要子联赛ID。
    """
    url = LEAGUE_PAGE_TPL.format(season=season, league_id=league_id)
    text = fetch_text(url, timeout=10)
    if not text:
        return None

    match = re.search(r"SubSclassID\s*=\s*(\d+)", text)
    if match:
        return int(match.group(1))

    return None


def get_sub_ids_from_js(league_id, season):
    """
    尝试直接从 JS 数据文件中解析 arrSubLeague 获取所有子联赛ID。
    返回: [(sub_id, sub_name), ...] 或 空列表
    """
    url = MATCH_DATA_URL_TPL.format(season=season, league_id=league_id)
    text = fetch_text(url, timeout=10)

    if not text or "arrSubLeague" not in text:
        return []

    match = re.search(r"arrSubLeague\s*=\s*\[(.*?)\];", text, re.DOTALL)
    if not match:
        return []

    sub_pattern = r"\[(\d+),'([^']*?)'"
    subs = re.findall(sub_pattern, match.group(1))
    return [(int(s[0]), s[1]) for s in subs]


def construct_data_url(league_id, sub_id, season):
    """根据联赛ID和子联赛ID构造数据URL"""
    if sub_id and sub_id > 0:
        return MATCH_DATA_SUB_URL_TPL.format(
            season=season, league_id=league_id, sub_id=sub_id
        )
    else:
        return MATCH_DATA_URL_TPL.format(season=season, league_id=league_id)


def get_all_leagues():
    """获取所有联赛列表"""
    print("📥 正在获取联赛列表 (leftData.js)...")
    text = fetch_text(LEFT_DATA_URL)
    if not text:
        print("❌ 无法获取联赛列表！")
        return []
    leagues = parse_left_data(text)
    print(f"✅ 共找到 {len(leagues)} 个联赛/赛事")
    return leagues


def get_league_seasons(league_id):
    """获取指定联赛的所有赛季"""
    url = SEASON_URL_TPL.format(league_id=league_id)
    text = fetch_text(url, timeout=10)
    return parse_seasons(text)


def get_data_urls_for_league(league_id, season):
    """
    获取联赛在指定赛季的数据URL列表。
    策略：
    1. 尝试从联赛HTML页面提取 SubSclassID
    2. 如果是0或获取不到，尝试直接访问 s{id}.js 并解析 arrSubLeague
    3. 构造最终URL
    返回: [(url, sub_name), ...]
    """
    results = []

    # 策略1: 从HTML页面获取默认 SubSclassID
    sub_id = get_sub_id_from_page(league_id, season)

    if sub_id is not None and sub_id > 0:
        # 有子联赛ID，先用这个ID获取数据文件，再从中解析所有子联赛
        data_url = construct_data_url(league_id, sub_id, season)
        text = fetch_text(data_url, timeout=10)

        if text and "arrSubLeague" in text:
            match = re.search(r"arrSubLeague\s*=\s*\[(.*?)\];", text, re.DOTALL)
            if match:
                sub_pattern = r"\[(\d+),'([^']*?)'"
                subs = re.findall(sub_pattern, match.group(1))
                for sid, sname in subs:
                    url = construct_data_url(league_id, int(sid), season)
                    results.append((url, sname))
            if not results:
                results.append((data_url, ""))
        elif text:
            results.append((data_url, ""))
    elif sub_id == 0:
        # SubSclassID=0, 不需要子联赛ID
        url = construct_data_url(league_id, 0, season)
        text = fetch_text(url, timeout=10)
        if text and len(text) > 100 and "<html" not in text.lower()[:100]:
            results.append((url, ""))
    else:
        # 获取不到SubSclassID，直接测试 s{id}.js
        url = construct_data_url(league_id, 0, season)
        text = fetch_text(url, timeout=10)
        if text and len(text) > 100 and "<html" not in text.lower()[:100]:
            if "arrSubLeague" in text:
                match = re.search(r"arrSubLeague\s*=\s*\[(.*?)\];", text, re.DOTALL)
                if match:
                    sub_pattern = r"\[(\d+),'([^']*?)'"
                    subs = re.findall(sub_pattern, match.group(1))
                    for sid, sname in subs:
                        sub_url = construct_data_url(league_id, int(sid), season)
                        results.append((sub_url, sname))
            if not results:
                results.append((url, ""))

    return results


def list_all_leagues(leagues):
    """打印所有联赛列表"""
    print(f"\n{'='*80}")
    print(f"{'ID':>6}  {'名称':<12} {'英文名':<20} {'类型':<6} {'区域'}")
    print(f"{'='*80}")

    current_area = ""
    for lg in sorted(leagues, key=lambda x: (x["area"], -x["type"], x["id"])):
        if lg["area"] != current_area:
            current_area = lg["area"]
            print(f"\n--- {current_area} ---")
        type_str = "联赛" if lg["type"] in (0, 1) else "杯赛"
        hot = " 🔥" if lg["type"] == 1 else ""
        print(f"{lg['id']:>6}  {lg['name_cn']:<12} {lg['name_en']:<20} {type_str}{hot:<6} {lg['area']}")


def batch_get_urls(leagues, season, max_workers=8):
    """批量获取所有联赛的数据URL"""
    all_urls = []
    total = len(leagues)

    print(f"\n🚀 开始批量获取 {total} 个联赛的数据URL (赛季: {season})...")
    print(f"   使用 {max_workers} 个并发线程\n")

    def process_league(league):
        urls = get_data_urls_for_league(league["id"], season)
        return league, urls

    done_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_league, lg): lg for lg in leagues}
        for future in as_completed(futures):
            done_count += 1
            league, urls = future.result()
            if urls:
                for url, sub_name in urls:
                    all_urls.append({
                        "league_id": league["id"],
                        "league_name": league["name_cn"],
                        "league_en": league["name_en"],
                        "sub_name": sub_name,
                        "season": season,
                        "url": url,
                        "area": league["area"],
                    })
                print(f"  [{done_count}/{total}] ✅ {league['name_cn']}: {len(urls)} 个URL")
            else:
                print(f"  [{done_count}/{total}] ⏭  {league['name_cn']}: 该赛季无数据")

    return all_urls


def download_data(urls, output_dir):
    """下载所有数据文件"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n📦 开始下载 {len(urls)} 个数据文件到 {output_dir}...")

    for i, item in enumerate(urls, 1):
        filename = item["url"].split("/")[-1].split("?")[0]
        filepath = output_path / item["season"] / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if filepath.exists():
            print(f"  [{i}/{len(urls)}] ⏭  已存在: {filename}")
            continue

        text = fetch_text(item["url"])
        if text:
            filepath.write_text(text, encoding="utf-8")
            print(f"  [{i}/{len(urls)}] ✅ 下载: {filename} ({len(text)} 字节)")
        else:
            print(f"  [{i}/{len(urls)}] ❌ 失败: {filename}")

        time.sleep(0.1)  # 礼貌性延迟


def main():
    parser = argparse.ArgumentParser(description="Titan007 联赛数据批量获取工具")
    parser.add_argument("--season", default="2025-2026", help="指定赛季 (默认: 2025-2026)")
    parser.add_argument("--top5", action="store_true", help="只获取五大联赛")
    parser.add_argument("--league-ids", type=str, help="指定联赛ID，逗号分隔 (如: 34,36,31)")
    parser.add_argument("--leagues-only", action="store_true", help="只获取联赛(排除杯赛)")
    parser.add_argument("--download", action="store_true", help="下载数据文件")
    parser.add_argument("--output-dir", default="titan007_data", help="下载输出目录")
    parser.add_argument("--list-leagues", action="store_true", help="列出所有联赛ID和名称")
    parser.add_argument("--output-json", type=str, help="将URL列表保存到JSON文件")
    parser.add_argument("--workers", type=int, default=8, help="并发线程数 (默认: 8)")
    args = parser.parse_args()

    # 获取所有联赛
    all_leagues = get_all_leagues()
    if not all_leagues:
        return

    # 列出联赛
    if args.list_leagues:
        list_all_leagues(all_leagues)
        return

    # 筛选联赛
    if args.top5:
        target_leagues = [lg for lg in all_leagues if lg["id"] in TOP5_IDS]
        print(f"🏟  已选择五大联赛: {', '.join(TOP5_IDS.values())}")
    elif args.league_ids:
        ids = [int(x.strip()) for x in args.league_ids.split(",")]
        target_leagues = [lg for lg in all_leagues if lg["id"] in ids]
        print(f"🏟  已选择 {len(target_leagues)} 个联赛")
    else:
        target_leagues = all_leagues

    # 过滤杯赛
    if args.leagues_only:
        target_leagues = [lg for lg in target_leagues if lg["type"] in (0, 1)]
        print(f"📋 已排除杯赛，剩余 {len(target_leagues)} 个联赛")

    # 批量获取URL
    urls = batch_get_urls(target_leagues, args.season, max_workers=args.workers)

    # 打印汇总
    print(f"\n{'='*80}")
    print(f"📊 汇总: 共获取 {len(urls)} 个有效数据URL")
    print(f"{'='*80}")

    for item in urls:
        sub = f" - {item['sub_name']}" if item["sub_name"] else ""
        print(f"  {item['league_name']}{sub}: {item['url']}")

    # 保存到JSON
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(urls, f, ensure_ascii=False, indent=2)
        print(f"\n💾 URL列表已保存到: {args.output_json}")

    # 下载数据
    if args.download:
        download_data(urls, args.output_dir)

    print("\n✨ 完成！")


if __name__ == "__main__":
    main()
