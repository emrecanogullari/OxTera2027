/**
 * Chess.com games that are not yours.
 * The player reader in chesscom.js still owns your own live seat.
 * Here, White / Black picks which player is scored. The payload shape matches that reader.
 */
(function (root) {
  const Ox = (root.OxTeraCoach = root.OxTeraCoach || {});
  Ox.sites = Ox.sites || {};

  const playing = Ox.sites.chesscom;
  if (!playing || typeof playing.readGameState !== "function") return;

  /** Color the user clicked. Null means the bottom player, same as chesscom.js. */
  let chosen = null;

  function cleanName(text) {
    return String(text || "").replace(/\s+/g, " ").trim();
  }

  function sameName(a, b) {
    return cleanName(a).toLowerCase() === cleanName(b).toLowerCase();
  }

  function usernameIn(el) {
    if (!el) return null;
    const node =
      el.querySelector(
        '[data-test-element="user-tagline-username"], .cc-user-username-component, .user-username-component, a[href*="/member/"]'
      ) || (el.matches && el.matches('a[href*="/member/"]') ? el : null);
    if (!node) return null;
    const href = node.getAttribute ? node.getAttribute("href") || "" : "";
    const slug = href.match(/\/member\/([^/?#]+)/i);
    if (slug) {
      try {
        return decodeURIComponent(slug[1]);
      } catch (_) {
        return slug[1];
      }
    }
    return cleanName(node.textContent) || null;
  }

  function headerUsername() {
    const scopes = [
      ".home-user-info",
      ".sidebar-user",
      ".nav-user-component",
      "[class*='user-menu']",
      ".sidebar-footer",
    ];
    for (const sel of scopes) {
      const name = usernameIn(document.querySelector(sel));
      if (name) return name;
    }
    const sidebar = document.querySelector(".sidebar-container, nav");
    if (!sidebar) return null;
    const nodes = sidebar.querySelectorAll(
      '[data-test-element="user-tagline-username"], .cc-user-username-component, .user-username-component, a[href*="/member/"]'
    );
    for (const node of nodes) {
      if (node.closest && node.closest(".player-component")) continue;
      const name = usernameIn(node.parentElement || node);
      if (name) return name;
    }
    return null;
  }

  function playerNames() {
    const names = [];
    for (const sel of [".player-bottom", ".player-top"]) {
      const name = usernameIn(document.querySelector(sel));
      if (name) names.push(name);
    }
    return names;
  }

  /** True only when the logged-in name is present and is neither player. */
  function isSomeoneElsesGame() {
    const me = headerUsername();
    if (!me) return false;
    const names = playerNames();
    if (names.length < 2) return false;
    return !names.some((name) => sameName(name, me));
  }

  function parseClockText(text) {
    if (!text) return null;
    const t = String(text).trim().replace(/\s+/g, "");
    const parts = t.split(":").map((part) => Number(part));
    if (!parts.length || parts.some((n) => Number.isNaN(n))) return null;
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    return null;
  }

  function parseThink(text) {
    const seconds = String(text || "").trim().match(/^([\d.]+)\s*s$/i);
    if (seconds) return Number(seconds[1]);
    return parseClockText(text);
  }

  function readThinkTimes(movesPlayed, color) {
    const collect = (selector) =>
      [...document.querySelectorAll(selector)]
        .map((el) => ({
          ply: Number(el.getAttribute("data-ply")),
          spent: parseThink(el.textContent),
        }))
        .filter((row) => row.spent != null && !Number.isNaN(row.spent) && row.ply > 0 && row.ply <= movesPlayed);
    const mine = collect(color === "white" ? ".time-white" : ".time-black");
    const theirs = collect(color === "white" ? ".time-black" : ".time-white");
    const out = {};
    if (mine.length) {
      out.prev_self_spent = mine[mine.length - 1].spent;
      out.avg_self_spent = mine.reduce((sum, row) => sum + row.spent, 0) / mine.length;
    }
    if (theirs.length) out.prev_opp_spent = theirs[theirs.length - 1].spent;
    return out;
  }

  function readWatchState() {
    const base = playing.readGameState();
    if (!base) return null;
    const bottom = base.color === "black" ? "black" : "white";
    const tracked = chosen === "white" || chosen === "black" ? chosen : bottom;
    const explicit = chosen === "white" || chosen === "black";
    const gameId = explicit ? `${base.game_id}:${tracked}` : base.game_id;
    if (tracked === bottom) {
      if (!explicit) return base;
      return Ox.buildRawGameState(
        Object.assign({}, base, {
          game_id: gameId,
        })
      );
    }
    const played = base.ply != null ? Number(base.ply) - 1 : 0;
    const spends = readThinkTimes(Math.max(0, played), tracked);
    return Ox.buildRawGameState(
      Object.assign(
        {
          site: base.site,
          game_id: gameId,
          color: tracked,
          base_s: base.base_s,
          inc_s: base.inc_s,
          elo_self: base.elo_opp != null ? base.elo_opp : 1500,
          elo_opp: base.elo_self,
          clock_self_s: base.clock_opp_s,
          clock_opp_s: base.clock_self_s,
          fen: base.fen,
          moves_san: base.moves_san,
          ply: base.ply,
        },
        spends
      )
    );
  }

  function paintButtons(active) {
    const bar = document.getElementById("ox-watch-colors");
    if (!bar) return;
    for (const btn of bar.querySelectorAll("button")) {
      const on = btn.dataset.color === active;
      btn.style.outline = on ? "2px solid #4cd964" : "none";
      btn.style.background = btn.dataset.color === "white" ? "#f4f4f5" : "#1c1c1e";
      btn.style.color = btn.dataset.color === "white" ? "#1c1c1e" : "#f4f4f5";
    }
  }

  function removePicker() {
    const bar = document.getElementById("ox-watch-colors");
    if (bar) bar.remove();
  }

  function showPicker(active) {
    const hud = document.getElementById("chess-coach-hud");
    if (!hud) return;
    let bar = document.getElementById("ox-watch-colors");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "ox-watch-colors";
      bar.style.cssText = "display:flex;gap:8px;margin-top:10px;";
      for (const color of ["white", "black"]) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.dataset.color = color;
        btn.textContent = color === "white" ? "White" : "Black";
        btn.style.cssText =
          "flex:1;cursor:pointer;border:none;border-radius:8px;padding:6px 0;font-weight:600;";
        btn.addEventListener("pointerdown", (event) => {
          event.stopPropagation();
        });
        btn.addEventListener("click", (event) => {
          event.stopPropagation();
          event.preventDefault();
          chosen = color;
          paintButtons(color);
          if (typeof adapter._retick === "function") adapter._retick();
        });
        bar.appendChild(btn);
      }
      hud.appendChild(bar);
    }
    paintButtons(active);
  }

  const adapter = {
    matches(hostname) {
      return playing.matches(hostname);
    },

    readGameState() {
      let watch = false;
      try {
        watch = isSomeoneElsesGame();
      } catch (err) {
        console.error("[OxTera chesscom-watch] could not tell whose game", err);
        removePicker();
        try {
          return playing.readGameState();
        } catch (playerErr) {
          console.error("[OxTera chesscom-watch] player read failed", playerErr);
          return null;
        }
      }
      if (!watch) {
        removePicker();
        return playing.readGameState();
      }
      try {
        const state = readWatchState();
        showPicker(chosen || (state && state.color) || null);
        return state;
      } catch (err) {
        console.error("[OxTera chesscom-watch] watch read failed", err);
        removePicker();
        try {
          return playing.readGameState();
        } catch (playerErr) {
          console.error("[OxTera chesscom-watch] player read failed", playerErr);
          return null;
        }
      }
    },

    onTurnStart(callback) {
      let lastSig = "";
      let pending = null;
      let lastHref = location.href;
      const tick = () => {
        if (location.href !== lastHref) {
          lastHref = location.href;
          lastSig = "";
          chosen = null;
          console.warn("[OxTera chesscom] URL changed →", lastHref);
          if (typeof Ox.setHudStatus === "function") {
            Ox.setHudStatus("navigated — rescanning board…");
          }
        }
        const state = adapter.readGameState();
        if (!state) return;
        const sig = `${state.game_id || ""}|${state.ply}|${state.color}`;
        if (sig === lastSig) return;
        lastSig = sig;
        console.warn("[OxTera chesscom-watch] game state ready", {
          ply: state.ply,
          color: state.color,
          clocks: [state.clock_self_s, state.clock_opp_s],
          tc: `${state.base_s}+${state.inc_s}`,
          href: location.href,
        });
        if (typeof Ox.setHudStatus === "function") Ox.setHudStatus("predicting…");
        try {
          callback(state);
        } catch (err) {
          console.error("[OxTera chesscom-watch] onTurnStart callback failed", err);
        }
      };
      adapter._retick = () => {
        lastSig = "";
        tick();
      };
      const schedule = () => {
        if (pending) clearTimeout(pending);
        pending = setTimeout(tick, 150);
      };
      adapter._timer = setInterval(tick, 500);
      adapter._observer = new MutationObserver(schedule);
      adapter._observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class", "style"],
      });
      window.addEventListener("popstate", schedule);
      setTimeout(tick, 200);
      setTimeout(tick, 1000);
      setTimeout(tick, 2500);
    },

    destroy() {
      if (adapter._timer) clearInterval(adapter._timer);
      if (adapter._observer) adapter._observer.disconnect();
      adapter._timer = null;
      adapter._observer = null;
      adapter._retick = null;
      removePicker();
      if (typeof playing.destroy === "function") playing.destroy();
    },
  };

  Ox.sites.chesscom = adapter;
})(typeof globalThis !== "undefined" ? globalThis : window);
