-- WC 2026 Predictions Bot — Supabase Schema

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE leagues (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('private', 'public')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE league_members (
    league_id BIGINT REFERENCES leagues(id),
    user_id BIGINT REFERENCES users(id),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (league_id, user_id)
);

CREATE TABLE matches (
    id BIGSERIAL PRIMARY KEY,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    kickoff_at TIMESTAMPTZ NOT NULL,
    stage TEXT NOT NULL DEFAULT 'group',   -- 'group' | 'r32' | 'r16' | 'qf' | 'sf' | '3rd' | 'final'
    group_name TEXT,                        -- 'A'..'L', NULL for knockout
    round INTEGER,                          -- 1, 2, or 3 within group
    home_score INTEGER,
    away_score INTEGER,
    outcome TEXT CHECK (outcome IN ('P1','P2','NP1','NP2','NPP1','NPP2')),
    status TEXT NOT NULL DEFAULT 'upcoming' -- 'upcoming' | 'live' | 'finished'
);

CREATE TABLE match_assignments (
    match_id BIGINT REFERENCES matches(id) PRIMARY KEY,
    first_user_id BIGINT REFERENCES users(id)
);

CREATE TABLE predictions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    match_id BIGINT REFERENCES matches(id),
    league_id BIGINT REFERENCES leagues(id),
    home_score INTEGER NOT NULL,
    away_score INTEGER NOT NULL,
    outcome_type TEXT,   -- NULL for group stage; 'P1'|'P2'|'NP1'|'NP2'|'NPP1'|'NPP2' for knockout
    points INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, match_id, league_id)
);

CREATE TABLE invite_tokens (
    token TEXT PRIMARY KEY,
    league_id BIGINT REFERENCES leagues(id),
    created_by BIGINT REFERENCES users(id),
    expires_at TIMESTAMPTZ,
    used BOOLEAN DEFAULT FALSE
);

-- Indexes
CREATE INDEX idx_matches_kickoff ON matches(kickoff_at);
CREATE INDEX idx_predictions_user ON predictions(user_id);
CREATE INDEX idx_predictions_match ON predictions(match_id);
