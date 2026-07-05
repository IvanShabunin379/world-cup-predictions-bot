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


_HOME_SIDE = {"P1", "NP1", "NPP1"}


def playoff_winner_guessed(pred_type: str, actual_type: str) -> bool:
    """True если угадана команда, проходящая дальше (независимо от способа)."""
    return (pred_type in _HOME_SIDE) == (actual_type in _HOME_SIDE)


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
    Scores follow each outcome type's own convention:
      P1/P2  — final score of regular time
      NP1/NP2 — score after extra time (non-draw)
      NPP1/NPP2 — score after 120 minutes (draw)
    pred/actual_type: 'P1'|'P2'|'NP1'|'NP2'|'NPP1'|'NPP2'
    """
    base, bonus = _PO[pred_type][actual_type]
    if bonus is None:
        return base
    if pred_type in ("P1", "P2") and actual_type in ("NPP1", "NPP2"):
        # Прогноз на победу vs фактические пенальти: точный счёт = счёт после
        # 120 минут + решающий гол победителю серии (1:1 + победа гостей → 1:2).
        # Без этого бонус в клетках П1/НПП1 и П2/НПП2 недостижим (счёт победного
        # прогноза никогда не равен ничейному).
        home_won = actual_type == "NPP1"
        eff_home = actual_home + (1 if home_won else 0)
        eff_away = actual_away + (0 if home_won else 1)
        exact = (pred_home == eff_home and pred_away == eff_away)
    else:
        exact = (pred_home == actual_home and pred_away == actual_away)
    return base + (bonus if exact else 0)
