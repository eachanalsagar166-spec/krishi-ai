"""
Test Suite for the Bolna voice-assistant session route (modules/voice_assistant.py).
Bolna's API is mocked, so no network calls are made and no real key is needed.
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import requests  # noqa: E402

from modules import voice_assistant as va  # noqa: E402

FAKE_KEY = "bn-TEST-secret-key-should-never-leak"


class FakeResponse:
    def __init__(self, status, payload=None, text_body=False):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._payload = payload
        self._text_body = text_body

    def json(self):
        if self._text_body:
            raise ValueError("not json")
        return self._payload


def with_fake_post(response=None, exc=None):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, body=json, timeout=timeout)
        if exc:
            raise exc
        return response

    original = requests.post
    requests.post = fake_post
    return captured, lambda: setattr(requests, "post", original)


def run_tests():
    print("=" * 65)
    print("RUNNING VOICE ASSISTANT ROUTE VERIFICATION (Bolna mocked)")
    print("=" * 65)

    # 1. Signed page tokens
    print("\n[Test 1] Page tokens are signed and expire...")
    tok = va.issue_voice_token(now=1_000_000)
    assert va.verify_voice_token(tok, now=1_000_000 + 60)
    assert not va.verify_voice_token(tok, now=1_000_000 + va.TOKEN_TTL_SECONDS + 1), "expired token accepted"
    ts, nonce, sig = tok.split(".")
    assert not va.verify_voice_token(f"{ts}.{nonce}.{'0' * len(sig)}", now=1_000_000), "forged signature accepted"
    assert not va.verify_voice_token(f"{int(ts) + 5}.{nonce}.{sig}", now=1_000_000), "tampered timestamp accepted"
    assert not va.verify_voice_token(None) and not va.verify_voice_token("garbage")
    print("  -> PASS: valid token accepted; expired, forged and tampered tokens rejected.")

    # 2. Rate limiting
    print("\n[Test 2] Per-client rate limit...")
    rl = va._RateLimiter(limit=3, window=60)
    assert all(rl.allow("a", now=t) for t in (0, 1, 2))
    assert not rl.allow("a", now=3) and rl.allow("b", now=3)
    assert rl.allow("a", now=61.5)
    print("  -> PASS: 4th call within the window blocked; other clients and later calls allowed.")

    # 3. Successful mint passes the session through and sends the documented request
    print("\n[Test 3] Successful mint...")
    session = {"run_id": "r1", "wss_url": "wss://sip.example/ws", "sip_username": "u1"}
    captured, restore = with_fake_post(FakeResponse(200, session))
    try:
        status, payload = va.mint_bolna_session(FAKE_KEY, "agent-123", {"name": "Asha"})
    finally:
        restore()
    assert status == 200 and payload == session
    assert captured["url"] == va.BOLNA_SESSION_ENDPOINT
    assert captured["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert captured["body"] == {"agent_id": "agent-123", "user_data": {"name": "Asha"}}
    assert FAKE_KEY not in str(payload)
    print(f"  -> PASS: POST {va.BOLNA_SESSION_ENDPOINT} with Bearer auth and agent_id; session returned unchanged.")

    # 4. Error mapping never echoes the key
    print("\n[Test 4] Upstream errors map to clear codes and never echo the key...")
    cases = [
        (FakeResponse(403, {"message": f"Invalid access token {FAKE_KEY}"}), 502, "upstream_auth"),
        (FakeResponse(401, {"detail": "Unauthorized"}), 502, "upstream_auth"),
        (FakeResponse(429, {"scope": "customer"}), 429, "at_capacity"),
        (FakeResponse(404, {"message": "agent not found"}), 502, "agent_not_found"),
        (FakeResponse(400, {"message": "user_data too large"}), 400, "bad_request"),
        (FakeResponse(500, text_body=True), 502, "upstream_error"),
    ]
    for resp, want_status, want_code in cases:
        _, restore = with_fake_post(resp)
        try:
            status, payload = va.mint_bolna_session(FAKE_KEY, "agent-123")
        finally:
            restore()
        assert (status, payload["error"]) == (want_status, want_code), (resp.status_code, status, payload)
        assert FAKE_KEY not in str(payload), f"key leaked for HTTP {resp.status_code}"
    for exc, want in ((requests.Timeout(), 504), (requests.ConnectionError(), 502)):
        _, restore = with_fake_post(exc=exc)
        try:
            status, payload = va.mint_bolna_session(FAKE_KEY, "agent-123")
        finally:
            restore()
        assert status == want and FAKE_KEY not in str(payload)
    print("  -> PASS: 401/403 -> 502 upstream_auth, 429 -> at_capacity (scope kept), timeouts -> 504; key redacted.")

    # 5. Browser config carries no secrets
    print("\n[Test 5] Widget config contains no secrets...")
    os.environ["BOLNA_API_KEY"] = FAKE_KEY
    try:
        cfg = va.widget_config(va.issue_voice_token())
    finally:
        del os.environ["BOLNA_API_KEY"]
    assert FAKE_KEY not in str(cfg) and "agent" not in " ".join(cfg).lower()
    assert cfg["sdkUrl"].endswith("@v3.0.1/dist/bolna-web-call.min.js") and cfg["sdkIntegrity"].startswith("sha384-")
    js = va._WIDGET_JS.read_text(encoding="utf-8")
    assert "BOLNA_API_KEY" not in js and "Authorization" not in js
    print("  -> PASS: config has session URL, page token and pinned SDK only.")

    # 6. Phone number normalisation for "call me"
    print("\n[Test 6] Phone numbers normalise to E.164 and reject junk...")
    good = {"+91 98765 43210": "+919876543210", "98765-43210": "+919876543210", "09876543210": "+919876543210",
            "0091 9876543210": "+919876543210", "(+91) 98765 43210": "+919876543210"}
    for raw, want in good.items():
        assert va.normalize_phone(raw) == want, (raw, va.normalize_phone(raw))
    for bad in ("", "12345", "+91 12345 67890", "abcdefghij", "+9198765432101", None):
        assert va.normalize_phone(bad) is None, bad
    assert va.normalize_phone("+1 415 555 0100") == "+14155550100"
    assert va.mask_phone("+919876543210") == "+91 ••••• •3210"
    print("  -> PASS: common Indian formats accepted; landline-style and malformed numbers rejected.")

    # 7. Outbound call request and error mapping
    print("\n[Test 7] Outbound call request and error mapping...")
    captured, restore = with_fake_post(FakeResponse(200, {"message": "done", "status": "queued", "execution_id": "e-1"}))
    try:
        status, payload = va.place_bolna_call(FAKE_KEY, "agent-123", "+919876543210", "+918035739222", {"source": "t"})
    finally:
        restore()
    assert status == 200 and payload == {"status": "queued", "execution_id": "e-1", "phone": "+91 ••••• •3210"}
    assert captured["url"] == va.BOLNA_CALL_ENDPOINT
    assert captured["body"] == {"agent_id": "agent-123", "recipient_phone_number": "+919876543210",
                                "from_phone_number": "+918035739222", "user_data": {"source": "t"}}
    cases = [
        (FakeResponse(400, {"error": 400, "message": "recipient_phone_number is required"}), 400, "invalid_number"),
        (FakeResponse(400, {"error": 400, "message": "Invalid from_phone_number"}), 502, "from_number_invalid"),
        (FakeResponse(403, {"message": f"Invalid access token {FAKE_KEY}"}), 502, "upstream_auth"),
        (FakeResponse(429, {"message": "still being activated", "retry_after_seconds": 95}), 429, "line_activating"),
    ]
    for resp, want_status, want_code in cases:
        _, restore = with_fake_post(resp)
        try:
            status, payload = va.place_bolna_call(FAKE_KEY, "agent-123", "+919876543210")
        finally:
            restore()
        assert (status, payload["error"]) == (want_status, want_code), (resp.status_code, status, payload)
        assert FAKE_KEY not in str(payload)
    print(f"  -> PASS: POST {va.BOLNA_CALL_ENDPOINT} with E.164 recipient; errors mapped, key never echoed.")

    # 8. Country restriction and settings file fallback
    print("\n[Test 8] Country allow-list and secrets.toml fallback...")
    assert va.allowed_country_codes() == ("+91",)
    os.environ["BOLNA_CALL_COUNTRY_CODES"] = "91, +1"
    try:
        assert va.allowed_country_codes() == ("+91", "+1")
    finally:
        del os.environ["BOLNA_CALL_COUNTRY_CODES"]
    va._secrets_cache.update(mtime=None, values={})
    original_file = va._SECRETS_FILE
    import tempfile
    tmp = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8")
    tmp.write('BOLNA_AGENT_ID = "from-secrets-file"\n')
    tmp.close()
    va._SECRETS_FILE = va.Path(tmp.name)
    try:
        assert va.get_setting("BOLNA_AGENT_ID") == "from-secrets-file"
        os.environ["BOLNA_AGENT_ID"] = "from-env"
        assert va.get_setting("BOLNA_AGENT_ID") == "from-env", "environment must win over the file"
    finally:
        os.environ.pop("BOLNA_AGENT_ID", None)
        va._SECRETS_FILE = original_file
        va._secrets_cache.update(mtime=None, values={})
        os.unlink(tmp.name)
    print("  -> PASS: +91 only by default; env var overrides .streamlit/secrets.toml.")

    print("\n" + "=" * 65)
    print("ALL 8 VOICE ASSISTANT TESTS PASSED")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
