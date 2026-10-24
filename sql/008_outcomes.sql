-- Lichess-style move judgments and game-outcome labels.
-- Win-percent drop uses the same Lichess curve as wp_from_cp:
--   inaccuracy >= 10, mistake >= 20, blunder >= 30
--   (lila: ui/ceval winning-chances / judgement thresholds)

CREATE TABLE IF NOT EXISTS move_outcomes (
  game_id text NOT NULL,
  ply int NOT NULL,
  think_s double precision NOT NULL,
  wp_loss double precision,
  inaccuracy boolean,
  mistake boolean,
  blunder boolean,
  judgment text,
  mover_result text NOT NULL CHECK (mover_result IN ('win', 'draw', 'loss')),
  PRIMARY KEY (game_id, ply),
  FOREIGN KEY (game_id, ply) REFERENCES moves (game_id, ply)
);

CREATE OR REPLACE FUNCTION lichess_judgment(wp_loss double precision)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE
    WHEN wp_loss IS NULL THEN NULL
    WHEN wp_loss >= 30 THEN 'blunder'
    WHEN wp_loss >= 20 THEN 'mistake'
    WHEN wp_loss >= 10 THEN 'inaccuracy'
    ELSE 'ok'
  END;
$$;

TRUNCATE move_outcomes;

INSERT INTO move_outcomes (
  game_id, ply, think_s, wp_loss,
  inaccuracy, mistake, blunder, judgment, mover_result
)
SELECT
  mm.game_id,
  mm.ply,
  mm.think_s,
  mm.wp_loss,
  CASE WHEN mm.wp_loss IS NULL THEN NULL ELSE mm.wp_loss >= 10 END,
  CASE WHEN mm.wp_loss IS NULL THEN NULL ELSE mm.wp_loss >= 20 END,
  CASE WHEN mm.wp_loss IS NULL THEN NULL ELSE mm.wp_loss >= 30 END,
  lichess_judgment(mm.wp_loss),
  CASE
    WHEN g.result = '1/2-1/2' THEN 'draw'
    WHEN (mm.color = 'w' AND g.result = '1-0')
      OR (mm.color = 'b' AND g.result = '0-1') THEN 'win'
    ELSE 'loss'
  END
FROM move_metrics mm
JOIN games g USING (game_id);

-- Labels only. Do not select this view as model inputs.
CREATE OR REPLACE VIEW model_labels AS
SELECT
  game_id,
  ply,
  think_s,
  mover_result,
  blunder,
  mistake,
  inaccuracy,
  judgment,
  wp_loss
FROM move_outcomes;

-- Inputs only. After-move eval / wp_loss / think_s / game result are omitted
-- so they cannot leak into a blunder or outcome model.
CREATE OR REPLACE VIEW model_features AS
SELECT
  mm.game_id,
  mm.ply,
  mm.color,
  mm.elo,
  mm.opp_elo,
  mm.elo_diff,
  mm.rating_band,
  mm.base,
  mm.inc,
  mm.tc,
  mm.clk_before_s,
  mm.clk_frac,
  mm.clk_frac_band,
  mm.ply_phase,
  mm.eval_before_mover,
  mm.wp_before,
  mm.time_trouble,
  mm.premove,
  r.fen_before,
  r.material_white,
  r.material_black,
  r.material_total,
  r.material_advantage_white,
  r.material_advantage_mover,
  r.prev_think_white_s,
  r.prev_think_black_s,
  r.opp_clk_s,
  r.log_clk_before,
  r.log_opp_clk,
  e.gap AS engine_gap,
  e.n_near_best,
  e.n_legal_moves,
  e.best_wp,
  e.second_wp
FROM move_metrics mm
LEFT JOIN move_replay r USING (game_id, ply)
LEFT JOIN engine_features e USING (game_id, ply);

CREATE OR REPLACE VIEW model_training_rows AS
SELECT
  f.*,
  l.think_s,
  l.mover_result,
  l.blunder,
  l.mistake,
  l.inaccuracy,
  l.judgment,
  l.wp_loss
FROM model_features f
JOIN model_labels l USING (game_id, ply);
