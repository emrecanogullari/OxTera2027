-- best_next_move holds one row per replayed ply.
-- Reads come from engine_features, moves, move_replay, and move_metrics.
-- This file only creates the table. It does not DELETE, TRUNCATE, DROP, or UPDATE
-- any existing table. engine_features is not written.

CREATE TABLE IF NOT EXISTS best_next_move (
  game_id text NOT NULL,
  ply int NOT NULL,
  color char(1) NOT NULL,
  san text NOT NULL,
  fen_before text NOT NULL,
  material_white int NOT NULL,
  material_black int NOT NULL,
  material_total int NOT NULL,
  material_advantage_white int NOT NULL,
  material_advantage_mover int NOT NULL,
  prev_think_white_s double precision,
  prev_think_black_s double precision,
  clk_before_s double precision NOT NULL,
  opp_clk_s double precision NOT NULL,
  log_clk_before double precision NOT NULL,
  log_opp_clk double precision NOT NULL,
  elo int NOT NULL,
  opp_elo int NOT NULL,
  elo_diff int NOT NULL,
  rating_band int NOT NULL,
  base int NOT NULL,
  inc int NOT NULL,
  tc text NOT NULL,
  clk_frac double precision NOT NULL,
  clk_frac_band text NOT NULL,
  ply_phase text NOT NULL,
  premove boolean NOT NULL,
  best_possible_move text,
  second_best_move text,
  best_possible_move_wp double precision,
  second_best_move_wp double precision,
  gap double precision,
  n_near_best int,
  n_legal_moves int,
  PRIMARY KEY (game_id, ply),
  FOREIGN KEY (game_id, ply) REFERENCES moves (game_id, ply)
);
