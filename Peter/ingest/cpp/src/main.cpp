#include "pgn.hpp"

#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>

// Simple argv walk instead of a library. --out-dir data --max-games 1000

namespace {

std::string csv_cell(const std::string& s) {
    bool quote = s.find_first_of(",\"\n") != std::string::npos;
    if (!quote) return s;
    std::string out = "\"";
    for (char c : s) {
        if (c == '"') out += "\"\"";
        else out += c;
    }
    out += '"';
    return out;
}

void write_game(std::ostream& out, const GameRow& g) {
    out << csv_cell(g.game_id) << ',' << g.white_elo << ',' << g.black_elo << ','
        << g.base << ',' << g.inc << ',' << csv_cell(g.result) << ','
        << csv_cell(g.termination) << ',' << csv_cell(g.utc_date) << '\n';
}

void write_move(std::ostream& out, const MoveRow& m) {
    out << csv_cell(m.game_id) << ',' << m.ply << ',' << m.color << ','
        << csv_cell(m.san) << ',' << std::fixed << std::setprecision(3) << m.clk_after_s
        << ',' << m.eval_cp << ',' << (m.is_mate ? 't' : 'f') << '\n';
}

int arg_int(int argc, char** argv, const char* flag, int fallback) {
    std::string want = flag;
    for (int i = 1; i + 1 < argc; ++i) {
        if (want == argv[i]) return std::stoi(argv[i + 1]);
    }
    return fallback;
}

std::string arg_str(int argc, char** argv, const char* flag, const char* fallback) {
    std::string want = flag;
    for (int i = 1; i + 1 < argc; ++i) {
        if (want == argv[i]) return argv[i + 1];
    }
    return fallback;
}

}  // namespace

int main(int argc, char** argv) {
    std::string out_dir = arg_str(argc, argv, "--out-dir", "data");
    int max_games = arg_int(argc, argv, "--max-games", 0);
    int max_seen = arg_int(argc, argv, "--max-seen", 0);

    std::ofstream games(out_dir + "/games.csv");
    std::ofstream moves(out_dir + "/moves.csv");
    if (!games || !moves) {
        std::cerr << "could not open CSV files in " << out_dir
                  << " (create the folder first)\n";
        return 1;
    }
    games << "game_id,white_elo,black_elo,base,inc,result,termination,utc_date\n";
    moves << "game_id,ply,color,san,clk_after_s,eval_cp,is_mate\n";

    Stats stats;
    ingest_stream(
        std::cin,
        max_games,
        max_seen,
        [&](const GameRow& g, const std::vector<MoveRow>& rows) {
            write_game(games, g);
            for (const auto& m : rows) write_move(moves, m);
            return true;
        },
        &stats
    );

    std::cerr << "seen=" << stats.seen << " kept=" << stats.kept << " moves=" << stats.moves
              << " filtered=" << stats.filtered << " dupes=" << stats.dupes
              << " no_moves=" << stats.no_moves << "\n";
    std::cerr << "wrote " << out_dir << "/games.csv and " << out_dir << "/moves.csv\n";
    return 0;
}
