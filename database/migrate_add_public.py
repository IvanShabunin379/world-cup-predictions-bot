"""
One-time migration: add Vanya and Nik to the public league.
Run: python -m database.migrate_add_public
"""
from database.db import get_db
from config import VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID


def migrate():
    db = get_db()

    public = db.table("leagues").select("id").eq("type", "public").execute().data
    if not public:
        print("Public league not found — run seed.py first.")
        return
    public_id = public[0]["id"]

    for tg_id, name in [(VANYA_TELEGRAM_ID, "Ваня"), (NIK_TELEGRAM_ID, "Ник")]:
        user = db.table("users").select("id").eq("telegram_id", tg_id).execute().data
        if not user:
            print(f"{name} not in users table yet — they need to /start first.")
            continue
        user_id = user[0]["id"]

        existing = (
            db.table("league_members")
            .select("user_id")
            .eq("league_id", public_id)
            .eq("user_id", user_id)
            .execute()
            .data
        )
        if existing:
            print(f"{name} already in public league.")
        else:
            db.table("league_members").insert({"league_id": public_id, "user_id": user_id}).execute()
            print(f"Added {name} to public league (id={public_id}).")


if __name__ == "__main__":
    migrate()
