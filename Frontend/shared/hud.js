/** HUD meters only — no site DOM selectors. */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});

  Ox.injectHud = function injectHud() {
    if (document.getElementById("chess-coach-hud")) return;

    const hud = document.createElement("div");
    hud.id = "chess-coach-hud";
    Object.assign(hud.style, {
      position: "fixed",
      top: "20px",
      right: "20px",
      zIndex: "999999",
      width: "240px",
      padding: "16px",
      borderRadius: "12px",
      backgroundColor: "rgba(24, 26, 27, 0.95)",
      boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
      border: "1px solid rgba(255, 255, 255, 0.1)",
      color: "#ffffff",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      cursor: "grab",
      userSelect: "none",
    });

    hud.innerHTML = `
      <div style="font-weight:700;font-size:14px;letter-spacing:0.5px;text-transform:uppercase;margin-bottom:8px;color:#a0a0a0;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:6px;">
        Coach HUD
      </div>
      <div id="hud-status" style="font-size:11px;color:#e6b41e;margin-bottom:10px;min-height:14px;">booting…</div>
      <div style="margin-bottom:12px;">
        <div style="font-size:12px;color:#8a8a8e;margin-bottom:4px;">Expected Thinking Time</div>
        <div id="hud-thinking-time" style="font-size:20px;font-weight:600;color:#4cd964;">-- s</div>
      </div>
      <div>
        <div style="font-size:12px;color:#8a8a8e;margin-bottom:4px;">Blunder Risk</div>
        <div id="hud-blunder-risk" style="font-size:20px;font-weight:600;color:#ff3b30;">-- %</div>
      </div>
    `;
    document.body.appendChild(hud);

    let dragging = false;
    let ox = 0;
    let oy = 0;
    hud.addEventListener("pointerdown", (e) => {
      dragging = true;
      hud.style.cursor = "grabbing";
      const r = hud.getBoundingClientRect();
      ox = e.clientX - r.left;
      oy = e.clientY - r.top;
      hud.setPointerCapture(e.pointerId);
    });
    hud.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      hud.style.left = `${e.clientX - ox}px`;
      hud.style.top = `${e.clientY - oy}px`;
      hud.style.right = "auto";
    });
    hud.addEventListener("pointerup", (e) => {
      dragging = false;
      hud.style.cursor = "grab";
      hud.releasePointerCapture(e.pointerId);
    });
  };

  Ox.setHudStatus = function setHudStatus(text) {
    const el = document.getElementById("hud-status");
    if (el) el.textContent = text || "";
  };

  /**
   * @param {{ predictions?: { time_spent_s?: number, p_blunder?: number } }} data
   */
  Ox.applyPredictions = function applyPredictions(data) {
    const preds = data && data.predictions;
    if (!preds) return;
    const timeElem = document.getElementById("hud-thinking-time");
    const riskElem = document.getElementById("hud-blunder-risk");
    if (timeElem && preds.time_spent_s !== undefined) {
      timeElem.textContent = `${Math.round(preds.time_spent_s)}s`;
    }
    if (riskElem && preds.p_blunder !== undefined) {
      riskElem.textContent = `${Math.round(preds.p_blunder * 100)}%`;
    }
    Ox.setHudStatus("live");
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
