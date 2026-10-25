console.log("Chess Coaching Extension: Complete content.js loaded.");

// --- 1. CRITICAL STYLING INJECTION ---
const styleTag = document.createElement('style');
styleTag.innerHTML = `
  #chess-coaching-hud {
    position: fixed !important;
    top: 20px !important;
    left: 20px !important;
    width: 290px !important;
    background-color: #161512 !important;
    color: #bab5ab !important;
    border: 1px solid #262421 !important;
    border-radius: 8px !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.8) !important;
    z-index: 2147483647 !important;
    padding: 12px !important;
    box-sizing: border-box !important;
    pointer-events: auto !important;
  }
  #chess-coaching-hud .hud-header {
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    font-weight: bold !important;
    font-size: 13px !important;
    border-bottom: 1px solid #262421 !important;
    padding-bottom: 6px !important;
    margin-bottom: 10px !important;
    color: #dfdbe5 !important;
    cursor: grab !important;
    user-select: none !important;
    touch-action: none !important;
  }
  #chess-coaching-hud .hud-header:active {
    cursor: grabbing !important;
  }
  #chess-coaching-hud .stat-row {
    display: flex !important;
    justify-content: space-between !important;
    font-size: 14px !important;
    margin-bottom: 6px !important;
  }
  #chess-coaching-hud .eval-pos { color: #629924 !important; font-weight: bold !important; }
  #chess-coaching-hud .move-highlight { background-color: #363431 !important; padding: 1px 6px !important; border-radius: 4px !important; color: #f0f0f0 !important; font-family: monospace !important; }
  
  /* Behavioral Metric Styles */
  .time-highlight { font-family: monospace; color: #e6b41e; font-weight: bold; }
  .time-deliberate { color: #e6b41e; font-weight: bold; }
  .time-quick { color: #629924; font-weight: bold; }
  .risk-safe { color: #629924; font-weight: bold; }
  .risk-caution { color: #e6b41e; font-weight: bold; }
  .risk-danger { color: #d23c3c; font-weight: bold; }

  .chart-container { width: 100% !important; height: 80px !important; margin: 8px 0 !important; background: #11100e !important; border-radius: 4px !important; padding: 4px !important; box-sizing: border-box !important; }
  .space-control-container { width: 100% !important; margin: 8px 0 !important; background: #11100e !important; border-radius: 6px !important; border: 1px solid #262421 !important; padding: 8px !important; box-sizing: border-box !important; }
  .space-header { display: flex !important; justify-content: space-between !important; font-size: 11px !important; color: #9e9991 !important; margin-bottom: 4px !important; }
  .space-bar-wrapper { display: flex !important; height: 8px !important; width: 100% !important; background-color: #262421 !important; border-radius: 4px !important; overflow: hidden !important; margin-bottom: 6px !important; }
  .space-bar-white { background-color: #dfdbe5 !important; height: 100% !important; }
  .space-bar-black { background-color: #363431 !important; height: 100% !important; }
  .space-sectors { display: grid !important; grid-template-columns: repeat(3, 1fr) !important; gap: 4px !important; text-align: center !important; font-size: 10px !important; color: #8a857c !important; border-top: 1px dashed #262421 !important; padding-top: 6px !important; }
  .sector-box { background: #161512 !important; border-radius: 3px !important; padding: 2px 0 !important; }
  .sector-box span { display: block !important; font-weight: bold !important; color: #bab5ab !important; }
  .art-container { width: 100% !important; margin: 8px 0 !important; background: #0d0c0a !important; border-radius: 6px !important; border: 1px solid #262421 !important; overflow: hidden !important; text-align: center !important; }
  #game-portrait-canvas { width: 100% !important; height: 60px !important; display: block !important; }
  .art-caption { font-size: 10px !important; color: #8a857c !important; padding: 3px 0 !important; background: #161512 !important; border-top: 1px solid #262421 !important; text-transform: uppercase !important; }
  .hud-legend { display: flex !important; justify-content: space-between !important; align-items: center !important; background-color: #11100e !important; padding: 6px 8px !important; border-radius: 4px !important; margin-top: 6px !important; font-size: 11px !important; color: #9e9991 !important; border: 1px solid #262421 !important; }
  .legend-item { display: flex !important; align-items: center !important; gap: 4px !important; }
  .legend-dot { width: 8px !important; height: 8px !important; border-radius: 50% !important; }
  .legend-dot.good { background-color: #629924 !important; }
  .legend-dot.key { background-color: #e6b41e !important; }
  .legend-dot.danger { background-color: #d23c3c !important; }
  #chess-coaching-hud .advice { font-size: 12px !important; color: #9e9991 !important; margin-top: 6px !important; border-top: 1px dashed #262421 !important; padding-top: 6px !important; }
`;
document.head.appendChild(styleTag);

// --- 2. GLOBAL STATE & CHARTS ---
let evalChart = null;
let evalHistory = [0.2];
let moveLabels = ['Start'];

let artCanvas, artCtx;
let gameMood = { 
    targetAdvantage: 0.2, currentAdvantage: 0.2, 
    targetTension: 0.2, currentTension: 0.2, 
    speed: 1.0 
};
let globalAngle = 0;

function initGamePortrait() {
    artCanvas = document.getElementById('game-portrait-canvas');
    if (!artCanvas) return;
    artCanvas.width = 266;
    artCanvas.height = 60;
    artCtx = artCanvas.getContext('2d');
    renderGamePortrait(0);
}

function renderGamePortrait(time) {
    if (!artCtx) return;
    const w = artCanvas.width;
    const h = artCanvas.height;
    
    gameMood.currentAdvantage += (gameMood.targetAdvantage - gameMood.currentAdvantage) * 0.05;
    gameMood.currentTension += (gameMood.targetTension - gameMood.currentTension) * 0.03;

    artCtx.fillStyle = '#0d0c0a';
    artCtx.fillRect(0, 0, w, h);

    const tension = gameMood.currentTension;
    const advantage = gameMood.currentAdvantage;
    globalAngle += (0.005 + (tension * 0.02)) * gameMood.speed;

    let baseHue = 100 + (advantage * 20);
    if (advantage < 0) baseHue = 0 + (advantage * 10);

    const cols = 12;
    const rows = 3;
    const cellW = w / cols;
    const cellH = h / rows;

    for (let x = 0; x < cols; x++) {
        for (let y = 0; y < rows; y++) {
            const posX = x * cellW + cellW / 2;
            const posY = y * cellH + cellH / 2;
            const wave = Math.sin(x * 0.5 + y * 0.5 + time * 0.003) * (tension * 6);
            
            artCtx.save();
            artCtx.translate(posX + wave, posY);
            artCtx.rotate(globalAngle + (x * 0.2));

            let hue = baseHue + ((x + y) * 4);
            let lightness = 35 + (tension * 20);
            
            artCtx.fillStyle = `hsla(${hue}, 65%, ${lightness}%, 0.75)`;
            artCtx.strokeStyle = `hsla(${hue}, 80%, 25%, 0.9)`;
            artCtx.lineWidth = 1;

            artCtx.beginPath();
            const size = (cellW * 0.55) + (tension * 3 * Math.sin(time * 0.005 + x));
            artCtx.moveTo(0, -size);
            artCtx.lineTo(size * 0.8, size * 0.7);
            artCtx.lineTo(-size * 0.8, size * 0.7);
            artCtx.closePath();
            
            artCtx.fill();
            artCtx.stroke();
            artCtx.restore();
        }
    }
    requestAnimationFrame(renderGamePortrait);
}

function initEvalChart() {
    const ctx = document.getElementById('eval-chart-canvas');
    if (!ctx || typeof Chart === 'undefined') return;

    evalChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: moveLabels,
            datasets: [{
                label: 'Eval',
                data: evalHistory,
                borderColor: '#629924',
                backgroundColor: 'rgba(98, 153, 36, 0.15)',
                borderWidth: 2,
                tension: 0.3,
                fill: true,
                pointRadius: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: { min: -5, max: 5, grid: { color: '#262421' }, ticks: { color: '#9e9991', font: { size: 9 } } }
            }
        }
    });
}

// --- 3. HUD INJECTION & DRAG SYSTEM ---
function injectHUD() {
    if (document.getElementById('chess-coaching-hud')) return;

    const hud = document.createElement('div');
    hud.id = 'chess-coaching-hud';
    hud.innerHTML = `
        <div class="hud-header" id="hud-drag-handle">
            <span>Team Coach HUD</span>
            <span class="status-dot active">●</span>
        </div>
        <div class="hud-body">
            <div class="stat-row">
                <span class="label">Eval:</span>
                <span id="hud-eval" class="value eval-pos">+0.20</span>
            </div>
            <div class="stat-row">
                <span class="label">Recommended:</span>
                <span id="hud-move" class="value move-highlight">e4</span>
            </div>
            <div class="stat-row">
                <span class="label">Expected Time:</span>
                <span id="hud-exp-time" class="value time-highlight">--:--</span>
            </div>
            <div class="stat-row">
                <span class="label">Blunder Risk:</span>
                <span id="hud-blunder-risk" class="value risk-safe">--</span>
            </div>

            <div class="chart-container">
                <canvas id="eval-chart-canvas"></canvas>
            </div>

            <div class="space-control-container">
                <div class="space-header">
                    <span>Space Control (W: <span id="space-white-val">50%</span>)</span>
                    <span>(B: <span id="space-black-val">50%</span>)</span>
                </div>
                <div class="space-bar-wrapper">
                    <div id="space-white-bar" class="space-bar-white" style="width: 50%;"></div>
                    <div id="space-black-bar" class="space-bar-black" style="width: 50%;"></div>
                </div>
                <div class="space-sectors">
                    <div class="sector-box">Q-Side<span id="sector-q">Equal</span></div>
                    <div class="sector-box">Center<span id="sector-c">Equal</span></div>
                    <div class="sector-box">K-Side<span id="sector-k">Equal</span></div>
                </div>
            </div>

            <div class="art-container">
                <canvas id="game-portrait-canvas"></canvas>
                <div class="art-caption">Game Portrait: <span id="art-mood">Structured Flow</span></div>
            </div>

            <div class="hud-legend">
                <div class="legend-item"><span class="legend-dot good"></span><span>Advantage</span></div>
                <div class="legend-item"><span class="legend-dot key"></span><span>Key Square</span></div>
                <div class="legend-item"><span class="legend-dot danger"></span><span>Threat</span></div>
            </div>

            <div class="stat-row advice">
                <p id="hud-advice">Waiting for live backend connection...</p>
            </div>
        </div>
    `;

    document.body.appendChild(hud);
    
    setTimeout(() => {
        initEvalChart();
        initGamePortrait();
    }, 100);

    // Pointer Capture Drag & Drop
    const header = document.getElementById('hud-drag-handle');
    let startX, startY, initialLeft, initialTop;

    header.addEventListener('pointerdown', (e) => {
        startX = e.clientX;
        startY = e.clientY;

        const rect = hud.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;

        hud.style.left = initialLeft + 'px';
        hud.style.top = initialTop + 'px';
        hud.style.right = 'auto';
        hud.style.bottom = 'auto';

        header.setPointerCapture(e.pointerId);
        e.stopPropagation();
    });

    header.addEventListener('pointermove', (e) => {
        if (!header.hasPointerCapture(e.pointerId)) return;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        hud.style.left = (initialLeft + dx) + 'px';
        hud.style.top = (initialTop + dy) + 'px';
        e.stopPropagation();
    });

    header.addEventListener('pointerup', (e) => {
        if (header.hasPointerCapture(e.pointerId)) {
            header.releasePointerCapture(e.pointerId);
        }
        e.stopPropagation();
    });
}

// --- 4. PYTHON BACKEND API INTEGRATION CLIENT ---
const BACKEND_URL = "http://127.0.0.1:8000/predict"; // Points to your team's FastAPI server

async function sendPredictionRequest(gameSpeed, gameFeatures, gameId) {
    try {
        const payload = {
            speed: gameSpeed, // "bullet", "blitz", or "classical"
            game_id: gameId,
            features: gameFeatures 
        };

        const response = await fetch(BACKEND_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error(`Server error: ${response.status}`);

        const data = await response.json();
        
        // Update Behavioral Metrics from Python backend response
        updateBehavioralMetrics(
            data.predictions.time_spent_s,
            data.predictions.p_blunder * 100 // Convert probability to percentage
        );

    } catch (err) {
        console.warn("Could not reach Python prediction server yet:", err);
    }
}

function updateBehavioralMetrics(expSeconds, blunderRiskPct) {
    const timeElem = document.getElementById('hud-exp-time');
    const riskElem = document.getElementById('hud-blunder-risk');
    
    if (timeElem && expSeconds !== undefined) {
        timeElem.innerText = `${expSeconds.toFixed(1)}s`;
        timeElem.className = expSeconds > 30 ? "value time-deliberate" : "value time-quick";
    }

    if (riskElem && blunderRiskPct !== undefined) {
        riskElem.innerText = `${blunderRiskPct.toFixed(0)}%`;
        if (blunderRiskPct > 25) {
            riskElem.className = "value risk-danger";
        } else if (blunderRiskPct > 10) {
            riskElem.className = "value risk-caution";
        } else {
            riskElem.className = "value risk-safe";
        }
    }
}

// Initialize HUD on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectHUD);
} else {
    injectHUD();
}