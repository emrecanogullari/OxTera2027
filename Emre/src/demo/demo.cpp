#include "demo.hpp"

#include "board.hpp"

#include <cstdio>

namespace {

const char* kStart = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

RawRow make_row(const char* move, int rank, double score, double confidence, double spread, int n) {
  RawRow row = raw_row_blank();
  row.move = move;
  row.has_rank = true;
  row.rank = rank;
  row.has_score = true;
  row.score = score;
  row.has_confidence = true;
  row.confidence = confidence;
  row.has_std = true;
  row.confidence_std = spread;
  row.has_n = true;
  row.n = n;
  return row;
}

char g_after_e4[128];
bool g_ready = false;

void ensure_after() {
  if (g_ready) return;
  fen_after_uci(kStart, "e2e4", g_after_e4, static_cast<int>(sizeof(g_after_e4)));
  g_ready = true;
}

}  // namespace

const char* start_fen() { return kStart; }

const char* after_e4_fen() {
  ensure_after();
  return g_after_e4;
}

int clear_rows(RawRow* out, int cap) {
  RawRow rows[4] = {
      make_row("e2e4", 1, 80, 0.95, 0.02, 100),
      make_row("d2d4", 2, 30, 0.90, 0.03, 80),
      make_row("g1f3", 3, 20, 0.70, 0.05, 40),
      make_row("e2e5", 4, 99, 0.99, 0.01, 5),
  };
  int n = cap < 4 ? cap : 4;
  for (int i = 0; i < n; ++i) out[i] = rows[i];
  return n;
}

int tie_rows(RawRow* out, int cap) {
  RawRow rows[4] = {
      make_row("e2e4", 1, 50, 0.80, 0.08, 40),
      make_row("d2d4", 2, 48, 0.78, 0.08, 40),
      make_row("g1f3", 3, 47, 0.77, 0.08, 36),
      make_row("a2a3", 4, 10, 0.20, 0.10, 4),
  };
  int n = cap < 4 ? cap : 4;
  for (int i = 0; i < n; ++i) out[i] = rows[i];
  return n;
}

FakeTable demo_table() {
  FakeTable table;
  RawRow clear[4];
  int clear_count = clear_rows(clear, 4);
  table.add(start_fen(), clear, clear_count);
  RawRow black[2] = {
      make_row("e7e5", 1, 70, 0.92, 0.02, 60),
      make_row("c7c5", 2, 25, 0.70, 0.04, 20),
  };
  table.add(after_e4_fen(), black, 2);
  return table;
}

int replay_sample(FakeTable* table, Ply* out, int cap) {
  RawRow clear[4];
  int clear_count = clear_rows(clear, 4);
  table->add(start_fen(), clear, clear_count);
  RawRow miss[2] = {
      make_row("c7c5", 1, 70, 0.92, 0.02, 60),
      make_row("e7e5", 2, 20, 0.80, 0.03, 30),
  };
  table->add(after_e4_fen(), miss, 2);
  if (cap < 2) return 0;
  Ply first{};
  std::snprintf(first.fen_before, sizeof(first.fen_before), "%s", start_fen());
  std::snprintf(first.played_move, sizeof(first.played_move), "e2e4");
  first.has_white_clock = true;
  first.has_black_clock = true;
  first.white_clock = 180;
  first.black_clock = 180;
  Ply second{};
  std::snprintf(second.fen_before, sizeof(second.fen_before), "%s", after_e4_fen());
  std::snprintf(second.played_move, sizeof(second.played_move), "e7e5");
  second.has_white_clock = true;
  second.has_black_clock = true;
  second.white_clock = 176;
  second.black_clock = 180;
  out[0] = first;
  out[1] = second;
  return 2;
}
