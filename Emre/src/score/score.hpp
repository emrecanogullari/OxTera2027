#pragma once

#include "candidates.hpp"
#include "judge.hpp"

constexpr int kMaxPlies = 512;

struct Ply {
  char fen_before[128];
  char played_move[8];
  bool has_white_clock;
  bool has_black_clock;
  double white_clock;
  double black_clock;
};

struct Attempt {
  char guessed[8];
  bool has_guess;
  char played[8];
  bool hit;
  const char* label;
};

struct HitLog {
  Attempt attempts[kMaxPlies];
  int count;
  int hits;
};

void hit_log_add(HitLog* log, const Judgment& judgment, const char* played);
int score_plies(const Ply* plies, int count, const FakeTable& table, HitLog* log);

// Mainline of a PGN. Clocks on each ply are the times before that move.
int plies_from_pgn(const char* pgn, Ply* out, int cap);
