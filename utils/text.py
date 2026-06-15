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
