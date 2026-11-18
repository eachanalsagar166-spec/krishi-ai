"""
ASGI entry point: the Krishi AI Streamlit app plus server-side API routes.

Run locally with either:
    streamlit run server.py
    uvicorn server:app --port 8501

Routes
    POST /api/bolna-session       mints a Bolna web-call session (see modules/voice_assistant.py)
    POST /api/bolna-call          asks the Bolna agent to phone the visitor ("call me")
    GET  /api/voice-assistant.js  the floating call-button script

`streamlit run app.py` still works, but without the voice assistant button,
because that mode cannot serve these routes.
"""
import os

import streamlit as st
from starlette.routing import Route

from modules.voice_assistant import (
    CALL_ROUTE, ROUTE_FLAG_ENV, SESSION_ROUTE, WIDGET_SCRIPT_ROUTE,
    bolna_call_endpoint, bolna_session_endpoint, widget_script_endpoint,
)

# Tells app.py (same process) that the routes exist, so it renders the call button.
os.environ[ROUTE_FLAG_ENV] = "1"

app = st.App(
    "app.py",
    routes=[
        Route(SESSION_ROUTE, bolna_session_endpoint, methods=["POST"]),
        Route(CALL_ROUTE, bolna_call_endpoint, methods=["POST"]),
        Route(WIDGET_SCRIPT_ROUTE, widget_script_endpoint, methods=["GET"]),
    ],
)
