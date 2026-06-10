"""
Group stage matches for WC 2026.
All kickoff_at times are in UTC.
Moscow time = UTC+3.
"""

GROUP_STAGE_MATCHES = [
    # ── GROUP A ──────────────────────────────────────────────
    {"home_team": "Мексика",           "away_team": "ЮАР",          "kickoff_at": "2026-06-11T19:00:00Z", "group_name": "A", "round": 1},
    {"home_team": "Южная Корея",       "away_team": "Чехия",         "kickoff_at": "2026-06-12T02:00:00Z", "group_name": "A", "round": 1},
    {"home_team": "Чехия",             "away_team": "ЮАР",           "kickoff_at": "2026-06-18T16:00:00Z", "group_name": "A", "round": 2},
    {"home_team": "Мексика",           "away_team": "Южная Корея",   "kickoff_at": "2026-06-19T01:00:00Z", "group_name": "A", "round": 2},
    {"home_team": "Чехия",             "away_team": "Мексика",       "kickoff_at": "2026-06-25T01:00:00Z", "group_name": "A", "round": 3},
    {"home_team": "ЮАР",               "away_team": "Южная Корея",   "kickoff_at": "2026-06-25T01:00:00Z", "group_name": "A", "round": 3},

    # ── GROUP B ──────────────────────────────────────────────
    {"home_team": "Канада",            "away_team": "Босния и Герц.", "kickoff_at": "2026-06-12T19:00:00Z", "group_name": "B", "round": 1},
    {"home_team": "Катар",             "away_team": "Швейцария",      "kickoff_at": "2026-06-13T19:00:00Z", "group_name": "B", "round": 1},
    {"home_team": "Швейцария",         "away_team": "Босния и Герц.", "kickoff_at": "2026-06-18T19:00:00Z", "group_name": "B", "round": 2},
    {"home_team": "Канада",            "away_team": "Катар",          "kickoff_at": "2026-06-18T22:00:00Z", "group_name": "B", "round": 2},
    {"home_team": "Швейцария",         "away_team": "Канада",         "kickoff_at": "2026-06-24T19:00:00Z", "group_name": "B", "round": 3},
    {"home_team": "Босния и Герц.",    "away_team": "Катар",          "kickoff_at": "2026-06-24T19:00:00Z", "group_name": "B", "round": 3},

    # ── GROUP C ──────────────────────────────────────────────
    {"home_team": "Бразилия",          "away_team": "Марокко",        "kickoff_at": "2026-06-13T22:00:00Z", "group_name": "C", "round": 1},
    {"home_team": "Гаити",             "away_team": "Шотландия",      "kickoff_at": "2026-06-14T01:00:00Z", "group_name": "C", "round": 1},
    {"home_team": "Шотландия",         "away_team": "Марокко",        "kickoff_at": "2026-06-19T22:00:00Z", "group_name": "C", "round": 2},
    {"home_team": "Бразилия",          "away_team": "Гаити",          "kickoff_at": "2026-06-20T00:30:00Z", "group_name": "C", "round": 2},
    {"home_team": "Шотландия",         "away_team": "Бразилия",       "kickoff_at": "2026-06-24T22:00:00Z", "group_name": "C", "round": 3},
    {"home_team": "Марокко",           "away_team": "Гаити",          "kickoff_at": "2026-06-24T22:00:00Z", "group_name": "C", "round": 3},

    # ── GROUP D ──────────────────────────────────────────────
    {"home_team": "США",               "away_team": "Парагвай",       "kickoff_at": "2026-06-13T01:00:00Z", "group_name": "D", "round": 1},
    {"home_team": "Австралия",         "away_team": "Турция",         "kickoff_at": "2026-06-14T04:00:00Z", "group_name": "D", "round": 1},
    {"home_team": "США",               "away_team": "Австралия",      "kickoff_at": "2026-06-19T19:00:00Z", "group_name": "D", "round": 2},
    {"home_team": "Турция",            "away_team": "Парагвай",       "kickoff_at": "2026-06-20T03:00:00Z", "group_name": "D", "round": 2},
    {"home_team": "Турция",            "away_team": "США",             "kickoff_at": "2026-06-26T02:00:00Z", "group_name": "D", "round": 3},
    {"home_team": "Парагвай",          "away_team": "Австралия",      "kickoff_at": "2026-06-26T02:00:00Z", "group_name": "D", "round": 3},

    # ── GROUP E ──────────────────────────────────────────────
    {"home_team": "Германия",          "away_team": "Кюрасао",        "kickoff_at": "2026-06-14T17:00:00Z", "group_name": "E", "round": 1},
    {"home_team": "Кот-д'Ивуар",      "away_team": "Эквадор",        "kickoff_at": "2026-06-14T23:00:00Z", "group_name": "E", "round": 1},
    {"home_team": "Германия",          "away_team": "Кот-д'Ивуар",   "kickoff_at": "2026-06-20T20:00:00Z", "group_name": "E", "round": 2},
    {"home_team": "Эквадор",           "away_team": "Кюрасао",        "kickoff_at": "2026-06-21T00:00:00Z", "group_name": "E", "round": 2},
    {"home_team": "Кюрасао",           "away_team": "Кот-д'Ивуар",   "kickoff_at": "2026-06-25T20:00:00Z", "group_name": "E", "round": 3},
    {"home_team": "Эквадор",           "away_team": "Германия",       "kickoff_at": "2026-06-25T20:00:00Z", "group_name": "E", "round": 3},

    # ── GROUP F ──────────────────────────────────────────────
    {"home_team": "Нидерланды",        "away_team": "Япония",         "kickoff_at": "2026-06-14T20:00:00Z", "group_name": "F", "round": 1},
    {"home_team": "Швеция",            "away_team": "Тунис",          "kickoff_at": "2026-06-15T02:00:00Z", "group_name": "F", "round": 1},
    {"home_team": "Нидерланды",        "away_team": "Швеция",         "kickoff_at": "2026-06-20T17:00:00Z", "group_name": "F", "round": 2},
    {"home_team": "Тунис",             "away_team": "Япония",         "kickoff_at": "2026-06-21T04:00:00Z", "group_name": "F", "round": 2},
    {"home_team": "Япония",            "away_team": "Швеция",         "kickoff_at": "2026-06-25T23:00:00Z", "group_name": "F", "round": 3},
    {"home_team": "Тунис",             "away_team": "Нидерланды",     "kickoff_at": "2026-06-25T23:00:00Z", "group_name": "F", "round": 3},

    # ── GROUP G ──────────────────────────────────────────────
    {"home_team": "Бельгия",           "away_team": "Египет",         "kickoff_at": "2026-06-15T19:00:00Z", "group_name": "G", "round": 1},
    {"home_team": "Иран",              "away_team": "Новая Зеландия", "kickoff_at": "2026-06-16T01:00:00Z", "group_name": "G", "round": 1},
    {"home_team": "Бельгия",           "away_team": "Иран",           "kickoff_at": "2026-06-21T19:00:00Z", "group_name": "G", "round": 2},
    {"home_team": "Новая Зеландия",    "away_team": "Египет",         "kickoff_at": "2026-06-22T01:00:00Z", "group_name": "G", "round": 2},
    {"home_team": "Египет",            "away_team": "Иран",           "kickoff_at": "2026-06-27T03:00:00Z", "group_name": "G", "round": 3},
    {"home_team": "Новая Зеландия",    "away_team": "Бельгия",        "kickoff_at": "2026-06-27T03:00:00Z", "group_name": "G", "round": 3},

    # ── GROUP H ──────────────────────────────────────────────
    {"home_team": "Испания",           "away_team": "Кабо-Верде",     "kickoff_at": "2026-06-15T16:00:00Z", "group_name": "H", "round": 1},
    {"home_team": "Саудовская Аравия", "away_team": "Уругвай",        "kickoff_at": "2026-06-15T22:00:00Z", "group_name": "H", "round": 1},
    {"home_team": "Испания",           "away_team": "Саудовская Аравия","kickoff_at": "2026-06-21T16:00:00Z", "group_name": "H", "round": 2},
    {"home_team": "Уругвай",           "away_team": "Кабо-Верде",     "kickoff_at": "2026-06-21T22:00:00Z", "group_name": "H", "round": 2},
    {"home_team": "Кабо-Верде",        "away_team": "Саудовская Аравия","kickoff_at": "2026-06-27T00:00:00Z", "group_name": "H", "round": 3},
    {"home_team": "Уругвай",           "away_team": "Испания",        "kickoff_at": "2026-06-27T00:00:00Z", "group_name": "H", "round": 3},

    # ── GROUP I ──────────────────────────────────────────────
    {"home_team": "Франция",           "away_team": "Сенегал",        "kickoff_at": "2026-06-16T19:00:00Z", "group_name": "I", "round": 1},
    {"home_team": "Ирак",              "away_team": "Норвегия",       "kickoff_at": "2026-06-16T22:00:00Z", "group_name": "I", "round": 1},
    {"home_team": "Франция",           "away_team": "Ирак",           "kickoff_at": "2026-06-22T21:00:00Z", "group_name": "I", "round": 2},
    {"home_team": "Норвегия",          "away_team": "Сенегал",        "kickoff_at": "2026-06-23T00:00:00Z", "group_name": "I", "round": 2},
    {"home_team": "Норвегия",          "away_team": "Франция",        "kickoff_at": "2026-06-26T19:00:00Z", "group_name": "I", "round": 3},
    {"home_team": "Сенегал",           "away_team": "Ирак",           "kickoff_at": "2026-06-26T19:00:00Z", "group_name": "I", "round": 3},

    # ── GROUP J ──────────────────────────────────────────────
    {"home_team": "Аргентина",         "away_team": "Алжир",          "kickoff_at": "2026-06-17T01:00:00Z", "group_name": "J", "round": 1},
    {"home_team": "Австрия",           "away_team": "Иордания",       "kickoff_at": "2026-06-17T04:00:00Z", "group_name": "J", "round": 1},
    {"home_team": "Аргентина",         "away_team": "Австрия",        "kickoff_at": "2026-06-22T17:00:00Z", "group_name": "J", "round": 2},
    {"home_team": "Иордания",          "away_team": "Алжир",          "kickoff_at": "2026-06-23T03:00:00Z", "group_name": "J", "round": 2},
    {"home_team": "Алжир",             "away_team": "Австрия",        "kickoff_at": "2026-06-28T02:00:00Z", "group_name": "J", "round": 3},
    {"home_team": "Иордания",          "away_team": "Аргентина",      "kickoff_at": "2026-06-28T02:00:00Z", "group_name": "J", "round": 3},

    # ── GROUP K ──────────────────────────────────────────────
    {"home_team": "Португалия",        "away_team": "ДР Конго",       "kickoff_at": "2026-06-17T17:00:00Z", "group_name": "K", "round": 1},
    {"home_team": "Узбекистан",        "away_team": "Колумбия",       "kickoff_at": "2026-06-18T02:00:00Z", "group_name": "K", "round": 1},
    {"home_team": "Португалия",        "away_team": "Узбекистан",     "kickoff_at": "2026-06-23T17:00:00Z", "group_name": "K", "round": 2},
    {"home_team": "Колумбия",          "away_team": "ДР Конго",       "kickoff_at": "2026-06-24T02:00:00Z", "group_name": "K", "round": 2},
    {"home_team": "Колумбия",          "away_team": "Португалия",     "kickoff_at": "2026-06-27T23:30:00Z", "group_name": "K", "round": 3},
    {"home_team": "ДР Конго",          "away_team": "Узбекистан",     "kickoff_at": "2026-06-27T23:30:00Z", "group_name": "K", "round": 3},

    # ── GROUP L ──────────────────────────────────────────────
    {"home_team": "Англия",            "away_team": "Хорватия",       "kickoff_at": "2026-06-17T20:00:00Z", "group_name": "L", "round": 1},
    {"home_team": "Гана",              "away_team": "Панама",         "kickoff_at": "2026-06-17T23:00:00Z", "group_name": "L", "round": 1},
    {"home_team": "Англия",            "away_team": "Гана",           "kickoff_at": "2026-06-23T20:00:00Z", "group_name": "L", "round": 2},
    {"home_team": "Панама",            "away_team": "Хорватия",       "kickoff_at": "2026-06-23T23:00:00Z", "group_name": "L", "round": 2},
    {"home_team": "Панама",            "away_team": "Англия",         "kickoff_at": "2026-06-27T21:00:00Z", "group_name": "L", "round": 3},
    {"home_team": "Хорватия",          "away_team": "Гана",           "kickoff_at": "2026-06-27T21:00:00Z", "group_name": "L", "round": 3},
]

# FIFA rankings (April 2026) for stratification in /assignmatches
FIFA_RANKINGS = {
    "Франция": 1,
    "Испания": 2,
    "Аргентина": 3,
    "Англия": 4,
    "Португалия": 5,
    "Бразилия": 6,
    "Нидерланды": 7,
    "Марокко": 8,
    "Бельгия": 9,
    "Германия": 10,
    "Хорватия": 12,
    "Колумбия": 13,
    "Сенегал": 14,
    "Мексика": 15,
    "США": 16,
    "Уругвай": 17,
    "Япония": 18,
    "Швейцария": 19,
    "Южная Корея": 22,
    "Австралия": 24,
    "Иран": 24,
    "Австрия": 28,
    "Швеция": 28,
    "Эквадор": 30,
    "Турция": 36,
    "Чехия": 40,
    "Кот-д'Ивуар": 45,
    "Норвегия": 48,
    "Канада": 48,
    "Босния и Герц.": 50,
    "Египет": 52,
    "Панама": 55,
    "Саудовская Аравия": 58,
    "Алжир": 60,
    "Кабо-Верде": 62,
    "Гана": 62,
    "ЮАР": 65,
    "Парагвай": 68,
    "ДР Конго": 68,
    "Катар": 72,
    "Ирак": 75,
    "Иордания": 88,
    "Узбекистан": 90,
    "Новая Зеландия": 100,
    "Гаити": 110,
    "Кюрасао": 130,
}
