#pragma once

#include "judge.hpp"

#include <mutex>

// The shown move stays put until the lead between first and second changes
// by this fraction of the score size.
constexpr double kLeadFraction = 0.1;

struct PanelView {
  const char* label;
  char move[8];
  bool has_move;
  double chance;
  double variance;
  double gap;
  int tie_count;
  int hits;
  int checked;
};

struct StickyReadout {
  double lead_fraction;
  char shown_move[8];
  bool has_shown;
  bool has_gap;
  double shown_gap;

  PanelView update(const Judgment& judgment);
};

struct Panel {
  StickyReadout readout;
  int hits;
  int checked;
  PanelView view;
  mutable std::mutex lock;

  Panel();
  ~Panel();
  Panel(const Panel&) = delete;
  Panel& operator=(const Panel&) = delete;

  PanelView show(const Judgment& judgment);
  void record(bool hit);
  PanelView snapshot() const;
};

void format_panel(const PanelView& view, char* out, int cap);
void serve_panel(Panel* panel, int port = 8765);
