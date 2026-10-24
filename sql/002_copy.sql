-- Bulk load after 001_schema.sql. Paths are on the machine running psql.
-- \copy reads the client filesystem; COPY reads the server filesystem.

\copy games (game_id, white_elo, black_elo, base, inc, result, termination, utc_date) FROM 'data/games.csv' CSV HEADER
\copy moves (game_id, ply, color, san, clk_after_s, eval_cp, is_mate) FROM 'data/moves.csv' CSV HEADER
