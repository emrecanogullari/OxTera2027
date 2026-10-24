-- Create after COPY and after move_metrics is built.

CREATE INDEX IF NOT EXISTS moves_game_id_idx ON moves (game_id);
CREATE INDEX IF NOT EXISTS games_utc_date_idx ON games (utc_date);
CREATE INDEX IF NOT EXISTS games_elo_idx ON games (white_elo, black_elo);
CREATE INDEX IF NOT EXISTS move_metrics_buckets_idx
  ON move_metrics (tc, rating_band, ply_phase, clk_frac_band);
CREATE INDEX IF NOT EXISTS move_metrics_game_idx ON move_metrics (game_id);
