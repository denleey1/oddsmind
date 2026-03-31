#!/usr/bin/env bash
# 澳门分歧信号扫描工具
# 用法：
#   ./scan_macau.sh              # 抓赔率 + 扫描今晚比赛
#   ./scan_macau.sh --no-fetch   # 只扫描（不重新抓赔率，更快）
#   ./scan_macau.sh --days 2     # 扫描未来2天

set -e
cd "$(dirname "$0")"
export MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"

FETCH=1
DAYS=1

for arg in "$@"; do
    case $arg in
        --no-fetch) FETCH=0 ;;
        --days)     shift; DAYS=$1 ;;
        --days=*)   DAYS="${arg#*=}" ;;
    esac
done

echo "=================================================="
echo "  澳门分歧信号扫描  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

# Step 1: 抓取近期比赛赔率
if [ "$FETCH" -eq 1 ]; then
    echo ""
    echo "[1/2] 抓取今晚比赛赔率..."
    python3 - <<'PYEOF'
import os, sys
os.environ['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', '')
sys.path.insert(0, '.')
from datetime import datetime, timedelta
from database.connection import get_connection
from scrapers.all_companies_scraper import AllCompaniesOddsScraper
from database.repository_upsert_ops import batch_upsert_odds
from database.optimized_repository import OptimizedOddsRepository
from database.models_odds import OddsModel

db = get_connection()
now = datetime.utcnow()

rows = db.execute_query('''
    SELECT match_id FROM matches
    WHERE match_status IN ('scheduled','pending','live')
      AND match_time BETWEEN %s AND %s
    ORDER BY match_time ASC
''', (now - timedelta(hours=2), now + timedelta(days=1)), fetch='all')

match_ids = [r['match_id'] for r in rows]
if not match_ids:
    print("  暂无近期比赛")
    sys.exit(0)

print(f"  找到 {len(match_ids)} 场比赛，开始抓取赔率...")
s = AllCompaniesOddsScraper()
result = s.scrape_with_all_companies(match_ids)

repo = OptimizedOddsRepository()
total = 0
mac_count = 0
for mid, sr in result.data.items():
    if hasattr(sr, 'data') and sr.data:
        odds_list = sr.data.get('odds', []) if isinstance(sr.data, dict) else []
        has_mac = any(o.get('company_id') == 80 for o in odds_list)
        if has_mac:
            mac_count += 1
        records = []
        for o in odds_list:
            o['match_id'] = mid
            try:
                m = OddsModel(**{k: v for k, v in o.items() if k in OddsModel.__dataclass_fields__})
                records.append(m)
            except Exception:
                pass
        saved = batch_upsert_odds(repo, records)
        total += saved

print(f"  保存 {total} 条赔率，其中 {mac_count}/{len(match_ids)} 场有澳门数据")
PYEOF
    echo ""
fi

# Step 2: 扫描信号
echo "[2/2] 扫描澳门分歧信号..."
python3 - <<PYEOF
import os, sys
os.environ['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', '')
sys.path.insert(0, '.')
from validation_test.macau_divergence_signal import scan_upcoming
scan_upcoming(days_ahead=$DAYS)
PYEOF

echo ""
echo "完成。如需重新扫描（不重新抓赔率）：./scan_macau.sh --no-fetch"
