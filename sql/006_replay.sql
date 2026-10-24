-- Board-derived features from SAN replay. Keyed like moves.

CREATE TABLE IF NOT EXISTS move_replay (
  game_id text NOT NULL,
  ply int NOT NULL,
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
  PRIMARY KEY (game_id, ply),
  FOREIGN KEY (game_id, ply) REFERENCES moves (game_id, ply)
);

CREATE INDEX IF NOT EXISTS move_replay_material_idx
  ON move_replay (material_total, material_advantage_mover);
