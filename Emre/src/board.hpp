#pragma once

// Standard chess: FEN, legal UCI moves, and playing a move.
// The judgment asks this module which moves are legal, then does its own math.

struct Board {
  int sq[64];
  int side;       // 0 white, 1 black
  int castle;     // bits: white K, white Q, black k, black q
  int ep;         // -1, or the square a pawn may capture onto
  int halfmove;
  int fullmove;

  bool parse(const char* fen);
  void write_fen(char* out, int cap) const;
  int legal_moves(char out[][8], int cap) const;
  bool play_uci(const char* uci);
  bool is_legal(const char* uci) const;
};

// Play uci on a FEN. Writes the resulting FEN. Returns false if the move is illegal.
bool fen_after_uci(const char* fen, const char* uci, char* out, int cap);
