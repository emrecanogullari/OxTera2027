/** POST /predict/live via background worker only (never fetch from the page). */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});

  Ox.DEBUG = true;
  Ox.API_CLIENT_VERSION = "1.4.0";
  // client_id is injected by the background service worker (not here).

  function sendPredictLive(payload) {
    return new Promise((resolve, reject) => {
      if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.sendMessage) {
        reject(new Error("chrome.runtime unavailable — remove + re-load the unpacked extension"));
        return;
      }
      chrome.runtime.sendMessage({ type: "predictLive", payload }, (response) => {
        if (chrome.runtime.lastError) {
          reject(
            new Error(
              chrome.runtime.lastError.message +
                " — open chrome://extensions, Remove the HUD, Load unpacked again from Frontend/"
            )
          );
          return;
        }
        if (!response) {
          reject(new Error("empty response from extension background"));
          return;
        }
        if (!response.ok) {
          reject(new Error(`predict/live ${response.status}: ${response.error || "failed"}`));
          return;
        }
        resolve(response);
      });
    });
  }

  /**
   * @param {object} rawGameState
   * @returns {Promise<object>}
   */
  Ox.predictLive = async function predictLive(rawGameState) {
    const payload = Object.assign({}, rawGameState, { debug: Ox.DEBUG !== false });
    console.groupCollapsed(
      `[OxTera ${Ox.API_CLIENT_VERSION}] predict/live via background proxy (not page fetch)`
    );
    console.log(payload);
    console.groupEnd();

    const response = await sendPredictLive(payload);
    const data = response.data;

    console.groupCollapsed(
      `[OxTera ${Ox.API_CLIENT_VERSION}] ok proxy=${response.proxyVersion} client=${response.clientId || "?"} p_blunder=${data.predictions?.p_blunder} engine=${data.debug?.engine_used}`
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
