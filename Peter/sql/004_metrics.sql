-- Rebuild move_metrics from games + moves. Safe to rerun.

TRUNCATE move_metrics;

INSERT INTO move_metrics
WITH base AS (
  SELECT
    m.game_id,
    m.ply,
    m.color,
    m.clk_after_s,
    m.eval_cp,
    g.base,
    g.inc,
    g.white_elo,
    g.black_elo,
    CASE WHEN m.color = 'w' THEN g.white_elo ELSE g.black_elo END AS elo,
    CASE WHEN m.color = 'w' THEN g.black_elo ELSE g.white_elo END AS opp_elo,
    LAG(m.clk_after_s) OVER (
      PARTITION BY m.game_id, m.color ORDER BY m.ply
    ) AS prev_clk,
    LAG(m.eval_cp) OVER (
      PARTITION BY m.game_id ORDER BY m.ply
    ) AS eval_before_white
  FROM moves m
  JOIN games g USING (game_id)
),
calc AS (
  SELECT
    game_id,
    ply,
    color,
    elo,
    opp_elo,
    elo - opp_elo AS elo_diff,
    (elo / 200) * 200 AS rating_band,
    base,
    inc,
    base::text || '+' || inc::text AS tc,
    COALESCE(prev_clk, base::double precision) AS clk_before_s,
    clk_after_s,
    COALESCE(prev_clk, base::double precision) - clk_after_s + inc AS think_s,
    CASE
      WHEN color = 'w' THEN eval_before_white
      ELSE -eval_before_white
    END AS eval_before_mover,
    CASE
      WHEN color = 'w' THEN eval_cp
      ELSE -eval_cp
    END AS eval_after_mover
  FROM base
)
SELECT
  game_id,
  ply,
  color,
  elo,
  opp_elo,
  elo_diff,
  rating_band,
  base,
  inc,
  tc,
  clk_before_s,
  clk_after_s,
  think_s,
  clk_before_s / NULLIF(base, 0) AS clk_frac,
  CASE
    WHEN clk_before_s / NULLIF(base, 0) < 0.10 THEN 'lt10'
    WHEN clk_before_s / NULLIF(base, 0) < 0.30 THEN '10to30'
    WHEN clk_before_s / NULLIF(base, 0) < 0.60 THEN '30to60'
    ELSE 'gt60'
  END AS clk_frac_band,
  CASE
    WHEN ply <= 20 THEN 'opening'
    WHEN ply <= 60 THEN 'middlegame'
    ELSE 'endgame'
  END AS ply_phase,
  eval_before_mover,
  eval_after_mover,
  CASE
    WHEN eval_before_mover IS NULL THEN NULL
    ELSE wp_from_cp(eval_before_mover::double precision)
  END AS wp_before,
  wp_from_cp(eval_after_mover::double precision) AS wp_after,
  CASE
    WHEN eval_before_mover IS NULL THEN NULL
    ELSE wp_from_cp(eval_before_mover::double precision)
         - wp_from_cp(eval_after_mover::double precision)
  END AS wp_loss,
  CASE
    WHEN eval_before_mover IS NULL THEN NULL
    ELSE (wp_from_cp(eval_before_mover::double precision)
          - wp_from_cp(eval_after_mover::double precision)) < 5
  END AS success,
  (clk_before_s / NULLIF(base, 0)) < 0.10 AS time_trouble,
  think_s < 0.3 AS premove
FROM calc;
