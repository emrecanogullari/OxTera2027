#include "demo.hpp"
#include "judge.hpp"
#include "readout.hpp"
#include "score.hpp"
#include "stream.hpp"

#include <cstdio>
#include <cstring>
#include <string>

namespace {

void print_usage() {
  std::fputs(
      "Move choice engine\n"
      "  engine examples\n"
      "  engine replay\n"
      "  engine watch GAME_ID\n"
      "  engine pgn path/to/game.pgn\n"
      "  engine fetch GAME_ID\n",
      stdout);
}

void show_one(const Judgment& judgment) {
  PanelView view{};
  view.label = judgment.label;
  if (judgment.has_move) {
    std::snprintf(view.move, sizeof(view.move), "%s", judgment.likely_move);
    view.has_move = true;
  }
  view.chance = judgment.chance;
  view.variance = judgment.variance;
  char text[256];
  format_panel(view, text, static_cast<int>(sizeof(text)));
  std::fputs(text, stdout);
  std::printf("gap %.1f, ties %d\n", judgment.gap, judgment.tie_count);
}

void show_examples() {
  RawRow clear[8];
  RawRow tied[8];
  int clear_count = clear_rows(clear, 8);
  int tie_count = tie_rows(tied, 8);
  show_one(judge(start_fen(), clear, clear_count));
  std::fputc('\n', stdout);
  show_one(judge(start_fen(), tied, tie_count));
}

void show_replay() {
  FakeTable table;
  Ply plies[8];
  int count = replay_sample(&table, plies, 8);
  HitLog log{};
  score_plies(plies, count, table, &log);
  for (int i = 0; i < log.count; ++i) {
    std::printf("%s: guessed %s, played %s (%s)\n", log.attempts[i].hit ? "hit" : "miss",
                log.attempts[i].has_guess ? log.attempts[i].guessed : "none", log.attempts[i].played, log.attempts[i].label);
  }
  std::printf("%d of %d guesses matched\n", log.hits, log.count);
}

struct WatchState {
  Panel* panel;
  FakeTable* table;
  bool has_previous;
  Position previous;
  Judgment previous_judgment;
};

void on_position(const Position& position, void* user) {
  auto* state = static_cast<WatchState*>(user);
  if (state->has_previous && position.has_last_move && std::strcmp(state->previous.fen, position.fen) != 0) {
    bool hit = state->previous_judgment.has_move &&
               std::strcmp(state->previous_judgment.likely_move, position.last_move) == 0;
    state->panel->record(hit);
  }
  RawRow rows[kMaxCandidates];
  int count = state->table->lookup(position.fen, rows, kMaxCandidates);
  Judgment judgment = judge(position.fen, rows, count);
  PanelView view = state->panel->show(judgment);
  char text[512];
  format_panel(view, text, static_cast<int>(sizeof(text)));
  std::fputs(text, stdout);
  std::printf("clocks white=%s", position.has_white_clock ? "" : "none");
  if (position.has_white_clock) std::printf("%.0f", position.white_clock);
  std::printf(" black=%s", position.has_black_clock ? "" : "none");
  if (position.has_black_clock) std::printf("%.0f", position.black_clock);
  std::fputc('\n', stdout);
  state->previous = position;
  state->previous_judgment = judgment;
  state->has_previous = true;
}

void watch(const char* game_id) {
  Panel panel;
  serve_panel(&panel);
  std::puts("Panel at http://127.0.0.1:8765/");
  FakeTable table = demo_table();
  WatchState state{};
  state.panel = &panel;
  state.table = &table;
  if (!stream_game(game_id, on_position, &state)) {
    std::fputs("Could not open the Lichess stream.\n", stderr);
  }
}

void replay_file(const char* path) {
  FILE* file = std::fopen(path, "rb");
  if (!file) {
    std::fprintf(stderr, "Could not open %s\n", path);
    return;
  }
  std::string text;
  char buffer[4096];
  size_t got = 0;
  while ((got = std::fread(buffer, 1, sizeof(buffer), file)) > 0) text.append(buffer, got);
  std::fclose(file);
  Ply plies[kMaxPlies];
  int count = plies_from_pgn(text.c_str(), plies, kMaxPlies);
  FakeTable table = demo_table();
  HitLog log{};
  score_plies(plies, count, table, &log);
  std::printf("%d of %d guesses matched\n", log.hits, log.count);
}

void replay_lichess(const char* game_id) {
  std::string pgn;
  if (!fetch_pgn(game_id, &pgn)) {
    std::fputs("Could not download the game.\n", stderr);
    return;
  }
  Ply plies[kMaxPlies];
  int count = plies_from_pgn(pgn.c_str(), plies, kMaxPlies);
  FakeTable table;
  HitLog log{};
  score_plies(plies, count, table, &log);
  std::printf("%d of %d guesses matched\n", log.hits, log.count);
  std::puts("The fake table has no rows for this game, so misses are expected until the real database is plugged in.");
}

}  // namespace

int main(int argc, char** argv) {
  const char* command = argc > 1 ? argv[1] : "examples";
  if (std::strcmp(command, "examples") == 0) {
    show_examples();
    return 0;
  }
  if (std::strcmp(command, "replay") == 0) {
    show_replay();
    return 0;
  }
  if (std::strcmp(command, "watch") == 0 && argc > 2) {
    watch(argv[2]);
    return 0;
  }
  if (std::strcmp(command, "pgn") == 0 && argc > 2) {
    replay_file(argv[2]);
    return 0;
  }
  if (std::strcmp(command, "fetch") == 0 && argc > 2) {
    replay_lichess(argv[2]);
    return 0;
  }
  print_usage();
  return 2;
}
