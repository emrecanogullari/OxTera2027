/**
 * Lichess page reader. HTML and CSS only.
 *
 * The request matches the path Chess.com already uses: a fen, the move names,
 * and think times, and only on our turn. The piece picture is not sent as
 * `placement`, because that selects a server path which rejects the position.
 * A frame is sent only after the pieces have stopped moving and the fen is
 * one the server can parse. The move list supplies castling and en passant
 * when every move name is usable; the fen is the fallback.
 */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});
  Ox.sites = Ox.sites || {};

  const SITE = "lichess";
  const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR";
  const PIECE = { pawn: "p", knight: "n", bishop: "b", rook: "r", queen: "q", king: "k" };
  const SAN = /^(?:O-O-O|O-O|[KQRBN](?:[a-h]|[1-8]|[a-h][1-8])?x?[a-h][1-8](?:=[QRBN])?|[a-h]x[a-h][1-8](?:=[QRBN])?|[a-h][1-8](?:=[QRBN])?)$/;

  /** Clock samples. content.js does not keep this history for Lichess. */
  const games = new Map();

  function parseClockText(text) {
    if (!text) return null;
    const cleaned = String(text).trim().replace(/[^\d:.]/g, "");
    const parts = cleaned.split(":").map((part) => Number(part));
    if (parts.length < 2 || parts.some((n) => Number.isNaN(n))) return null;
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
    const base = Number(baseMatch[1]) * 60;
    if (!(base > 0) || inc < 0) return null;
    return { base_s: base, inc_s: inc };
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
      if (grid[row][file]) return null;
      grid[row][file] = letter;
    }
    const ranks = grid.map((rank) => {
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
    });
    if (ranks.some((rank) => rankWidth(rank) !== 8)) return null;
    const placement = ranks.join("/");
    const whiteKings = placement.split("K").length - 1;
    const blackKings = placement.split("k").length - 1;
    if (whiteKings !== 1 || blackKings !== 1) return null;
    return placement;
  }

  function rankWidth(row) {
    let width = 0;
    for (const ch of row) {
      if (ch >= "1" && ch <= "8") width += Number(ch);
      else width += 1;
    }
    return width;
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
    if (rank8.length !== 8 || rank1.length !== 8) return "-";
    let rights = "";
    if (rank1[4] === "K" && rank1[7] === "R") rights += "K";
    if (rank1[4] === "K" && rank1[0] === "R") rights += "Q";
    if (rank8[4] === "k" && rank8[7] === "r") rights += "k";
    if (rank8[4] === "k" && rank8[0] === "r") rights += "q";
    return rights || "-";
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
    const raw = textOf(san || moveEl).replace(/[+#?!]+$/g, "");
    const token = raw.split(/\s+/)[0];
    return SAN.test(token) ? token : null;
  }

  function readMoves(placement) {
    const moves = mainlineMoves();
    if (!moves.length) return { sans: [], movesPlayed: placement === START ? 0 : null, trusted: placement === START };
    const idx = moves.findIndex(
      (move) => move.classList.contains("active") || move.classList.contains("current")
    );
    let slice;
    if (idx >= 0) slice = moves.slice(0, idx + 1);
    else if (placement === START) slice = [];
    else slice = moves;
    const sans = slice.map(sanOf);
    if (sans.some((san) => !san)) {
      return { sans: [], movesPlayed: placement === START ? 0 : null, trusted: false };
    }
    return { sans, movesPlayed: sans.length, trusted: true };
  }

  function parseThink(text) {
    const seconds = String(text || "").trim().match(/^([\d.]+)\s*s$/i);
    if (!seconds) return null;
    const value = Number(seconds[1]);
    return Number.isFinite(value) && value >= 0 ? value : null;
  }

  /**
   * Printed think times win. A `<clock>` is time remaining, so the spend is
   * the previous remaining clock minus this one, plus the increment.
   */
  function readThinkTimes(movesPlayed, color, base, inc) {
    const moves = mainlineMoves().slice(0, movesPlayed);
    if (!moves.length || moves.length !== movesPlayed) return {};
    const labels = moves.map((move) => parseThink(textOf(move.querySelector(".time, .movetime"))));
    if (labels.every((value) => value != null)) return spendsFor(labels, color);
    const clocks = moves.map((move) => parseClockText(textOf(move.querySelector("clock"))));
    if (!clocks.every((value) => value != null && value >= 0)) return {};
    let whiteBefore = base;
    let blackBefore = base;
    const spends = clocks.map((after, index) => {
      const whiteMove = index % 2 === 0;
      const before = whiteMove ? whiteBefore : blackBefore;
      if (whiteMove) whiteBefore = after;
      else blackBefore = after;
      return Math.max(0, before - after + inc);
    });
    return spendsFor(spends, color);
  }

  function spendsFor(spends, color) {
    const mine = [];
    const theirs = [];
    spends.forEach((spent, index) => {
      if (spent == null || !Number.isFinite(spent) || spent < 0) return;
      const whiteMove = index % 2 === 0;
      if ((color === "white") === whiteMove) mine.push(spent);
      else theirs.push(spent);
    });
    const out = {};
    if (mine.length) {
      out.prev_self_spent = mine[mine.length - 1];
      out.avg_self_spent = mine.reduce((sum, value) => sum + value, 0) / mine.length;
    }
    if (theirs.length) out.prev_opp_spent = theirs[theirs.length - 1];
    return out;
  }

  function historyFor(gameId) {
    const key = String(gameId || "default");
    let game = games.get(key);
    if (!game) {
      game = { selfSpents: [], prevOpp: NaN, lastSelf: null, lastOpp: null, lastPly: 0, lastSig: "" };
      games.set(key, game);
    }
    return game;
  }

  /**
   * Once per settled position. Our think is recorded when the opponent's turn
   * starts, because that is when our clock stops. Their think is recorded
   * when our turn starts. Scrolling the analysis back resets the samples.
   */
  function noteClocks(state) {
    const game = historyFor(state.game_id);
    const sig = `${state.placement}|${state.ply}`;
    if (sig === game.lastSig) return;
    const ply = state.ply != null ? Number(state.ply) : 0;
    if (ply > 0 && game.lastPly > ply) {
      game.selfSpents = [];
      game.prevOpp = NaN;
      game.lastSelf = null;
      game.lastOpp = null;
      game.lastPly = 0;
    }
    const inc = Number(state.inc_s) || 0;
    if (ply > game.lastPly) {
      const ourTurn = (ply % 2 === 1) === (state.color === "white");
      if (!ourTurn && game.lastSelf != null) {
        const spentSelf = game.lastSelf - Number(state.clock_self_s) + inc;
        if (spentSelf >= 0 && Number.isFinite(spentSelf)) game.selfSpents.push(spentSelf);
      }
      if (ourTurn && game.lastOpp != null) {
        const spentOpp = game.lastOpp - Number(state.clock_opp_s) + inc;
        if (spentOpp >= 0 && Number.isFinite(spentOpp)) game.prevOpp = spentOpp;
      }
    }
    game.lastSelf = Number(state.clock_self_s);
    game.lastOpp = Number(state.clock_opp_s);
    game.lastPly = ply;
    game.lastSig = sig;
  }

  function spendsFromHistory(state) {
    const game = historyFor(state.game_id);
    const out = {};
    if (game.selfSpents.length) {
      out.prev_self_spent = game.selfSpents[game.selfSpents.length - 1];
      out.avg_self_spent = game.selfSpents.reduce((sum, value) => sum + value, 0) / game.selfSpents.length;
    }
    if (Number.isFinite(game.prevOpp) && game.prevOpp >= 0) out.prev_opp_spent = game.prevOpp;
    return out;
  }

  function readGameId() {
    const parts = location.pathname.split("/").filter(Boolean);
    const id = [...parts].reverse().find((part) => /^[A-Za-z0-9]{8}$/.test(part) && part !== "analysis");
    return id || location.pathname;
  }

  function emit(state) {
    if (!state || !adapter._callback) return;
    const sig = `${state.fen}|${state.ply}|${state.color}`;
    if (sig === adapter._lastSig) return;
    adapter._lastSig = sig;
    if (typeof Ox.setHudStatus === "function") Ox.setHudStatus("predicting…");
    try {
      adapter._callback(state);
    } catch (err) {
      console.error("[OxTera lichess] onTurnStart callback failed", err);
    }
  }

  const adapter = {
    _armed: null,
    _lastSig: "",
    _callback: null,

    matches(hostname) {
      return (hostname || "").toLowerCase().includes("lichess.org");
    },

    readGameState() {
      const selfIsWhite = whiteAtBottom();
      if (selfIsWhite == null) return null;
      const color = selfIsWhite ? "white" : "black";
      const clocks = readClocks();
      if (clocks.clock_self_s == null || clocks.clock_opp_s == null) return null;
      if (clocks.clock_self_s < 0 || clocks.clock_opp_s < 0) return null;
      const tc = readTimeControl();
      if (!tc) return null;
      const ratings = readRatings(selfIsWhite);
      if (ratings.elo_self == null) return null;
      const placement = placementFromPieces(selfIsWhite);
      if (!placement) return null;

      // The move list and the pieces often update a frame apart. Sending in
      // that gap makes the server keep a picture that does not belong to those
      // moves, and the blunder chance is then for the wrong position.
      const stamp = `${placement}|${mainlineMoves().map(sanOf).join(",")}`;
      if (adapter._armed !== stamp) {
        adapter._armed = stamp;
        if (adapter._confirm) clearTimeout(adapter._confirm);
        adapter._confirm = setTimeout(() => {
          emit(adapter.readGameState());
        }, 40);
        return null;
      }

      const moves = readMoves(placement);
      const trustMoves = moves.trusted && moves.movesPlayed != null;
      // Without a usable move list the move number is unknown, so the fen would
      // tell the server this is move 1. Wait until the list is readable.
      if (!trustMoves && placement !== START) return null;
      const played = trustMoves ? moves.movesPlayed : 0;
      // Side comes from how many moves are on the list. A highlighted clock can
      // lag a frame behind the pieces, which would make the fen illegal to use.
      const side = played % 2 === 0 ? "w" : "b";

      const fullmove = Math.floor((trustMoves ? played : 0) / 2) + 1;
      const fen = `${placement} ${side} ${castlingFromPlacement(placement)} - 0 ${fullmove}`;
      const ply = trustMoves ? played + 1 : placement === START ? 1 : undefined;
      const draft = {
        game_id: readGameId(),
        color,
        placement,
        fen,
        ply,
        inc_s: tc.inc_s,
        clock_self_s: clocks.clock_self_s,
        clock_opp_s: clocks.clock_opp_s,
      };
      noteClocks(draft);

      const sideToMove = side === "w" ? "white" : "black";
      if (sideToMove !== color) return null;

      const printed = trustMoves ? readThinkTimes(played, color, tc.base_s, tc.inc_s) : {};
      const spends = Object.assign(spendsFromHistory(draft), printed);
      return Ox.buildRawGameState(
        Object.assign(
          {
            site: SITE,
            game_id: draft.game_id,
            color,
            base_s: tc.base_s,
            inc_s: tc.inc_s,
            elo_self: ratings.elo_self,
            elo_opp: ratings.elo_opp,
            clock_self_s: clocks.clock_self_s,
            clock_opp_s: clocks.clock_opp_s,
            fen,
            side_to_move: sideToMove,
            moves_san: trustMoves ? moves.sans : [],
            ply,
          },
          spends
        )
      );
    },

    onTurnStart(callback) {
      adapter._callback = callback;
      if (typeof Ox.setHudStatus === "function") Ox.setHudStatus("reading the board…");
      const tick = () => emit(adapter.readGameState());
      const schedule = () => {
        if (adapter._pending) clearTimeout(adapter._pending);
        adapter._pending = setTimeout(tick, 16);
      };
      adapter._timer = setInterval(tick, 500);
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
        adapter._observer.observe(moves, {
          childList: true,
          subtree: true,
          attributes: true,
          attributeFilter: ["class"],
        });
      }
    },

    destroy() {
      if (adapter._timer) clearInterval(adapter._timer);
      if (adapter._pending) clearTimeout(adapter._pending);
      if (adapter._confirm) clearTimeout(adapter._confirm);
      if (adapter._observer) adapter._observer.disconnect();
      adapter._timer = null;
      adapter._pending = null;
      adapter._confirm = null;
      adapter._observer = null;
      adapter._callback = null;
    },
  };

  Ox.sites.lichess = adapter;
})(typeof globalThis !== "undefined" ? globalThis : window);
