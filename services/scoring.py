"""
Scoring logic for both group stage and playoff.
"""

# ── Group stage ───────────────────────────────────────────────────────────────

def score_group(pred_home: int, pred_away: int, actual_home: int, actual_away: int) -> int:
    if pred_home == actual_home and pred_away == actual_away:
        return 3
    pred_outcome = _outcome(pred_home, pred_away)
    actual_outcome = _outcome(actual_home, actual_away)
    if pred_outcome == actual_outcome:
        return 1
    return 0


def _outcome(home: int, away: int) -> str:
    if home > away:
        return "W1"
    if home < away:
        return "W2"
    return "D"


# ── Playoff ───────────────────────────────────────────────────────────────────
# Points table: POINTS[pred_type][actual_type] = (base, exact_score_bonus)
# exact_score_bonus = None means no bonus is ever applied (exceptions ⬛)

_PO = {
    "P1":   {"P1": (2, 2), "P2": (0, 0), "NP1": (1, 1),  "NP2": (0, 0), "NPP1": (1, 1),  "NPP2": (0, 0)},
    "P2":   {"P1": (0, 0), "P2": (2, 2), "NP1": (0, 0),  "NP2": (1, 1), "NPP1": (0, 0),  "NPP2": (1, 1)},
    "NP1":  {"P1": (1, None),"P2":(0,0), "NP1": (3, 1),  "NP2": (1, 0), "NPP1": (2, None),"NPP2":(1, 0)},
    "NP2":  {"P1": (0, 0), "P2": (1, None),"NP1":(1, 0), "NP2": (3, 1), "NPP1": (1, 0),  "NPP2":(2, None)},
    "NPP1": {"P1": (1, 0), "P2": (0, 0), "NP1": (2, None),"NP2": (1, 0), "NPP1": (3, 1),  "NPP2":(2, 0)},
    "NPP2": {"P1": (0, 0), "P2": (1, 0), "NP1": (1, 0),  "NP2": (2, None),"NPP1": (2, 0), "NPP2":(3, 1)},
}


def score_playoff(
    pred_home: int, pred_away: int, pred_type: str,
    actual_home: int, actual_away: int, actual_type: str,
) -> int:
    """
    pred/actual scores are the 90-minute score.
    pred/actual_type: 'P1'|'P2'|'NP1'|'NP2'|'NPP1'|'NPP2'
    """
    base, bonus = _PO[pred_type][actual_type]
    if bonus is None:
        return base
    exact = (pred_home == actual_home and pred_away == actual_away)
    return base + (bonus if exact else 0)
