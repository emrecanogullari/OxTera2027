#pragma once

// The live position. Clocks are kept for a later timing model and are not used
// by the judgment.

struct Position {
  char fen[128];
  bool has_white_clock;
  bool has_black_clock;
  double white_clock;
  double black_clock;
  bool has_last_move;
  char last_move[8];
};
