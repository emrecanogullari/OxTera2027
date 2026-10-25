#include "readout.hpp"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <thread>

namespace {

const char* kPage =
    "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Move choice</title>"
    "<style>body{font-family:Georgia,serif;background:#161616;color:#f4f1ea;margin:0}"
    "main{max-width:28rem;margin:4rem auto;padding:0 1.5rem}p{margin:0.4rem 0;font-size:1.15rem}"
    ".label{letter-spacing:0.04em;text-transform:uppercase;font-size:0.85rem;color:#c8b99a}"
    ".move{font-size:2.4rem;margin:0.6rem 0}.muted{color:#9a9386}</style></head><body><main>"
    "<p class=\"label\" id=\"label\">waiting</p><p class=\"move\" id=\"move\">—</p>"
    "<p>Chance <span id=\"chance\">—</span></p><p>Variance <span id=\"variance\">—</span></p>"
    "<p class=\"muted\" id=\"score\">No moves checked yet</p></main><script>"
    "async function refresh(){const state=await (await fetch('/state')).json();"
    "document.getElementById('label').textContent=state.label||'waiting';"
    "document.getElementById('move').textContent=state.move||'—';"
    "document.getElementById('chance').textContent=state.chance==null?'—':Math.round(state.chance*100)+'%';"
    "document.getElementById('variance').textContent=state.variance==null?'—':state.variance.toFixed(2);"
    "const checked=state.checked||0,hits=state.hits||0;"
    "document.getElementById('score').textContent=checked?hits+' of '+checked+' guesses matched the move that was played':'No moves checked yet';}"
    "refresh();setInterval(refresh,500);</script></body></html>";

void copy_move(char* dest, const char* src) {
  if (!src) {
    dest[0] = '\0';
    return;
  }
  std::snprintf(dest, 8, "%s", src);
}

bool has_chance(const Judgment& judgment, const char* move) {
  if (!move || !move[0]) return false;
  for (int i = 0; i < judgment.chance_count; ++i) {
    if (std::strcmp(judgment.chances[i].move, move) == 0) return true;
  }
  return false;
}

double chance_of(const Judgment& judgment, const char* move) {
  for (int i = 0; i < judgment.chance_count; ++i) {
    if (std::strcmp(judgment.chances[i].move, move) == 0) return judgment.chances[i].p;
  }
  return 0.0;
}

void send_all(int fd, const char* data, int length) {
  int sent = 0;
  while (sent < length) {
    ssize_t n = ::send(fd, data + sent, static_cast<size_t>(length - sent), 0);
    if (n <= 0) return;
    sent += static_cast<int>(n);
  }
}

void reply(int fd, const char* type, const char* body) {
  char header[256];
  int body_len = static_cast<int>(std::strlen(body));
  int header_len = std::snprintf(header, sizeof(header),
                                 "HTTP/1.1 200 OK\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n",
                                 type, body_len);
  send_all(fd, header, header_len);
  send_all(fd, body, body_len);
}

void serve_loop(Panel* panel, int port) {
  int server = ::socket(AF_INET, SOCK_STREAM, 0);
  if (server < 0) return;
  int yes = 1;
  setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
  sockaddr_in address{};
  address.sin_family = AF_INET;
  address.sin_port = htons(static_cast<uint16_t>(port));
  address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  if (bind(server, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0) {
    std::fprintf(stderr, "Panel could not listen on 127.0.0.1:%d\n", port);
    ::close(server);
    return;
  }
  ::listen(server, 16);
  while (true) {
    int client = ::accept(server, nullptr, nullptr);
    if (client < 0) continue;
    char request[2048];
    ssize_t got = ::recv(client, request, sizeof(request) - 1, 0);
    if (got < 0) got = 0;
    request[got] = '\0';
    bool state = std::strstr(request, "GET /state") != nullptr;
    if (state) {
      PanelView view = panel->snapshot();
      char body[512];
      if (view.has_move) {
        std::snprintf(body, sizeof(body),
                      "{\"label\":\"%s\",\"move\":\"%s\",\"chance\":%.6f,\"variance\":%.6f,\"hits\":%d,\"checked\":%d}",
                      view.label ? view.label : "waiting", view.move, view.chance, view.variance, view.hits, view.checked);
      } else {
        std::snprintf(body, sizeof(body),
                      "{\"label\":\"%s\",\"move\":null,\"chance\":null,\"variance\":null,\"hits\":%d,\"checked\":%d}",
                      view.label ? view.label : "waiting", view.hits, view.checked);
      }
      reply(client, "application/json", body);
    } else {
      reply(client, "text/html; charset=utf-8", kPage);
    }
    ::close(client);
  }
}

}  // namespace

PanelView StickyReadout::update(const Judgment& judgment) {
  double scale = judgment.score_scale > 1e-9 ? judgment.score_scale : 1e-9;
  bool gone = has_shown && !has_chance(judgment, shown_move);
  bool lead_moved = !has_gap || std::fabs(judgment.gap - shown_gap) >= lead_fraction * scale;
  if (!has_shown || gone || lead_moved) {
    copy_move(shown_move, judgment.has_move ? judgment.likely_move : "");
    has_shown = judgment.has_move;
    shown_gap = judgment.gap;
    has_gap = true;
  }

  PanelView view{};
  view.label = judgment.label;
  copy_move(view.move, has_shown ? shown_move : "");
  view.has_move = has_shown && view.move[0];
  view.chance = view.has_move ? chance_of(judgment, view.move) : 0.0;
  view.variance = judgment.variance;
  view.gap = judgment.gap;
  view.tie_count = judgment.tie_count;
  return view;
}

Panel::Panel() : readout{}, hits(0), checked(0), view{} {
  readout.lead_fraction = kLeadFraction;
  view.label = "waiting";
}

Panel::~Panel() = default;

PanelView Panel::show(const Judgment& judgment) {
  std::lock_guard<std::mutex> guard(lock);
  view = readout.update(judgment);
  view.hits = hits;
  view.checked = checked;
  return view;
}

void Panel::record(bool hit) {
  std::lock_guard<std::mutex> guard(lock);
  checked += 1;
  if (hit) hits += 1;
  view.hits = hits;
  view.checked = checked;
}

PanelView Panel::snapshot() const {
  std::lock_guard<std::mutex> guard(lock);
  return view;
}

void format_panel(const PanelView& view, char* out, int cap) {
  const char* move = view.has_move ? view.move : "—";
  char chance[16] = "—";
  char variance[16] = "—";
  if (view.has_move) std::snprintf(chance, sizeof(chance), "%.0f%%", std::round(view.chance * 100.0));
  if (view.label && std::strcmp(view.label, "waiting") != 0) {
    std::snprintf(variance, sizeof(variance), "%.2f", view.variance);
  }
  const char* score = "No moves checked yet";
  char score_buf[64];
  if (view.checked > 0) {
    std::snprintf(score_buf, sizeof(score_buf), "%d of %d guesses matched", view.hits, view.checked);
    score = score_buf;
  }
  std::snprintf(out, static_cast<size_t>(cap), "%s\nLikely move: %s\nChance: %s\nVariance: %s\n%s\n",
                view.label ? view.label : "waiting", move, chance, variance, score);
}

void serve_panel(Panel* panel, int port) {
  std::thread(serve_loop, panel, port).detach();
}
