#include "board.hpp"
#include "candidates.hpp"
#include "demo.hpp"
#include "judge.hpp"
#include "readout.hpp"
#include "score.hpp"
#include "stream.hpp"

#include <cmath>
#include <cstdio>
#include <cstring>

namespace {

int g_failed = 0;

void expect(bool cond, const char* file, int line, const char* text) {
  if (cond) return;
  std::fprintf(stderr, "FAIL %s:%d %s\n", file, line, text);
  g_failed += 1;
}

#define EXPECT(cond) expect((cond), __FILE__, __LINE__, #cond)

bool chance_has(const Judgment& judgment, const char* move) {
  for (int i = 0; i < judgment.chance_count; ++i) {
    if (std::strcmp(judgment.chances[i].move, move) == 0) return true;
  }
  return false;
}

double chance_sum(const Judgment& judgment) {
  double sum = 0;
  for (int i = 0; i < judgment.chance_count; ++i) sum += judgment.chances[i].p;
  return sum;
}

Judgment swap_winner(const Judgment& judgment) {
  Judgment flipped = judgment;
  if (flipped.chance_count < 2) return flipped;
  Chance first = flipped.chances[0];
  flipped.chances[0] = flipped.chances[1];
  flipped.chances[1] = first;
  int best = 0;
  for (int i = 1; i < flipped.chance_count; ++i) {
    if (flipped.chances[i].p > flipped.chances[best].p) best = i;
  }
  std::snprintf(flipped.likely_move, sizeof(flipped.likely_move), "%s", flipped.chances[best].move);
  flipped.chance = flipped.chances[best].p;
  flipped.has_move = true;
  return flipped;
}

void test_clear_best() {
  RawRow rows[8];
  int count = clear_rows(rows, 8);
  Judgment result = judge(start_fen(), rows, count);
  EXPECT(std::strcmp(result.label, "clear best") == 0);
  EXPECT(std::strcmp(result.likely_move, "e2e4") == 0);
  EXPECT(result.chance > 0.8);
  EXPECT(result.variance < 0.2);
  EXPECT(result.tie_count == 1);
  EXPECT(!chance_has(result, "e2e5"));
  EXPECT(std::fabs(chance_sum(result) - 1.0) < 1e-9);
}

void test_close_moves() {
  RawRow rows[8];
  int count = tie_rows(rows, 8);
  Judgment result = judge(start_fen(), rows, count);
  EXPECT(std::strcmp(result.label, "many close moves") == 0);
  EXPECT(result.tie_count > 1);
  EXPECT(result.chance < 0.6);
  EXPECT(result.variance > 0.4);
  EXPECT(!chance_has(result, "a2a3"));
  EXPECT(std::fabs(chance_sum(result) - 1.0) < 1e-9);
}

void test_low_confidence() {
  RawRow row = raw_row_blank();
  row.move = "e2e4";
  row.has_score = true;
  row.score = 100;
  row.has_confidence = true;
  row.confidence = 0.4;
  row.has_std = true;
  row.confidence_std = 0.05;
  row.has_n = true;
  row.n = 3;
  Judgment result = judge(start_fen(), &row, 1);
  EXPECT(std::strcmp(result.label, "no moves") == 0);
  EXPECT(!result.has_move);
}

void test_timing_hook() {
  Chance chances[2] = {};
  std::snprintf(chances[0].move, 8, "e2e4");
  chances[0].p = 0.7;
  std::snprintf(chances[1].move, 8, "d2d4");
  chances[1].p = 0.3;
  apply_timing(chances, 2);
  EXPECT(std::fabs(chances[0].p - 0.7) < 1e-12);
  EXPECT(std::fabs(chances[1].p - 0.3) < 1e-12);
}

void test_adapter_keys() {
  RawRow row = raw_row_blank();
  row.uci = "e2e4";
  row.has_std = true;
  row.confidence_std = 0.2;
  row.has_score = true;
  row.score = 5;
  Candidate out[1];
  int count = to_candidates(&row, 1, out, 1);
  EXPECT(count == 1);
  EXPECT(std::strcmp(out[0].move, "e2e4") == 0);
  EXPECT(std::fabs(out[0].confidence_std - 0.2) < 1e-12);
  EXPECT(out[0].rank == 1);
}

void test_stream_clocks() {
  const char* line =
      "{\"fen\":\"rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1\","
      "\"lm\":\"e2e4\",\"wc\":177,\"bc\":180}";
  Position position;
  EXPECT(parse_stream_line(line, &position));
  EXPECT(std::strcmp(position.last_move, "e2e4") == 0);
  EXPECT(position.has_white_clock && position.white_clock == 177);
  EXPECT(position.has_black_clock && position.black_clock == 180);
  EXPECT(!parse_stream_line("\n", &position));
}

void test_replay() {
  FakeTable table;
  Ply plies[4];
  int count = replay_sample(&table, plies, 4);
  HitLog log{};
  score_plies(plies, count, table, &log);
  EXPECT(log.count == 2);
  EXPECT(log.attempts[0].hit);
  EXPECT(!log.attempts[1].hit);
  EXPECT(log.hits == 1);
}

void test_pgn_clocks() {
  const char* pgn = "[TimeControl \"180+0\"]\n\n1. e4 { [%clk 0:02:56] } e5 { [%clk 0:02:58] }\n";
  Ply plies[4];
  int count = plies_from_pgn(pgn, plies, 4);
  EXPECT(count == 2);
  EXPECT(std::strcmp(plies[0].fen_before, start_fen()) == 0);
  EXPECT(std::strcmp(plies[0].played_move, "e2e4") == 0);
  EXPECT(plies[0].has_white_clock && plies[0].white_clock == 180);
  EXPECT(plies[0].has_black_clock && plies[0].black_clock == 180);
  EXPECT(std::strcmp(plies[1].played_move, "e7e5") == 0);
  EXPECT(std::strcmp(plies[1].fen_before, after_e4_fen()) == 0);
  EXPECT(plies[1].white_clock == 176);
  EXPECT(plies[1].black_clock == 180);
  EXPECT(std::strcmp(after_e4_fen(), "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1") == 0);
}

RawRow make_lookup_row() {
  RawRow row = raw_row_blank();
  row.move = "e7e5";
  row.has_score = true;
  row.score = 1;
  row.has_confidence = true;
  row.confidence = 1;
  row.has_std = true;
  row.confidence_std = 0;
  return row;
}

void test_fen_key_ignores_later_fields() {
  FakeTable table;
  RawRow row = make_lookup_row();
  table.add(after_e4_fen(), &row, 1);
  char shifted[128];
  std::snprintf(shifted, sizeof(shifted), "%s", after_e4_fen());
  char* tail = std::strstr(shifted, " 0 1");
  EXPECT(tail != nullptr);
  if (tail) std::snprintf(tail, sizeof(shifted) - static_cast<size_t>(tail - shifted), " 7 9");
  RawRow found[2];
  EXPECT(table.lookup(shifted, found, 2) == 1);
}

void test_board_moves() {
  Board board;
  EXPECT(board.parse(start_fen()));
  char moves[256][8];
  int count = board.legal_moves(moves, 256);
  EXPECT(count == 20);
  EXPECT(board.is_legal("e2e4"));
  EXPECT(!board.is_legal("e2e5"));
  EXPECT(board.parse("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"));
  EXPECT(board.is_legal("e1g1"));
  EXPECT(board.is_legal("e1c1"));
}

void test_sticky_holds() {
  RawRow clear[8];
  int count = clear_rows(clear, 8);
  Judgment first = judge(start_fen(), clear, count);
  Judgment swapped = swap_winner(first);
  StickyReadout panel{};
  panel.lead_fraction = kLeadFraction;
  panel.update(first);
  PanelView shown = panel.update(swapped);
  EXPECT(std::strcmp(shown.move, first.likely_move) == 0);
  EXPECT(std::fabs(shown.variance - swapped.variance) < 1e-12);
}

void test_sticky_swaps_when_the_lead_changes() {
  RawRow tied[8];
  RawRow clear[8];
  Judgment first = judge(start_fen(), tied, tie_rows(tied, 8));
  Judgment later = judge(start_fen(), clear, clear_rows(clear, 8));
  StickyReadout panel{};
  panel.lead_fraction = kLeadFraction;
  panel.update(first);
  PanelView shown = panel.update(later);
  EXPECT(std::strcmp(shown.move, later.likely_move) == 0);
}

}  // namespace

int main() {
  test_clear_best();
  test_close_moves();
  test_low_confidence();
  test_timing_hook();
  test_adapter_keys();
  test_stream_clocks();
  test_replay();
  test_pgn_clocks();
  test_fen_key_ignores_later_fields();
  test_board_moves();
  test_sticky_holds();
  test_sticky_swaps_when_the_lead_changes();
  if (g_failed) {
    std::fprintf(stderr, "%d check(s) failed\n", g_failed);
    return 1;
  }
  std::puts("all checks passed");
  return 0;
}
