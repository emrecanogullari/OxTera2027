#pragma once

// Header vs .cpp: this file is the *interface* (types + function names).
// pgn.cpp is the *implementation*. Other files #include this, never pgn.cpp.

#include <functional>
#include <istream>
#include <string>
#include <unordered_map>
#include <vector>

struct GameRow {
    std::string game_id;
    int white_elo = 0;
    int black_elo = 0;
    int base = 0;
    int inc = 0;
    std::string result;
    std::string termination;
    std::string utc_date;
};

struct MoveRow {
    std::string game_id;
    int ply = 0;
    char color = 'w';
    std::string san;
    double clk_after_s = 0;
    int eval_cp = 0;
    bool is_mate = false;
};

struct Stats {
    int seen = 0;
    int kept = 0;
    int filtered = 0;
    int dupes = 0;
    int no_moves = 0;
    int moves = 0;
};

using TagMap = std::unordered_map<std::string, std::string>;

TagMap parse_tags(const std::string& header_text);
bool keep_headers(const TagMap& tags, GameRow* out);
std::vector<MoveRow> parse_moves(const std::string& game_id, const std::string& movetext);

// Read a PGN stream. on_game returns false to stop (after --max-games).
void ingest_stream(
    std::istream& in,
    int max_games,
    int max_seen,
    const std::function<bool(const GameRow&, const std::vector<MoveRow>&)>& on_game,
    Stats* stats
);
