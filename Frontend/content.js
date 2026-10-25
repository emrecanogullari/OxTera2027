/**
 * Boot only: detect site → pick adapter → shared HUD/API pipeline.
 * No chess.com / Lichess DOM selectors here.
 */
(function () {
  const Ox = globalThis.OxTeraCoach;
  if (!Ox) {
    console.error("[OxTera] shared scripts failed to load");
    return;
  }

  const siteId = Ox.detectSite(location.hostname);
  const adapter = siteId && Ox.sites && Ox.sites[siteId];
  if (!adapter || !adapter.matches(location.hostname)) {
    console.warn("[OxTera] no site adapter for", location.hostname);
    return;
  }

  console.log("[OxTera] content boot", Ox.API_CLIENT_VERSION || "?", "site=", siteId);
  chrome.runtime.sendMessage({ type: "ping" }, (res) => {
    if (chrome.runtime.lastError) {
      console.error("[OxTera] background not reachable:", chrome.runtime.lastError.message);
      return;
    }
    console.log("[OxTera] background ping ok", res);
  });

  Ox.injectHud();
  if (typeof Ox.setHudStatus === "function") Ox.setHudStatus("scanning chess.com board…");

  let inFlightKey = null;
  let lastDoneKey = null;

  async function handleTurn(raw) {
    if (!raw) return;
    let payload = raw;
    if (typeof Ox.recordClocks === "function") {
      Ox.recordClocks(raw);
      payload = Ox.enrichWithSpend(raw);
    }
    const sideToMove =
      payload.side_to_move ||
      (payload.ply != null ? (payload.ply % 2 === 1 ? "white" : "black") : payload.color);
    const turnKey = `${payload.game_id || ""}|${payload.ply}|${sideToMove}`;
    // Drop duplicate ticks (same ply) and pile-ups while Stockfish is busy.
    if (turnKey === lastDoneKey || turnKey === inFlightKey) return;
    console.log("[OxTera] turn scrape", {
      site: payload.site,
      game_id: payload.game_id,
      color: payload.color,
      side_to_move: sideToMove,
      ply: payload.ply,
      clocks: [payload.clock_self_s, payload.clock_opp_s],
      tc: `${payload.base_s}+${payload.inc_s}`,
      fen: payload.fen,
      moves: (payload.moves_san || payload.moves_uci || []).length,
    });
    inFlightKey = turnKey;
    try {
      const data = await Ox.predictLive(payload);
      lastDoneKey = turnKey;
      // Prefetch on opponent's turn; only paint HUD when it is our move.
      if (payload.ply != null && sideToMove !== payload.color) {
        console.log("[OxTera] opponent to move — prediction fetched, HUD not updated");
        return;
      }
      Ox.applyPredictions(data);
    } catch (err) {
      console.error("[OxTera] predict/live failed", err);
    } finally {
      if (inFlightKey === turnKey) inFlightKey = null;
    }
  }

  adapter.onTurnStart(handleTurn);

  const first = adapter.readGameState();
  if (first) {
    handleTurn(first);
  } else {
    console.log("[OxTera] no game state yet at boot — waiting for board/clocks (see chesscom diagnose logs)");
  }
})();
