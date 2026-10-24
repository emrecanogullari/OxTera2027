-- Normalized layers (option A). Engine queue (option B) is not required yet:
-- add annotation_jobs later keyed by (game_id, ply) once fen_before exists.
-- lookup_budgets is option F (tiny product table for the extension).

CREATE TABLE IF NOT EXISTS games (
  game_id text PRIMARY KEY,
  white_elo int NOT NULL,
  black_elo int NOT NULL,
  base int NOT NULL,
  inc int NOT NULL,
  result text NOT NULL,
  termination text NOT NULL,
  utc_date date NOT NULL
);

CREATE TABLE IF NOT EXISTS moves (
  game_id text NOT NULL REFERENCES games (game_id),
  ply int NOT NULL,
  color char(1) NOT NULL CHECK (color IN ('w', 'b')),
  san text NOT NULL,
  clk_after_s real NOT NULL,
  eval_cp int NOT NULL,
  is_mate boolean NOT NULL,
  PRIMARY KEY (game_id, ply)
);

-- Built in SQL from games + moves. One row per scored ply.
CREATE TABLE IF NOT EXISTS move_metrics (
  game_id text NOT NULL,
  ply int NOT NULL,
  color char(1) NOT NULL,
  elo int NOT NULL,
  opp_elo int NOT NULL,
  elo_diff int NOT NULL,
  rating_band int NOT NULL,
  base int NOT NULL,
  inc int NOT NULL,
  tc text NOT NULL,
  clk_before_s double precision NOT NULL,
  clk_after_s double precision NOT NULL,
  think_s double precision NOT NULL,
  clk_frac double precision NOT NULL,
  clk_frac_band text NOT NULL,
  ply_phase text NOT NULL,
  eval_before_mover int,
  eval_after_mover int NOT NULL,
  wp_before double precision,
  wp_after double precision NOT NULL,
  wp_loss double precision,
  success boolean,
  time_trouble boolean NOT NULL,
  premove boolean NOT NULL,
  PRIMARY KEY (game_id, ply),
  FOREIGN KEY (game_id, ply) REFERENCES moves (game_id, ply)
);

-- Sidecar for Stockfish later. Empty until annotation runs.
CREATE TABLE IF NOT EXISTS engine_features (
  game_id text NOT NULL,
  ply int NOT NULL,
  fen_before text,
  best_wp double precision,
  second_wp double precision,
  gap double precision,
  n_near_best int,
  n_legal_moves int,
  PRIMARY KEY (game_id, ply),
  FOREIGN KEY (game_id, ply) REFERENCES moves (game_id, ply)
);

-- Option F: versioned bucket table the extension can copy or query.
CREATE TABLE IF NOT EXISTS lookup_budgets (
  version text NOT NULL,
  tc text NOT NULL,
  rating_band int NOT NULL,
  ply_phase text NOT NULL,
  clk_frac_band text NOT NULL,
  gap_band text NOT NULL DEFAULT 'none',
  n int NOT NULL,
  p50_s double precision,
  p75_s double precision,
  budget_s double precision,
  PRIMARY KEY (version, tc, rating_band, ply_phase, clk_frac_band, gap_band)
);

CREATE OR REPLACE FUNCTION wp_from_cp(cp double precision)
RETURNS double precision
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT 50.0 + 50.0 * (2.0 / (1.0 + exp(-0.00368208 * cp)) - 1.0);
$$;
