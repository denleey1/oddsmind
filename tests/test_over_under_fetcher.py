import unittest
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from scrapers.over_under_fetcher import OverUnderOddsFetcher


SCHEDULED_HTML = """
<html>
  <head><title>Home VS Away</title></head>
  <body>
    <div id="headVs">VS</div>
    <table>
      <tr bgcolor="#FFFFFF">
        <td width="35"></td>
        <td height="25">36*</td>
        <td><span class="down" companyID="8"></span></td>
        <td title="2026-03-23 08:34">0.80</td>
        <td title="2026-03-23 08:34">2/2.5</td>
        <td title="2026-03-23 08:34">1.00</td>
        <td oddstype="wholeOdds">0.95</td>
        <td oddstype="wholeOdds">2.5</td>
        <td oddstype="wholeOdds">0.85</td>
        <td><a href="/changeDetail/overunder.aspx?id=2807964&companyID=8&l=0">详</a></td>
      </tr>
    </table>
  </body>
</html>
"""


LIVE_HTML = """
<html>
  <head><title>Home VS Away</title></head>
  <body>
    <div id="headVs">
      <div class="score">2</div>
      <span class="row red b">完</span>
      <div class="score">1</div>
    </div>
    <table>
      <tr bgcolor="#FFFFFF">
        <td width="35"></td>
        <td height="25">36*</td>
        <td><span class="down" companyID="8"></span></td>
        <td title="2026-03-23 08:34">0.80</td>
        <td title="2026-03-23 08:34">2/2.5</td>
        <td title="2026-03-23 08:34">1.00</td>
        <td oddstype="wholeOdds">9.50</td>
        <td oddstype="wholeOdds">3.5</td>
        <td oddstype="wholeOdds">0.05</td>
        <td><a href="/changeDetail/overunder.aspx?id=2807964&companyID=8&l=0">详</a></td>
      </tr>
    </table>
  </body>
</html>
"""


DETAIL_HTML = """
<html>
  <body>
    <table cellspacing="1" cellpadding="0" width="100%" align="center" bgcolor="#AFC7E2" border="0" class="font13">
      <tr><td>时间</td><td>比分</td><td>大球</td><td>进球数</td><td>小球</td><td>变化时间</td><td>状态</td></tr>
      <tr><td>71</td><td>2-0</td><td>0.85</td><td>2.5</td><td>0.95</td><td>3-28 22:30</td><td>滚</td></tr>
      <tr><td>70</td><td>2-0</td><td>0.80</td><td>2.5</td><td>1.00</td><td>3-28 22:29</td><td>滚</td></tr>
      <tr><td></td><td></td><td>0.95</td><td>2.5</td><td>0.85</td><td>3-28 20:47</td><td>即</td></tr>
      <tr><td></td><td></td><td>0.92</td><td>2.5</td><td>0.87</td><td>3-28 20:46</td><td>即</td></tr>
    </table>
  </body>
</html>
"""


class OverUnderFetcherTests(unittest.TestCase):
    def test_page_started_detection(self):
        scheduled = BeautifulSoup(SCHEDULED_HTML, "html.parser")
        live = BeautifulSoup(LIVE_HTML, "html.parser")

        self.assertFalse(OverUnderOddsFetcher._page_started(scheduled))
        self.assertTrue(OverUnderOddsFetcher._page_started(live))

    def test_parse_html_marks_live_summary_as_not_prematch(self):
        fetcher = OverUnderOddsFetcher(delay=0.1, workers=1)
        try:
            scheduled_records = fetcher._parse_html("2807964", SCHEDULED_HTML)
            live_records = fetcher._parse_html("2807964", LIVE_HTML)
        finally:
            fetcher.close()

        self.assertEqual(len(scheduled_records), 1)
        self.assertTrue(scheduled_records[0].current_is_prematch)
        self.assertEqual(scheduled_records[0].current_source, "summary")

        self.assertEqual(len(live_records), 1)
        self.assertFalse(live_records[0].current_is_prematch)
        self.assertEqual(live_records[0].current_source, "live_summary")
        self.assertIn("/changeDetail/overunder.aspx", live_records[0].detail_url)

    def test_extract_latest_prematch_close_prefers_last_immediate(self):
        resolved = OverUnderOddsFetcher._extract_latest_prematch_close(DETAIL_HTML)
        self.assertEqual(resolved, ("2.5", "0.95", "0.85", "3-28 20:47"))

    def test_hydrate_replaces_live_summary_with_immediate(self):
        fetcher = OverUnderOddsFetcher(delay=0.1, workers=1)
        try:
            live_records = fetcher._parse_html("2807964", LIVE_HTML)
            with patch.object(
                fetcher,
                "_fetch_latest_prematch_close",
                return_value=("2.5", "0.95", "0.85", "3-28 20:47"),
            ):
                hydrated = fetcher._hydrate_prematch_closes("2807964", MagicMock(), live_records)
        finally:
            fetcher.close()

        self.assertEqual(len(hydrated), 1)
        self.assertTrue(hydrated[0].current_is_prematch)
        self.assertEqual(hydrated[0].current_source, "detail_immediate")
        self.assertEqual(hydrated[0].line_close, "2.5")
        self.assertEqual(hydrated[0].over_odds_close, "0.95")
        self.assertEqual(hydrated[0].under_odds_close, "0.85")
        self.assertEqual(hydrated[0].time_close, "3-28 20:47")


if __name__ == "__main__":
    unittest.main()
