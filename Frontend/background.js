/**
 * Service worker proxies API calls so HTTPS pages (chess.com / Lichess) are not
 * blocked by mixed-content rules when talking to a local HTTP FastAPI server.
 *
 * IMPORTANT: change BACKEND_BASE here only — never fetch from content scripts.
 */
const BACKEND_BASE = "http://127.0.0.1:8000";
const PROXY_VERSION = "1.3.2";

chrome.runtime.onInstalled.addListener(() => {
  console.log(`[OxTera background ${PROXY_VERSION}] installed; API=${BACKEND_BASE}`);
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "predictLive") {
    if (message && message.type === "ping") {
      sendResponse({ ok: true, version: PROXY_VERSION, backend: BACKEND_BASE });
      return false;
    }
    return false;
  }

  const url = `${BACKEND_BASE}/predict/live`;
  console.log(`[OxTera background ${PROXY_VERSION}] POST`, url);

  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(message.payload || {}),
  })
    .then(async (res) => {
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
        });
        return;
      }
      sendResponse({ ok: true, data, proxyVersion: PROXY_VERSION });
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
