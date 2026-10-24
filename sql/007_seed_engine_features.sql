-- One engine_features row per replayed ply, FEN filled, Stockfish columns null.

INSERT INTO engine_features (game_id, ply, fen_before)
SELECT game_id, ply, fen_before
FROM move_replay
ON CONFLICT (game_id, ply) DO UPDATE
SET fen_before = EXCLUDED.fen_before;
