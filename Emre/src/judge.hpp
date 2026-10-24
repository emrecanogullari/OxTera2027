#pragma once

#include "candidates.hpp"

// At most one chess position's worth of candidate moves.
constexpr int kMaxCandidates = 64;
constexpr double kConfidenceCutoff = 0.5;

struct Chance {
  char move[8];
  double p;
};

struct Judgment {
  const char* label;
  char likely_move[8];
  bool has_move;
  double chance;
  double variance;
  double gap;
  int tie_count;
  Chance chances[kMaxCandidates];
  int chance_count;
  double score_scale;
};

// Later timing model. For now this leaves the chances as they are.
void apply_timing(Chance* chances, int count);

// Drop illegal and low-confidence moves, then decide if one move is clearly ahead.
// No heap use. `rows` is only read.
Judgment judge(const char* fen, const RawRow* rows, int count, double cutoff = kConfidenceCutoff);
