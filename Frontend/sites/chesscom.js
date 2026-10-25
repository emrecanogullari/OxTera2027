/**
 * Chess.com site adapter — DOM selectors live ONLY here.
 * Implements: matches, readGameState, onTurnStart, destroy.
 */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});
  Ox.sites = Ox.sites || {};

  const SITE = "chesscom";

  function parseClockText(text) {
    if (!text) return null;
    const t = String(text).trim().replace(/\s+/g, "");
    // mm:ss or h:mm:ss
    const parts = t.split(":").map((p) => Number(p));
    if (parts.some((n) => Number.isNaN(n))) return null;
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    return null;
  }

  /** Heuristic: "3+2" style labels — small bases are minutes. */
  function parseTcLabel(text) {
    if (!text) return null;
    const raw = String(text).trim();
    const m = raw.match(/(\d+)\s*\+\s*(\d+)/);
    if (!m) return null;
    let base = Number(m[1]);
    const inc = Number(m[2]);
    // If written as 180+0 / 60+0 treat as seconds; if 1–30 treat as minutes.
    if (base <= 30) base *= 60;
    return { base_s: base, inc_s: inc };
  }

  function readClocks() {
    // Common chess.com clock nodes (may change; keep all attempts inside this file).
    const selectors = [
      ".clock-component.clock-bottom",
      ".clock-component.clock-top",
      "[class*='clock-bottom']",
      "[class*='clock-top']",
      ".player-clock",
    ];
    const bottom =
      document.querySelector(".clock-component.clock-bottom, [class*='clock-bottom']") ||
      document.querySelectorAll(".clock-component")[1];
    const top =
      document.querySelector(".clock-component.clock-top, [class*='clock-top']") ||
      document.querySelectorAll(".clock-component")[0];
    const selfText = bottom && (bottom.innerText || bottom.textContent);
    const oppText = top && (top.innerText || top.textContent);
    return {
      clock_self_s: parseClockText(selfText),
      clock_opp_s: parseClockText(oppText),
      _usedSelectors: selectors.length,
    };
  }

  function readColor() {
    // Bottom clock is usually "self". Board orientation: .board.flipped => playing black.
    const board =
      document.querySelector("wc-chess-board") ||
      document.querySelector("chess-board") ||
      document.querySelector(".board");
    if (board && (board.classList.contains("flipped") || board.getAttribute("flipped") != null)) {
      return "black";
    }
    return "white";
  }

  function readRatings() {
    const bottoms = document.querySelectorAll(
      ".player-bottom .user-tagline-rating, .board-player-bottom [class*='rating'], .player-component.player-bottom [class*='rating']"
    );
    const tops = document.querySelectorAll(
      ".player-top .user-tagline-rating, .board-player-top [class*='rating'], .player-component.player-top [class*='rating']"
    );
    const parseRating = (el) => {
      if (!el) return null;
      const m = String(el.textContent || "").match(/(\d{3,4})/);
      return m ? Number(m[1]) : null;
    };
    return {
      elo_self: parseRating(bottoms[0]) ?? 1500,
      elo_opp: parseRating(tops[0]) ?? undefined,
    };
  }

  function readTimeControl() {
    const candidates = [
      document.querySelector("[class*='time-control']"),
      document.querySelector(".game-time"),
      document.querySelector("[data-cy='game-time']"),
      ...Array.from(document.querySelectorAll("span, div")).filter((el) =>
        /^\d+\s*\+\s*\d+$/.test((el.textContent || "").trim())
      ).slice(0, 3),
    ];
    for (const el of candidates) {
      if (!el) continue;
      const tc = parseTcLabel(el.textContent);
      if (tc) return tc;
    }
    // Default blitz 3+2 if unknown (better than failing the whole read).
    return { base_s: 180, inc_s: 2 };
  }

  function readMovesUci() {
    // chess.com move list nodes vary; try SAN list and leave UCI empty if unsure.
    // Server accepts fen OR moves_uci; fen is preferred when available.
    return [];
  }

  function readFen() {
    const board =
      document.querySelector("wc-chess-board") ||
      document.querySelector("chess-board");
    if (board) {
      const fen =
        board.getAttribute("fen") ||
        board.game?.getFEN?.() ||
        board.game?.fen ||
        null;
      if (typeof fen === "string" && fen.includes("/")) return fen;
    }
    return null;
  }

  function readGameId() {
    const m = location.pathname.match(/\/(?:game|play)\/(?:live\/)?(\d+)/);
    if (m) return m[1];
    return location.pathname;
  }

  function readPlyFromMoveList() {
    const nodes = document.querySelectorAll(
      ".move-list-move, [data-node], .main-line-ply, .node"
    );
    if (nodes.length) return nodes.length;
    return undefined;
  }

  const adapter = {
    matches(hostname) {
      return (hostname || "").toLowerCase().includes("chess.com");
    },

    readGameState() {
      const clocks = readClocks();
      if (clocks.clock_self_s == null || clocks.clock_opp_s == null) return null;
      const tc = readTimeControl();
      const ratings = readRatings();
      const fen = readFen();
      const moves_uci = readMovesUci();
      const ply = readPlyFromMoveList();
      return Ox.buildRawGameState({
        site: SITE,
        game_id: readGameId(),
        color: readColor(),
        base_s: tc.base_s,
        inc_s: tc.inc_s,
        elo_self: ratings.elo_self,
        elo_opp: ratings.elo_opp,
        clock_self_s: clocks.clock_self_s,
        clock_opp_s: clocks.clock_opp_s,
        fen: fen || undefined,
        moves_uci,
        ply,
      });
    },

    onTurnStart(callback) {
      let lastPly = -1;
      let lastSelfClock = null;
      const tick = () => {
        const state = adapter.readGameState();
        if (!state) return;
        const ply = state.ply != null ? state.ply : (state.moves_uci || []).length;
        const clockChanged =
          lastSelfClock != null && Math.abs(state.clock_self_s - lastSelfClock) > 0.4;
        // Our turn often: bottom clock is ticking (value decreasing) after ply increase.
        if (ply !== lastPly || clockChanged) {
          if (ply !== lastPly) {
            lastPly = ply;
            try {
              callback(state);
            } catch (err) {
              console.error("[OxTera chesscom] onTurnStart callback failed", err);
            }
          }
        }
        lastSelfClock = state.clock_self_s;
      };
      adapter._timer = setInterval(tick, 1000);
      // Initial attempt after DOM settles
      setTimeout(tick, 800);
      const rootEl = document.body;
      adapter._observer = new MutationObserver(() => {
        /* polling is primary; observer nudges sooner */
      });
      adapter._observer.observe(rootEl, { childList: true, subtree: true, characterData: true });
    },

    destroy() {
      if (adapter._timer) clearInterval(adapter._timer);
      if (adapter._observer) adapter._observer.disconnect();
      adapter._timer = null;
      adapter._observer = null;
    },
  };

  Ox.sites.chesscom = adapter;
})(typeof globalThis !== "undefined" ? globalThis : window);
