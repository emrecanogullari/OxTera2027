/** HUD: edge risk glow + robot helper panel. No site DOM selectors. */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});

  /** Blunder probability (0–1) at which edge red is fully intense. */
  const BLUNDER_RED_CAP = 0.2;

  const ROBOT_SVG = `
    <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect x="8" y="11" width="16" height="14" rx="3.5" fill="#c8d0d4"/>
      <rect x="10" y="14" width="5" height="5" rx="1.5" fill="#1a2226"/>
      <rect x="17" y="14" width="5" height="5" rx="1.5" fill="#1a2226"/>
      <circle cx="12.5" cy="16.5" r="1.4" fill="#5dce7a"/>
      <circle cx="19.5" cy="16.5" r="1.4" fill="#5dce7a"/>
      <rect x="12" y="22" width="8" height="1.8" rx="0.9" fill="#6a757a"/>
      <rect x="14.5" y="4" width="3" height="5" rx="1.2" fill="#9aa4a8"/>
      <circle cx="16" cy="3.5" r="2.2" fill="#e8c547"/>
      <rect x="4" y="15" width="3.5" height="6" rx="1.5" fill="#9aa4a8"/>
      <rect x="24.5" y="15" width="3.5" height="6" rx="1.5" fill="#9aa4a8"/>
    </svg>
  `;

  function ensureEdgeGlow() {
    let el = document.getElementById("oxtera-edge-glow");
    if (el) return el;
    el = document.createElement("div");
    el.id = "oxtera-edge-glow";
    el.setAttribute("aria-hidden", "true");
    document.body.appendChild(el);
    return el;
  }

  /**
   * Map p_blunder (0–1) → edge intensity. Full red at BLUNDER_RED_CAP (20%).
   * @param {number} pBlunder
   */
  Ox.setBlunderEdgeGlow = function setBlunderEdgeGlow(pBlunder) {
    const el = ensureEdgeGlow();
    const p = Number(pBlunder);
    if (!Number.isFinite(p) || p <= 0) {
      el.classList.remove("oxtera-active");
      el.style.setProperty("--oxtera-red-a", "0");
      el.style.setProperty("--oxtera-red-glow", "0");
      return;
    }
    const t = Math.min(1, Math.max(0, p / BLUNDER_RED_CAP));
    // Ease slightly so low risk stays subtle, then climbs toward the cap.
    const eased = t * t * (3 - 2 * t);
    const alpha = (0.12 + eased * 0.72).toFixed(3);
    const glow = (eased * 0.85).toFixed(3);
    el.style.setProperty("--oxtera-red-a", alpha);
    el.style.setProperty("--oxtera-red-glow", glow);
    el.classList.add("oxtera-active");
  };

  Ox.injectHud = function injectHud() {
    ensureEdgeGlow();
    if (document.getElementById("oxtera-robot-root")) return;

    const root = document.createElement("div");
    root.id = "oxtera-robot-root";
    root.innerHTML = `
      <aside id="oxtera-robot-panel" role="dialog" aria-label="BlunderBot coach" aria-hidden="true">
        <div class="oxtera-panel-title">BlunderBot</div>
        <div id="hud-status" class="oxtera-panel-status">booting…</div>
        <div class="oxtera-metric">
          <div class="oxtera-metric-label">Predicted think time</div>
          <div id="hud-thinking-time" class="oxtera-metric-value think">-- s</div>
        </div>
        <div class="oxtera-metric">
          <div class="oxtera-metric-label">Blunder chance</div>
          <div id="hud-blunder-risk" class="oxtera-metric-value blunder">-- %</div>
        </div>
      </aside>
      <button
        type="button"
        id="oxtera-robot-toggle"
        aria-label="Open BlunderBot"
        aria-expanded="false"
        aria-controls="oxtera-robot-panel"
        title="BlunderBot"
      >${ROBOT_SVG}</button>
    `;
    document.body.appendChild(root);

    const toggle = document.getElementById("oxtera-robot-toggle");
    const panel = document.getElementById("oxtera-robot-panel");
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = !root.classList.contains("oxtera-open");
      root.classList.toggle("oxtera-open", open);
      toggle.classList.toggle("oxtera-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Close BlunderBot" : "Open BlunderBot");
      panel.setAttribute("aria-hidden", open ? "false" : "true");
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
    if (preds.p_blunder !== undefined) {
      const pct = Math.round(preds.p_blunder * 100);
      if (riskElem) riskElem.textContent = `${pct}%`;
      Ox.setBlunderEdgeGlow(preds.p_blunder);
    }
    Ox.setHudStatus("live");
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
