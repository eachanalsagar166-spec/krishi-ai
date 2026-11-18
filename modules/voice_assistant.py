"""
Bolna AI voice assistant: server-side session minting and the floating call widget.

Server side
    POST /api/bolna-session (mounted by server.py through st.App) exchanges the
    secret BOLNA_API_KEY for a single-use Bolna web-call session and returns
    the session JSON to the browser. The key never leaves the server, is never
    logged and is never echoed back. The route only answers same-origin
    requests that carry a short-lived token signed by this server (issued to
    pages it rendered) and is rate-limited per client, so it cannot be used as
    an open proxy for your Bolna minutes.

Client side
    render_voice_widget() injects static/voice_assistant.js once per page. The
    script builds the floating button inside a Shadow DOM (so site CSS cannot
    leak in or out), loads the pinned Bolna Web Call SDK from jsDelivr with a
    subresource-integrity hash, and drives the call states.

Docs: https://www.bolna.ai/docs/developer-resources/sdks/web-call
"""
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger("krishi.voice")

# --- Bolna configuration -------------------------------------------------------
BOLNA_SESSION_ENDPOINT = os.environ.get("BOLNA_SESSION_ENDPOINT", "https://api.bolna.ai/web-call/session")
DEFAULT_AGENT_ID = "9ae02706-b806-46dc-b146-0efbdd6389d6"
BOLNA_CALL_ENDPOINT = os.environ.get("BOLNA_CALL_ENDPOINT", "https://api.bolna.ai/call")
SESSION_ROUTE = "/api/bolna-session"
CALL_ROUTE = "/api/bolna-call"
WIDGET_SCRIPT_ROUTE = "/api/voice-assistant.js"

# Pinned SDK build + subresource-integrity hash (sha384 of v3.0.1 dist file).
SDK_URL = "https://cdn.jsdelivr.net/gh/bolna-ai/web-call@v3.0.1/dist/bolna-web-call.min.js"
SDK_INTEGRITY = "sha384-eIwZYmjK+HzlUdEuzvTa1rYdY23/D0fy+vJe8XlqhzxXELVUw9bCEhdOfcMQlIvq"

# --- Route guards --------------------------------------------------------------
TOKEN_HEADER = "x-krishi-voice-token"
PHONE_HEADER = "x-krishi-phone"
TOKEN_TTL_SECONDS = 6 * 3600
RATE_LIMIT_CALLS = 5           # session mints allowed ...
RATE_LIMIT_WINDOW = 600        # ... per client per 10 minutes
MAX_BODY_BYTES = 64 * 1024
MAX_USER_DATA_BYTES = 50 * 1024  # Bolna's documented user_data cap
UPSTREAM_TIMEOUT_SECONDS = 12

# Phone callbacks ("call me"): limited to these country codes and rate-limited per visitor and per number
DEFAULT_CALL_COUNTRY_CODES = "+91"
CALL_LIMIT_PER_CLIENT = (3, 900)    # 3 calls per 15 minutes per visitor
CALL_LIMIT_PER_NUMBER = (2, 1800)   # 2 calls per 30 minutes to the same number

# Set by server.py when the route is mounted; the widget is only rendered then.
ROUTE_FLAG_ENV = "KRISHI_VOICE_ROUTE"

_SECRET = (os.environ.get("KRISHI_VOICE_SECRET") or secrets.token_hex(32)).encode("utf-8")
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WIDGET_JS = _PROJECT_ROOT / "static" / "voice_assistant.js"
_SECRETS_FILE = _PROJECT_ROOT / ".streamlit" / "secrets.toml"
_secrets_cache: Dict[str, Any] = {"mtime": None, "values": {}}


def _secrets_file_values() -> Dict[str, Any]:
    """Top-level keys of .streamlit/secrets.toml (git-ignored), re-read when the file changes."""
    try:
        mtime = _SECRETS_FILE.stat().st_mtime
    except OSError:
        return {}
    if _secrets_cache["mtime"] != mtime:
        try:
            try:
                import tomllib  # Python 3.11+
                values = tomllib.loads(_SECRETS_FILE.read_text(encoding="utf-8"))
            except ImportError:
                import toml  # installed with Streamlit
                values = toml.loads(_SECRETS_FILE.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Could not parse .streamlit/secrets.toml")
            values = {}
        _secrets_cache.update(mtime=mtime, values=values if isinstance(values, dict) else {})
    return _secrets_cache["values"]


def get_setting(name: str, default: str = "") -> str:
    """Environment variable, then .streamlit/secrets.toml, then st.secrets (Streamlit Cloud)."""
    value = os.environ.get(name, "").strip()
    if not value:
        raw = _secrets_file_values().get(name)
        value = str(raw).strip() if raw is not None else ""
    if not value:
        try:
            import streamlit as st
            raw = st.secrets.get(name)
            value = str(raw).strip() if raw is not None else ""
        except Exception:
            value = ""
    return value or default


def voice_route_mounted() -> bool:
    return os.environ.get(ROUTE_FLAG_ENV) == "1"


def voice_configured() -> bool:
    return bool(get_setting("BOLNA_API_KEY"))


# ------------------------------------------------------------------------------
# Signed page tokens
# ------------------------------------------------------------------------------
def issue_voice_token(now: Optional[float] = None) -> str:
    ts = int(now if now is not None else time.time())
    msg = f"{ts}.{secrets.token_hex(8)}"
    sig = hmac.new(_SECRET, msg.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{msg}.{sig}"


def verify_voice_token(token: Optional[str], now: Optional[float] = None) -> bool:
    if not token or token.count(".") != 2:
        return False
    ts_str, nonce, sig = token.split(".")
    try:
        ts = int(ts_str)
    except ValueError:
        return False
    expected = hmac.new(_SECRET, f"{ts_str}.{nonce}".encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expected):
        return False
    age = (now if now is not None else time.time()) - ts
    return -60 <= age <= TOKEN_TTL_SECONDS


# ------------------------------------------------------------------------------
# Rate limiting (in-process sliding window)
# ------------------------------------------------------------------------------
class _RateLimiter:
    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._hits: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


_limiter = _RateLimiter(RATE_LIMIT_CALLS, RATE_LIMIT_WINDOW)


# ------------------------------------------------------------------------------
# Session minting
# ------------------------------------------------------------------------------
def _error(status: int, code: str, message: str, **extra) -> Tuple[int, Dict[str, Any]]:
    return status, {"error": code, "message": message, **extra}


def mint_bolna_session(api_key: str, agent_id: str, user_data: Optional[dict] = None) -> Tuple[int, Dict[str, Any]]:
    """
    Calls Bolna's session endpoint. Returns (status, json) for the browser:
    the session unchanged on success, or a sanitized error. Never includes the key.
    """
    body: Dict[str, Any] = {"agent_id": agent_id}
    if user_data:
        body["user_data"] = user_data
    try:
        resp = requests.post(
            BOLNA_SESSION_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        logger.warning("Bolna session mint timed out")
        return _error(504, "upstream_timeout", "The voice service took too long to respond.")
    except requests.RequestException:
        logger.warning("Bolna session mint could not reach the voice service")
        return _error(502, "upstream_unreachable", "The voice service could not be reached.")

    try:
        data = resp.json()
    except ValueError:
        data = None

    if resp.ok and isinstance(data, dict):
        return 200, data

    logger.warning("Bolna session mint failed with HTTP %s", resp.status_code)
    detail = ""
    if isinstance(data, dict):
        raw = data.get("message") or data.get("detail") or data.get("error") or ""
        detail = (raw if isinstance(raw, str) else json.dumps(raw))[:300].replace(api_key, "[redacted]")
    if resp.status_code == 429:
        scope = data.get("scope") if isinstance(data, dict) else None
        return _error(429, "at_capacity", "All voice lines are busy right now.", scope=scope)
    if resp.status_code in (401, 403):
        return _error(502, "upstream_auth",
                      "Bolna rejected the request: check BOLNA_API_KEY and that web calls are enabled for this account.",
                      detail=detail)
    if resp.status_code == 404:
        return _error(502, "agent_not_found", "Bolna could not find this agent.", detail=detail)
    if resp.status_code == 400:
        return _error(400, "bad_request", "Bolna rejected the session request.", detail=detail)
    return _error(502, "upstream_error", "The voice service returned an error.", detail=detail)


def _same_origin(request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True  # same-origin fetches from some browsers omit Origin on POST; the token still applies
    # Behind a proxy (e.g. Streamlit Community Cloud) the public host arrives as X-Forwarded-Host
    hosts = {h.strip() for h in (request.headers.get("x-forwarded-host") or "").split(",") if h.strip()}
    hosts.add(request.headers.get("host") or "")
    return urlparse(origin).netloc in hosts


def _guarded(handler):
    """Logs unexpected errors with a traceback and answers with JSON instead of a bare 500."""
    async def endpoint(request):
        from starlette.responses import JSONResponse
        try:
            return await handler(request)
        except Exception as exc:  # noqa: BLE001 - last-resort guard for a public route
            logger.exception("Voice route %s failed", request.url.path)
            detail = f"{type(exc).__name__}: {exc}"[:200]
            key = get_setting("BOLNA_API_KEY")
            if key:
                detail = detail.replace(key, "[redacted]")
            return JSONResponse({"error": "server_error", "message": "The voice service hit an unexpected error.",
                                 "detail": detail}, status_code=500, headers={"Cache-Control": "no-store"})
    endpoint.__name__ = getattr(handler, "__name__", "endpoint")
    return endpoint


async def _bolna_session(request):
    """Starlette handler for POST /api/bolna-session."""
    from starlette.concurrency import run_in_threadpool
    from starlette.responses import JSONResponse

    def reply(status_payload: Tuple[int, Dict[str, Any]]):
        status, payload = status_payload
        return JSONResponse(payload, status_code=status, headers={"Cache-Control": "no-store"})

    if not _same_origin(request):
        return reply(_error(403, "forbidden_origin", "Cross-origin requests are not allowed."))
    if not verify_voice_token(request.headers.get(TOKEN_HEADER)):
        return reply(_error(401, "invalid_token", "This page has expired. Reload it and try again."))
    client = request.client.host if request.client else "unknown"
    if not _limiter.allow(client):
        return reply(_error(429, "rate_limited", "Too many calls in a short time. Please wait a few minutes."))

    api_key = get_setting("BOLNA_API_KEY")
    if not api_key:
        logger.warning("Voice call requested but BOLNA_API_KEY is not set")
        return reply(_error(503, "not_configured", "The voice assistant is not set up yet."))
    agent_id = get_setting("BOLNA_AGENT_ID", DEFAULT_AGENT_ID)

    raw = await request.body() if request.method == "POST" else b""
    if len(raw) > MAX_BODY_BYTES:
        return reply(_error(413, "payload_too_large", "Request is too large."))
    user_data = None
    if raw.strip():
        try:
            parsed = json.loads(raw)
        except ValueError:
            return reply(_error(400, "bad_json", "Request body must be JSON."))
        user_data = parsed.get("user_data") if isinstance(parsed, dict) else None
        if user_data is not None and not isinstance(user_data, dict):
            return reply(_error(400, "bad_user_data", "user_data must be an object."))
        if user_data and len(json.dumps(user_data).encode("utf-8")) > MAX_USER_DATA_BYTES:
            return reply(_error(413, "user_data_too_large", "user_data is larger than 50 KB."))

    return reply(await run_in_threadpool(mint_bolna_session, api_key, agent_id, user_data))


# ------------------------------------------------------------------------------
# Phone callbacks ("call me")
# ------------------------------------------------------------------------------
_call_limiter_client = _RateLimiter(*CALL_LIMIT_PER_CLIENT)
_call_limiter_number = _RateLimiter(*CALL_LIMIT_PER_NUMBER)


def allowed_country_codes() -> Tuple[str, ...]:
    raw = get_setting("BOLNA_CALL_COUNTRY_CODES", DEFAULT_CALL_COUNTRY_CODES)
    codes = tuple(c.strip() if c.strip().startswith("+") else "+" + c.strip() for c in raw.split(",") if c.strip())
    return codes or (DEFAULT_CALL_COUNTRY_CODES,)


def normalize_phone(raw: Optional[str], default_cc: str = "+91") -> Optional[str]:
    """
    Returns an E.164 number (e.g. +919876543210) or None. Accepts spaces,
    dashes, brackets, a 00 prefix, a leading 0, or a bare national number.
    """
    s = re.sub(r"[\s\-().]", "", raw or "")
    if not s:
        return None
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+"):
        s = s[1:] if s.startswith("0") else s
        s = default_cc + s
    if not re.fullmatch(r"\+[1-9]\d{7,14}", s):
        return None
    if s.startswith("+91") and not re.fullmatch(r"\+91[6-9]\d{9}", s):
        return None  # Indian mobiles are 10 digits starting 6-9
    return s


def mask_phone(e164: str) -> str:
    return f"{e164[:3]} ••••• •{e164[-4:]}" if len(e164) > 7 else "•••"


def place_bolna_call(api_key: str, agent_id: str, phone: str,
                     from_number: str = "", user_data: Optional[dict] = None) -> Tuple[int, Dict[str, Any]]:
    """Asks Bolna to phone `phone` with the agent. Returns (status, json) safe for the browser."""
    body: Dict[str, Any] = {"agent_id": agent_id, "recipient_phone_number": phone}
    if from_number:
        body["from_phone_number"] = from_number
    if user_data:
        body["user_data"] = user_data
    try:
        resp = requests.post(
            BOLNA_CALL_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        logger.warning("Bolna outbound call request timed out")
        return _error(504, "upstream_timeout", "The voice service took too long to respond.")
    except requests.RequestException:
        logger.warning("Bolna outbound call request could not reach the voice service")
        return _error(502, "upstream_unreachable", "The voice service could not be reached.")

    try:
        data = resp.json()
    except ValueError:
        data = None

    if resp.ok and isinstance(data, dict):
        logger.info("Bolna call queued to %s", mask_phone(phone))
        return 200, {"status": data.get("status") or "queued", "execution_id": data.get("execution_id"),
                     "phone": mask_phone(phone)}

    logger.warning("Bolna outbound call failed with HTTP %s", resp.status_code)
    message = ""
    if isinstance(data, dict):
        raw = data.get("message") or data.get("detail") or ""
        message = (raw if isinstance(raw, str) else json.dumps(raw))[:300].replace(api_key, "[redacted]")
    lowered = message.lower()
    if resp.status_code == 429:
        retry = data.get("retry_after_seconds") if isinstance(data, dict) else None
        return _error(429, "line_activating", "The calling line is still being activated.", retry_after_seconds=retry)
    if resp.status_code in (401, 403):
        return _error(502, "upstream_auth",
                      "Bolna rejected the request: check BOLNA_API_KEY and that calling is enabled for this account.",
                      detail=message)
    if resp.status_code == 400 and "recipient" in lowered:
        return _error(400, "invalid_number", "Bolna could not call this number.", detail=message)
    if resp.status_code == 400 and "from_phone_number" in lowered:
        return _error(502, "from_number_invalid", "The caller number configured on the server is not valid.", detail=message)
    if resp.status_code == 404:
        return _error(502, "agent_not_found", "Bolna could not find this agent.", detail=message)
    if resp.status_code == 400:
        return _error(400, "bad_request", "Bolna rejected the call request.", detail=message)
    return _error(502, "upstream_error", "The voice service returned an error.", detail=message)


async def _bolna_call(request):
    """Starlette handler for POST /api/bolna-call: the agent phones the visitor's number."""
    from starlette.concurrency import run_in_threadpool
    from starlette.responses import JSONResponse

    def reply(status_payload: Tuple[int, Dict[str, Any]]):
        status, payload = status_payload
        return JSONResponse(payload, status_code=status, headers={"Cache-Control": "no-store"})

    if not _same_origin(request):
        return reply(_error(403, "forbidden_origin", "Cross-origin requests are not allowed."))
    if not verify_voice_token(request.headers.get(TOKEN_HEADER)):
        return reply(_error(401, "invalid_token", "This page has expired. Reload it and try again."))

    if request.method == "GET":
        # Streamlit Community Cloud's proxy only forwards GET to custom routes, so the
        # number travels in a header (never in the URL, which proxies log).
        parsed = {"phone": request.headers.get(PHONE_HEADER, "")}
    else:
        raw = await request.body()
        if len(raw) > 4096:
            return reply(_error(413, "payload_too_large", "Request is too large."))
        try:
            parsed = json.loads(raw or b"{}")
        except ValueError:
            return reply(_error(400, "bad_json", "Request body must be JSON."))
    codes = allowed_country_codes()
    phone = normalize_phone(parsed.get("phone") if isinstance(parsed, dict) else None, default_cc=codes[0])
    if not phone:
        return reply(_error(400, "invalid_number", "Enter a valid mobile number."))
    if not phone.startswith(codes):
        return reply(_error(400, "country_not_allowed", "Calls are only available to these country codes.",
                            allowed=list(codes)))

    client = request.client.host if request.client else "unknown"
    if not _call_limiter_client.allow(client) or not _call_limiter_number.allow(phone):
        return reply(_error(429, "rate_limited", "Too many call requests. Please wait a few minutes."))

    api_key = get_setting("BOLNA_API_KEY")
    if not api_key:
        logger.warning("Phone call requested but BOLNA_API_KEY is not set")
        return reply(_error(503, "not_configured", "The voice assistant is not set up yet."))
    agent_id = get_setting("BOLNA_AGENT_ID", DEFAULT_AGENT_ID)
    from_number = get_setting("BOLNA_FROM_NUMBER")
    return reply(await run_in_threadpool(place_bolna_call, api_key, agent_id, phone, from_number,
                                         {"source": "krishi-ai-website"}))


# ------------------------------------------------------------------------------
# Widget
# ------------------------------------------------------------------------------
def _widget_version() -> str:
    return hashlib.sha1(_WIDGET_JS.read_bytes()).hexdigest()[:12]


async def widget_script_endpoint(request):
    """
    Serves static/voice_assistant.js as JavaScript. (Inline <script> text that
    contains markup strings is stripped by st.html's sanitizer, so the widget
    is loaded with <script src> instead.)
    """
    from starlette.responses import Response

    versioned = request.query_params.get("v") == _widget_version()
    return Response(
        _WIDGET_JS.read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=86400, immutable" if versioned else "no-cache",
                 "X-Content-Type-Options": "nosniff"},
    )


def widget_config(token: str) -> Dict[str, Any]:
    """Everything the browser needs. Contains no secrets."""
    return {
        # Relative URLs: the app may be served under a path prefix (Streamlit Cloud uses /~/+/)
        "sessionUrl": SESSION_ROUTE.lstrip("/"),
        "callUrl": CALL_ROUTE.lstrip("/"),
        "countryCode": allowed_country_codes()[0],
        "tokenHeader": TOKEN_HEADER,
        "phoneHeader": PHONE_HEADER,
        "token": token,
        "sdkUrl": SDK_URL,
        "sdkIntegrity": SDK_INTEGRITY,
        "assistantName": "Krishi assistant",
    }


# ------------------------------------------------------------------------------
# Native Streamlit call button + dialog
# ------------------------------------------------------------------------------
# The floating button is a real Streamlit button and the call is placed from
# Python, so no custom HTTP route is needed. This works on any host, including
# Streamlit Community Cloud, whose proxy does not pass custom API routes through.
CALL_MESSAGES = {
    "invalid_number": "Enter a valid mobile number, for example +91 98765 43210.",
    "country_not_allowed": "We can only call Indian (+91) mobile numbers.",
    "rate_limited": "You've requested several calls in a short time. Please wait a few minutes.",
    "not_configured": "The voice assistant isn't set up yet. Please try again later.",
    "line_activating": "Our calling line is still being activated. Please try again in a few minutes.",
    "at_capacity": "All our assistants are busy right now. Please try again in a minute.",
}
FAB_CSS = """
.st-key-voice_fab { position: fixed !important; right: calc(24px + env(safe-area-inset-right, 0px));
  bottom: calc(72px + env(safe-area-inset-bottom, 0px)); z-index: 999990; width: auto !important; }
.st-key-voice_fab button { width: 56px !important; height: 56px !important; min-height: 56px !important;
  border-radius: 50% !important; padding: 0 !important; justify-content: center !important;
  background: #26734D !important; border: 0 !important; color: #FFFFFF !important;
  box-shadow: 0 1px 2px rgba(20,45,34,.12), 0 10px 28px -10px rgba(20,45,34,.55) !important;
  transition: background-color .2s ease, transform .2s ease !important; }
.st-key-voice_fab button:hover { background: #1F5F40 !important; transform: translateY(-2px); }
.st-key-voice_fab button p { display: none !important; }
.st-key-voice_fab button::before { margin-right: 0 !important; width: 24px !important; height: 24px !important;
  flex-basis: 24px !important; background-color: #FFFFFF !important; }
@media (max-width: 640px) {
  .st-key-voice_fab { right: calc(16px + env(safe-area-inset-right, 0px)); bottom: calc(64px + env(safe-area-inset-bottom, 0px)); }
  .st-key-voice_fab button { width: 52px !important; height: 52px !important; min-height: 52px !important; }
}
"""


def _call_allowed(phone: str) -> bool:
    import streamlit as st
    sid = st.session_state.setdefault("_voice_sid", secrets.token_hex(8))
    return _call_limiter_client.allow("session:" + sid) and _call_limiter_number.allow(phone)


def request_phone_call(raw_phone: str) -> Tuple[str, str]:
    """Validates and places a "call me" request. Returns (kind, message) for the UI."""
    codes = allowed_country_codes()
    phone = normalize_phone(raw_phone, default_cc=codes[0])
    if not phone:
        return "error", CALL_MESSAGES["invalid_number"]
    if not phone.startswith(codes):
        return "error", CALL_MESSAGES["country_not_allowed"]
    if not _call_allowed(phone):
        return "error", CALL_MESSAGES["rate_limited"]
    api_key = get_setting("BOLNA_API_KEY")
    if not api_key:
        logger.warning("Phone call requested but BOLNA_API_KEY is not set")
        return "error", CALL_MESSAGES["not_configured"]
    status, payload = place_bolna_call(api_key, get_setting("BOLNA_AGENT_ID", DEFAULT_AGENT_ID), phone,
                                       get_setting("BOLNA_FROM_NUMBER"), {"source": "krishi-ai-website"})
    if status == 200:
        return "success", (f"Calling you now. Your phone ({payload['phone']}) will ring in a few seconds; "
                           "answer it to talk to the Krishi assistant.")
    code = payload.get("error", "")
    if code in ("upstream_auth", "agent_not_found", "from_number_invalid", "upstream_error", "bad_request"):
        logger.warning("Call failed: %s %s", code, payload.get("detail", ""))
    return "error", CALL_MESSAGES.get(code, "We couldn't place the call. Please try again.")


def _browser_call_html(session: Dict[str, Any]) -> str:
    """A small in-dialog web-call UI. No '<' inside the script: st.html drops scripts that look like markup."""
    box = "kvc-web-" + secrets.token_hex(4)
    data = json.dumps(session).replace("<", "\\u003c")
    script = """
(function () {
  var S = %s, SDK = %s, SRI = %s, host = document.getElementById(%s);
  if (!host) return;
  var btn = document.createElement("button"), status = document.createElement("div"), call = null;
  btn.type = "button"; btn.textContent = "Start browser call";
  btn.style.cssText = "width:100%%;height:40px;border-radius:8px;border:0;background:#26734D;color:#fff;font:inherit;font-weight:500;cursor:pointer";
  status.style.cssText = "margin-top:8px;font-size:13px;color:#777F78";
  status.textContent = "Allow microphone access when your browser asks. This link expires in 2 minutes.";
  host.appendChild(btn); host.appendChild(status);
  function load() {
    if (window.BolnaWebCall) return Promise.resolve(window.BolnaWebCall);
    return new Promise(function (ok, bad) {
      var s = document.createElement("script"); s.src = SDK; s.integrity = SRI; s.crossOrigin = "anonymous";
      s.onload = function () { ok(window.BolnaWebCall); }; s.onerror = bad; document.head.appendChild(s);
    });
  }
  btn.onclick = function () {
    if (call) { call.stop(); return; }
    btn.disabled = true; status.textContent = "Connecting...";
    load().then(function (Web) {
      call = new Web({ session: S });
      call.on("call-start", function () { btn.disabled = false; btn.textContent = "End call"; btn.style.background = "#C65B52"; status.textContent = "Live. Speak naturally."; });
      call.on("call-end", function () { btn.disabled = true; btn.textContent = "Call ended"; btn.style.background = "#A8C3AD"; status.textContent = "Close this window and reopen it to call again."; call = null; });
      call.on("error", function (e) {
        btn.disabled = true; btn.style.background = "#A8C3AD";
        status.textContent = (e && e.code === "microphone_denied") ? "Microphone access is blocked. Allow it in your browser and try again." : "We couldn't start the call. Please try again.";
      });
      return call.start();
    }).catch(function () { btn.disabled = true; status.textContent = "We couldn't start the call. Please try again."; });
  };
  window.addEventListener("pagehide", function () { if (call) call.stop(); });
})();
""" % (data, json.dumps(SDK_URL), json.dumps(SDK_INTEGRITY), json.dumps(box))
    return f'<div id="{box}"></div><script>{script}</script>'


def render_voice_widget():
    """Floating call button + "Call me" dialog (call once per run, from the shared layout)."""
    import streamlit as st

    @st.dialog("Get a call from our assistant")
    def voice_dialog():
        st.caption("Enter your mobile number and the Krishi assistant will ring you right away.")
        phone = st.text_input("Your mobile number", key="voice_phone", placeholder="+91 98765 43210")
        if st.button("Call me", type="primary", width="stretch", key="voice_call_me"):
            st.session_state["voice_result"] = request_phone_call(phone)
        result = st.session_state.get("voice_result")
        if result:
            (st.success if result[0] == "success" else st.error)(result[1])
        st.caption("Our AI assistant will call this number now. Standard call rates may apply.")
        st.divider()
        if st.button("Talk in the browser instead", width="stretch", key="voice_web"):
            api_key = get_setting("BOLNA_API_KEY")
            if not api_key:
                st.error(CALL_MESSAGES["not_configured"])
            else:
                status, session = mint_bolna_session(api_key, get_setting("BOLNA_AGENT_ID", DEFAULT_AGENT_ID))
                if status == 200:
                    st.html(_browser_call_html(session), unsafe_allow_javascript=True)
                else:
                    st.error(CALL_MESSAGES.get(session.get("error", ""), "We couldn't start the call. Please try again."))

    st.html(f"<style>{FAB_CSS}</style>")
    with st.container(key="voice_fab"):
        if st.button("Call us", key="voice_fab_btn", help="Talk to our AI assistant"):
            st.session_state.pop("voice_result", None)
            voice_dialog()


# Public route handlers (wrapped so failures are logged and returned as JSON)
bolna_session_endpoint = _guarded(_bolna_session)
bolna_call_endpoint = _guarded(_bolna_call)
