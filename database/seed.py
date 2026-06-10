"""
Run once to seed the database: leagues, users, and all group-stage matches.
Usage: python -m database.seed
"""
import asyncio
from database.db import get_db
from data.matches import GROUP_STAGE_MATCHES
from config import PRIVATE_LEAGUE_NAME, PUBLIC_LEAGUE_NAME, VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID


def seed():
    db = get_db()

    # ── Leagues ──────────────────────────────────────────────
    existing = db.table("leagues").select("id, type").execute().data
    league_types = {l["type"]: l["id"] for l in existing}

    if "private" not in league_types:
        res = db.table("leagues").insert({"name": PRIVATE_LEAGUE_NAME, "type": "private"}).execute()
        private_id = res.data[0]["id"]
        print(f"Created private league id={private_id}")
    else:
        private_id = league_types["private"]
        print(f"Private league already exists id={private_id}")

    if "public" not in league_types:
        res = db.table("leagues").insert({"name": PUBLIC_LEAGUE_NAME, "type": "public"}).execute()
        public_id = res.data[0]["id"]
        print(f"Created public league id={public_id}")
    else:
        public_id = league_types["public"]
        print(f"Public league already exists id={public_id}")

    # ── Private league users ──────────────────────────────────
    for tg_id, name in [(VANYA_TELEGRAM_ID, "Ваня"), (NIK_TELEGRAM_ID, "Ник")]:
        if tg_id == 0:
            print(f"WARNING: {name} telegram_id is 0 — fill in .env first!")
            continue
        user = db.table("users").select("id").eq("telegram_id", tg_id).execute().data
        if not user:
            res = db.table("users").insert({"telegram_id": tg_id, "name": name}).execute()
            user_id = res.data[0]["id"]
            print(f"Created user {name} id={user_id}")
        else:
            user_id = user[0]["id"]
            print(f"User {name} already exists id={user_id}")

        member = db.table("league_members").select("user_id").eq("league_id", private_id).eq("user_id", user_id).execute().data
        if not member:
            db.table("league_members").insert({"league_id": private_id, "user_id": user_id}).execute()
            print(f"  Added {name} to private league")

    # ── Matches ───────────────────────────────────────────────
    existing_matches = db.table("matches").select("id").execute().data
    if existing_matches:
        print(f"Matches already seeded ({len(existing_matches)} rows), skipping.")
    else:
        rows = [
            {
                "home_team": m["home_team"],
                "away_team": m["away_team"],
                "kickoff_at": m["kickoff_at"],
                "stage": "group",
                "group_name": m["group_name"],
                "round": m["round"],
                "status": "upcoming",
            }
            for m in GROUP_STAGE_MATCHES
        ]
        db.table("matches").insert(rows).execute()
        print(f"Inserted {len(rows)} group stage matches.")


if __name__ == "__main__":
    seed()
