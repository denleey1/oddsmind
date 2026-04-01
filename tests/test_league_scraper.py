import unittest
from unittest.mock import patch

from scrapers.exceptions import ContentError
from scrapers.league_scraper import LeagueScraper


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content.encode("utf-8")


class LeagueScraperRetryTests(unittest.TestCase):
    def test_fetch_validated_league_content_retries_until_valid(self):
        scraper = LeagueScraper()
        valid_content = "var arrLeague = []; " + ("var arrTeam = []; " * 8)
        responses = iter([
            _FakeResponse("short html"),
            _FakeResponse(valid_content),
        ])

        with patch.object(scraper, "make_request", side_effect=lambda url: next(responses)) as make_request:
            with patch("scrapers.league_scraper.time.sleep", return_value=None):
                content = scraper._fetch_validated_league_content("JPN_J2", "https://example.test")

        self.assertIn("var arrLeague", content)
        self.assertEqual(make_request.call_count, 2)

    def test_fetch_validated_league_content_raises_after_retries(self):
        scraper = LeagueScraper()

        with patch.object(scraper, "make_request", return_value=_FakeResponse("short html")) as make_request:
            with patch("scrapers.league_scraper.time.sleep", return_value=None):
                with self.assertRaises(ContentError):
                    scraper._fetch_validated_league_content("JPN_J2", "https://example.test", max_attempts=3)

        self.assertEqual(make_request.call_count, 3)


if __name__ == "__main__":
    unittest.main()
