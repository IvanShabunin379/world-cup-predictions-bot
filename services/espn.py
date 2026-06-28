"""
Match results from ESPN's free hidden API (no key required).

Endpoint:
  https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=YYYYMMDD

ESPN uses English team names and groups fixtures by US-Eastern date, so we
query a small date window around the match kickoff and match by team name.
"""
import aiohttp
from datetime import timezone, timedelta
from dateutil import parser as dtparser

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

# ESPN English displayName → our Russian DB name
TEAM_EN_TO_RU: dict[str, str] = {
    "Algeria": "Алжир",
    "Argentina": "Аргентина",
    "Australia": "Австралия",
    "Austria": "Австрия",
    "Belgium": "Бельгия",
    "Bosnia-Herzegovina": "Босния и Герц.",
    "Brazil": "Бразилия",
    "Canada": "Канада",
    "Cape Verde": "Кабо-Верде",
    "Colombia": "Колумбия",
    "Congo DR": "ДР Конго",
    "Croatia": "Хорватия",
    "Curaçao": "Кюрасао",
    "Czechia": "Чехия",
    "Ecuador": "Эквадор",
    "Egypt": "Египет",
    "England": "Англия",
    "France": "Франция",
    "Germany": "Германия",
    "Ghana": "Гана",
    "Haiti": "Гаити",
    "Iran": "Иран",
    "Iraq": "Ирак",
    "Ivory Coast": "Кот-д'Ивуар",
    "Japan": "Япония",
    "Jordan": "Иордания",
    "Mexico": "Мексика",
    "Morocco": "Марокко",
    "Netherlands": "Нидерланды",
    "New Zealand": "Новая Зеландия",
    "Norway": "Норвегия",
    "Panama": "Панама",
    "Paraguay": "Парагвай",
    "Portugal": "Португалия",
    "Qatar": "Катар",
    "Saudi Arabia": "Саудовская Аравия",
    "Scotland": "Шотландия",
    "Senegal": "Сенегал",
    "South Africa": "ЮАР",
    "South Korea": "Южная Корея",
    "Spain": "Испания",
    "Sweden": "Швеция",
    "Switzerland": "Швейцария",
    "Tunisia": "Тунис",
    "Türkiye": "Турция",
    "United States": "США",
    "Uruguay": "Уругвай",
    "Uzbekistan": "Узбекистан",
}


def _en_to_ru(name: str) -> str | None:
    return TEAM_EN_TO_RU.get(name)


async def _fetch_date(session: aiohttp.ClientSession, date_str: str) -> list[dict]:
    """date_str: 'YYYYMMDD'. Returns parsed events for that ESPN date."""
    try:
        async with session.get(ESPN_URL, params={"dates": date_str}, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            data = await resp.json()
    except Exception:
        return []

    results = []
    for e in data.get("events", []):
        try:
            comp = e["competitions"][0]
            status = comp["status"]["type"]
            home = away = None
            home_score = away_score = None
            home_winner = False
            for c in comp["competitors"]:
                ru = _en_to_ru(c["team"]["displayName"])
                score = int(c["score"]) if c.get("score") not in (None, "") else None
                winner = bool(c.get("winner"))
                if c["homeAway"] == "home":
                    home, home_score, home_winner = ru, score, winner
                else:
                    away, away_score = ru, score
            results.append({
                "home_team": home,
                "away_team": away,
                "home_score": home_score,
                "away_score": away_score,
                "home_winner": home_winner,
                "completed": bool(status.get("completed")),
                "status_name": status.get("name", ""),
                "short_detail": status.get("shortDetail", ""),
            })
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return results


def determine_playoff_outcome(
    status_name: str, short_detail: str,
    home_score: int, away_score: int, home_winner: bool,
) -> str | None:
    """
    Infer playoff outcome type from ESPN status fields.
    Returns 'P1'|'P2'|'NP1'|'NP2'|'NPP1'|'NPP2' or None if undetermined.
    """
    name = status_name.upper()
    detail = short_detail.upper()
    if "PEN" in name or "AP" == detail or "PENS" in detail or "PEN" in detail:
        return "NPP1" if home_winner else "NPP2"
    if "AET" in name or "AET" in detail:
        return "NP1" if home_winner else "NP2"
    if home_score > away_score:
        return "P1"
    if home_score < away_score:
        return "P2"
    return None


async def fetch_match_result(kickoff_iso: str, home_team_ru: str, away_team_ru: str) -> dict | None:
    """
    Find a finished result for the given match.

    Returns {"home_score", "away_score", "completed", "status_name"} oriented to
    our home/away, or None if not found / not finished yet.
    """
    kickoff = dtparser.parse(kickoff_iso).replace(tzinfo=timezone.utc)
    # ESPN groups by US-Eastern date, so check the kickoff UTC date and the day before.
    candidates = {
        (kickoff - timedelta(days=1)).strftime("%Y%m%d"),
        kickoff.strftime("%Y%m%d"),
    }

    async with aiohttp.ClientSession() as session:
        for date_str in sorted(candidates):
            events = await _fetch_date(session, date_str)
            for ev in events:
                if ev["home_team"] == home_team_ru and ev["away_team"] == away_team_ru:
                    return ev
                # ESPN may list teams in swapped orientation — handle that too.
                if ev["home_team"] == away_team_ru and ev["away_team"] == home_team_ru:
                    return {
                        "home_score": ev["away_score"],
                        "away_score": ev["home_score"],
                        "home_winner": not ev["home_winner"],
                        "completed": ev["completed"],
                        "status_name": ev["status_name"],
                        "short_detail": ev["short_detail"],
                    }
    return None
