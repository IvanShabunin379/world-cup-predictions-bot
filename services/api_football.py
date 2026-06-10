"""
Fetches match results from API-Football (via RapidAPI).
Docs: https://www.api-football.com/documentation-v3
"""
import aiohttp
from config import API_FOOTBALL_KEY

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-rapidapi-key": API_FOOTBALL_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io",
}

# WC 2026 league ID on API-Football (update when confirmed)
WC_2026_LEAGUE_ID = 1  # placeholder — verify on api-football.com
WC_2026_SEASON = 2026


async def fetch_fixture(fixture_id: int) -> dict | None:
    url = f"{BASE_URL}/fixtures"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS, params={"id": fixture_id}) as resp:
            data = await resp.json()
            fixtures = data.get("response", [])
            return fixtures[0] if fixtures else None


async def fetch_fixtures_by_date(date_str: str) -> list[dict]:
    """date_str: 'YYYY-MM-DD'"""
    url = f"{BASE_URL}/fixtures"
    params = {
        "league": WC_2026_LEAGUE_ID,
        "season": WC_2026_SEASON,
        "date": date_str,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS, params=params) as resp:
            data = await resp.json()
            return data.get("response", [])


def parse_result(fixture: dict) -> dict | None:
    """
    Returns {"home_score": int, "away_score": int, "status": str}
    status: 'FT' (full time), 'AET' (after extra time), 'PEN' (penalties), etc.
    """
    try:
        goals = fixture["goals"]
        status = fixture["fixture"]["status"]["short"]
        return {
            "home_score": goals["home"],
            "away_score": goals["away"],
            "status": status,
        }
    except (KeyError, TypeError):
        return None
