def plural_points(n: int) -> str:
    """Russian plural for 'очко': 1 очко, 3 очка, 5 очков."""
    if 11 <= n % 100 <= 14:
        return "очков"
    last = n % 10
    if last == 1:
        return "очко"
    if 2 <= last <= 4:
        return "очка"
    return "очков"


def pred_result_label(pts, is_playoff: bool, winner_ok: bool) -> str:
    """Emoji + points for a scored prediction.

    ✅🎯 = максимум (группа 3, плей-офф 4); ✅ = угадан победитель/исход;
    🟡 = очки есть, но победитель не угадан (только плей-офф); ❌ = 0.
    """
    pts = pts or 0
    if pts == (4 if is_playoff else 3):
        emoji = "✅🎯"
    elif winner_ok if is_playoff else pts > 0:
        emoji = "✅"
    elif pts > 0:
        emoji = "🟡"
    else:
        emoji = "❌"
    return f"{emoji} {pts} {plural_points(pts)}"
