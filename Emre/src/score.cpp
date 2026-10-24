#include "score.hpp"

#include "board.hpp"

#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace {

void copy_text(char* dest, int cap, const char* src) {
  if (!src) {
    dest[0] = '\0';
    return;
  }
  std::snprintf(dest, static_cast<size_t>(cap), "%s", src);
}

int file_of_uci(const char* uci) { return uci[0] - 'a'; }
int rank_of_uci(const char* uci) { return uci[1] - '1'; }
int square_uci(const char* uci) { return rank_of_uci(uci) * 8 + file_of_uci(uci); }

int piece_kind(int piece) {
  if (piece >= 7) return piece - 6;
  return piece;
}

bool san_to_uci(const Board& board, const char* san, char* uci_out) {
  char token[32];
  int length = 0;
  for (const char* p = san; *p && length < 30; ++p) {
    if (*p == '+' || *p == '#' || *p == '!' || *p == '?') continue;
    token[length++] = *p;
  }
  token[length] = '\0';
  if (length == 0) return false;

  char moves[256][8];
  int move_count = board.legal_moves(moves, 256);
  bool white = board.side == 0;

  if (std::strcmp(token, "O-O") == 0 || std::strcmp(token, "0-0") == 0) {
    const char* castle = white ? "e1g1" : "e8g8";
    for (int i = 0; i < move_count; ++i) {
      if (std::strcmp(moves[i], castle) == 0) {
        copy_text(uci_out, 8, castle);
        return true;
      }
    }
    return false;
  }
  if (std::strcmp(token, "O-O-O") == 0 || std::strcmp(token, "0-0-0") == 0) {
    const char* castle = white ? "e1c1" : "e8c8";
    for (int i = 0; i < move_count; ++i) {
      if (std::strcmp(moves[i], castle) == 0) {
        copy_text(uci_out, 8, castle);
        return true;
      }
    }
    return false;
  }

  char promo = 0;
  char* equals = std::strchr(token, '=');
  if (equals && equals[1]) {
    promo = static_cast<char>(std::tolower(static_cast<unsigned char>(equals[1])));
    *equals = '\0';
    length = static_cast<int>(std::strlen(token));
  }

  int dest_index = -1;
  for (int i = 0; i + 1 < length; ++i) {
    if (token[i] >= 'a' && token[i] <= 'h' && token[i + 1] >= '1' && token[i + 1] <= '8') dest_index = i;
  }
  if (dest_index < 0) return false;
  int dest = (token[dest_index + 1] - '1') * 8 + (token[dest_index] - 'a');

  int kind = 1;
  int start = 0;
  switch (token[0]) {
    case 'N': kind = 2; start = 1; break;
    case 'B': kind = 3; start = 1; break;
    case 'R': kind = 4; start = 1; break;
    case 'Q': kind = 5; start = 1; break;
    case 'K': kind = 6; start = 1; break;
    default: break;
  }

  int file_hint = -1;
  int rank_hint = -1;
  for (int i = start; i < dest_index; ++i) {
    if (token[i] == 'x') continue;
    if (token[i] >= 'a' && token[i] <= 'h') file_hint = token[i] - 'a';
    if (token[i] >= '1' && token[i] <= '8') rank_hint = token[i] - '1';
  }

  int matches = 0;
  char found[8] = {};
  for (int i = 0; i < move_count; ++i) {
    if (std::strlen(moves[i]) < 4) continue;
    int to = (moves[i][3] - '1') * 8 + (moves[i][2] - 'a');
    if (to != dest) continue;
    int from = square_uci(moves[i]);
    if (piece_kind(board.sq[from]) != kind) continue;
    if (file_hint >= 0 && file_of_uci(moves[i]) != file_hint) continue;
    if (rank_hint >= 0 && rank_of_uci(moves[i]) != rank_hint) continue;
    bool is_promo = std::strlen(moves[i]) >= 5;
    if (promo) {
      if (!is_promo || moves[i][4] != promo) continue;
    } else if (is_promo) {
      continue;
    }
    matches += 1;
    copy_text(found, 8, moves[i]);
  }
  if (matches != 1) return false;
  copy_text(uci_out, 8, found);
  return true;
}

bool clock_seconds(const char* comment, double* seconds) {
  const char* mark = std::strstr(comment, "[%clk ");
  if (!mark) return false;
  int hours = 0;
  int minutes = 0;
  double secs = 0;
  if (std::sscanf(mark, "[%%clk %d:%d:%lf]", &hours, &minutes, &secs) != 3) return false;
  *seconds = hours * 3600.0 + minutes * 60.0 + secs;
  return true;
}

bool initial_seconds(const char* time_control, double* seconds) {
  if (!time_control || !time_control[0] || std::strcmp(time_control, "-") == 0 || std::strcmp(time_control, "?") == 0) {
    return false;
  }
  const char* plus = std::strchr(time_control, '+');
  char base[32];
  size_t length = plus ? static_cast<size_t>(plus - time_control) : std::strlen(time_control);
  if (length == 0 || length >= sizeof(base)) return false;
  std::memcpy(base, time_control, length);
  base[length] = '\0';
  for (char* p = base; *p; ++p) {
    if (*p < '0' || *p > '9') return false;
  }
  *seconds = std::atof(base);
  return true;
}

const char* header_value(const char* pgn, const char* name, char* out, int cap) {
  char pattern[64];
  std::snprintf(pattern, sizeof(pattern), "[%s \"", name);
  const char* found = std::strstr(pgn, pattern);
  if (!found) {
    out[0] = '\0';
    return out;
  }
  found += std::strlen(pattern);
  int n = 0;
  while (found[n] && found[n] != '"' && n + 1 < cap) {
    out[n] = found[n];
    n += 1;
  }
  out[n] = '\0';
  return out;
}

}  // namespace

void hit_log_add(HitLog* log, const Judgment& judgment, const char* played) {
  if (!log || log->count >= kMaxPlies) return;
  Attempt& attempt = log->attempts[log->count];
  copy_text(attempt.guessed, 8, judgment.has_move ? judgment.likely_move : "");
  attempt.has_guess = judgment.has_move;
  copy_text(attempt.played, 8, played);
  attempt.hit = judgment.has_move && std::strcmp(judgment.likely_move, played) == 0;
  attempt.label = judgment.label;
  log->count += 1;
  if (attempt.hit) log->hits += 1;
}

int score_plies(const Ply* plies, int count, const FakeTable& table, HitLog* log) {
  log->count = 0;
  log->hits = 0;
  for (int i = 0; i < count; ++i) {
    RawRow rows[kMaxCandidates];
    int n = table.lookup(plies[i].fen_before, rows, kMaxCandidates);
    Judgment judgment = judge(plies[i].fen_before, rows, n);
    hit_log_add(log, judgment, plies[i].played_move);
  }
  return log->hits;
}

int plies_from_pgn(const char* pgn, Ply* out, int cap) {
  if (!pgn || !out || cap <= 0) return 0;
  char time_control[32];
  header_value(pgn, "TimeControl", time_control, static_cast<int>(sizeof(time_control)));
  double initial = 0;
  bool has_initial = initial_seconds(time_control, &initial);

  const char* body = std::strstr(pgn, "\n\n");
  const char* cursor = body ? body + 2 : pgn;

  Board board;
  board.parse("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  // A FEN header overrides the start, when the PGN has one.
  char fen_header[128];
  header_value(pgn, "FEN", fen_header, static_cast<int>(sizeof(fen_header)));
  if (fen_header[0]) board.parse(fen_header);

  bool has_white = has_initial;
  bool has_black = has_initial;
  double white_clock = initial;
  double black_clock = initial;
  int count = 0;
  bool last_was_move = false;

  while (*cursor && count < cap) {
    while (*cursor == ' ' || *cursor == '\n' || *cursor == '\r' || *cursor == '\t') ++cursor;
    if (!*cursor) break;
    if (*cursor == '{') {
      const char* end = std::strchr(cursor, '}');
      if (!end) break;
      if (last_was_move && count > 0) {
        char comment[128];
        int n = static_cast<int>(end - (cursor + 1));
        if (n > 120) n = 120;
        std::memcpy(comment, cursor + 1, static_cast<size_t>(n));
        comment[n] = '\0';
        double seconds = 0;
        if (clock_seconds(comment, &seconds)) {
          // The side to move has already switched, so this clock belongs to the player who just moved.
          // It is the time the next ply will see, not a rewrite of the ply already stored.
          if (board.side == 1) {
            white_clock = seconds;
            has_white = true;
          } else {
            black_clock = seconds;
            has_black = true;
          }
        }
      }
      cursor = end + 1;
      last_was_move = false;
      continue;
    }
    if (*cursor == ';') {
      while (*cursor && *cursor != '\n') ++cursor;
      continue;
    }
    if (*cursor == '(') {
      int depth = 1;
      ++cursor;
      while (*cursor && depth) {
        if (*cursor == '(') depth += 1;
        else if (*cursor == ')') depth -= 1;
        ++cursor;
      }
      continue;
    }
    if (*cursor == '$') {
      ++cursor;
      while (*cursor >= '0' && *cursor <= '9') ++cursor;
      continue;
    }

    char token[32];
    int n = 0;
    while (*cursor && *cursor != ' ' && *cursor != '\n' && *cursor != '\r' && *cursor != '\t' && *cursor != '{' && n < 30) {
      token[n++] = *cursor++;
    }
    token[n] = '\0';
    if (n == 0) break;
    if (std::strcmp(token, "1-0") == 0 || std::strcmp(token, "0-1") == 0 || std::strcmp(token, "1/2-1/2") == 0 ||
        std::strcmp(token, "*") == 0) {
      last_was_move = false;
      continue;
    }
    bool digits_or_dots = true;
    for (int i = 0; i < n; ++i) {
      if (token[i] != '.' && (token[i] < '0' || token[i] > '9')) digits_or_dots = false;
    }
    if (digits_or_dots) {
      last_was_move = false;
      continue;
    }

    char uci[8];
    if (!san_to_uci(board, token, uci)) {
      last_was_move = false;
      continue;
    }
    Ply& ply = out[count];
    board.write_fen(ply.fen_before, static_cast<int>(sizeof(ply.fen_before)));
    copy_text(ply.played_move, 8, uci);
    ply.has_white_clock = has_white;
    ply.has_black_clock = has_black;
    ply.white_clock = white_clock;
    ply.black_clock = black_clock;
    if (!board.play_uci(uci)) {
      last_was_move = false;
      continue;
    }
    count += 1;
    last_was_move = true;
  }
  return count;
}
