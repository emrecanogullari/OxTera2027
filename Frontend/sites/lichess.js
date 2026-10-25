/**
 * Lichess page reader. HTML and CSS only — no lichess.analysis, no data-fen.
 * Live games and the analysis page use different class names; both are handled here.
 * The shared server turns this snapshot into the model vector.
 */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});
  Ox.sites = Ox.sites || {};

  const SITE = "lichess";
  const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR";
  const PIECE = { pawn: "p", knight: "n", bishop: "b", rook: "r", queen: "q", king: "k" };

  function parseClockText(text) {
    if (!text) return null;
    const cleaned = String(text).trim().replace(/[^\d:.]/g, "");
    const parts = cleaned.split(":");
    if (parts.length < 2) return null;
    const mins = Number(parts[0]);
    const secs = Number(parts[1]);
    if (Number.isNaN(mins) || Number.isNaN(secs)) return null;
    return mins * 60 + secs;
  }

  function textOf(el) {
    return el ? String(el.textContent || "").trim() : "";
  }

  function ratingFrom(el) {
    const text = el ? String(el.innerText || el.textContent || "") : "";
    const paren = text.match(/\((\d{3,4})\)/);
    if (paren) return Number(paren[1]);
    const bare = text.match(/\b(\d{3,4})\b/);
    return bare ? Number(bare[1]) : null;
  }

  function whiteAtBottom() {
    const wrap = document.querySelector(".cg-wrap");
    if (!wrap) return null;
    return !wrap.classList.contains("orientation-black");
  }

  function clockElement(which) {
    return (
      document.querySelector(`.analyse__clock.${which}`) ||
      document.querySelector(`.rclock-${which} .time`) ||
      document.querySelector(`.rclock-${which}`)
    );
  }

  function readClocks() {
    return {
      clock_self_s: parseClockText(textOf(clockElement("bottom"))),
      clock_opp_s: parseClockText(textOf(clockElement("top"))),
    };
  }

  /** "5+0" on Lichess is minutes + increment seconds. Fractions are sub-minute. */
  function readTimeControl() {
    const raw = textOf(document.querySelector(".setup")) || textOf(document.querySelector(".game__meta__infos"));
    if (!raw) return null;
    const incMatch = raw.match(/[+]\s*(\d+)/);
    const inc = incMatch ? Number(incMatch[1]) : 0;
    if (raw.includes("¼")) return { base_s: 15, inc_s: inc };
    if (raw.includes("½")) return { base_s: 30, inc_s: inc };
    if (raw.includes("¾")) return { base_s: 45, inc_s: inc };
    const baseMatch = raw.match(/(\d+)\s*\+/);
    if (!baseMatch) return null;
    return { base_s: Number(baseMatch[1]) * 60, inc_s: inc };
  }

  function readRatings(selfIsWhite) {
    const whiteEl =
      document.querySelector(".player.color-icon.white") ||
      document.querySelector(selfIsWhite ? ".ruser-bottom" : ".ruser-top");
    const blackEl =
      document.querySelector(".player.color-icon.black") ||
      document.querySelector(selfIsWhite ? ".ruser-top" : ".ruser-bottom");
    const players = document.querySelector(".game__meta__players");
    let white = ratingFrom(whiteEl);
    let black = ratingFrom(blackEl);
    if ((white == null || black == null) && players) {
      const found = [...String(players.innerText || "").matchAll(/\((\d{3,4})\)/g)].map((m) => Number(m[1]));
      if (white == null && found[0] != null) white = found[0];
      if (black == null && found[1] != null) black = found[1];
    }
    return {
      elo_self: selfIsWhite ? white : black,
      elo_opp: selfIsWhite ? black : white,
    };
  }

  function placementFromPieces(selfIsWhite) {
    const board = document.querySelector("cg-board");
    if (!board) return null;
    const width = board.getBoundingClientRect().width;
    if (!width) return null;
    const sq = width / 8;
    const grid = Array.from({ length: 8 }, () => Array(8).fill(""));
    for (const piece of board.querySelectorAll("piece")) {
      if (piece.classList.contains("ghost") || piece.classList.contains("dragging")) continue;
      const cls = String(piece.className).split(/\s+/);
      const kind = cls.find((c) => PIECE[c]);
      if (!kind) continue;
      const match = /translate\(([-\d.]+)px,\s*([-\d.]+)px\)/.exec(piece.style.transform || "");
      if (!match) continue;
      let file = Math.round(parseFloat(match[1]) / sq);
      let row = Math.round(parseFloat(match[2]) / sq);
      if (!selfIsWhite) {
        file = 7 - file;
        row = 7 - row;
      }
      if (file < 0 || file > 7 || row < 0 || row > 7) continue;
      const letter = cls.includes("white") ? PIECE[kind].toUpperCase() : PIECE[kind];
      grid[row][file] = letter;
    }
    const placement = grid
      .map((rank) => {
        let out = "";
        let empty = 0;
        for (let i = 0; i < 8; i += 1) {
          if (!rank[i]) empty += 1;
          else {
            if (empty) {
              out += empty;
              empty = 0;
            }
            out += rank[i];
          }
        }
        if (empty) out += empty;
        return out;
      })
      .join("/");
    return placement.includes("K") && placement.includes("k") ? placement : null;
  }

  function sideLetter(selfIsWhite, movesPlayed) {
    const bottomOn = document.querySelector(".analyse__clock.bottom.active, .rclock-bottom.running");
    const topOn = document.querySelector(".analyse__clock.top.active, .rclock-top.running");
    if (bottomOn && !topOn) return selfIsWhite ? "w" : "b";
    if (topOn && !bottomOn) return selfIsWhite ? "b" : "w";
    return movesPlayed % 2 === 0 ? "w" : "b";
  }

  function mainlineMoves() {
    const col =
      document.querySelector(".analyse__moves .tview2-column") ||
      document.querySelector(".rmoves .tview2-column") ||
      document.querySelector(".tview2-column") ||
      document.querySelector(".rmoves");
    if (!col) return [];
    const moves = [...col.querySelectorAll(":scope > move")];
    if (moves.length) return moves;
    return [...col.querySelectorAll(":scope > kwdb")];
  }

  function sanOf(moveEl) {
    const san = moveEl.querySelector("san");
    return textOf(san || moveEl).replace(/[+#?!]+$/g, "");
  }

  function readMoves(placement) {
    const moves = mainlineMoves();
    if (!moves.length) return { sans: [], movesPlayed: placement === START ? 0 : null };
    const idx = moves.findIndex(
      (move) => move.classList.contains("active") || move.classList.contains("current")
    );
    let slice;
    if (idx >= 0) slice = moves.slice(0, idx + 1);
    else if (placement === START) slice = [];
    else slice = moves;
    const sans = slice.map(sanOf).filter(Boolean);
    return { sans, movesPlayed: sans.length };
  }

  /** Remaining clock printed on a move, when the page has one. Null if that move has none. */
  function readMoveClocks(movesPlayed) {
    return mainlineMoves()
      .slice(0, movesPlayed)
      .map((move) => parseClockText(textOf(move.querySelector("clock"))));
  }

  function readGameId() {
    const parts = location.pathname.split("/").filter(Boolean);
    const id = [...parts].reverse().find((part) => /^[A-Za-z0-9]{8}$/.test(part) && part !== "analysis");
    return id || location.pathname;
  }

  const adapter = {
    matches(hostname) {
      return (hostname || "").toLowerCase().includes("lichess.org");
    },

    readGameState() {
      const selfIsWhite = whiteAtBottom();
      if (selfIsWhite == null) return null;
      const clocks = readClocks();
      if (clocks.clock_self_s == null || clocks.clock_opp_s == null) return null;
      const tc = readTimeControl();
      if (!tc) return null;
      const ratings = readRatings(selfIsWhite);
      if (ratings.elo_self == null || ratings.elo_opp == null) return null;
      const placement = placementFromPieces(selfIsWhite);
      if (!placement) return null;
      const moves = readMoves(placement);
      if (moves.movesPlayed == null) return null;
      const played = moves.movesPlayed;
      const side = sideLetter(selfIsWhite, played);
      const moveClocks = readMoveClocks(played);
      return Ox.buildRawGameState({
        site: SITE,
        game_id: readGameId(),
        color: selfIsWhite ? "white" : "black",
        side_to_move: side === "w" ? "white" : "black",
        base_s: tc.base_s,
        inc_s: tc.inc_s,
        elo_self: ratings.elo_self,
        elo_opp: ratings.elo_opp,
        clock_self_s: clocks.clock_self_s,
        clock_opp_s: clocks.clock_opp_s,
        placement,
        moves_san: moves.sans,
        move_clocks: moveClocks.some((value) => value != null) ? moveClocks : undefined,
        ply: played + 1,
      });
    },

    onTurnStart(callback) {
      let lastSig = "";
      let pending = null;
      const tick = () => {
        const state = adapter.readGameState();
        if (!state) return;
        const sig = `${state.game_id || ""}|${state.ply}|${state.side_to_move || ""}`;
        if (sig === lastSig) return;
        lastSig = sig;
        try {
          callback(state);
        } catch (err) {
          console.error("[OxTera lichess] onTurnStart callback failed", err);
        }
      };
      const schedule = () => {
        if (pending) clearTimeout(pending);
        pending = setTimeout(tick, 32);
      };
      adapter._observer = new MutationObserver(schedule);
      const board = document.querySelector("cg-board") || document.body;
      adapter._observer.observe(board, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class", "style"],
      });
      const moves = document.querySelector(".analyse__moves, .rmoves");
      if (moves) {
        adapter._observer.observe(moves, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
      }
      // One look after the board paints. Later reads happen when the pieces or the move list change.
      requestAnimationFrame(() => requestAnimationFrame(tick));
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
