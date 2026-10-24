#include "stream.hpp"

#include <curl/curl.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace {

const char* kUserAgent = "oxhack-move-choice-engine";

const char* find_key(const char* json, const char* key) {
  char pattern[64];
  std::snprintf(pattern, sizeof(pattern), "\"%s\"", key);
  const char* found = std::strstr(json, pattern);
  if (!found) return nullptr;
  found += std::strlen(pattern);
  while (*found == ' ' || *found == '\t' || *found == '\n' || *found == '\r') ++found;
  if (*found != ':') return nullptr;
  ++found;
  while (*found == ' ' || *found == '\t' || *found == '\n' || *found == '\r') ++found;
  return found;
}

bool read_string(const char* at, char* out, int cap) {
  if (!at || *at != '"') return false;
  ++at;
  int n = 0;
  while (*at && *at != '"' && n + 1 < cap) {
    out[n++] = *at++;
  }
  out[n] = '\0';
  return n > 0;
}

bool read_number(const char* at, double* out) {
  if (!at) return false;
  char* end = nullptr;
  double value = std::strtod(at, &end);
  if (end == at) return false;
  *out = value;
  return true;
}

size_t append_body(char* data, size_t size, size_t count, void* user) {
  auto* body = static_cast<std::string*>(user);
  body->append(data, size * count);
  return size * count;
}

struct StreamState {
  std::string pending;
  void (*on_position)(const Position&, void*);
  void* user;
};

size_t on_stream(char* data, size_t size, size_t count, void* user) {
  auto* state = static_cast<StreamState*>(user);
  state->pending.append(data, size * count);
  size_t newline = 0;
  while ((newline = state->pending.find('\n')) != std::string::npos) {
    std::string line = state->pending.substr(0, newline);
    state->pending.erase(0, newline + 1);
    Position position;
    if (parse_stream_line(line.c_str(), &position)) state->on_position(position, state->user);
  }
  return size * count;
}

}  // namespace

bool parse_stream_line(const char* line, Position* out) {
  if (!line || !out) return false;
  while (*line == ' ' || *line == '\t' || *line == '\r') ++line;
  if (!*line) return false;

  Position position{};
  if (!read_string(find_key(line, "fen"), position.fen, static_cast<int>(sizeof(position.fen)))) return false;

  if (!read_string(find_key(line, "lm"), position.last_move, static_cast<int>(sizeof(position.last_move)))) {
    position.has_last_move = read_string(find_key(line, "lastMove"), position.last_move, static_cast<int>(sizeof(position.last_move)));
  } else {
    position.has_last_move = true;
  }

  position.has_white_clock = read_number(find_key(line, "wc"), &position.white_clock);
  position.has_black_clock = read_number(find_key(line, "bc"), &position.black_clock);
  *out = position;
  return true;
}

bool stream_game(const char* game_id, void (*on_position)(const Position&, void*), void* user) {
  if (!game_id || !on_position) return false;
  std::string url = std::string("https://lichess.org/api/stream/game/") + game_id;
  CURL* curl = curl_easy_init();
  if (!curl) return false;
  StreamState state;
  state.on_position = on_position;
  state.user = user;
  curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
  curl_easy_setopt(curl, CURLOPT_USERAGENT, kUserAgent);
  curl_easy_setopt(curl, CURLOPT_ACCEPT_ENCODING, "");
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, nullptr);
  struct curl_slist* headers = nullptr;
  headers = curl_slist_append(headers, "Accept: application/x-ndjson");
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, on_stream);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, &state);
  curl_easy_setopt(curl, CURLOPT_TIMEOUT, 0L);
  CURLcode code = curl_easy_perform(curl);
  curl_slist_free_all(headers);
  curl_easy_cleanup(curl);
  return code == CURLE_OK;
}

bool fetch_pgn(const char* game_id, std::string* out) {
  if (!game_id || !out) return false;
  std::string url = std::string("https://lichess.org/game/export/") + game_id + "?clocks=true&evals=false&opening=false";
  CURL* curl = curl_easy_init();
  if (!curl) return false;
  out->clear();
  struct curl_slist* headers = nullptr;
  headers = curl_slist_append(headers, "Accept: application/x-chess-pgn");
  curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
  curl_easy_setopt(curl, CURLOPT_USERAGENT, kUserAgent);
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, append_body);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, out);
  curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
  CURLcode code = curl_easy_perform(curl);
  curl_slist_free_all(headers);
  curl_easy_cleanup(curl);
  return code == CURLE_OK;
}
