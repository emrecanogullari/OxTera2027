/** POST /predict/live — no site DOM. */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});

  Ox.BACKEND_BASE = "http://127.0.0.1:8000";

  /**
   * @param {object} rawGameState
   * @returns {Promise<object>}
   */
  Ox.DEBUG = true;

  Ox.predictLive = async function predictLive(rawGameState) {
    const payload = Object.assign({}, rawGameState, { debug: Ox.DEBUG !== false });
    console.groupCollapsed("[OxTera] POST /predict/live — request (raw scrape)");
    console.log(payload);
    console.groupEnd();

    const res = await fetch(`${Ox.BACKEND_BASE}/predict/live`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`predict/live ${res.status}: ${detail}`);
    }
    const data = await res.json();

    console.groupCollapsed(
      `[OxTera] predict/live — response p_blunder=${data.predictions?.p_blunder} engine=${data.debug?.engine_used}`
    );
    console.log("predictions", data.predictions);
    console.log("model", data.model);
    if (data.debug) {
      console.log("derived features (null = missing/NaN)", data.debug.features);
      console.log("raw echoed", data.debug.raw);
      if (data.debug.note) console.warn(data.debug.note);
    }
    console.groupEnd();

    return data;
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
