/*
 * Krishi AI floating voice assistant (Bolna).
 *
 * Primary action: "Call me". The visitor enters a mobile number and our server
 * (POST /api/bolna-call) asks Bolna to phone them with the agent.
 * Secondary action: talk in the browser with the Bolna Web Call SDK, using a
 * session minted by POST /api/bolna-session.
 *
 * Injected by modules/voice_assistant.py. The UI lives in a Shadow DOM attached
 * to the page body, so it survives Streamlit reruns and its CSS cannot clash
 * with the app's. The Bolna API key never reaches the browser.
 */
(function () {
  "use strict";
  var cfg = window.__kiVoiceConfig || {};
  if (window.__kiVoice) { window.__kiVoice.updateConfig(cfg); return; }

  var ICONS = {
    phone: '<path d="M13 2a9 9 0 0 1 9 9"/><path d="M13 6a5 5 0 0 1 5 5"/><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    hangup: '<path d="M10.1 13.9a14 14 0 0 0 3.732 2.668 1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2 18 18 0 0 1-12.728-5.272"/><path d="M22 2 2 22"/><path d="M4.76 13.582A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 .244.473"/>',
    mic: '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/>',
    micOff: '<line x1="2" x2="22" y1="2" y2="22"/><path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2"/><path d="M5 10v2a7 7 0 0 0 12 5"/><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12"/><line x1="12" x2="12" y1="19" y2="22"/>',
    close: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    check: '<path d="M20 6 9 17l-5-5"/>'
  };
  function svg(name, size) {
    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[name] + '</svg>';
  }

  var MESSAGES = {
    microphone_denied: "Microphone access is blocked. Allow it from the icon in your browser's address bar, then try again.",
    at_capacity: "All our assistants are busy right now. Please try again in a minute.",
    rate_limited: "You've requested several calls in a short time. Please wait a few minutes.",
    not_configured: "The voice assistant isn't set up yet. Please try again later.",
    invalid_token: "This page has been open a while. Reload it and try again.",
    connect_failed: "We couldn't connect. Check your internet connection and try again.",
    call_rejected: "The assistant couldn't take the call. Please try again.",
    autoplay_blocked: "Your browser blocked the call audio. Tap the call button once more.",
    sdk_unavailable: "The voice service couldn't load. Check your connection or ad blocker, then try again.",
    no_microphone: "No microphone was found. Connect one and try again.",
    insecure: "Browser calls need a secure (https) page.",
    invalid_number: "Enter a valid mobile number, for example +91 98765 43210.",
    country_not_allowed: "We can only call Indian (+91) mobile numbers.",
    line_activating: "Our calling line is still being activated. Please try again in a few minutes.",
    network: "We couldn't reach our server. Check your connection and try again.",
    default: "We couldn't place the call. Please try again."
  };

  var CSS = [
    ':host { all: initial; }',
    '*, *::before, *::after { box-sizing: border-box; }',
    '[hidden] { display: none !important; }',
    '.kvc { position: fixed; right: calc(24px + env(safe-area-inset-right, 0px)); bottom: calc(24px + env(safe-area-inset-bottom, 0px));',
    '  z-index: 2147483000; display: flex; flex-direction: column; align-items: flex-end; gap: 12px;',
    '  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; color: #202720;',
    '  -webkit-font-smoothing: antialiased; pointer-events: none; }',
    '.kvc > * { pointer-events: auto; }',
    '.row { position: relative; display: flex; align-items: center; justify-content: flex-end; gap: 10px; }',
    '.fab { position: relative; width: 56px; height: 56px; border-radius: 50%; border: 0; padding: 0; cursor: pointer;',
    '  display: grid; place-items: center; color: #fff; background: #26734D;',
    '  box-shadow: 0 1px 2px rgba(20,45,34,.12), 0 10px 28px -10px rgba(20,45,34,.55);',
    '  transition: background-color .2s ease, transform .2s cubic-bezier(.2,.7,.2,1), box-shadow .2s ease; -webkit-tap-highlight-color: transparent; }',
    '.fab:hover { background: #1F5F40; transform: translateY(-2px); box-shadow: 0 2px 4px rgba(20,45,34,.12), 0 16px 32px -12px rgba(20,45,34,.6); }',
    '.fab:active { transform: scale(.96); }',
    '.fab:focus-visible { outline: none; box-shadow: 0 0 0 3px #fff, 0 0 0 5px #26734D; }',
    '.fab .ic { position: relative; z-index: 1; display: grid; place-items: center; }',
    '.fab .ic svg { width: 24px; height: 24px; }',
    '.fab .ring { position: absolute; inset: 0; border-radius: 50%; pointer-events: none; }',
    '.kvc[data-state="active"] .fab { background: #C65B52; }',
    '.kvc[data-state="active"] .fab:hover { background: #B04C44; }',
    '.kvc[data-state="active"] .fab:focus-visible { box-shadow: 0 0 0 3px #fff, 0 0 0 5px #C65B52; }',
    '.kvc[data-state="active"] .fab .ring { border: 2px solid rgba(198,91,82,.55); transform: scale(calc(1 + var(--lvl, 0) * .35)); transition: transform .12s linear; }',
    '.kvc[data-state="active"] .fab::after { content: ""; position: absolute; inset: 0; border-radius: 50%; border: 2px solid rgba(198,91,82,.5); animation: kvc-pulse 1.8s ease-out infinite; }',
    '.kvc[data-state="queued"] .fab::after { content: ""; position: absolute; inset: 0; border-radius: 50%; border: 2px solid rgba(38,115,77,.5); animation: kvc-pulse 1.8s ease-out infinite; }',
    '.kvc[data-state="connecting"] .fab, .kvc[data-state="ringing"] .fab, .kvc[data-state="dialing"] .fab { background: #1F5F40; }',
    '.kvc[data-state="connecting"] .fab .ring, .kvc[data-state="ringing"] .fab .ring, .kvc[data-state="dialing"] .fab .ring { border: 2px solid rgba(255,255,255,.35); border-top-color: #fff; animation: kvc-spin .9s linear infinite; inset: 5px; }',
    '@keyframes kvc-pulse { from { transform: scale(1); opacity: .9; } to { transform: scale(1.6); opacity: 0; } }',
    '@keyframes kvc-spin { to { transform: rotate(360deg); } }',
    '.tip { background: #142D22; color: #fff; font-size: 13px; font-weight: 500; line-height: 1; padding: 9px 12px; border-radius: 8px; white-space: nowrap;',
    '  box-shadow: 0 8px 20px -10px rgba(20,45,34,.5); opacity: 0; transform: translateX(6px); transition: opacity .2s ease, transform .2s ease; pointer-events: none; }',
    '.kvc[data-state="idle"] .row:hover .tip, .kvc[data-state="idle"] .row:focus-within .tip, .kvc.show-tip[data-state="idle"] .tip { opacity: 1; transform: none; }',
    '.panel { width: min(320px, calc(100vw - 32px)); background: #fff; border: 1px solid #E6E9E3; border-radius: 14px; padding: 16px;',
    '  box-shadow: 0 2px 6px rgba(20,45,34,.06), 0 18px 40px -18px rgba(20,45,34,.35); display: none;',
    '  animation: kvc-in .22s cubic-bezier(.2,.7,.2,1); }',
    '.kvc:not([data-state="idle"]) .panel { display: block; }',
    '@keyframes kvc-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }',
    '.head { display: flex; align-items: center; gap: 8px; }',
    '.dot { width: 8px; height: 8px; border-radius: 50%; background: #A8C3AD; flex: 0 0 8px; }',
    '.kvc[data-state="active"] .dot, .kvc[data-state="queued"] .dot { background: #26734D; animation: kvc-dot 1.6s ease-out infinite; }',
    '.kvc[data-state="error"] .dot { background: #C65B52; }',
    '.kvc[data-state="connecting"] .dot, .kvc[data-state="ringing"] .dot, .kvc[data-state="dialing"] .dot { background: #D69A32; }',
    '@keyframes kvc-dot { 0% { box-shadow: 0 0 0 0 rgba(38,115,77,.5); } 100% { box-shadow: 0 0 0 8px rgba(38,115,77,0); } }',
    '.title { font-size: 14px; font-weight: 600; letter-spacing: -.01em; flex: 1; }',
    '.time { font-size: 13px; color: #777F78; font-variant-numeric: tabular-nums; }',
    '.x { border: 0; background: transparent; color: #777F78; width: 28px; height: 28px; border-radius: 6px; display: grid; place-items: center; cursor: pointer; margin: -4px -6px -4px 0; }',
    '.x:hover { background: #F5F5F0; color: #202720; }',
    '.x:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(38,115,77,.25); }',
    '.x svg { width: 16px; height: 16px; }',
    '.msg { font-size: 13px; line-height: 1.45; color: #777F78; margin: 6px 0 0 16px; }',
    '.form { margin-top: 14px; }',
    '.label { display: block; font-size: 12px; font-weight: 500; color: #777F78; margin-bottom: 6px; }',
    '.input { width: 100%; height: 42px; border-radius: 8px; border: 1px solid #E6E9E3; background: #F7F7F2; padding: 0 12px;',
    '  font: inherit; font-size: 15px; color: #202720; font-variant-numeric: tabular-nums; transition: border-color .15s ease, box-shadow .15s ease; }',
    '.input:focus { outline: none; border-color: #26734D; box-shadow: 0 0 0 3px rgba(38,115,77,.15); background: #fff; }',
    '.input[aria-invalid="true"] { border-color: #C65B52; }',
    '.field-err { font-size: 12px; color: #C65B52; margin-top: 6px; min-height: 0; }',
    '.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }',
    '.btn { flex: 1 1 auto; height: 38px; border-radius: 8px; border: 1px solid #E6E9E3; background: #fff; color: #202720; font: inherit; font-size: 13px; font-weight: 500;',
    '  display: inline-flex; align-items: center; justify-content: center; gap: 6px; cursor: pointer; padding: 0 12px; transition: background-color .15s ease, border-color .15s ease; }',
    '.btn:hover { background: #F8F9F5; border-color: #D6DBD3; }',
    '.btn:focus-visible { outline: none; box-shadow: 0 0 0 3px rgba(38,115,77,.25); }',
    '.btn:disabled { opacity: .6; cursor: default; }',
    '.btn svg { width: 16px; height: 16px; }',
    '.btn.primary { background: #26734D; border-color: #26734D; color: #fff; }',
    '.btn.primary:hover { background: #1F5F40; border-color: #1F5F40; }',
    '.btn.end { background: #C65B52; border-color: #C65B52; color: #fff; }',
    '.btn.end:hover { background: #B04C44; border-color: #B04C44; }',
    '.btn.mute[aria-pressed="true"] { background: #F5F5F0; }',
    '.link { display: block; width: 100%; margin-top: 10px; border: 0; background: none; padding: 4px; font: inherit; font-size: 12px;',
    '  color: #26734D; cursor: pointer; text-align: center; text-decoration: underline; text-underline-offset: 2px; }',
    '.link:hover { color: #1F5F40; }',
    '.link:focus-visible { outline: none; border-radius: 4px; box-shadow: 0 0 0 3px rgba(38,115,77,.25); }',
    '.fine { font-size: 11px; color: #8A918B; margin-top: 10px; line-height: 1.4; }',
    '.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }',
    '@media (max-width: 640px) {',
    '  .kvc { right: calc(16px + env(safe-area-inset-right, 0px)); bottom: calc(16px + env(safe-area-inset-bottom, 0px)); }',
    '  .fab { width: 52px; height: 52px; }',
    '  .tip { display: none; }',
    '}',
    '@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }'
  ].join("\n");

  var host = document.createElement("div");
  host.id = "krishi-voice-assistant";
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });
  root.innerHTML =
    '<style>' + CSS + '</style>' +
    '<div class="kvc" data-state="idle">' +
    '  <div class="panel" role="dialog" aria-label="Call our AI assistant">' +
    '    <div class="head"><span class="dot"></span><span class="title"></span><span class="time"></span>' +
    '      <button class="x" type="button" aria-label="Close">' + svg("close", 16) + '</button></div>' +
    '    <div class="msg"></div>' +
    '    <form class="form" novalidate>' +
    '      <label class="label" for="kvc-phone">Your mobile number</label>' +
    '      <input class="input" id="kvc-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="+91 98765 43210" maxlength="20">' +
    '      <div class="field-err" role="alert"></div>' +
    '      <div class="actions"><button class="btn primary callme" type="submit">' + svg("phone", 16) + '<span>Call me</span></button></div>' +
    '      <button class="link webcall" type="button">Talk in the browser instead</button>' +
    '      <div class="fine">Our AI assistant will call this number now. Standard call rates may apply.</div>' +
    '    </form>' +
    '    <div class="actions live-actions">' +
    '      <button class="btn mute" type="button" aria-pressed="false">' + svg("mic", 16) + '<span>Mute</span></button>' +
    '      <button class="btn primary retry" type="button">' + svg("phone", 16) + '<span>Try again</span></button>' +
    '      <button class="btn end" type="button">' + svg("hangup", 16) + '<span>End call</span></button>' +
    '    </div>' +
    '  </div>' +
    '  <div class="row">' +
    '    <span class="tip" aria-hidden="true">Talk to us</span>' +
    '    <button class="fab" type="button" aria-label="Talk to our AI assistant" aria-haspopup="dialog"><span class="ring"></span><span class="ic">' + svg("phone", 24) + '</span></button>' +
    '  </div>' +
    '  <div class="sr" aria-live="polite"></div>' +
    '</div>';

  var $ = function (sel) { return root.querySelector(sel); };
  var el = {
    kvc: $(".kvc"), fab: $(".fab"), icon: $(".fab .ic"), title: $(".title"), time: $(".time"), msg: $(".msg"),
    form: $(".form"), phone: $(".input"), fieldErr: $(".field-err"), callme: $(".callme"), webcall: $(".webcall"),
    liveActions: $(".live-actions"), mute: $(".mute"), end: $(".end"), retry: $(".retry"), close: $(".x"), live: $(".sr")
  };

  var call = null, uiState = "idle", timerId = null, startedAt = 0, resetId = null, attempt = 0, errorShown = false;
  var lastMode = "phone";  // which flow "Try again" repeats

  function announce(text) { el.live.textContent = ""; setTimeout(function () { el.live.textContent = text; }, 30); }

  function remembered() { try { return window.localStorage.getItem("kvc-phone") || ""; } catch (_) { return ""; } }
  function remember(v) { try { window.localStorage.setItem("kvc-phone", v); } catch (_) { /* storage unavailable */ } }

  function setUi(state, opts) {
    opts = opts || {};
    uiState = state;
    el.kvc.setAttribute("data-state", state);
    clearTimeout(resetId);
    var name = cfg.assistantName || "AI assistant";
    var webBusy = state === "connecting" || state === "ringing";
    el.form.hidden = state !== "form";
    el.liveActions.hidden = !(state === "active" || webBusy || state === "error");
    el.mute.hidden = state !== "active";
    el.end.hidden = !(state === "active" || webBusy);
    el.end.querySelector("span").textContent = webBusy ? "Cancel" : "End call";
    el.retry.hidden = state !== "error";
    el.close.hidden = state === "active" || webBusy || state === "dialing";
    if (state !== "active") { stopTimer(); el.time.textContent = ""; el.kvc.style.removeProperty("--lvl"); }
    el.icon.innerHTML = svg(state === "active" ? "hangup" : "phone", 24);
    el.fab.setAttribute("aria-label",
      state === "active" ? "End call" : (webBusy ? "Cancel call" : (state === "idle" ? "Talk to our AI assistant" : "Close")));

    if (state === "form") {
      el.title.textContent = "Get a call from our assistant";
      el.msg.textContent = "Enter your mobile number and the " + name + " will ring you right away.";
      el.fieldErr.textContent = opts.fieldError || "";
      el.phone.setAttribute("aria-invalid", opts.fieldError ? "true" : "false");
      el.callme.disabled = false;
      if (!el.phone.value) el.phone.value = remembered();
      setTimeout(function () { el.phone.focus(); }, 30);
      loadSdk().catch(function () {});  // warm the browser-call SDK in case they pick that option
    } else if (state === "dialing") {
      el.title.textContent = "Requesting your call…";
      el.msg.textContent = "One moment.";
    } else if (state === "queued") {
      el.title.textContent = "Calling you now";
      el.msg.textContent = "Your phone (" + (opts.phone || "your number") + ") will ring in a few seconds. Answer it to talk to the " + name + ".";
      announce("Calling you now.");
      resetId = setTimeout(function () { setUi("idle"); }, 20000);
    } else if (webBusy) {
      el.title.textContent = state === "ringing" ? "Ringing…" : "Connecting…";
      el.msg.textContent = state === "ringing" ? "Connecting you to the " + name + "." : "Allow microphone access if your browser asks.";
    } else if (state === "active") {
      el.title.textContent = "Live with " + name;
      el.msg.textContent = "Speak naturally. Ask about prices, buyers or your farm.";
      startTimer();
      announce("Call connected.");
    } else if (state === "ended") {
      el.title.textContent = "Call ended";
      el.msg.textContent = opts.message || "Thanks for calling.";
      announce("Call ended.");
      resetId = setTimeout(function () { setUi("idle"); }, 3500);
    } else if (state === "error") {
      el.title.textContent = lastMode === "phone" ? "Couldn't place the call" : "Couldn't start the call";
      el.msg.textContent = opts.message || MESSAGES.default;
      announce(el.msg.textContent);
    }
  }

  function startTimer() {
    stopTimer();
    startedAt = Date.now();
    var tick = function () {
      var s = Math.floor((Date.now() - startedAt) / 1000);
      el.time.textContent = String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
    };
    tick();
    timerId = setInterval(tick, 1000);
  }
  function stopTimer() { if (timerId) { clearInterval(timerId); timerId = null; } }

  // GET with custom headers: works behind Streamlit Community Cloud's proxy (which drops
  // POSTs to custom routes), keeps the phone number out of URLs, and custom headers
  // cannot be sent cross-site without a CORS preflight we never allow.
  function postJson(url, body) {
    var headers = {};
    headers[cfg.tokenHeader || "x-krishi-voice-token"] = cfg.token || "";
    if (body && body.phone) headers[cfg.phoneHeader || "x-krishi-phone"] = body.phone;
    return fetch(url, { method: "GET", headers: headers, credentials: "same-origin", cache: "no-store" })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (data) {
          if (!r.ok) {
            var err = new Error((data && data.message) || ("Request failed (" + r.status + ")"));
            err.code = (data && data.error) || (r.status === 429 ? "at_capacity" : "default");
            err.status = r.status;
            throw err;
          }
          return data;
        });
      });
  }

  // ---- "Call me": the agent phones the visitor ----
  function looksLikePhone(v) { return /^\+?[\d\s\-().]{8,20}$/.test(v) && v.replace(/\D/g, "").length >= 10; }

  function requestPhoneCall(ev) {
    if (ev) ev.preventDefault();
    lastMode = "phone";
    var value = (el.phone.value || "").trim();
    if (!looksLikePhone(value)) { setUi("form", { fieldError: MESSAGES.invalid_number }); return; }
    remember(value);
    setUi("dialing");
    postJson(cfg.callUrl, { phone: value }).then(function (data) {
      setUi("queued", { phone: data.phone });
    }).catch(function (e) {
      var code = e && e.code;
      if (code === "invalid_number" || code === "country_not_allowed") { setUi("form", { fieldError: MESSAGES[code] }); return; }
      if (!e || !e.status) { setUi("error", { message: MESSAGES.network }); return; }
      if (window.console && /upstream|agent|from_number|bad_request/.test(code || "")) console.warn("[krishi-voice] call error:", code, e.message);
      setUi("error", { message: MESSAGES[code] || MESSAGES.default });
    });
  }

  // ---- Talk in the browser: Bolna Web Call SDK (pinned build, integrity-checked) ----
  var sdkPromise = null;
  function loadSdk() {
    if (window.BolnaWebCall) return Promise.resolve(window.BolnaWebCall);
    if (sdkPromise) return sdkPromise;
    sdkPromise = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = cfg.sdkUrl;
      if (cfg.sdkIntegrity) { s.integrity = cfg.sdkIntegrity; s.crossOrigin = "anonymous"; }
      s.async = true;
      s.onload = function () { window.BolnaWebCall ? resolve(window.BolnaWebCall) : reject(new Error("sdk_unavailable")); };
      s.onerror = function () { sdkPromise = null; reject(new Error("sdk_unavailable")); };
      document.head.appendChild(s);
    });
    return sdkPromise;
  }

  function errorCode(e) {
    if (!e) return "default";
    if (e.cause && e.cause.code) return e.cause.code;  // our server's code, wrapped by the SDK
    if (e.code) return e.code;
    if (e.message === "sdk_unavailable") return "sdk_unavailable";
    return "default";
  }

  function fail(e, myAttempt) {
    if (myAttempt !== attempt || errorShown) return;
    var code = errorCode(e);
    if (code === "microphone_denied" && e && e.cause && e.cause.name === "NotFoundError") code = "no_microphone";
    if (/upstream|agent_not_found|mint_failed/.test(code)) {
      if (window.console) console.warn("[krishi-voice] session error:", code, (e && e.cause && e.cause.message) || (e && e.message) || "");
      code = "default";
    }
    errorShown = true;
    cleanup();
    setUi("error", { message: MESSAGES[code] || MESSAGES.default });
  }

  function cleanup() {
    var c = call;
    call = null;
    if (c) { try { c.stop(); } catch (_) { /* already ended */ } }
  }

  function startWebCall() {
    lastMode = "web";
    if (!window.isSecureContext || !navigator.mediaDevices) { setUi("error", { message: MESSAGES.insecure }); return; }
    attempt += 1;
    var myAttempt = attempt;
    errorShown = false;
    setUi("connecting");
    loadSdk().then(function (SDK) {
      if (myAttempt !== attempt) return;
      var c = new SDK({ getSession: function () { return postJson(cfg.sessionUrl, {}); } });
      call = c;
      c.on("state-change", function (s) { if (myAttempt === attempt && (s === "connecting" || s === "ringing")) setUi(s); });
      c.on("call-start", function () { if (myAttempt === attempt) setUi("active"); });
      c.on("volume-level", function (v) { el.kvc.style.setProperty("--lvl", String(Math.min(1, Math.max(0, v)))); });
      c.on("error", function (e) { fail(e, myAttempt); });
      c.on("call-end", function (p) {
        if (myAttempt !== attempt) return;
        var reason = p && p.reason;
        if (reason === "failed") { fail({ code: "connect_failed" }, myAttempt); return; }
        call = null;
        setUi("ended", { message: reason === "remote-hangup" ? "The assistant ended the call." : "Thanks for calling." });
      });
      return c.start();
    }).catch(function (e) { fail(e, myAttempt); });
  }

  function endWebCall() {
    attempt += 1;  // ignore late events from the ending call
    var wasBusy = uiState === "connecting" || uiState === "ringing";
    cleanup();
    setUi("ended", { message: wasBusy ? "Call cancelled." : "Thanks for calling." });
  }

  // ---- Wiring ----
  el.fab.addEventListener("click", function () {
    if (uiState === "active" || uiState === "connecting" || uiState === "ringing") { endWebCall(); return; }
    if (uiState === "dialing") return;
    if (uiState === "idle") { setUi("form"); } else { setUi("idle"); }
  });
  el.form.addEventListener("submit", requestPhoneCall);
  el.phone.addEventListener("input", function () {
    if (el.fieldErr.textContent) { el.fieldErr.textContent = ""; el.phone.setAttribute("aria-invalid", "false"); }
  });
  el.webcall.addEventListener("click", startWebCall);
  el.end.addEventListener("click", endWebCall);
  el.retry.addEventListener("click", function () { if (lastMode === "web") { startWebCall(); } else { setUi("form"); } });
  el.close.addEventListener("click", function () { setUi("idle"); el.fab.focus(); });
  el.mute.addEventListener("click", function () {
    if (!call) return;
    var next = !call.isMuted();
    call.setMuted(next);
    el.mute.setAttribute("aria-pressed", String(next));
    el.mute.innerHTML = svg(next ? "micOff" : "mic", 16) + "<span>" + (next ? "Unmute" : "Mute") + "</span>";
  });
  root.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && (uiState === "form" || uiState === "error" || uiState === "ended" || uiState === "queued")) {
      setUi("idle"); el.fab.focus();
    }
  });
  window.addEventListener("pagehide", cleanup);
  window.addEventListener("beforeunload", cleanup);

  // Show the "Talk to us" label briefly on the first page view of the session.
  try {
    if (!window.sessionStorage.getItem("kvc-tip-shown")) {
      window.sessionStorage.setItem("kvc-tip-shown", "1");
      setTimeout(function () { el.kvc.classList.add("show-tip"); }, 900);
      setTimeout(function () { el.kvc.classList.remove("show-tip"); }, 5200);
    }
  } catch (_) { /* storage unavailable: hover/focus still shows the label */ }

  window.__kiVoice = {
    updateConfig: function (next) { if (next) { cfg = next; } },
    state: function () { return uiState; }
  };
})();
