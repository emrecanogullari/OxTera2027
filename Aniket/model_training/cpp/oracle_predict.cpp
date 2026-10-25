// Command-line front end for oracle_model.hpp.
//
//   oracle_predict MODEL.txt [VECTORS.csv]           predictions for every row -> CSV on stdout (stdin if no file)
//   oracle_predict MODEL.txt --features              the input order the model expects (its superset vector)
//   oracle_predict MODEL.txt VECTORS.csv --check     compare with the expected columns (tests/<speed>.csv)
//   oracle_predict MODEL.txt VECTORS.csv --bench     time the predictions
//
// Input CSV: a header row naming the columns (any order, extra columns ignored), then one row per move.
// "nan", "NA" or an empty cell = missing.
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>

#include "oracle_model.hpp"

namespace {

std::vector<std::string> split(const std::string& line) {
  std::vector<std::string> cells;
  std::string cell;
  std::stringstream ss(line);
  while (std::getline(ss, cell, ',')) cells.push_back(cell);
  if (!line.empty() && line.back() == ',') cells.push_back("");
  return cells;
}

double parse(const std::string& s) {
  if (s.empty() || s == "nan" || s == "NaN" || s == "NA") return oracle::kMissing;
  char* end = nullptr;
  const double v = std::strtod(s.c_str(), &end);
  if (end == s.c_str()) throw std::runtime_error("not a number: '" + s + "'");
  return v;
}

int run(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "usage: oracle_predict MODEL.txt [VECTORS.csv] [--features | --check | --bench]\n";
    return 2;
  }
  const oracle::Model model(argv[1]);
  std::string csv;
  bool check = false, bench = false;
  for (int i = 2; i < argc; ++i) {
    const std::string a = argv[i];
    if (a == "--features") {
      for (const auto& f : model.features()) std::cout << f << "\n";
      return 0;
    }
    if (a == "--check") check = true;
    else if (a == "--bench") bench = true;
    else csv = a;
  }

  std::ifstream file;
  if (!csv.empty()) {
    file.open(csv);
    if (!file) throw std::runtime_error("cannot open " + csv);
  }
  std::istream& in = csv.empty() ? std::cin : file;
  std::string line;
  if (!std::getline(in, line)) throw std::runtime_error("empty input");
  const std::vector<std::string> header = split(line);
  std::map<std::string, std::size_t> col;
  for (std::size_t i = 0; i < header.size(); ++i) col[header[i]] = i;
  auto find = [&](const std::string& name) {
    const auto it = col.find(name);
    if (it == col.end()) throw std::runtime_error("input has no column '" + name + "'");
    return it->second;
  };
  std::vector<std::size_t> feat_col;
  for (const auto& f : model.features()) feat_col.push_back(find(f));
  std::vector<std::size_t> want_col;
  if (check)
    for (const char* o : oracle::kOutputs) want_col.push_back(find(o));

  const std::size_t n_feat = feat_col.size();
  std::vector<double> X;                    // rows x features, model order
  std::vector<std::array<double, 7>> want;  // expected outputs (--check)
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    const std::vector<std::string> cells = split(line);
    for (std::size_t c : feat_col) X.push_back(parse(c < cells.size() ? cells[c] : ""));
    if (check) {
      std::array<double, 7> w{};
      for (std::size_t k = 0; k < 7; ++k) w[k] = parse(cells.at(want_col[k]));
      want.push_back(w);
    }
  }
  const std::size_t n = X.size() / n_feat;

  if (bench) {
    double checksum = 0;
    std::size_t done = 0;
    const auto t0 = std::chrono::steady_clock::now();
    double secs = 0;
    while (secs < 1.0) {  // repeat the whole file for at least a second
      for (std::size_t r = 0; r < n; ++r) checksum += model.predict(&X[r * n_feat]).p_blunder;
      done += n;
      secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    }
    std::printf("%-9s %zu trees: %.2f us per move (all 3 models), %.0f moves/s  [checksum %.3f]\n",
                model.speed().c_str(), model.n_trees(), 1e6 * secs / done, done / secs, checksum);
    return 0;
  }

  if (check) {
    double max_dp = 0;
    std::size_t bad_think = 0, bad_flag = 0;
    for (std::size_t r = 0; r < n; ++r) {
      const oracle::Prediction p = model.predict(&X[r * n_feat]);
      const std::array<double, 7>& w = want[r];
      bad_think += (p.think_low != w[0]) + (p.think_median != w[1]) + (p.think_high != w[2]);
      bad_flag += (p.flag_blunder != int(w[4])) + (p.flag_blunder_next5 != int(w[6]));
      max_dp = std::max({max_dp, std::abs(p.p_blunder - w[3]), std::abs(p.p_blunder_next5 - w[5])});
    }
    const bool ok = bad_think == 0 && bad_flag == 0 && max_dp < 1e-9;
    std::printf("%-9s %zu moves: think-time mismatches %zu, flag mismatches %zu, max chance difference %.1e -> %s\n",
                model.speed().c_str(), n, bad_think, bad_flag, max_dp, ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
  }

  std::printf("think_low,think_median,think_high,p_blunder,flag_blunder,p_blunder_next5,flag_blunder_next5\n");
  for (std::size_t r = 0; r < n; ++r) {
    const oracle::Prediction p = model.predict(&X[r * n_feat]);
    std::printf("%.0f,%.0f,%.0f,%.6f,%d,%.6f,%d\n", p.think_low, p.think_median, p.think_high, p.p_blunder,
                p.flag_blunder, p.p_blunder_next5, p.flag_blunder_next5);
  }
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    return run(argc, argv);
  } catch (const std::exception& e) {
    std::cerr << "oracle_predict: " << e.what() << "\n";
    return 1;
  }
}
