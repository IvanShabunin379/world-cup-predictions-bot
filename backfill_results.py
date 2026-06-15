"""
One-off backfill: fetch results for all past matches from ESPN, update the
matches table, and compute points for every prediction. Safe to re-run.
"""
import asyncio
import io
import sys
from datetime import timezone
from dateutil import parser as dtparser

from database.db import get_db
from services.espn import fetch_match_result
from services.scoring import score_group, score_playoff
from utils.timezone import now_utc

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


async def main():
    db = get_db()
    now = now_utc()

    matches = db.table("matches").select("*").execute().data
    past = [
        m for m in matches
        if dtparser.parse(m["kickoff_at"]).replace(tzinfo=timezone.utc) < now
    ]
    print(f"Past matches to check: {len(past)}")

    updated = 0
    for m in past:
        result = await fetch_match_result(m["kickoff_at"], m["home_team"], m["away_team"])
        if not result or not result.get("completed") or result["home_score"] is None:
            print(f"  ⏳ no result yet: {m['home_team']} — {m['away_team']}")
            continue

        hs, as_ = result["home_score"], result["away_score"]

        if m["status"] != "finished" or m["home_score"] != hs or m["away_score"] != as_:
            db.table("matches").update({
                "home_score": hs, "away_score": as_, "status": "finished",
            }).eq("id", m["id"]).execute()
            updated += 1

        # Compute points for all predictions on this match
        preds = db.table("predictions").select("*").eq("match_id", m["id"]).execute().data
        for p in preds:
            if m["stage"] == "group":
                pts = score_group(p["home_score"], p["away_score"], hs, as_)
            else:
                pts = score_playoff(
                    p["home_score"], p["away_score"], p["outcome_type"],
                    hs, as_, m.get("outcome"),
                )
            db.table("predictions").update({"points": pts}).eq("id", p["id"]).execute()

        print(f"  ✅ {m['home_team']} {hs}:{as_} {m['away_team']}  ({len(preds)} прогнозов)")

    print(f"\nDone. Matches updated: {updated}")


if __name__ == "__main__":
    asyncio.run(main())
