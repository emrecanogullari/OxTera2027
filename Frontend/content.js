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
    Ox.recordClocks(raw);
    const enriched = Ox.enrichWithSpend(raw);
    console.log("[OxTera] turn scrape", {
      site: enriched.site,
      game_id: enriched.game_id,
      color: enriched.color,
      ply: enriched.ply,
      clocks: [enriched.clock_self_s, enriched.clock_opp_s],
      tc: `${enriched.base_s}+${enriched.inc_s}`,
      fen: enriched.fen,
      moves: (enriched.moves_uci || []).length,
    });
    try {
      const data = await Ox.predictLive(enriched);
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
