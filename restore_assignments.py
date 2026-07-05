"""
One-off script: regenerates match_assignments with proper stratification.
Re-runs the same algorithm as /assignmatches but with a fixed seed so the
result is reproducible. Run once; after that predict.py no longer overwrites.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from services.match_assignments import generate_assignments
from database.db import get_db
from config import VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID

db = get_db()
vanya_id = db.table("users").select("id").eq("telegram_id", VANYA_TELEGRAM_ID).execute().data[0]["id"]
nik_id   = db.table("users").select("id").eq("telegram_id", NIK_TELEGRAM_ID).execute().data[0]["id"]

assignments = generate_assignments(seed=42)

vanya_count = sum(1 for uid in assignments.values() if uid == vanya_id)
nik_count   = sum(1 for uid in assignments.values() if uid == nik_id)
print(f"Assigned {len(assignments)} matches: Ваня={vanya_count}, Ник={nik_count}")

# Quick sanity: show Group B round 2
rows = db.table("match_assignments").select(
    "match_id, first_user_id, matches(home_team, away_team, group_name, round)"
).in_("match_id", list(assignments.keys())).execute().data

group_b_r2 = [r for r in rows if (r.get("matches") or {}).get("group_name") == "B"
                               and (r.get("matches") or {}).get("round") == 2]
for r in group_b_r2:
    m = r["matches"]
    name = "Ваня" if r["first_user_id"] == vanya_id else "Ник"
    print(f"  Группа B Тур 2: {m['home_team']} – {m['away_team']} → первый: {name}")
