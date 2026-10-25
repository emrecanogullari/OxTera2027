/** Shared RawGameState contract for POST /predict/live. No site DOM here. */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});

  /**
   * Build the scrape payload for POST /predict/live.
   * Do not set client_id here — the background service worker injects it.
   *
   * @param {object} fields
   * @returns {object}
   */
  Ox.buildRawGameState = function buildRawGameState(fields) {
    return {
      site: fields.site,
      game_id: fields.game_id ?? null,
      color: fields.color,
      base_s: Number(fields.base_s),
      inc_s: Number(fields.inc_s),
      elo_self: Number(fields.elo_self),
      elo_opp: fields.elo_opp != null ? Number(fields.elo_opp) : undefined,
      clock_self_s: Number(fields.clock_self_s),
      clock_opp_s: Number(fields.clock_opp_s),
      fen: fields.fen || undefined,
      placement: fields.placement || undefined,
      side_to_move: fields.side_to_move || undefined,
      moves_uci: Array.isArray(fields.moves_uci) ? fields.moves_uci.slice() : [],
      moves_san: Array.isArray(fields.moves_san) ? fields.moves_san.slice() : [],
      move_clocks: Array.isArray(fields.move_clocks) ? fields.move_clocks.slice() : undefined,
      ply: fields.ply != null ? Number(fields.ply) : undefined,
      prev_self_spent: fields.prev_self_spent,
      avg_self_spent: fields.avg_self_spent,
      prev_opp_spent: fields.prev_opp_spent,
      prior_blunders_self: fields.prior_blunders_self,
    };
  };

  Ox.detectSite = function detectSite(hostname) {
    const h = (hostname || "").toLowerCase();
    if (h.includes("chess.com")) return "chesscom";
    if (h.includes("lichess.org")) return "lichess";
    return null;
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
