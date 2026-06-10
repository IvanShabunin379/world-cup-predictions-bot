"""
Generates who predicts first (Vanya or Nik) for each group-stage match.

Stratification:
1. Each group: exactly 3 matches per player.
2. Within each group, each round: exactly 1 match per player (from the 2 matches of that round).
3. Within each round-pair in a group, the "stronger" match (lower sum of FIFA ranks =
   more predictable) is assigned randomly but balanced globally across both players.
"""
import random
from database.db import get_db
from data.matches import FIFA_RANKINGS
from config import VANYA_TELEGRAM_ID, NIK_TELEGRAM_ID


def _strength(home: str, away: str) -> int:
    """Lower = more predictable (both teams are higher ranked)."""
    return FIFA_RANKINGS.get(home, 150) + FIFA_RANKINGS.get(away, 150)


def generate_assignments(seed: int | None = None) -> dict[int, int]:
    """
    Returns {match_id: first_user_id} for all group-stage matches.
    Saves results to match_assignments table.
    """
    if seed is not None:
        random.seed(seed)

    db = get_db()
    vanya = db.table("users").select("id").eq("telegram_id", VANYA_TELEGRAM_ID).execute().data[0]["id"]
    nik = db.table("users").select("id").eq("telegram_id", NIK_TELEGRAM_ID).execute().data[0]["id"]
    players = [vanya, nik]

    matches = (
        db.table("matches")
        .select("id, home_team, away_team, group_name, round")
        .eq("stage", "group")
        .order("group_name")
        .order("round")
        .execute()
        .data
    )

    # Group matches by (group, round)
    from collections import defaultdict
    by_group_round: dict[tuple, list] = defaultdict(list)
    for m in matches:
        by_group_round[(m["group_name"], m["round"])].append(m)

    assignments: dict[int, int] = {}
    # Track how many "strong" matches each player gets globally
    strong_count = {vanya: 0, nik: 0}

    groups = sorted({m["group_name"] for m in matches})
    for group in groups:
        # Determine who goes first in round 1 of this group (flip each round)
        first_player_idx = random.randint(0, 1)
        for rnd in [1, 2, 3]:
            pair = by_group_round.get((group, rnd), [])
            if len(pair) != 2:
                continue
            m1, m2 = sorted(pair, key=lambda m: _strength(m["home_team"], m["away_team"]))
            # m1 = stronger (more predictable, lower sum), m2 = weaker
            p_first = players[first_player_idx % 2]
            p_second = players[(first_player_idx + 1) % 2]

            # Decide which player gets the stronger match
            # Balance: give strong match to whoever has fewer strong matches so far
            if strong_count[p_first] <= strong_count[p_second]:
                assignments[m1["id"]] = p_first
                assignments[m2["id"]] = p_second
                strong_count[p_first] += 1
            else:
                assignments[m1["id"]] = p_second
                assignments[m2["id"]] = p_first
                strong_count[p_second] += 1

            first_player_idx += 1  # alternate per round

    # Save to DB
    rows = [{"match_id": mid, "first_user_id": uid} for mid, uid in assignments.items()]
    db.table("match_assignments").delete().neq("match_id", 0).execute()
    db.table("match_assignments").insert(rows).execute()

    return assignments
