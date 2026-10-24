#pragma once

#include "position.hpp"

#include <string>

// Pull fen, lm / lastMove, wc, and bc out of one ndjson line.
// A blank keepalive returns false.
bool parse_stream_line(const char* line, Position* out);

// Follow https://lichess.org/api/stream/game/{id} until it closes.
// on_position is called for each position. Returns false if the request fails.
bool stream_game(const char* game_id, void (*on_position)(const Position&, void*), void* user);

bool fetch_pgn(const char* game_id, std::string* out);
