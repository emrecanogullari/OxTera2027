#include "board.hpp"

#include <cstdio>
#include <cstring>
#include <initializer_list>

namespace {

constexpr int kEmpty = 0;
constexpr int kWPawn = 1;
constexpr int kWKnight = 2;
constexpr int kWBishop = 3;
constexpr int kWRook = 4;
constexpr int kWQueen = 5;
constexpr int kWKing = 6;
constexpr int kBPawn = 7;
constexpr int kBKnight = 8;
constexpr int kBBishop = 9;
constexpr int kBRook = 10;
constexpr int kBQueen = 11;
constexpr int kBKing = 12;

constexpr int kCastleWK = 1;
constexpr int kCastleWQ = 2;
constexpr int kCastleBK = 4;
constexpr int kCastleBQ = 8;

int file_of(int sq) { return sq & 7; }
int rank_of(int sq) { return sq >> 3; }
int make_sq(int file, int rank) { return rank * 8 + file; }

bool white_piece(int piece) { return piece >= kWPawn && piece <= kWKing; }
bool black_piece(int piece) { return piece >= kBPawn && piece <= kBKing; }

int piece_from_char(char c) {
  switch (c) {
    case 'P': return kWPawn;
    case 'N': return kWKnight;
    case 'B': return kWBishop;
    case 'R': return kWRook;
    case 'Q': return kWQueen;
    case 'K': return kWKing;
    case 'p': return kBPawn;
    case 'n': return kBKnight;
    case 'b': return kBBishop;
    case 'r': return kBRook;
    case 'q': return kBQueen;
    case 'k': return kBKing;
    default: return kEmpty;
  }
}

char char_from_piece(int piece) {
  const char* chars = ".PNBRQKpnbrqk";
  if (piece < 0 || piece > 12) return '.';
  return chars[piece];
}

int promo_letter(int piece) {
  switch (piece) {
    case kWQueen:
    case kBQueen: return 'q';
    case kWRook:
    case kBRook: return 'r';
    case kWBishop:
    case kBBishop: return 'b';
    case kWKnight:
    case kBKnight: return 'n';
    default: return 0;
  }
}

void write_uci(char* out, int from, int to, int promo) {
  out[0] = static_cast<char>('a' + file_of(from));
  out[1] = static_cast<char>('1' + rank_of(from));
  out[2] = static_cast<char>('a' + file_of(to));
  out[3] = static_cast<char>('1' + rank_of(to));
  int letter = promo_letter(promo);
  if (letter) {
    out[4] = static_cast<char>(letter);
    out[5] = '\0';
  } else {
    out[4] = '\0';
  }
}

bool step(int sq, int df, int dr, int* next) {
  int file = file_of(sq) + df;
  int rank = rank_of(sq) + dr;
  if (file < 0 || file > 7 || rank < 0 || rank > 7) return false;
  *next = make_sq(file, rank);
  return true;
}

bool ray_hits(const int* sqs, int target, int df, int dr, int a, int b) {
  int file = file_of(target);
  int rank = rank_of(target);
  while (true) {
    file += df;
    rank += dr;
    if (file < 0 || file > 7 || rank < 0 || rank > 7) return false;
    int piece = sqs[make_sq(file, rank)];
    if (piece == kEmpty) continue;
    return piece == a || piece == b;
  }
}

bool attacked_by(const int* sqs, int target, bool by_white) {
  if (by_white) {
    for (int df : {-1, 1}) {
      int file = file_of(target) + df;
      int rank = rank_of(target) - 1;
      if (file >= 0 && file < 8 && rank >= 0 && rank < 8 && sqs[make_sq(file, rank)] == kWPawn) {
        return true;
      }
    }
  } else {
    for (int df : {-1, 1}) {
      int file = file_of(target) + df;
      int rank = rank_of(target) + 1;
      if (file >= 0 && file < 8 && rank >= 0 && rank < 8 && sqs[make_sq(file, rank)] == kBPawn) {
        return true;
      }
    }
  }

  const int knight_df[8] = {1, 2, 2, 1, -1, -2, -2, -1};
  const int knight_dr[8] = {2, 1, -1, -2, -2, -1, 1, 2};
  int knight = by_white ? kWKnight : kBKnight;
  for (int i = 0; i < 8; ++i) {
    int next = 0;
    if (step(target, knight_df[i], knight_dr[i], &next) && sqs[next] == knight) return true;
  }

  int king = by_white ? kWKing : kBKing;
  for (int df = -1; df <= 1; ++df) {
    for (int dr = -1; dr <= 1; ++dr) {
      if (df == 0 && dr == 0) continue;
      int next = 0;
      if (step(target, df, dr, &next) && sqs[next] == king) return true;
    }
  }

  int bishop = by_white ? kWBishop : kBBishop;
  int rook = by_white ? kWRook : kBRook;
  int queen = by_white ? kWQueen : kBQueen;
  const int bishop_df[4] = {1, 1, -1, -1};
  const int bishop_dr[4] = {1, -1, 1, -1};
  const int rook_df[4] = {1, -1, 0, 0};
  const int rook_dr[4] = {0, 0, 1, -1};
  for (int i = 0; i < 4; ++i) {
    if (ray_hits(sqs, target, bishop_df[i], bishop_dr[i], bishop, queen)) return true;
    if (ray_hits(sqs, target, rook_df[i], rook_dr[i], rook, queen)) return true;
  }
  return false;
}

int find_king(const int* sqs, bool white) {
  int king = white ? kWKing : kBKing;
  for (int i = 0; i < 64; ++i) {
    if (sqs[i] == king) return i;
  }
  return -1;
}

// `board.side` is still the player who just moved. The other color would capture.
bool opponent_can_capture_ep(const Board& board) {
  if (board.ep < 0) return false;
  bool capturer_white = board.side == 1;
  int pawn = capturer_white ? kWPawn : kBPawn;
  int rank = rank_of(board.ep) + (capturer_white ? -1 : 1);
  if (rank < 0 || rank > 7) return false;
  for (int df : {-1, 1}) {
    int file = file_of(board.ep) + df;
    if (file < 0 || file > 7) continue;
    if (board.sq[make_sq(file, rank)] == pawn) return true;
  }
  return false;
}

void apply_move(Board* board, int from, int to, int promo) {
  int piece = board->sq[from];
  int captured = board->sq[to];
  bool ep_capture = (piece == kWPawn || piece == kBPawn) && to == board->ep && board->ep >= 0 && captured == kEmpty;
  if (ep_capture) {
    int cap_sq = to + (piece == kWPawn ? -8 : 8);
    board->sq[cap_sq] = kEmpty;
  }

  board->sq[from] = kEmpty;
  board->sq[to] = promo ? promo : piece;

  if (piece == kWKing && from == 4 && to == 6) {
    board->sq[7] = kEmpty;
    board->sq[5] = kWRook;
  } else if (piece == kWKing && from == 4 && to == 2) {
    board->sq[0] = kEmpty;
    board->sq[3] = kWRook;
  } else if (piece == kBKing && from == 60 && to == 62) {
    board->sq[63] = kEmpty;
    board->sq[61] = kBRook;
  } else if (piece == kBKing && from == 60 && to == 58) {
    board->sq[56] = kEmpty;
    board->sq[59] = kBRook;
  }

  if (piece == kWKing) board->castle &= ~(kCastleWK | kCastleWQ);
  if (piece == kBKing) board->castle &= ~(kCastleBK | kCastleBQ);
  if (from == 7 || to == 7) board->castle &= ~kCastleWK;
  if (from == 0 || to == 0) board->castle &= ~kCastleWQ;
  if (from == 63 || to == 63) board->castle &= ~kCastleBK;
  if (from == 56 || to == 56) board->castle &= ~kCastleBQ;

  board->ep = -1;
  if (piece == kWPawn && to - from == 16) board->ep = from + 8;
  if (piece == kBPawn && from - to == 16) board->ep = from - 8;
  if (!opponent_can_capture_ep(*board)) board->ep = -1;

  if (piece == kWPawn || piece == kBPawn || captured != kEmpty || ep_capture) board->halfmove = 0;
  else board->halfmove += 1;

  if (board->side == 1) board->fullmove += 1;
  board->side ^= 1;
}

struct GenMove {
  int from;
  int to;
  int promo;
};

void push_move(GenMove* moves, int* count, int cap, int from, int to, int promo) {
  if (*count >= cap) return;
  moves[*count].from = from;
  moves[*count].to = to;
  moves[*count].promo = promo;
  *count += 1;
}

void add_pawn_promos(GenMove* moves, int* count, int cap, int from, int to, bool white) {
  push_move(moves, count, cap, from, to, white ? kWQueen : kBQueen);
  push_move(moves, count, cap, from, to, white ? kWRook : kBRook);
  push_move(moves, count, cap, from, to, white ? kWBishop : kBBishop);
  push_move(moves, count, cap, from, to, white ? kWKnight : kBKnight);
}

void add_slider(const Board& board, GenMove* moves, int* count, int cap, int from, int df, int dr) {
  int next = from;
  while (step(next, df, dr, &next)) {
    int piece = board.sq[next];
    if (piece == kEmpty) {
      push_move(moves, count, cap, from, next, 0);
      continue;
    }
    bool own = board.side == 0 ? white_piece(piece) : black_piece(piece);
    if (!own) push_move(moves, count, cap, from, next, 0);
    break;
  }
}

int generate(const Board& board, GenMove* moves, int cap) {
  int count = 0;
  bool white = board.side == 0;
  for (int from = 0; from < 64; ++from) {
    int piece = board.sq[from];
    if (piece == kEmpty) continue;
    if (white && !white_piece(piece)) continue;
    if (!white && !black_piece(piece)) continue;

    if (piece == kWPawn || piece == kBPawn) {
      int forward = piece == kWPawn ? 8 : -8;
      int start_rank = piece == kWPawn ? 1 : 6;
      int promo_rank = piece == kWPawn ? 6 : 1;
      int one = 0;
      if (step(from, 0, piece == kWPawn ? 1 : -1, &one) && board.sq[one] == kEmpty) {
        if (rank_of(from) == promo_rank) add_pawn_promos(moves, &count, cap, from, one, white);
        else push_move(moves, &count, cap, from, one, 0);
        if (rank_of(from) == start_rank) {
          int two = from + 2 * forward;
          if (board.sq[two] == kEmpty) push_move(moves, &count, cap, from, two, 0);
        }
      }
      for (int df : {-1, 1}) {
        int next = 0;
        if (!step(from, df, piece == kWPawn ? 1 : -1, &next)) continue;
        int target = board.sq[next];
        bool enemy = target != kEmpty && (white ? black_piece(target) : white_piece(target));
        bool ep = next == board.ep;
        if (!enemy && !ep) continue;
        if (rank_of(from) == promo_rank) add_pawn_promos(moves, &count, cap, from, next, white);
        else push_move(moves, &count, cap, from, next, 0);
      }
      continue;
    }

    if (piece == kWKnight || piece == kBKnight) {
      const int df[8] = {1, 2, 2, 1, -1, -2, -2, -1};
      const int dr[8] = {2, 1, -1, -2, -2, -1, 1, 2};
      for (int i = 0; i < 8; ++i) {
        int next = 0;
        if (!step(from, df[i], dr[i], &next)) continue;
        int target = board.sq[next];
        if (target == kEmpty || (white ? black_piece(target) : white_piece(target))) {
          push_move(moves, &count, cap, from, next, 0);
        }
      }
      continue;
    }

    if (piece == kWBishop || piece == kBBishop || piece == kWQueen || piece == kBQueen) {
      const int df[4] = {1, 1, -1, -1};
      const int dr[4] = {1, -1, 1, -1};
      for (int i = 0; i < 4; ++i) add_slider(board, moves, &count, cap, from, df[i], dr[i]);
    }
    if (piece == kWRook || piece == kBRook || piece == kWQueen || piece == kBQueen) {
      const int df[4] = {1, -1, 0, 0};
      const int dr[4] = {0, 0, 1, -1};
      for (int i = 0; i < 4; ++i) add_slider(board, moves, &count, cap, from, df[i], dr[i]);
    }
    if (piece == kWKing || piece == kBKing) {
      for (int df = -1; df <= 1; ++df) {
        for (int dr = -1; dr <= 1; ++dr) {
          if (df == 0 && dr == 0) continue;
          int next = 0;
          if (!step(from, df, dr, &next)) continue;
          int target = board.sq[next];
          if (target == kEmpty || (white ? black_piece(target) : white_piece(target))) {
            push_move(moves, &count, cap, from, next, 0);
          }
        }
      }
    }
  }

  if (white && board.sq[4] == kWKing) {
    bool home_safe = !attacked_by(board.sq, 4, false);
    if ((board.castle & kCastleWK) && board.sq[5] == kEmpty && board.sq[6] == kEmpty && board.sq[7] == kWRook &&
        home_safe && !attacked_by(board.sq, 5, false) && !attacked_by(board.sq, 6, false)) {
      push_move(moves, &count, cap, 4, 6, 0);
    }
    if ((board.castle & kCastleWQ) && board.sq[1] == kEmpty && board.sq[2] == kEmpty && board.sq[3] == kEmpty &&
        board.sq[0] == kWRook && home_safe && !attacked_by(board.sq, 3, false) && !attacked_by(board.sq, 2, false)) {
      push_move(moves, &count, cap, 4, 2, 0);
    }
  }
  if (!white && board.sq[60] == kBKing) {
    bool home_safe = !attacked_by(board.sq, 60, true);
    if ((board.castle & kCastleBK) && board.sq[61] == kEmpty && board.sq[62] == kEmpty && board.sq[63] == kBRook &&
        home_safe && !attacked_by(board.sq, 61, true) && !attacked_by(board.sq, 62, true)) {
      push_move(moves, &count, cap, 60, 62, 0);
    }
    if ((board.castle & kCastleBQ) && board.sq[57] == kEmpty && board.sq[58] == kEmpty && board.sq[59] == kEmpty &&
        board.sq[56] == kBRook && home_safe && !attacked_by(board.sq, 59, true) && !attacked_by(board.sq, 58, true)) {
      push_move(moves, &count, cap, 60, 58, 0);
    }
  }
  return count;
}

bool leaves_king_safe(const Board& board, const GenMove& move) {
  Board next = board;
  apply_move(&next, move.from, move.to, move.promo);
  bool moved_white = board.side == 0;
  int king = find_king(next.sq, moved_white);
  if (king < 0) return false;
  return !attacked_by(next.sq, king, !moved_white);
}

int square_from_text(const char* text) {
  if (!text || text[0] < 'a' || text[0] > 'h' || text[1] < '1' || text[1] > '8') return -1;
  return make_sq(text[0] - 'a', text[1] - '1');
}

}  // namespace

bool Board::parse(const char* fen) {
  std::memset(sq, 0, sizeof(sq));
  side = 0;
  castle = 0;
  ep = -1;
  halfmove = 0;
  fullmove = 1;
  if (!fen || !fen[0]) return false;

  int rank = 7;
  int file = 0;
  const char* p = fen;
  for (; *p && *p != ' '; ++p) {
    if (*p == '/') {
      rank -= 1;
      file = 0;
      continue;
    }
    if (*p >= '1' && *p <= '8') {
      file += *p - '0';
      continue;
    }
    int piece = piece_from_char(*p);
    if (piece == kEmpty || rank < 0 || file > 7) return false;
    sq[make_sq(file, rank)] = piece;
    file += 1;
  }
  if (*p == ' ') ++p;
  if (*p != 'w' && *p != 'b') return false;
  side = *p == 'b' ? 1 : 0;
  ++p;
  if (*p == ' ') ++p;

  if (*p == '-') {
    ++p;
  } else {
    while (*p && *p != ' ') {
      if (*p == 'K') castle |= kCastleWK;
      else if (*p == 'Q') castle |= kCastleWQ;
      else if (*p == 'k') castle |= kCastleBK;
      else if (*p == 'q') castle |= kCastleBQ;
      ++p;
    }
  }
  if (*p == ' ') ++p;
  if (*p == '-') {
    ep = -1;
    ++p;
  } else {
    ep = square_from_text(p);
    if (ep < 0) return false;
    p += 2;
  }
  if (*p == ' ') ++p;
  halfmove = 0;
  while (*p >= '0' && *p <= '9') {
    halfmove = halfmove * 10 + (*p - '0');
    ++p;
  }
  if (*p == ' ') ++p;
  fullmove = 0;
  while (*p >= '0' && *p <= '9') {
    fullmove = fullmove * 10 + (*p - '0');
    ++p;
  }
  if (fullmove <= 0) fullmove = 1;
  return true;
}

void Board::write_fen(char* out, int cap) const {
  if (cap <= 0) return;
  int used = 0;
  auto put = [&](char c) {
    if (used + 1 < cap) out[used++] = c;
  };
  for (int rank = 7; rank >= 0; --rank) {
    int empty = 0;
    for (int file = 0; file < 8; ++file) {
      int piece = sq[make_sq(file, rank)];
      if (piece == kEmpty) {
        empty += 1;
        continue;
      }
      if (empty) {
        put(static_cast<char>('0' + empty));
        empty = 0;
      }
      put(char_from_piece(piece));
    }
    if (empty) put(static_cast<char>('0' + empty));
    if (rank) put('/');
  }
  put(' ');
  put(side == 0 ? 'w' : 'b');
  put(' ');
  if (!castle) {
    put('-');
  } else {
    if (castle & kCastleWK) put('K');
    if (castle & kCastleWQ) put('Q');
    if (castle & kCastleBK) put('k');
    if (castle & kCastleBQ) put('q');
  }
  put(' ');
  if (ep < 0) {
    put('-');
  } else {
    put(static_cast<char>('a' + file_of(ep)));
    put(static_cast<char>('1' + rank_of(ep)));
  }
  put(' ');
  char number[16];
  std::snprintf(number, sizeof(number), "%d %d", halfmove, fullmove);
  for (char* n = number; *n; ++n) put(*n);
  if (used < cap) out[used] = '\0';
  else out[cap - 1] = '\0';
}

int Board::legal_moves(char out[][8], int cap) const {
  GenMove generated[256];
  int total = generate(*this, generated, 256);
  int written = 0;
  for (int i = 0; i < total && written < cap; ++i) {
    if (!leaves_king_safe(*this, generated[i])) continue;
    write_uci(out[written], generated[i].from, generated[i].to, generated[i].promo);
    written += 1;
  }
  return written;
}

bool Board::is_legal(const char* uci) const {
  char moves[256][8];
  int count = legal_moves(moves, 256);
  for (int i = 0; i < count; ++i) {
    if (std::strcmp(moves[i], uci) == 0) return true;
  }
  return false;
}

bool Board::play_uci(const char* uci) {
  if (!uci) return false;
  GenMove generated[256];
  int total = generate(*this, generated, 256);
  char text[8];
  for (int i = 0; i < total; ++i) {
    if (!leaves_king_safe(*this, generated[i])) continue;
    write_uci(text, generated[i].from, generated[i].to, generated[i].promo);
    if (std::strcmp(text, uci) != 0) continue;
    apply_move(this, generated[i].from, generated[i].to, generated[i].promo);
    return true;
  }
  return false;
}

bool fen_after_uci(const char* fen, const char* uci, char* out, int cap) {
  Board board;
  if (!board.parse(fen)) return false;
  if (!board.play_uci(uci)) return false;
  board.write_fen(out, cap);
  return true;
}
