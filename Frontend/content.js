(function () {
  // 1. Create container for the HUD
  const hudContainer = document.createElement("div");
  hudContainer.id = "chess-coach-hud";
  
  // Style HUD container (drag position & aesthetic)
  Object.assign(hudContainer.style, {
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
    userSelect: "none"
  });

  // 2. Build minimal HUD HTML (Only Expected Time & Blunder Risk)
  hudContainer.innerHTML = `
    <div style="font-weight: 700; font-size: 14px; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 12px; color: #a0a0a0; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px;">
      Coach HUD
    </div>

    <div style="margin-bottom: 12px;">
      <div style="font-size: 12px; color: #8a8a8e; margin-bottom: 4px;">Expected Thinking Time</div>
      <div id="hud-thinking-time" style="font-size: 20px; font-weight: 600; color: #4cd964;">-- s</div>
    </div>

    <div>
      <div style="font-size: 12px; color: #8a8a8e; margin-bottom: 4px;">Blunder Risk</div>
      <div id="hud-blunder-risk" style="font-size: 20px; font-weight: 600; color: #ff3b30;">-- %</div>
    </div>
  `;

  document.body.appendChild(hudContainer);

  // 3. Make HUD Draggable via Pointer Events
  let isDragging = false;
  let offsetX = 0;
  let offsetY = 0;

  hudContainer.addEventListener("pointerdown", (e) => {
    isDragging = true;
    hudContainer.style.cursor = "grabbing";
    offsetX = e.clientX - hudContainer.getBoundingClientRect().left;
    offsetY = e.clientY - hudContainer.getBoundingClientRect().top;
    hudContainer.setPointerCapture(e.pointerId);
  });

  hudContainer.addEventListener("pointermove", (e) => {
    if (!isDragging) return;
    hudContainer.style.left = `${e.clientX - offsetX}px`;
    hudContainer.style.top = `${e.clientY - offsetY}px`;
    hudContainer.style.right = "auto";
  });

  hudContainer.addEventListener("pointerup", (e) => {
    isDragging = false;
    hudContainer.style.cursor = "grab";
    hudContainer.releasePointerCapture(e.pointerId);
  });

  // 4. API Client: Fetch Predictions matching PredictRequest schema
  async function updateHUDMetrics() {
    try {
      const response = await fetch("http://127.0.0.1:8000/predict", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          speed: "blitz",
          game_id: "lichess_game_test",
          features: {}
        })
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const data = await response.json();
      console.log("[Coach HUD]: Received data", data);

      const timeElem = document.getElementById("hud-thinking-time");
      const riskElem = document.getElementById("hud-blunder-risk");

      // Extract values matching app.py PredictResponse schema
      if (data.predictions) {
        if (timeElem && data.predictions.time_spent_s !== undefined) {
          timeElem.textContent = `${Math.round(data.predictions.time_spent_s)}s`;
        }

        if (riskElem && data.predictions.p_blunder !== undefined) {
          const riskVal = data.predictions.p_blunder;
          const riskPct = Math.round(riskVal * 100);
          riskElem.textContent = `${riskPct}%`;
        }
      }
    } catch (err) {
      console.error("[Coach HUD Error]: Failed to fetch predictions", err);
    }
  }

  // Initial trigger to test connection on load
  updateHUDMetrics();

})();
