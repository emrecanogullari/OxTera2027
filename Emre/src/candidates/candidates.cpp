#include "candidates.hpp"

#include <cstdio>
#include <cstring>

namespace {

void copy_move(char* dest, const char* src) {
  if (!src) {
    dest[0] = '\0';
    return;
  }
  std::snprintf(dest, 8, "%s", src);
}

}  // namespace

std::string fen_key(const char* fen) {
  std::string key;
  if (!fen) return key;
  int spaces = 0;
  for (const char* p = fen; *p; ++p) {
    if (*p == ' ') {
      if (++spaces == 4) break;
    }
    key.push_back(*p);
  }
  return key;
}

int to_candidates(const RawRow* rows, int count, Candidate* out, int cap) {
  int written = 0;
  if (!rows || !out || cap <= 0) return 0;
  for (int i = 0; i < count && written < cap; ++i) {
    const char* move = rows[i].move ? rows[i].move : rows[i].uci;
    if (!move || !move[0]) continue;
    Candidate& item = out[written];
    copy_move(item.move, move);
    item.rank = rows[i].has_rank ? rows[i].rank : i + 1;
    item.score = rows[i].has_score ? rows[i].score : 0.0;
    item.confidence = rows[i].has_confidence ? rows[i].confidence : 1.0;
    item.confidence_std = rows[i].has_std ? rows[i].confidence_std : 0.0;
    item.n = rows[i].has_n ? rows[i].n : 0;
    written += 1;
  }
  return written;
}

void FakeTable::add(const char* fen, const RawRow* rows, int count) {
  Entry entry;
  entry.key = fen_key(fen);
  for (int i = 0; i < count; ++i) {
    const char* move = rows[i].move ? rows[i].move : rows[i].uci;
    entry.owned_moves.emplace_back(move ? move : "");
    RawRow stored = rows[i];
    stored.move = nullptr;
    stored.uci = nullptr;
    entry.rows.push_back(stored);
    entry.use_move_key.push_back(rows[i].move ? 1 : 0);
  }
  entries.push_back(std::move(entry));
}

int FakeTable::lookup(const char* fen, RawRow* out, int cap) const {
  if (!out || cap <= 0) return 0;
  std::string key = fen_key(fen);
  for (const Entry& entry : entries) {
    if (entry.key != key) continue;
    int n = static_cast<int>(entry.rows.size());
    if (n > cap) n = cap;
    for (int i = 0; i < n; ++i) {
      out[i] = entry.rows[static_cast<size_t>(i)];
      const char* owned = entry.owned_moves[static_cast<size_t>(i)].c_str();
      if (entry.use_move_key[static_cast<size_t>(i)]) out[i].move = owned;
      else out[i].uci = owned;
    }
    return n;
  }
  return 0;
}
