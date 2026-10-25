/**
 * Generic think-time history from successive RawGameState clock readings.
 * Site-agnostic: adapters just call record(state) then enrich(state).
 */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});

  /** @type {Map<string, { selfSpents: number[], prevOpp: number, lastSelf: number|null, lastOpp: number|null, lastPly: number }>} */
  const games = new Map();

  function keyOf(state) {
    return String(state.game_id || "default");
  }

  /**
   * @param {object} state RawGameState
   */
  Ox.recordClocks = function recordClocks(state) {
    const key = keyOf(state);
    let g = games.get(key);
    if (!g) {
      g = { selfSpents: [], prevOpp: NaN, lastSelf: null, lastOpp: null, lastPly: 0 };
      games.set(key, g);
    }
    const ply = state.ply != null ? Number(state.ply) : 0;
    const inc = Number(state.inc_s) || 0;
    if (g.lastPly > 0 && ply > g.lastPly && g.lastSelf != null) {
      const spentSelf = g.lastSelf - Number(state.clock_self_s) + inc;
      if (spentSelf >= 0) g.selfSpents.push(spentSelf);
      if (g.lastOpp != null) {
        const spentOpp = g.lastOpp - Number(state.clock_opp_s) + inc;
        if (spentOpp >= 0) g.prevOpp = spentOpp;
      }
    }
    g.lastSelf = Number(state.clock_self_s);
    g.lastOpp = Number(state.clock_opp_s);
    g.lastPly = ply;
  };

  /**
   * Attach prev/avg spend fields onto a RawGameState copy.
   * @param {object} state
   * @returns {object}
   */
  Ox.enrichWithSpend = function enrichWithSpend(state) {
    const g = games.get(keyOf(state));
    const out = Object.assign({}, state);
    if (!g) return out;
    if (g.selfSpents.length) {
      out.prev_self_spent = g.selfSpents[g.selfSpents.length - 1];
      out.avg_self_spent = g.selfSpents.reduce((a, b) => a + b, 0) / g.selfSpents.length;
    }
    if (!Number.isNaN(g.prevOpp)) out.prev_opp_spent = g.prevOpp;
    return out;
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
