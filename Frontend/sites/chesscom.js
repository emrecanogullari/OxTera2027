/**
 * Chess.com page reader. HTML and CSS only — no board.game, no fen attribute.
 * Piece squares, clocks, ratings, the Info "Time:" line, and the move list
 * are the inputs. The shared server turns them into the model vector.
 */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});
  Ox.sites = Ox.sites || {};

  const SITE = "chesscom";
  const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR";

  function parseClockText(text) {
    if (!text) return null;
    const t = String(text).trim().replace(/\s+/g, "");
    const parts = t.split(":").map((part) => Number(part));
    if (!parts.length || parts.some((n) => Number.isNaN(n))) return null;
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    return null;
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

  function boardElement() {
    return document.querySelector("#board-single") || document.querySelector("wc-chess-board");
  }

  function readColor() {
    const bottom = document.querySelector(".clock-bottom");
    if (bottom) {
      if (bottom.classList.contains("clock-black")) return "black";
      if (bottom.classList.contains("clock-white")) return "white";
    }
    const board = boardElement();
    if (board && board.classList.contains("flipped")) return "black";
    return null;
  }

  function readClocks() {
    const bottom = document.querySelector(".clock-bottom .clock-time-monospace");
    const top = document.querySelector(".clock-top .clock-time-monospace");
    return {
      clock_self_s: parseClockText(textOf(bottom)),
      clock_opp_s: parseClockText(textOf(top)),
    };
  }

  function readRatings() {
    return {
      elo_self: ratingFrom(document.querySelector(".player-bottom")),
      elo_opp: ratingFrom(document.querySelector(".player-top")),
    };
  }

  /**
   * "Time: 3 min" is 180+0. "Time: 3 | 2" and "3 | 2" are minutes plus seconds.
   * The line lives in the Info panel; it stays in the page after that tab is opened.
   */
  function parseTimeControl(raw) {
    if (!raw) return null;
    const text = String(raw).replace(/^Time:\s*/i, "").trim();
    const minutes = text.match(/^(\d+)\s*min(?:\s*(?:\|\s*|\+\s*)(\d+)(?:\s*sec)?)?$/i);
    if (minutes) return { base_s: Number(minutes[1]) * 60, inc_s: minutes[2] ? Number(minutes[2]) : 0 };
    const pipe = text.match(/^(\d+)\s*\|\s*(\d+)$/);
    if (pipe) return { base_s: Number(pipe[1]) * 60, inc_s: Number(pipe[2]) };
    const seconds = text.match(/^(\d+)\s*sec(?:\s*(?:\|\s*|\+\s*)(\d+))?$/i);
    if (seconds) return { base_s: Number(seconds[1]), inc_s: seconds[2] ? Number(seconds[2]) : 0 };
    const plus = text.match(/^(\d+)\s*\+\s*(\d+)$/);
    if (plus) return { base_s: Number(plus[1]) * 60, inc_s: Number(plus[2]) };
    return null;
  }

  function readTimeControl() {
    const labelled = [...document.querySelectorAll(".user-selectable div, [class*='game-info'] div")]
      .map((el) => textOf(el))
      .find((text) => /^Time:/i.test(text));
    const fromInfo = parseTimeControl(labelled);
    if (fromInfo) return fromInfo;
    const chip = [...document.querySelectorAll(".board-layout-main span, .board-layout-main div")].find((el) => {
      if (el.children.length) return false;
      return parseTimeControl(textOf(el)) != null;
    });
    return chip ? parseTimeControl(textOf(chip)) : null;
  }

  function placementFromPieces() {
    const board = boardElement();
    if (!board) return null;
    const grid = Array.from({ length: 8 }, () => Array(8).fill(""));
    let count = 0;
    for (const piece of board.querySelectorAll(":scope > .piece")) {
      const cls = String(piece.className).split(/\s+/);
      const square = cls.find((c) => /^square-\d{2}$/.test(c));
      const kind = cls.find((c) => /^[wb][pnbrqk]$/.test(c));
      if (!square || !kind) continue;
      const n = Number(square.slice(7));
      const file = Math.floor(n / 10) - 1;
      const rank = (n % 10) - 1;
      if (file < 0 || file > 7 || rank < 0 || rank > 7) continue;
      const letter = kind[1];
      grid[7 - rank][file] = kind[0] === "w" ? letter.toUpperCase() : letter;
      count += 1;
    }
    if (!count) return null;
    return grid
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
  }

  function expandRank(row) {
    let out = "";
    for (const ch of row) {
      if (ch >= "1" && ch <= "8") out += " ".repeat(Number(ch));
      else out += ch;
    }
    return out;
  }

  function castlingFromPlacement(placement) {
    const rows = placement.split("/");
    if (rows.length !== 8) return "-";
    const rank8 = expandRank(rows[0]);
    const rank1 = expandRank(rows[7]);
    let rights = "";
    if (rank1[4] === "K" && rank1[7] === "R") rights += "K";
    if (rank1[4] === "K" && rank1[0] === "R") rights += "Q";
    if (rank8[4] === "k" && rank8[7] === "r") rights += "k";
    if (rank8[4] === "k" && rank8[0] === "r") rights += "q";
    return rights || "-";
  }

  function sideLetter(movesPlayed) {
    const turn = document.querySelector(".clock-player-turn");
    if (turn) {
      if (turn.classList.contains("clock-white")) return "w";
      if (turn.classList.contains("clock-black")) return "b";
    }
    return movesPlayed % 2 === 0 ? "w" : "b";
  }

  function readMoves(placement) {
    const nodes = [...document.querySelectorAll(".node.main-line-ply")];
    if (!nodes.length) return { sans: [], movesPlayed: placement === START ? 0 : null };
    const sans = nodes.map((node) => textOf(node.querySelector(".node-highlight-content") || node));
    const selected = nodes.findIndex(
      (node) => node.classList.contains("selected") || node.querySelector(".selected")
    );
    let slice;
    if (selected >= 0) slice = sans.slice(0, selected + 1);
    else if (placement === START) slice = [];
    else slice = sans;
    return { sans: slice.filter(Boolean), movesPlayed: slice.filter(Boolean).length };
  }

  function parseThink(text) {
    const seconds = String(text || "").trim().match(/^([\d.]+)\s*s$/i);
    if (seconds) return Number(seconds[1]);
    return parseClockText(text);
  }

  function readThinkTimes(movesPlayed, color) {
    const collect = (selector) =>
      [...document.querySelectorAll(selector)]
        .map((el) => ({
          ply: Number(el.getAttribute("data-ply")),
          spent: parseThink(textOf(el)),
        }))
        .filter((row) => row.spent != null && !Number.isNaN(row.spent) && row.ply > 0 && row.ply <= movesPlayed);
    const mine = collect(color === "white" ? ".time-white" : ".time-black");
    const theirs = collect(color === "white" ? ".time-black" : ".time-white");
    const out = {};
    if (mine.length) {
      out.prev_self_spent = mine[mine.length - 1].spent;
      out.avg_self_spent = mine.reduce((sum, row) => sum + row.spent, 0) / mine.length;
    }
    if (theirs.length) out.prev_opp_spent = theirs[theirs.length - 1].spent;
    return out;
  }

  function readGameId() {
    const match = location.pathname.match(/\/(?:game|play)\/(?:live\/)?(\d+)/);
    return match ? match[1] : location.pathname;
  }

  const adapter = {
    matches(hostname) {
      return (hostname || "").toLowerCase().includes("chess.com");
    },

    readGameState() {
      const color = readColor();
      if (!color) return null;
      const clocks = readClocks();
      if (clocks.clock_self_s == null || clocks.clock_opp_s == null) return null;
      const tc = readTimeControl();
      if (!tc) return null;
      const ratings = readRatings();
      if (ratings.elo_self == null) return null;
      const placement = placementFromPieces();
      if (!placement) return null;
      const moves = readMoves(placement);
      const played = moves.movesPlayed == null ? 0 : moves.movesPlayed;
      const side = sideLetter(played);
      const fullmove = Math.floor(played / 2) + 1;
      const fen = `${placement} ${side} ${castlingFromPlacement(placement)} - 0 ${fullmove}`;
      const ply = moves.movesPlayed == null && placement !== START ? undefined : played + 1;
      const spends = readThinkTimes(played, color);
      return Ox.buildRawGameState(
        Object.assign(
          {
            site: SITE,
            game_id: readGameId(),
            color,
            base_s: tc.base_s,
            inc_s: tc.inc_s,
            elo_self: ratings.elo_self,
            elo_opp: ratings.elo_opp,
            clock_self_s: clocks.clock_self_s,
            clock_opp_s: clocks.clock_opp_s,
            fen,
            moves_san: moves.sans,
            ply,
          },
          spends
        )
      );
    },

    onTurnStart(callback) {
      let lastSig = "";
      let pending = null;
      const tick = () => {
        const state = adapter.readGameState();
        if (!state) return;
        const sig = `${state.fen}|${state.ply}|${state.color}`;
        if (sig === lastSig) return;
        lastSig = sig;
        try {
          callback(state);
        } catch (err) {
          console.error("[OxTera chesscom] onTurnStart callback failed", err);
        }
      };
      const schedule = () => {
        if (pending) clearTimeout(pending);
        pending = setTimeout(tick, 150);
      };
      adapter._timer = setInterval(tick, 500);
      adapter._observer = new MutationObserver(schedule);
      const board = boardElement() || document.body;
      adapter._observer.observe(board, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class", "style"],
      });
      const list = document.querySelector("wc-simple-move-list, .move-list");
      if (list) adapter._observer.observe(list, { childList: true, subtree: true, attributes: true });
      setTimeout(tick, 400);
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
