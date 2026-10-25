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

  Ox.injectHud();

  async function handleTurn(raw) {
    if (!raw) return;
    let payload = raw;
    if (raw.site !== "lichess") {
      Ox.recordClocks(raw);
      payload = Ox.enrichWithSpend(raw);
      const sideToMove = payload.ply % 2 === 1 ? "white" : "black";
      if (payload.ply != null && sideToMove !== payload.color) return;
    }
    const sideToMove = payload.side_to_move || (payload.ply % 2 === 1 ? "white" : "black");
    console.log("[OxTera] turn scrape", {
      site: payload.site,
      game_id: payload.game_id,
      color: payload.color,
      side_to_move: sideToMove,
      ply: payload.ply,
      clocks: [payload.clock_self_s, payload.clock_opp_s],
      tc: `${payload.base_s}+${payload.inc_s}`,
      placement: payload.placement,
      moves: (payload.moves_san || payload.moves_uci || []).length,
    });
    try {
      const data = await Ox.predictLive(payload);
      // Opponent turns are sent so the server can search while they think.
      // The panel only shows the position we are about to play.
      if (payload.ply != null && sideToMove !== payload.color) return;
      Ox.applyPredictions(data);
    } catch (err) {
      console.error("[OxTera] predict/live failed", err);
    }
  }

  adapter.onTurnStart(handleTurn);

  // One immediate attempt so HUD is not empty on load.
  const first = adapter.readGameState();
  if (first) handleTurn(first);
})();
