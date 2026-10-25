// Blunder Oracle predictor: the 3 trained models of one speed in plain C++17, header only, no dependencies.
//
//   oracle::Model m("models/blitz.txt");          // written by ../4_export_cpp.py
//   std::vector<double> x = {...};                 // the speed's superset feature vector, in m.features() order,
//                                                  // NaN (oracle::kMissing) where a feature is not defined yet
//   oracle::Prediction p = m.predict(x);
//   // p.think_low, p.think_median, p.think_high   think time in whole seconds (80% range and median)
//   // p.p_blunder, p.flag_blunder                 chance this move is a blunder, and the 1/0 flag (chance >= cutoff)
//   // p.p_blunder_next5, p.flag_blunder_next5     the same for a blunder on this move or my next 4
//   std::array<double, 7> v = m.predict_vector(x); // the same 7 numbers, in kOutputs order
//
// Each model is a sum of decision trees: walk every tree from its root ("is feature <= threshold?", with a stored
// direction for missing values) to a leaf, and add the leaf values to a baseline. Same arithmetic as scikit-learn.
// Do not compile with -ffast-math: missing values are NaN and that flag lets the compiler assume NaN never occurs.
#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace oracle {

constexpr double kMissing = std::numeric_limits<double>::quiet_NaN();

// Reads one number token. strtod also accepts "inf", which operator>> does not: scikit-learn writes threshold inf
// for a split that sends every known value left and only missing values right.
inline double read_number(std::istream& in) {
  std::string s;
  if (!(in >> s)) throw std::runtime_error("truncated model file");
  char* end = nullptr;
  const double v = std::strtod(s.c_str(), &end);
  if (end == s.c_str() || *end != '\0') throw std::runtime_error("not a number: '" + s + "'");
  return v;
}

constexpr std::array<const char*, 7> kOutputs = {"think_low", "think_median", "think_high", "p_blunder",
                                                 "flag_blunder", "p_blunder_next5", "flag_blunder_next5"};

struct Prediction {
  double think_low, think_median, think_high;  // whole seconds
  double p_blunder;                            // 0..1
  int flag_blunder;                            // 1 if p_blunder >= cutoff
  double p_blunder_next5;                      // 0..1
  int flag_blunder_next5;                      // 1 if p_blunder_next5 >= cutoff
};

// One boosted model: baseline + the leaf value each tree sends x to.
class Booster {
 public:
  double score(const double* x) const {
    double s = baseline_;
    for (int32_t root : roots_) {
      const Node* n = &nodes_[root];
      while (n->feature >= 0) {
        const double v = x[n->feature];
        const bool left = std::isnan(v) ? n->missing_left : v <= n->t;
        n = &nodes_[left ? n->left : n->right];
      }
      s += n->t;
    }
    return s;
  }

  // Reads "<baseline> <n_trees>" and the trees that follow (see ../4_export_cpp.py for the format).
  void read(std::istream& in, int n_features) {
    int n_trees = 0;
    baseline_ = read_number(in);
    if (!(in >> n_trees) || n_trees <= 0) throw std::runtime_error("bad booster header");
    for (int t = 0; t < n_trees; ++t) {
      std::string tag;
      int n_nodes = 0;
      if (!(in >> tag >> n_nodes) || tag != "tree" || n_nodes <= 0) throw std::runtime_error("bad tree header");
      const int32_t offset = static_cast<int32_t>(nodes_.size());
      roots_.push_back(offset);
      for (int i = 0; i < n_nodes; ++i) {
        Node n{};
        int missing_left = 0, left = 0, right = 0;
        if (!(in >> n.feature)) throw std::runtime_error("bad node");
        if (n.feature < 0) {
          n.feature = -1;
          n.t = read_number(in);  // leaf value
        } else {
          n.t = read_number(in);  // threshold
          in >> missing_left >> left >> right;
          if (n.feature >= n_features || left <= i || right <= i || left >= n_nodes || right >= n_nodes)
            throw std::runtime_error("node points outside its tree or feature vector");
          n.missing_left = missing_left != 0;
          n.left = offset + left;
          n.right = offset + right;
        }
        if (!in) throw std::runtime_error("truncated tree");
        nodes_.push_back(n);
      }
    }
  }

  std::size_t n_trees() const { return roots_.size(); }

 private:
  struct Node {
    double t;            // split threshold, or the leaf value
    int32_t feature;     // index into the superset vector; -1 = leaf
    int32_t left, right; // absolute node indices
    bool missing_left;   // where a NaN feature goes
  };
  double baseline_ = 0;
  std::vector<int32_t> roots_;
  std::vector<Node> nodes_;
};

// The 3 models of one speed: think time (3 quantile boosters), blunder, blunder in next 5.
class Model {
 public:
  explicit Model(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("cannot open " + path);
    std::string tag;
    int version = 0, n = 0;
    if (!(in >> tag >> version) || tag != "oracle-model" || version != 1)
      throw std::runtime_error(path + ": not an oracle-model v1 file");
    if (!(in >> tag >> speed_) || tag != "speed" || !(in >> tag >> n) || tag != "features" || n <= 0)
      throw std::runtime_error(path + ": bad header");
    features_.resize(n);
    for (auto& f : features_) in >> f;
    int seen = 0;
    while (in >> tag && tag != "end") {
      if (tag == "booster") {
        std::string name, kind;
        in >> name >> kind;
        booster(name, path).read(in, n);
        ++seen;
      } else if (tag == "widen") {
        widen_ = read_number(in);
      } else if (tag == "cutoff") {
        std::string name;
        in >> name;
        const double c = read_number(in);
        if (name == "blunder") cut_blunder_ = c;
        else if (name == "blunder_next5") cut_next5_ = c;
        else throw std::runtime_error(path + ": unknown cutoff '" + name + "'");
      } else {
        throw std::runtime_error(path + ": unexpected '" + tag + "'");
      }
    }
    if (tag != "end" || seen != 5 || std::isnan(widen_) || std::isnan(cut_blunder_) || std::isnan(cut_next5_))
      throw std::runtime_error(path + ": incomplete model file");
  }

  const std::string& speed() const { return speed_; }
  const std::vector<std::string>& features() const { return features_; }  // expected input order

  Prediction predict(const double* x) const {
    double q[3] = {think_[0].score(x), think_[1].score(x), think_[2].score(x)};  // log(1 + seconds)
    std::sort(q, q + 3);  // the three never cross
    q[0] -= widen_;       // calibrated 80% range
    q[2] += widen_;
    Prediction p{};
    p.think_low = seconds(q[0]);
    p.think_median = seconds(q[1]);
    p.think_high = seconds(q[2]);
    p.p_blunder = sigmoid(blunder_.score(x));
    p.flag_blunder = p.p_blunder >= cut_blunder_;
    p.p_blunder_next5 = sigmoid(next5_.score(x));
    p.flag_blunder_next5 = p.p_blunder_next5 >= cut_next5_;
    return p;
  }

  Prediction predict(const std::vector<double>& x) const {
    if (x.size() != features_.size())
      throw std::invalid_argument(speed_ + " model expects " + std::to_string(features_.size()) + " features, got " +
                                  std::to_string(x.size()));
    return predict(x.data());
  }

  std::array<double, 7> predict_vector(const std::vector<double>& x) const {
    const Prediction p = predict(x);
    return {p.think_low, p.think_median, p.think_high, p.p_blunder, double(p.flag_blunder), p.p_blunder_next5,
            double(p.flag_blunder_next5)};
  }

  std::size_t n_trees() const {
    return think_[0].n_trees() + think_[1].n_trees() + think_[2].n_trees() + blunder_.n_trees() + next5_.n_trees();
  }

 private:
  static double seconds(double log1p_s) { return std::max(0.0, std::floor(std::expm1(log1p_s))); }
  static double sigmoid(double z) { return 1.0 / (1.0 + std::exp(-z)); }

  Booster& booster(const std::string& name, const std::string& path) {
    if (name == "think_low") return think_[0];
    if (name == "think_median") return think_[1];
    if (name == "think_high") return think_[2];
    if (name == "blunder") return blunder_;
    if (name == "blunder_next5") return next5_;
    throw std::runtime_error(path + ": unknown booster '" + name + "'");
  }

  std::string speed_;
  std::vector<std::string> features_;
  Booster think_[3], blunder_, next5_;
  double widen_ = kMissing, cut_blunder_ = kMissing, cut_next5_ = kMissing;
};

}  // namespace oracle
