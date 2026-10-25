-- Add the training columns to engine_features and fill them from tables
-- that already hold the values. This file does not DELETE, TRUNCATE, or DROP.
-- It does not write any table except engine_features.
-- n_captures is added here and filled by a board count of fen_before.

ALTER TABLE engine_features
  ADD COLUMN IF NOT EXISTS clock_self double precision,
  ADD COLUMN IF NOT EXISTS clock_opp double precision,
  ADD COLUMN IF NOT EXISTS clock_ratio double precision,
  ADD COLUMN IF NOT EXISTS frac_self double precision,
  ADD COLUMN IF NOT EXISTS time_trouble boolean,
  ADD COLUMN IF NOT EXISTS base integer,
  ADD COLUMN IF NOT EXISTS inc integer,
  ADD COLUMN IF NOT EXISTS ply_phase text,
  ADD COLUMN IF NOT EXISTS prev_self_spent double precision,
  ADD COLUMN IF NOT EXISTS avg_self_spent double precision,
  ADD COLUMN IF NOT EXISTS prev_opp_spent double precision,
  ADD COLUMN IF NOT EXISTS color character(1),
  ADD COLUMN IF NOT EXISTS elo_self integer,
  ADD COLUMN IF NOT EXISTS mat_total integer,
  ADD COLUMN IF NOT EXISTS mat_diff integer,
  ADD COLUMN IF NOT EXISTS n_captures integer,
  ADD COLUMN IF NOT EXISTS wp_self double precision,
  ADD COLUMN IF NOT EXISTS abs_cp integer,
  ADD COLUMN IF NOT EXISTS last_swing double precision,
  ADD COLUMN IF NOT EXISTS prev_self_wp_loss double precision,
  ADD COLUMN IF NOT EXISTS prior_blunders_self integer,
  ADD COLUMN IF NOT EXISTS best_possible_move text,
  ADD COLUMN IF NOT EXISTS second_best_move text,
  ADD COLUMN IF NOT EXISTS time_spent double precision,
  ADD COLUMN IF NOT EXISTS blunder smallint,
  ADD COLUMN IF NOT EXISTS blunder_next5 smallint;

WITH src AS (
  SELECT
    e.game_id,
    e.ply,
    m.color,
    r.clk_before_s AS clock_self,
    r.opp_clk_s AS clock_opp,
    r.clk_before_s / GREATEST(r.opp_clk_s, 1) AS clock_ratio,
    mm.clk_frac AS frac_self,
    mm.time_trouble,
    mm.base,
    mm.inc,
    mm.ply_phase,
    CASE WHEN m.color = 'w' THEN r.prev_think_white_s ELSE r.prev_think_black_s END AS prev_self_spent,
    AVG(mm.think_s) OVER (
      PARTITION BY e.game_id, m.color
      ORDER BY e.ply
      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) AS avg_self_spent,
    CASE WHEN m.color = 'w' THEN r.prev_think_black_s ELSE r.prev_think_white_s END AS prev_opp_spent,
    mm.elo AS elo_self,
    r.material_total AS mat_total,
    r.material_advantage_mover AS mat_diff,
    mm.wp_before AS wp_self,
    CASE WHEN mm.eval_before_mover IS NULL THEN NULL ELSE abs(mm.eval_before_mover) END AS abs_cp,
    LAG(mm.wp_loss) OVER (PARTITION BY e.game_id ORDER BY e.ply) AS last_swing,
    LAG(mm.wp_loss) OVER (PARTITION BY e.game_id, m.color ORDER BY e.ply) AS prev_self_wp_loss,
    COALESCE(SUM(CASE WHEN mm.wp_loss >= 20 THEN 1 ELSE 0 END) OVER (
      PARTITION BY e.game_id, m.color
      ORDER BY e.ply
      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ), 0) AS prior_blunders_self,
    b.best_possible_move,
    b.second_best_move,
    b.best_possible_move_wp AS best_wp,
    b.second_best_move_wp AS second_wp,
    b.gap,
    b.n_near_best,
    b.n_legal_moves,
    mm.think_s AS time_spent,
    CASE
      WHEN mm.wp_loss IS NULL THEN NULL
      WHEN mm.wp_loss >= 20 THEN 1
      ELSE 0
    END AS blunder,
    CASE
      WHEN mm.wp_loss IS NULL AND e.ply = 1 THEN 0
      WHEN mm.wp_loss IS NULL THEN NULL
      WHEN mm.wp_loss >= 20 THEN 1
      ELSE 0
    END AS window_blunder
  FROM engine_features e
  JOIN moves m USING (game_id, ply)
  JOIN move_replay r USING (game_id, ply)
  JOIN move_metrics mm USING (game_id, ply)
  JOIN best_next_move b USING (game_id, ply)
),
ready AS (
  SELECT
    src.*,
    LEAD(window_blunder, 1) OVER w AS b1,
    LEAD(window_blunder, 2) OVER w AS b2,
    LEAD(window_blunder, 3) OVER w AS b3,
    LEAD(window_blunder, 4) OVER w AS b4,
    LEAD(ply, 1) OVER w AS ply1,
    LEAD(ply, 2) OVER w AS ply2,
    LEAD(ply, 3) OVER w AS ply3,
    LEAD(ply, 4) OVER w AS ply4
  FROM src
  WINDOW w AS (PARTITION BY game_id, color ORDER BY ply)
)
UPDATE engine_features e
SET
  clock_self = ready.clock_self,
  clock_opp = ready.clock_opp,
  clock_ratio = ready.clock_ratio,
  frac_self = ready.frac_self,
  time_trouble = ready.time_trouble,
  base = ready.base,
  inc = ready.inc,
  ply_phase = ready.ply_phase,
  prev_self_spent = ready.prev_self_spent,
  avg_self_spent = ready.avg_self_spent,
  prev_opp_spent = ready.prev_opp_spent,
  color = ready.color,
  elo_self = ready.elo_self,
  mat_total = ready.mat_total,
  mat_diff = ready.mat_diff,
  wp_self = ready.wp_self,
  abs_cp = ready.abs_cp,
  last_swing = ready.last_swing,
  prev_self_wp_loss = ready.prev_self_wp_loss,
  prior_blunders_self = ready.prior_blunders_self,
  best_possible_move = ready.best_possible_move,
  second_best_move = ready.second_best_move,
  best_wp = ready.best_wp,
  second_wp = ready.second_wp,
  gap = ready.gap,
  n_near_best = ready.n_near_best,
  n_legal_moves = ready.n_legal_moves,
  time_spent = ready.time_spent,
  blunder = ready.blunder,
  blunder_next5 = CASE
    WHEN ready.window_blunder = 1 OR ready.b1 = 1 OR ready.b2 = 1 OR ready.b3 = 1 OR ready.b4 = 1 THEN 1
    WHEN ready.window_blunder IS NULL
      OR (ready.ply1 IS NOT NULL AND ready.b1 IS NULL)
      OR (ready.ply2 IS NOT NULL AND ready.b2 IS NULL)
      OR (ready.ply3 IS NOT NULL AND ready.b3 IS NULL)
      OR (ready.ply4 IS NOT NULL AND ready.b4 IS NULL)
    THEN NULL
    ELSE 0
  END
FROM ready
WHERE e.game_id = ready.game_id
  AND e.ply = ready.ply;
