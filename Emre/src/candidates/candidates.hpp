#pragma once

#include <string>
#include <vector>

// One move the database is offering. Fixed text so the judgment does not allocate.
struct Candidate {
  char move[8];
  int rank;
  double score;
  double confidence;
  double confidence_std;
  int n;
};

// The outside row, before we know the real database format.
// to_candidates is the only place that reads these fields.
struct RawRow {
  const char* move;  // "move", or null
  const char* uci;   // "uci", used when move is null
  bool has_rank;
  int rank;
  bool has_score;
  double score;
  bool has_confidence;
  double confidence;
  bool has_std;
  double confidence_std;  // "confidence_std" or "std"
  bool has_n;
  int n;
};

inline RawRow raw_row_blank() {
  RawRow row{};
  row.move = nullptr;
  row.uci = nullptr;
  return row;
}

// Copies at most `cap` rows into `out`. Returns how many were written.
int to_candidates(const RawRow* rows, int count, Candidate* out, int cap);

// Stand-in table. The key is the first four FEN fields, so halfmove clocks do not matter.
class FakeTable {
 public:
  void add(const char* fen, const RawRow* rows, int count);
  int lookup(const char* fen, RawRow* out, int cap) const;

 private:
  struct Entry {
    std::string key;
    std::vector<std::string> owned_moves;
    std::vector<RawRow> rows;
    std::vector<char> use_move_key;
  };
  std::vector<Entry> entries;
};

std::string fen_key(const char* fen);
