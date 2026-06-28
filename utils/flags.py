TEAM_FLAGS: dict[str, str] = {
    # Group A
    "Мексика":            "🇲🇽",
    "ЮАР":                "🇿🇦",
    "Южная Корея":        "🇰🇷",
    "Чехия":              "🇨🇿",
    # Group B
    "Канада":             "🇨🇦",
    "Босния и Герц.":     "🇧🇦",
    "Катар":              "🇶🇦",
    "Швейцария":          "🇨🇭",
    # Group C
    "Бразилия":           "🇧🇷",
    "Марокко":            "🇲🇦",
    "Гаити":              "🇭🇹",
    "Шотландия":          "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    # Group D
    "США":                "🇺🇸",
    "Парагвай":           "🇵🇾",
    "Австралия":          "🇦🇺",
    "Турция":             "🇹🇷",
    # Group E
    "Германия":           "🇩🇪",
    "Кюрасао":            "🇨🇼",
    "Кот-д'Ивуар":        "🇨🇮",
    "Эквадор":            "🇪🇨",
    # Group F
    "Нидерланды":         "🇳🇱",
    "Япония":             "🇯🇵",
    "Швеция":             "🇸🇪",
    "Тунис":              "🇹🇳",
    # Group G
    "Бельгия":            "🇧🇪",
    "Египет":             "🇪🇬",
    "Иран":               "🇮🇷",
    "Новая Зеландия":     "🇳🇿",
    # Group H
    "Испания":            "🇪🇸",
    "Кабо-Верде":         "🇨🇻",
    "Саудовская Аравия":  "🇸🇦",
    "Уругвай":            "🇺🇾",
    # Group I
    "Франция":            "🇫🇷",
    "Сенегал":            "🇸🇳",
    "Ирак":               "🇮🇶",
    "Норвегия":           "🇳🇴",
    # Group J
    "Аргентина":          "🇦🇷",
    "Алжир":              "🇩🇿",
    "Австрия":            "🇦🇹",
    "Иордания":           "🇯🇴",
    # Group K
    "Португалия":         "🇵🇹",
    "ДР Конго":           "🇨🇩",
    "Узбекистан":         "🇺🇿",
    "Колумбия":           "🇨🇴",
    # Group L
    "Англия":             "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "Хорватия":           "🇭🇷",
    "Гана":               "🇬🇭",
    "Панама":             "🇵🇦",
}


def flag(team: str) -> str:
    return TEAM_FLAGS.get(team, "🏳")


def fmt_team(team: str) -> str:
    return f"{flag(team)} {team}"


def fmt_match(home: str, away: str) -> str:
    return f"{flag(home)} {home} – {flag(away)} {away}"


def fmt_pred_short(pred: dict, home_team: str, away_team: str) -> str:
    """Short prediction label: '4:2 доп. вр.' / '1:1, Аргентина по пен.' / '2:1'"""
    hs, as_ = pred["home_score"], pred["away_score"]
    ot = pred.get("outcome_type")
    if not ot or ot in ("P1", "P2"):
        return f"{hs}:{as_}"
    elif ot in ("NP1", "NP2"):
        return f"{hs}:{as_} доп. вр."
    else:  # NPP1, NPP2
        winner = home_team if ot == "NPP1" else away_team
        return f"{hs}:{as_}, {winner} по пен."


def fmt_playoff_confirm(match: dict, hs: int, as_: int, outcome: str | None) -> str:
    """Full confirmation line: '🇦🇷 Аргентина 4:2 (доп. вр.) 🇫🇷 Франция'"""
    h, a = match["home_team"], match["away_team"]
    fh, fa = flag(h), flag(a)
    if not outcome or outcome in ("P1", "P2"):
        return f"{fh} {h} {hs}:{as_} {fa} {a}"
    elif outcome in ("NP1", "NP2"):
        return f"{fh} {h} {hs}:{as_} (доп. вр.) {fa} {a}"
    else:  # NPP1, NPP2
        winner = h if outcome == "NPP1" else a
        return f"{fh} {h} {hs}:{as_} {fa} {a}\n(по пен. {winner})"
