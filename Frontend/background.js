/**
 * Service worker proxies API calls so HTTPS pages (chess.com / Lichess) are not
 * blocked by mixed-content rules when talking to a local HTTP FastAPI server.
 *
 * Identity: a persistent clientId is minted once and injected into every
 * /predict/live body so the server can isolate ledgers across extensions.
 *
 * API base: chrome.storage.local.backendBase (default http://127.0.0.1:8000).
 * Override from the service-worker console, e.g.:
 *   chrome.storage.local.set({ backendBase: "http://10.0.0.5:8000" })
 */
const DEFAULT_BACKEND_BASE = "http://10.21.244.196:8000";
const PROXY_VERSION = "1.4.0";

function uuid() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

async function ensureIdentity() {
  const stored = await chrome.storage.local.get(["clientId", "backendBase"]);
  const patch = {};
  if (!stored.clientId || typeof stored.clientId !== "string") {
    patch.clientId = uuid();
  }
  if (!stored.backendBase || typeof stored.backendBase !== "string") {
    patch.backendBase = DEFAULT_BACKEND_BASE;
  }
  if (Object.keys(patch).length) {
    await chrome.storage.local.set(patch);
  }
  const next = await chrome.storage.local.get(["clientId", "backendBase"]);
  return {
    clientId: next.clientId,
    backendBase: (next.backendBase || DEFAULT_BACKEND_BASE).replace(/\/$/, ""),
  };
}

chrome.runtime.onInstalled.addListener(() => {
  ensureIdentity().then(({ clientId, backendBase }) => {
    console.log(
      `[OxTera background ${PROXY_VERSION}] installed; API=${backendBase} clientId=${clientId}`
    );
  });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "predictLive") {
    if (message && message.type === "ping") {
      ensureIdentity()
        .then(({ clientId, backendBase }) => {
          sendResponse({
            ok: true,
            version: PROXY_VERSION,
            backend: backendBase,
            clientId,
          });
        })
        .catch((err) => {
          sendResponse({ ok: false, error: String(err) });
        });
      return true;
    }
    return false;
  }

  ensureIdentity()
    .then(({ clientId, backendBase }) => {
      const url = `${backendBase}/predict/live`;
      const payload = Object.assign({}, message.payload || {}, { client_id: clientId });
      console.log(`[OxTera background ${PROXY_VERSION}] POST`, url, `client=${clientId}`);

      return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then(async (res) => {
        const text = await res.text();
        let data = null;
        try {
          data = text ? JSON.parse(text) : null;
        } catch {
          data = { detail: text };
        }
        if (!res.ok) {
          sendResponse({
            ok: false,
            status: res.status,
            error: typeof data?.detail === "string" ? data.detail : text || `HTTP ${res.status}`,
            proxyVersion: PROXY_VERSION,
            clientId,
          });
          return;
        }
        sendResponse({ ok: true, data, proxyVersion: PROXY_VERSION, clientId });
      });
    })
    .catch((err) => {
      sendResponse({
        ok: false,
        status: 0,
        error: String(err && err.message ? err.message : err),
        proxyVersion: PROXY_VERSION,
      });
    });

  return true; // async sendResponse
});
