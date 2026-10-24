#include "pgn.hpp"

#include <cctype>
#include <cmath>
#include <iostream>
#include <sstream>
#include <unordered_set>

namespace {

const std::unordered_set<std::string> kKeepEvents{"Rated Blitz game"};
const std::unordered_set<std::string> kKeepTc{"180+0", "300+0"};
const std::unordered_set<std::string> kKeepTerm{"Normal"};
const std::unordered_set<std::string> kResults{"1-0", "0-1", "1/2-1/2", "*"};
const int kEloMin = 1000;
const int kEloMax = 2200;
const int kMateCp = 10000;

std::string trim(const std::string& s) {
    size_t a = 0;
    while (a < s.size() && std::isspace(static_cast<unsigned char>(s[a]))) ++a;
    size_t b = s.size();
    while (b > a && std::isspace(static_cast<unsigned char>(s[b - 1]))) --b;
    return s.substr(a, b - a);
}

bool parse_int(const std::string& s, int* out) {
    if (s.empty() || s == "?") return false;
    try {
        size_t n = 0;
        int v = std::stoi(s, &n);
        if (n != s.size()) return false;
        *out = v;
        return true;
    } catch (...) {
        return false;
    }
}

bool parse_clock(const std::string& value, double* out) {
    int parts[3] = {0, 0, 0};
    int n = 0;
    std::stringstream ss(value);
    std::string tok;
    while (std::getline(ss, tok, ':')) {
        if (n >= 3) return false;
        try {
            parts[n++] = std::stoi(trim(tok));
        } catch (...) {
            return false;
        }
    }
    if (n == 3) {
        *out = parts[0] * 3600.0 + parts[1] * 60.0 + parts[2];
        return true;
    }
    if (n == 2) {
        *out = parts[0] * 60.0 + parts[1];
        return true;
    }
    if (n == 1) {
        *out = parts[0];
        return true;
    }
    return false;
}

bool parse_eval(const std::string& value, int* cp, bool* is_mate) {
    std::string t = trim(value);
    if (!t.empty() && t[0] == '#') {
        int n = 0;
        if (!parse_int(t.substr(1), &n) || n == 0) return false;
        *is_mate = true;
        *cp = (n > 0 ? 1 : -1) * kMateCp;
        return true;
    }
    try {
        size_t eaten = 0;
        double pawns = std::stod(t, &eaten);
        if (eaten != t.size()) return false;
        *is_mate = false;
        *cp = static_cast<int>(std::lround(pawns * 100.0));
        return true;
    } catch (...) {
        return false;
    }
}

bool is_move_number(const std::string& tok) {
    if (tok.empty()) return false;
    size_t i = 0;
    while (i < tok.size() && std::isdigit(static_cast<unsigned char>(tok[i]))) ++i;
    if (i == 0) return false;
    while (i < tok.size() && tok[i] == '.') ++i;
    return i == tok.size();
}

bool is_nag(const std::string& tok) {
    if (tok.size() < 2 || tok[0] != '$') return false;
    for (size_t i = 1; i < tok.size(); ++i) {
        if (!std::isdigit(static_cast<unsigned char>(tok[i]))) return false;
    }
    return true;
}

std::string game_id_from_site(const std::string& site) {
    const std::string needle = "lichess.org/";
    auto pos = site.find(needle);
    if (pos == std::string::npos) return {};
    pos += needle.size();
    size_t end = pos;
    while (end < site.size() && std::isalnum(static_cast<unsigned char>(site[end]))) ++end;
    return site.substr(pos, end - pos);
}

std::string utc_date(const std::string& raw) {
    if (raw.empty() || raw[0] == '?') return {};
    std::string d = raw;
    for (char& c : d) {
        if (c == '.') c = '-';
    }
    return d;
}

bool extract_bracket(const std::string& comment, const char* key, std::string* out) {
    std::string tag = std::string("[%") + key;
    auto pos = comment.find(tag);
    if (pos == std::string::npos) return false;
    pos += tag.size();
    while (pos < comment.size() && std::isspace(static_cast<unsigned char>(comment[pos]))) ++pos;
    auto end = comment.find(']', pos);
    if (end == std::string::npos) return false;
    *out = trim(comment.substr(pos, end - pos));
    return true;
}

}  // namespace

TagMap parse_tags(const std::string& header_text) {
    TagMap tags;
    std::istringstream in(header_text);
    std::string line;
    while (std::getline(in, line)) {
        line = trim(line);
        if (line.size() < 6 || line.front() != '[' || line.back() != ']') continue;
        // [Key "value"]
        auto sp = line.find(' ');
        if (sp == std::string::npos) continue;
        std::string key = line.substr(1, sp - 1);
        auto q1 = line.find('"', sp);
        auto q2 = line.rfind('"');
        if (q1 == std::string::npos || q2 <= q1) continue;
        tags[key] = line.substr(q1 + 1, q2 - q1 - 1);
    }
    return tags;
}

bool keep_headers(const TagMap& tags, GameRow* out) {
    auto get = [&](const char* k) -> std::string {
        auto it = tags.find(k);
        return it == tags.end() ? std::string() : it->second;
    };
    if (!kKeepEvents.count(get("Event"))) return false;
    if (!kKeepTerm.count(get("Termination"))) return false;
    std::string tc = get("TimeControl");
    if (!kKeepTc.count(tc)) return false;
    auto plus = tc.find('+');
    if (plus == std::string::npos) return false;
    int base = 0, inc = 0;
    if (!parse_int(tc.substr(0, plus), &base) || !parse_int(tc.substr(plus + 1), &inc)) {
        return false;
    }
    int we = 0, be = 0;
    if (!parse_int(get("WhiteElo"), &we) || !parse_int(get("BlackElo"), &be)) return false;
    if (we < kEloMin || we > kEloMax || be < kEloMin || be > kEloMax) return false;
    std::string gid = game_id_from_site(get("Site"));
    std::string date = utc_date(get("UTCDate"));
    if (date.empty()) date = utc_date(get("Date"));
    std::string result = get("Result");
    if (gid.empty() || date.empty() || result.empty()) return false;
    out->game_id = gid;
    out->white_elo = we;
    out->black_elo = be;
    out->base = base;
    out->inc = inc;
    out->result = result;
    out->termination = get("Termination");
    out->utc_date = date;
    return true;
}

std::vector<MoveRow> parse_moves(const std::string& game_id, const std::string& movetext) {
    std::vector<MoveRow> rows;
    std::string pending_san;
    int ply = 0;
    auto flush = [&](const std::string& comment) {
        if (pending_san.empty()) return;
        std::string san = pending_san;
        pending_san.clear();
        std::string ev, clk;
        if (!extract_bracket(comment, "eval", &ev) || !extract_bracket(comment, "clk", &clk)) {
            return;
        }
        int cp = 0;
        bool mate = false;
        double seconds = 0;
        if (!parse_eval(ev, &cp, &mate) || !parse_clock(clk, &seconds)) return;
        ++ply;
        MoveRow m;
        m.game_id = game_id;
        m.ply = ply;
        m.color = (ply % 2 == 1) ? 'w' : 'b';
        m.san = san;
        m.clk_after_s = seconds;
        m.eval_cp = cp;
        m.is_mate = mate;
        rows.push_back(m);
    };

    const std::string& s = movetext;
    size_t i = 0;
    while (i < s.size()) {
        while (i < s.size() && std::isspace(static_cast<unsigned char>(s[i]))) ++i;
        if (i >= s.size()) break;
        if (s[i] == '{') {
            int depth = 1;
            ++i;
            size_t start = i;
            while (i < s.size() && depth) {
                if (s[i] == '{') ++depth;
                else if (s[i] == '}') {
                    --depth;
                    if (depth == 0) break;
                }
                ++i;
            }
            flush(s.substr(start, i - start));
            if (i < s.size()) ++i;
            continue;
        }
        if (s[i] == '(') {
            int depth = 1;
            ++i;
            while (i < s.size() && depth) {
                if (s[i] == '(') ++depth;
                else if (s[i] == ')') --depth;
                else if (s[i] == '{') {
                    auto end = s.find('}', i);
                    i = (end == std::string::npos) ? s.size() : end;
                }
                ++i;
            }
            continue;
        }
        if (s[i] == ';') {
            auto end = s.find('\n', i);
            i = (end == std::string::npos) ? s.size() : end + 1;
            continue;
        }
        size_t start = i;
        while (i < s.size() && !std::isspace(static_cast<unsigned char>(s[i])) &&
               s[i] != '{' && s[i] != '}' && s[i] != '(' && s[i] != ')') {
            ++i;
        }
        std::string tok = s.substr(start, i - start);
        if (tok.empty() || is_move_number(tok) || is_nag(tok)) continue;
        if (kResults.count(tok)) break;
        while (!tok.empty() && (tok.back() == '?' || tok.back() == '!')) tok.pop_back();
        pending_san = tok;
    }
    return rows;
}

void ingest_stream(
    std::istream& in,
    int max_games,
    int max_seen,
    const std::function<bool(const GameRow&, const std::vector<MoveRow>&)>& on_game,
    Stats* stats
) {
    std::string line;
    std::string headers;
    std::string moves;
    bool in_moves = false;
    std::unordered_set<std::string> seen_ids;

    auto emit = [&]() {
        if (headers.empty()) return true;
        ++stats->seen;
        if (stats->seen % 2000 == 0) {
            std::cerr << "progress seen=" << stats->seen << " kept=" << stats->kept
                      << " filtered=" << stats->filtered << "\n";
        }
        if (max_seen > 0 && stats->seen > max_seen) return false;
        TagMap tags = parse_tags(headers);
        GameRow game;
        if (!keep_headers(tags, &game)) {
            ++stats->filtered;
        } else if (seen_ids.count(game.game_id)) {
            ++stats->dupes;
        } else if (moves.find("[%eval") == std::string::npos ||
                   moves.find("[%clk") == std::string::npos) {
            ++stats->filtered;
        } else {
            auto rows = parse_moves(game.game_id, moves);
            if (rows.empty()) {
                ++stats->no_moves;
            } else {
                seen_ids.insert(game.game_id);
                ++stats->kept;
                stats->moves += static_cast<int>(rows.size());
                if (!on_game(game, rows)) return false;
                if (max_games > 0 && stats->kept >= max_games) return false;
            }
        }
        return true;
    };

    while (std::getline(in, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::string stripped = trim(line);
        if (stripped.empty()) {
            if (in_moves) {
                if (!emit()) return;
                headers.clear();
                moves.clear();
                in_moves = false;
            } else if (!headers.empty()) {
                in_moves = true;
            }
            continue;
        }
        if (stripped.front() == '[' && !in_moves) {
            if (!headers.empty()) headers.push_back('\n');
            headers += stripped;
            continue;
        }
        in_moves = true;
        if (!moves.empty()) moves.push_back('\n');
        moves += stripped;
    }
    emit();
}
