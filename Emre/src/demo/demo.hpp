#pragma once

#include "candidates.hpp"
#include "score.hpp"

const char* start_fen();
const char* after_e4_fen();
int clear_rows(RawRow* out, int cap);
int tie_rows(RawRow* out, int cap);
FakeTable demo_table();
int replay_sample(FakeTable* table, Ply* out, int cap);
