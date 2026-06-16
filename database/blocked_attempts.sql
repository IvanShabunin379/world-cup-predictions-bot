-- Records when the second predictor in the private (Братья) league wanted the
-- exact score already taken by the first predictor and had to choose another.
-- The "wanted" score equals the first predictor's score, so we only store WHO was blocked.

create table if not exists blocked_attempts (
    id bigserial primary key,
    match_id bigint references matches(id),
    user_id bigint references users(id),
    created_at timestamptz default now(),
    unique (match_id, user_id)
);

-- Seed the known historical cases (Vanya=1, Nik=2):
insert into blocked_attempts (match_id, user_id) values
    (8,  2),   -- Катар – Швейцария: Ник хотел 0:3
    (13, 2),   -- Бразилия – Марокко: Ник хотел 1:1
    (20, 1),   -- Австралия – Турция: Ваня хотел 1:2
    (49, 1)    -- Франция – Сенегал: Ваня хотел 1:1
on conflict do nothing;
