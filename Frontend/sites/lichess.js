/**
 * Lichess site adapter — DOM selectors live ONLY here.
 * Must not import or reuse chess.com selectors/parsers.
 * Implements: matches, readGameState, onTurnStart, destroy.
 */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});
  Ox.sites = Ox.sites || {};

  const SITE = "lichess";

  function parseClockText(text) {
    if (!text) return null;
    const t = String(text).trim();
    // Lichess often "0:45" or "1:02" or with tenths "0:45.1"
    const cleaned = t.replace(/[^\d:.]/g, "");
    const parts = cleaned.split(":");
    if (parts.length < 2) return null;
    const mins = Number(parts[0]);
    const secs = Number(parts[1]);
    if (Number.isNaN(mins) || Number.isNaN(secs)) return null;
    return mins * 60 + secs;
  }

  function parseTcFromUrlOrDom() {
    // /blitz, setup, or .setup span like "3+2"
    const setup = document.querySelector(".setup, .game__meta .setup, [data-setup]");
    const raw =
      (setup && (setup.getAttribute("data-setup") || setup.textContent)) ||
      document.querySelector(".game__meta")?.textContent ||
      "";
    const m = String(raw).match(/(\d+)\+(\d+)/);
    if (m) {
      let base = Number(m[1]);
      const inc = Number(m[2]);
      if (base <= 30) base *= 60;
      return { base_s: base, inc_s: inc };
    }
    // Path hints
    const path = location.pathname.toLowerCase();
    if (path.includes("bullet")) return { base_s: 60, inc_s: 0 };
    if (path.includes("blitz")) return { base_s: 180, inc_s: 0 };
    if (path.includes("classical")) return { base_s: 1800, inc_s: 0 };
    return { base_s: 180, inc_s: 0 };
  }

  function bottomIsWhite() {
    // Lichess: body or cg-wrap orientation
    const wrap = document.querySelector("cg-container, .cg-wrap, .main-board");
    if (wrap && wrap.classList.contains("orientation-black")) return false;
    const coords = document.querySelector(".cg-wrap.orientation-black");
    if (coords) return false;
    // rclock-bottom belongs to the player at the bottom
    return true;
  }

  function readClocks() {
    const bottom = document.querySelector(".rclock-bottom .time, .rclock.rclock-bottom time, .rclock-bottom");
    const top = document.querySelector(".rclock-top .time, .rclock.rclock-top time, .rclock-top");
    return {
      clock_self_s: parseClockText(bottom && (bottom.textContent || "")),
      clock_opp_s: parseClockText(top && (top.textContent || "")),
    };
  }

  function readRatings() {
    const bottom = document.querySelector(".ruser-bottom .rating, .ruser.ruser-bottom rating");
    const top = document.querySelector(".ruser-top .rating, .ruser.ruser-top rating");
    const parse = (el) => {
      if (!el) return null;
      const m = String(el.textContent || "").match(/(\d{3,4})/);
      return m ? Number(m[1]) : null;
    };
    return { elo_self: parse(bottom) ?? 1500, elo_opp: parse(top) ?? undefined };
  }

  function readFen() {
    // Lichess sometimes exposes FEN on cg-board via data or round data
    const script = document.querySelector("#page-data, script[type='application/json']");
    // Fallback: null — server can still use empty moves at start
    void script;
    const fenEl = document.querySelector("[data-fen]");
    if (fenEl) return fenEl.getAttribute("data-fen");
    return null;
  }

  function readMovesUci() {
    // Prefer leaving empty unless we have reliable UCI; SAN→UCI needs a board lib.
    return [];
  }

  function readPly() {
    const moves = document.querySelectorAll(".lichess-pgn-viewer moves kwdb, .moves m1, .moves m2, .tview2 move");
    if (moves.length) return moves.length;
    return undefined;
  }

  function readGameId() {
    const m = location.pathname.match(/\/([a-zA-Z0-9]{8,12})(?:\/|$)/);
    return m ? m[1] : location.pathname;
  }

  const adapter = {
    matches(hostname) {
      return (hostname || "").toLowerCase().includes("lichess.org");
    },

    readGameState() {
      const clocks = readClocks();
      if (clocks.clock_self_s == null || clocks.clock_opp_s == null) return null;
      const tc = parseTcFromUrlOrDom();
      const ratings = readRatings();
      const whiteAtBottom = bottomIsWhite();
      return Ox.buildRawGameState({
        site: SITE,
        game_id: readGameId(),
        color: whiteAtBottom ? "white" : "black",
        base_s: tc.base_s,
        inc_s: tc.inc_s,
        elo_self: ratings.elo_self,
        elo_opp: ratings.elo_opp,
        clock_self_s: clocks.clock_self_s,
        clock_opp_s: clocks.clock_opp_s,
        fen: readFen() || undefined,
        moves_uci: readMovesUci(),
        ply: readPly(),
      });
    },

    onTurnStart(callback) {
      let lastPly = -1;
      const tick = () => {
        const state = adapter.readGameState();
        if (!state) return;
        const ply = state.ply != null ? state.ply : 0;
        if (ply !== lastPly) {
          lastPly = ply;
          try {
            callback(state);
          } catch (err) {
            console.error("[OxTera lichess] onTurnStart callback failed", err);
          }
        }
      };
      adapter._timer = setInterval(tick, 1000);
      setTimeout(tick, 800);
      adapter._observer = new MutationObserver(() => {});
      adapter._observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    },

    destroy() {
      if (adapter._timer) clearInterval(adapter._timer);
      if (adapter._observer) adapter._observer.disconnect();
      adapter._timer = null;
      adapter._observer = null;
    },
  };

  Ox.sites.lichess = adapter;
})(typeof globalThis !== "undefined" ? globalThis : window);
