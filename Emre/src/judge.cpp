#include "judge.hpp"

#include "board.hpp"

#include <cmath>
#include <cstdio>
#include <cstring>

namespace {

constexpr const char* kClear = "clear best";
constexpr const char* kClose = "many close moves";
constexpr const char* kNone = "no moves";

struct Kept {
  Candidate candidate;
  double cautious;
};

void copy_move(char* dest, const char* src) {
  if (!src) {
    dest[0] = '\0';
    return;
  }
  std::snprintf(dest, 8, "%s", src);
}

bool move_in(const char moves[][8], int count, const char* move) {
  for (int i = 0; i < count; ++i) {
    if (std::strcmp(moves[i], move) == 0) return true;
  }
  return false;
}

void sort_by_score(Kept* items, int count) {
  for (int i = 1; i < count; ++i) {
    Kept item = items[i];
    int j = i;
    while (j > 0 && items[j - 1].candidate.score < item.candidate.score) {
      items[j] = items[j - 1];
      j -= 1;
    }
    items[j] = item;
  }
}

Judgment none() {
  Judgment result{};
  result.label = kNone;
  result.likely_move[0] = '\0';
  result.has_move = false;
  return result;
}

void fill_chances(const Kept* kept, int count, const Kept* tied, int tie_count, double best_score,
                  double noise, double score_scale, bool clear, Judgment* result) {
  char tied_moves[kMaxCandidates][8];
  for (int i = 0; i < tie_count; ++i) copy_move(tied_moves[i], tied[i].candidate.move);

  double scale = score_scale > 1.0 ? score_scale : 1.0;
  double temperature = clear ? std::fmax(noise, std::fmax(scale * 0.05, 1e-6))
                             : std::fmax(noise, std::fmax(scale * 0.5, 1e-6));

  double weights[kMaxCandidates];
  double total = 0.0;
  for (int i = 0; i < count; ++i) {
    double weight = kept[i].cautious * std::exp((kept[i].candidate.score - best_score) / temperature);
    if (!clear && !move_in(tied_moves, tie_count, kept[i].candidate.move)) weight *= 0.01;
    weights[i] = weight;
    total += weight;
  }

  result->chance_count = count;
  if (total <= 0.0) {
    double share = 1.0 / static_cast<double>(count);
    for (int i = 0; i < count; ++i) {
      copy_move(result->chances[i].move, kept[i].candidate.move);
      result->chances[i].p = share;
    }
  } else {
    for (int i = 0; i < count; ++i) {
      copy_move(result->chances[i].move, kept[i].candidate.move);
      result->chances[i].p = weights[i] / total;
    }
  }
  apply_timing(result->chances, result->chance_count);
}

}  // namespace

void apply_timing(Chance* chances, int count) {
  (void)chances;
  (void)count;
}

Judgment judge(const char* fen, const RawRow* rows, int count, double cutoff) {
  Candidate parsed[kMaxCandidates];
  int parsed_count = to_candidates(rows, count, parsed, kMaxCandidates);

  char legal[256][8];
  Board board;
  int legal_count = 0;
  if (board.parse(fen)) legal_count = board.legal_moves(legal, 256);

  Kept kept[kMaxCandidates];
  int kept_count = 0;
  for (int i = 0; i < parsed_count; ++i) {
    if (!move_in(legal, legal_count, parsed[i].move)) continue;
    double cautious = parsed[i].confidence - parsed[i].confidence_std;
    if (cautious < 0.0) cautious = 0.0;
    if (cautious < cutoff) continue;
    kept[kept_count].candidate = parsed[i];
    kept[kept_count].cautious = cautious;
    kept_count += 1;
  }

  if (kept_count == 0) return none();
  sort_by_score(kept, kept_count);

  double score_scale = 0.0;
  for (int i = 0; i < kept_count; ++i) {
    double magnitude = std::fabs(kept[i].candidate.score);
    if (magnitude > score_scale) score_scale = magnitude;
  }

  if (kept_count == 1) {
    Judgment result{};
    result.label = kClear;
    copy_move(result.likely_move, kept[0].candidate.move);
    result.has_move = true;
    result.chance = 1.0;
    result.variance = 0.0;
    result.gap = 0.0;
    result.tie_count = 1;
    result.chance_count = 1;
    copy_move(result.chances[0].move, kept[0].candidate.move);
    result.chances[0].p = 1.0;
    result.score_scale = score_scale;
    apply_timing(result.chances, 1);
    return result;
  }

  double gap = kept[0].candidate.score - kept[1].candidate.score;
  double spread = std::sqrt(kept[0].candidate.confidence_std * kept[0].candidate.confidence_std +
                            kept[1].candidate.confidence_std * kept[1].candidate.confidence_std);
  double noise = spread * (score_scale > 1.0 ? score_scale : 1.0);
  bool clear = gap > noise;

  Kept tied[kMaxCandidates];
  int tie_count = 0;
  for (int i = 0; i < kept_count; ++i) {
    if (kept[0].candidate.score - kept[i].candidate.score <= noise) {
      tied[tie_count] = kept[i];
      tie_count += 1;
    }
  }

  Judgment result{};
  result.label = clear ? kClear : kClose;
  result.gap = gap;
  result.tie_count = clear ? 1 : tie_count;
  result.score_scale = score_scale;
  fill_chances(kept, kept_count, tied, tie_count, kept[0].candidate.score, noise, score_scale, clear, &result);

  int best = 0;
  for (int i = 1; i < result.chance_count; ++i) {
    if (result.chances[i].p > result.chances[best].p) best = i;
  }
  copy_move(result.likely_move, result.chances[best].move);
  result.has_move = result.likely_move[0] != '\0';
  result.chance = result.chances[best].p;
  result.variance = 1.0;
  for (int i = 0; i < result.chance_count; ++i) result.variance -= result.chances[i].p * result.chances[i].p;
  return result;
}
