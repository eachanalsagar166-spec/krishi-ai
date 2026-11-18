"""
Krishi AI – Intelligent Farming Decision System
Commercial-Grade AgriTech SaaS Platform
Includes:
- Complete User Authentication: Sign In, Sign Up, Remember Me, Rate Limiting, Forgot Password, Data Isolation
- Light, natural premium UI (see modules/ui.py): warm off-white canvas, forest-green accents,
  Inter typography, Lucide outline icons, restrained motion
- Enterprise Modules:
  1. Overview (Greeting, Market Highlights, Live Farm Weather, Farm Profile, Recent Predictions)
  2. Fertilizer Advisor (Crop NPK Deficit, Urea/DAP/MOP Bag Calculation, 3-Stage Split Schedule)
  3. Mandi Net Proceeds & Logistics (APMC Ranking, ORS Road Routing, Normal vs Cold-Chain)
  4. Price Forecast & Sell Timing Advisor (DuckDB 4-Year Parquet Analytics, Plotly Interactive Forecast,
     Trend-Shift Calibration, Sell Now vs Wait Engine)
  5. Fraud & Unfair Offer Detector (Predatory Bid Anomaly Detection, Farmer Loss, Negotiation Script)
  6. Reports (User-Isolated Prediction History, CSV Export)
  7. Settings (Farm Profile Configuration, Password Management, Session Logout)
"""
import os
import sys
import json
import datetime
from html import escape as esc
from typing import Optional

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Modules
from modules.auth_db import (
    register_user, authenticate_user, get_user_by_session_token,
    invalidate_session, create_password_reset_token, reset_password_with_token,
    change_user_password, update_farm_profile, get_user_predictions
)
from modules.data_loader import load_normalized_marketplace_data
from modules.transport_engine import DEFAULT_VEHICLE_CONFIGS
from modules.proceeds_calculator import compute_mandi_proceeds_table
from modules.fraud_detector import evaluate_buyer_offer
from modules.historical_data import (
    get_distinct_filter_values, query_historical_prices, historical_data_available
)
from modules.forecasting import train_and_forecast_price
from modules.sell_advisor import evaluate_sell_timing
from modules.fertilizer_advisor import calculate_fertilizer_prescription
from modules.fair_price_model import predict_fair_price_band
from modules.trend_shift import (
    to_daily_series, detect_trend_shift, recalibrate_forecast, predictions_from_forecast,
    shift_signal_history, trend_lines, recency_parameters
)
from modules.weather import fetch_farm_weather
from modules.buyer_network import (
    BUYER_TYPES, PAYMENT_TERMS, PICKUP_OPTIONS, GRADES, FARMER_GRADES, LOCAL_RADIUS_KM, DEMO_BUYER_PASSWORD,
    location_options, get_buyer_profile, upsert_buyer_profile, create_quotation, set_quotation_status,
    list_buyer_quotations, list_open_quotations, quoted_commodities, match_buyers,
    create_connection_request, list_farmer_requests, list_buyer_requests, respond_to_request, withdraw_request
)
from modules.geo_ors import estimate_road_distance_demo
from modules.voice_assistant import render_voice_widget
from modules.ui import (
    COLORS, TONES, PLOTLY_CONFIG, COUNT_UP_SCRIPT, icon, button_icon_css, global_css, hex_alpha,
    page_header, card_title, badge, kpi_card, callout, empty_state, style_figure,
    stat_list, count, sparkline_uri, page_transition_css, icon_data_uri
)

# Page Configuration
st.set_page_config(
    page_title="Krishi AI – Intelligent Farming Decision System",
    page_icon=":material/eco:",
    layout="wide",
    initial_sidebar_state="auto"  # open on desktop, collapsed on phones
)

# ==============================================================================
# NAVIGATION & ICON REGISTRY
# ==============================================================================
# Sections of (state key, sidebar label, icon, page slug), per role
FARMER_NAV = [
    (None, [("Dashboard", "Overview", "house", "overview")]),
    ("Advisory", [("Fertilizer Advisor", "Fertilizer Advisor", "package", "fertilizer")]),
    ("Markets", [
        ("Mandi Net Proceeds", "Mandi Net Proceeds", "truck", "mandi"),
        ("Price Forecast", "Price Forecast", "chart-line", "forecast"),
        ("Trend Shift", "Trend Shift", "activity", "trendshift"),
        ("Buyer Network", "Buyer Network", "store", "buyers"),
        ("Fraud Detector", "Offer Check", "shield-check", "fraud"),
    ]),
    ("Account", [
        ("Reports", "Reports", "file-text", "reports"),
        ("Settings", "Settings", "settings", "settings"),
    ]),
]
BUYER_NAV = [
    ("Buyer desk", [
        ("Buyer Requests", "Requests", "inbox", "brequests"),
        ("Buyer Quotations", "Quotations", "file-text", "bquotes"),
    ]),
    ("Markets", [
        ("Price Forecast", "Price Forecast", "chart-line", "forecast"),
        ("Trend Shift", "Trend Shift", "activity", "trendshift"),
    ]),
    ("Account", [("Buyer Profile", "Business profile", "store", "bprofile")]),
]
ALL_NAV_ITEMS = {item[0]: item for nav in (FARMER_NAV, BUYER_NAV) for _, items in nav for item in items}
NAV_ITEMS = list(ALL_NAV_ITEMS.values())


def nav_for(role: str):
    return BUYER_NAV if role == "buyer" else FARMER_NAV


def nav_widget_key(state_key: str) -> str:
    return "nav_" + state_key.lower().replace(" ", "_")


# Widget key -> Lucide icon. Streamlit tags keyed widgets with `st-key-<key>`,
# which button_icon_css() uses to prefix the button with an outline icon.
QUICK_ACTIONS = [
    ("qa_buyers", "Find buyers for your crop", "store", "Buyer Network"),
    ("qa_fertilizer", "Plan fertilizer", "package", "Fertilizer Advisor"),
    ("qa_mandi", "Rank mandis by net proceeds", "truck", "Mandi Net Proceeds"),
    ("qa_forecast", "Forecast prices", "chart-line", "Price Forecast"),
    ("qa_offer", "Check a buyer's offer", "shield-check", "Fraud Detector"),
]
BUTTON_ICONS = {
    "auth_tab_signin": "log-in",
    "auth_tab_signup": "user-plus",
    "auth_tab_forgot": "key-round",
    "btn_signin": "log-in",
    "demo_farmer": "sprout",
    "demo_admin": "shield-check",
    "demo_buyer": "store",
    "pf_open_ts": "activity",
    "bq_publish": "send",
    "bp_save": "save",
    "btn_signup": "user-plus",
    "btn_gen_token": "key-round",
    "btn_reset_pwd": "lock",
    "btn_logout": "log-out",
    "btn_download_reports": "download",
    "btn_save_profile": "save",
    "btn_update_pwd": "lock",
    **{key: ic for key, _, ic, _ in QUICK_ACTIONS},
    **{nav_widget_key(key): ic for key, _, ic, _ in NAV_ITEMS},
}
CHEVRON_URI = icon_data_uri("chevron-right")
QUICK_ACTION_CSS = "\n".join(
    f".st-key-{key} button {{ justify-content: flex-start !important; min-height: 44px; }}\n"
    f".st-key-{key} button::after {{ content: ''; margin-left: auto; width: 14px; height: 14px; flex: 0 0 14px; "
    f"background-color: {COLORS['text_muted']}; -webkit-mask: url({CHEVRON_URI}) center / contain no-repeat; "
    f"mask: url({CHEVRON_URI}) center / contain no-repeat; }}"
    for key, *_ in QUICK_ACTIONS
)

st.html(global_css())
st.html(f"<style>{button_icon_css(BUTTON_ICONS)}\n{QUICK_ACTION_CSS}\n"
        f"{page_transition_css(slug for *_, slug in NAV_ITEMS)}</style>")


# Session State Initialization
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "auth_view" not in st.session_state:
    st.session_state.auth_view = "signin"  # 'signin', 'signup', 'forgot'
if "active_nav" not in st.session_state:
    st.session_state.active_nav = "Dashboard"

# Trend-shift settings are shared by the Trend Shift and Price Forecast pages.
# Re-assigning them every run keeps their values when their widgets are not on screen.
TS_DEFAULTS = {"ts_recal": False, "ts_sensitivity": 50, "ts_overlay": True,
               "ts_recent": 14, "ts_baseline": 60, "ts_threshold": 10, "ts_signif": 2.0}
for _k, _v in TS_DEFAULTS.items():
    st.session_state[_k] = st.session_state.get(_k, _v)

# Verify Existing Session
if st.session_state.auth_token and not st.session_state.current_user:
    validated_user = get_user_by_session_token(st.session_state.auth_token)
    if validated_user:
        st.session_state.current_user = validated_user
    else:
        st.session_state.auth_token = None


# ==============================================================================
# CACHED DATA LOADERS
# ==============================================================================
@st.cache_data
def get_cached_marketplace():
    return load_normalized_marketplace_data()


@st.cache_data(show_spinner=False, ttl=3600)
def cached_filter_values(commodity, state, district=None):
    return get_distinct_filter_values(commodity=commodity, state=state, district=district)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_price_history(commodity, state, district, markets):
    return query_historical_prices(
        commodity=commodity, state=state, district=district,
        markets=list(markets) if markets else None
    )


@st.cache_data(show_spinner=False, ttl=3600)
def cached_forecast(commodity, state, district, markets, target_market):
    """Trains the forecaster once per scope so calibration controls stay real-time."""
    df_hist = cached_price_history(commodity, state, district, markets)
    df_target = df_hist[df_hist["Market"] == target_market] if target_market else df_hist
    if df_target.empty:
        df_target = df_hist
    return train_and_forecast_price(df_target, horizons=[3, 7, 14]), df_target


@st.cache_data(show_spinner=False, ttl=3600)
def cached_mandi_table(crop, quantity_kg, lat, lon, vehicle_name):
    return compute_mandi_proceeds_table(
        df_marketplace=df_market, crop_name=crop, quantity_kg=quantity_kg,
        farmer_lat=lat, farmer_lon=lon, vehicle_config=DEFAULT_VEHICLE_CONFIGS[vehicle_name].copy()
    )


@st.cache_data(show_spinner=False, ttl=3600)
def cached_fair_price(crop, state):
    """Fair mandi modal price (₹/kg) from the APMC snapshot, used to audit buyer quotes."""
    return predict_fair_price_band(df_market, crop, state).get("fair_modal_price_kg")


@st.cache_data(show_spinner=False, ttl=3600)
def cached_shift_history(commodity, state, market, recent, baseline, threshold, signif):
    _, df_target = cached_forecast(commodity, state, "All Districts", (market,), None)
    return shift_signal_history(to_daily_series(df_target), recent, baseline, threshold,
                                significance_z=signif or None)


def run_shift(daily):
    """Pattern-shift scan using the settings chosen on the Trend Shift page."""
    ss = st.session_state
    return detect_trend_shift(daily, ss.ts_recent, ss.ts_baseline, ss.ts_threshold,
                              significance_z=ss.ts_signif or None)


@st.cache_data(show_spinner=False, ttl=1800)
def _cached_weather(lat, lon):
    data = fetch_farm_weather(lat, lon)
    if data is None:
        raise RuntimeError("weather unavailable")  # exceptions are not cached, so we retry next run
    return data


def get_farm_weather(lat, lon):
    try:
        return _cached_weather(round(float(lat), 3), round(float(lon), 3))
    except RuntimeError:
        return None


df_market = get_cached_marketplace()


def initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "U"


def unit(value: str, suffix: str) -> str:
    return f'{value}<span class="ki-unit">{suffix}</span>'


def money(v: float, decimals: int = 2, signed: bool = False) -> str:
    """₹ amount with a true minus sign for negatives (e.g. −₹2,323.80)."""
    sign = "−" if v < 0 else ("+" if signed and v > 0 else "")
    return f"{sign}₹{abs(v):,.{decimals}f}"


def fmt_date(d) -> str:
    try:
        return pd.to_datetime(d).strftime("%d %b %Y")
    except Exception:
        return str(d)


def go_to(nav_key: str):
    st.session_state.active_nav = nav_key
    st.rerun()


# ==============================================================================
# AUTHENTICATION SCREEN
# ==============================================================================
def render_authentication_page():
    st.html(f"""
    <div class="ki-auth-hero">
        <div class="ki-auth-mark">{icon('leaf', 22)}</div>
        <h1 class="ki-auth-title">Krishi AI</h1>
        <p class="ki-auth-sub">Market intelligence, fertilizer planning and fair-price protection for modern farm enterprises.</p>
    </div>
    """)

    _, col_card, _ = st.columns([1, 1.5, 1])

    with col_card:
        with st.container(border=True, key="card_auth"):
            tabs = [
                ("signin", "Sign In", "auth_tab_signin"),
                ("signup", "Sign Up", "auth_tab_signup"),
                ("forgot", "Recover", "auth_tab_forgot"),
            ]
            with st.container(key="auth_tabs"):
                for col, (view, label, key) in zip(st.columns(3), tabs):
                    with col:
                        is_active = st.session_state.auth_view == view
                        if st.button(label, key=key, width="stretch", type="primary" if is_active else "secondary"):
                            st.session_state.auth_view = view
                            st.rerun()

            # SIGN IN VIEW
            if st.session_state.auth_view == "signin":
                st.html(card_title(None, "Sign in to your account",
                                   "Enter your verified credentials to access your farm portal."))

                login_email = st.text_input("Email address", value="farmer@krishiai.com", placeholder="name@farm.com", key="auth_email")
                login_pwd = st.text_input("Password", value="Password@123", type="password", key="auth_pwd")

                c_rem, c_fgt = st.columns([1, 1])
                with c_rem:
                    remember_me = st.checkbox("Remember me (30 days)", value=True)
                with c_fgt:
                    st.html('<div class="ki-hint" style="text-align:right;">Forgot password? Use <strong>Recover</strong>.</div>')

                if st.button("Sign in", type="primary", width="stretch", key="btn_signin"):
                    if not login_email or not login_pwd:
                        st.error("Please enter both email address and password.")
                    else:
                        with st.spinner("Verifying credentials..."):
                            success, msg, token, user_data = authenticate_user(login_email, login_pwd, remember_me=remember_me)
                            if success:
                                st.session_state.auth_token = token
                                st.session_state.current_user = user_data
                                st.success("Welcome back. Loading your farm...")
                                st.rerun()
                            else:
                                st.error(msg)

                st.html('<div class="ki-divider-label"><span>Instant demo access</span></div>')

                demos = [
                    ("demo_farmer", "Demo Farmer", "farmer@krishiai.com", "Password@123", "Tomato farm · Ramanagara"),
                    ("demo_buyer", "Demo Buyer", "buyer@krishiai.com", DEMO_BUYER_PASSWORD, "Vegetable dealer · Ramanagara"),
                    ("demo_admin", "Demo Admin", "admin@krishiai.com", "Admin@123", "APMC oversight"),
                ]
                for col, (key, label, email, pwd, caption) in zip(st.columns(3), demos):
                    with col:
                        if st.button(label, width="stretch", key=key):
                            s, m, t, u = authenticate_user(email, pwd, remember_me=True)
                            if s:
                                st.session_state.auth_token = t
                                st.session_state.current_user = u
                                st.session_state.active_nav = "Buyer Requests" if u["role"] == "buyer" else "Dashboard"
                                st.rerun()
                            else:
                                st.error(m)
                        st.caption(caption)

            # SIGN UP VIEW
            elif st.session_state.auth_view == "signup":
                st.html(card_title(None, "Create farmer account",
                                   "Farmers manage their farm; dealers and industries post quotations to farmers."))

                su_type = st.segmented_control("Account type", ["Farmer", "Buyer (dealer or industry)"],
                                               default="Farmer", key="su_type")
                su_name = st.text_input("Full name", placeholder="e.g. Ramesh Gowda")
                su_email = st.text_input("Email address", placeholder="name@farm.com")
                su_phone = st.text_input("Phone number (optional)", placeholder="+91 98450 12345")
                su_pwd = st.text_input("Create password", type="password", help="Minimum 8 characters with an uppercase letter and a number")
                su_pwd_conf = st.text_input("Confirm password", type="password")
                su_agree = st.checkbox("I accept the Krishi AI Terms of Service and Privacy Policy")

                if st.button("Create my account", type="primary", width="stretch", key="btn_signup"):
                    if not su_name or not su_email or not su_pwd:
                        st.error("Please fill in all required fields.")
                    elif not su_agree:
                        st.error("Please accept the Terms of Service to continue.")
                    elif su_pwd != su_pwd_conf:
                        st.error("Passwords do not match. Please re-enter carefully.")
                    else:
                        with st.spinner("Configuring isolated farm database..."):
                            su_role = "buyer" if su_type and su_type.startswith("Buyer") else "farmer"
                            ok_r, msg_r = register_user(su_name, su_email, su_pwd, su_phone, role=su_role)
                            if ok_r:
                                st.success(msg_r)
                                st.session_state.auth_view = "signin"
                                st.rerun()
                            else:
                                st.error(msg_r)

            # FORGOT PASSWORD VIEW
            else:
                st.html(card_title(None, "Account recovery",
                                   "Generate a single-use secure reset token, then set a new password."))

                fgt_email = st.text_input("Registered email address", placeholder="name@farm.com")
                if st.button("Generate recovery token", width="stretch", key="btn_gen_token"):
                    if not fgt_email:
                        st.error("Please enter your registered email address.")
                    else:
                        tok_ok, tok_msg, gen_token = create_password_reset_token(fgt_email)
                        if tok_ok and gen_token:
                            st.success("Recovery token generated successfully.")
                            st.info(f"**Your reset token:** `{gen_token}`")
                        else:
                            st.warning(tok_msg)

                st.html('<div class="ki-divider-label"><span>Reset password with token</span></div>')
                in_token = st.text_input("Reset token", placeholder="Paste token here")
                in_new_pwd = st.text_input("New password", type="password")

                if st.button("Update password", type="primary", width="stretch", key="btn_reset_pwd"):
                    if not in_token or not in_new_pwd:
                        st.error("Please provide both token and new password.")
                    else:
                        rst_ok, rst_msg = reset_password_with_token(in_token, in_new_pwd)
                        if rst_ok:
                            st.success(rst_msg)
                            st.session_state.auth_view = "signin"
                            st.rerun()
                        else:
                            st.error(rst_msg)

    features = [
        ("package", "Fertilizer Prescriptions", "Crop NPK deficit, 50 kg bag dosage and split schedules"),
        ("truck", "Mandi Logistics", "Road routing, cold-chain parity and net proceeds ranking"),
        ("chart-line", "Price Forecasting", "4-year DuckDB models with trend-shift calibration"),
        ("shield-check", "Fair-Price Protection", "Predatory quote detection and counter-offers"),
    ]
    tiles = "".join(
        f"""<div class="ki-feature"><span class="ki-feature-icon">{icon(ic, 18)}</span>
            <div><div class="ki-feature-title">{t}</div><div class="ki-feature-body">{b}</div></div></div>"""
        for ic, t, b in features
    )
    st.html(f"""
    <div class="ki-feature-wrap">
        <div class="ki-feature-grid">{tiles}</div>
        <div class="ki-security-note">{icon('lock', 14)}<span>bcrypt password hashing · tenant-isolated data · no plain-text storage</span></div>
    </div>
    """)


# ==============================================================================
# OVERVIEW
# ==============================================================================
def market_snapshot(farm: dict) -> dict:
    """
    Real market highlights for the farm's primary crop at its home market,
    using the same cached pipeline (and cache keys) as the Price Forecast view.
    """
    if not historical_data_available():
        return {"status": "NO_ARCHIVE"}
    crop = (farm.get("primary_crops") or "Tomato").split(",")[0].strip()
    state = farm.get("state", "Karnataka")
    meta = cached_filter_values(crop, state)
    if crop not in meta["commodities"]:
        return {"status": "NO_CROP", "crop": crop}
    markets = cached_filter_values(crop, state, "All Districts")["markets"]
    home = [m for m in (farm.get("district"), farm.get("village")) if m and m in markets]
    scope = home[:1] or markets[:1]
    if not scope:
        return {"status": "NO_CROP", "crop": crop}
    fc_output, df_target = cached_forecast(crop, state, "All Districts", tuple(scope), None)
    if fc_output.get("status") != "SUCCESS":
        return {"status": "INSUFFICIENT", "crop": crop, "market": scope[0]}
    daily = to_daily_series(df_target)
    return {
        "status": "SUCCESS", "crop": crop, "market": scope[0], "fc": fc_output,
        "daily": daily, "shift": run_shift(daily),
    }


def weather_card_html(wx: dict, place: str) -> str:
    cur = wx["current"]
    days = wx["daily"]
    today = days[0]
    lo_all = min(d["t_min"] for d in days)
    hi_all = max(d["t_max"] for d in days)
    span = (hi_all - lo_all) or 1.0
    rows = ""
    for i, d in enumerate(days):
        name = "Today" if i == 0 else pd.to_datetime(d["date"]).strftime("%a")
        left = (d["t_min"] - lo_all) / span * 100
        width = max(4.0, (d["t_max"] - d["t_min"]) / span * 100)
        rain = f'{d["rain_prob"]:.0f}%' if (d["rain_prob"] or 0) >= 20 else ""
        rows += f"""
        <div class="ki-wx-day ki-num">
            <span class="ki-wx-day-name">{name}</span>
            <span class="ki-wx-icon" title="{d['label']}">{icon(d['icon'], 18)}</span>
            <span class="ki-wx-day-rain">{rain}</span>
            <span class="ki-wx-day-lo">{d['t_min']:.0f}°</span>
            <span class="ki-wx-range"><span class="ki-wx-range-fill" style="left:{left:.1f}%; width:{width:.1f}%;"></span></span>
            <span class="ki-wx-day-hi">{d['t_max']:.0f}°</span>
        </div>"""
    updated = pd.to_datetime(cur["time"]).strftime("%H:%M") if cur.get("time") else ""
    head_html = card_title("cloud-sun", "Weather", f"{esc(place)} · updated {updated}")
    return f"""
    {head_html}
    <div class="ki-wx-now">
        <div>
            <div class="ki-wx-temp ki-num">{count(cur['temperature'], 0, suffix='°', key='wx_temp')}</div>
            <div class="ki-wx-cond">{cur['label']}</div>
            <div class="ki-wx-hl ki-num">H {today['t_max']:.0f}° · L {today['t_min']:.0f}° · Feels like {cur['feels_like']:.0f}°</div>
        </div>
        <span class="ki-wx-icon">{icon(cur['icon'], 56, stroke=1.25)}</span>
    </div>
    <div class="ki-wx-metrics ki-num">
        <div><div class="ki-wx-metric-label">{icon('droplets', 13)}Humidity</div><div class="ki-wx-metric-value">{cur['humidity']:.0f}%</div></div>
        <div><div class="ki-wx-metric-label">{icon('wind', 13)}Wind</div><div class="ki-wx-metric-value">{cur['wind_speed']:.0f} km/h</div></div>
        <div><div class="ki-wx-metric-label">{icon('cloud-rain', 13)}Rain today</div><div class="ki-wx-metric-value">{today['rain_mm']:.1f} mm</div></div>
    </div>
    <div class="ki-eyebrow" style="margin:14px 0 2px 0;">7-day outlook</div>
    <div>{rows}</div>
    <div class="ki-attribution">Weather data by Open-Meteo.com</div>
    """


def hourly_figure(wx: dict) -> go.Figure:
    hr = wx["hourly"]
    x = pd.to_datetime(hr["time"])
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x, y=hr["rain_prob"], name="Chance of rain", yaxis="y2",
        marker=dict(color=hex_alpha(COLORS["sage"], 0.55), line=dict(width=0)),
        hovertemplate="%{y:.0f}% rain<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=hr["temperature"], name="Temperature", mode="lines",
        line=dict(color=COLORS["forest"], width=2, shape="spline"),
        hovertemplate="%{y:.0f}°C<extra></extra>",
    ))
    style_figure(fig, height=200)
    fig.update_layout(
        showlegend=False, hovermode="x unified", bargap=0.35, margin=dict(l=4, r=4, t=8, b=4),
        yaxis=dict(ticksuffix="°", nticks=4),
        yaxis2=dict(overlaying="y", side="right", range=[0, 100], showgrid=False, ticksuffix="%",
                    tickmode="array", tickvals=[0, 50, 100], ticktext=["0%", "50%", "100%"], zeroline=False,
                    tickfont=dict(color=COLORS["text_muted"], size=10)),
    )
    fig.update_xaxes(tickformat="%-I %p", nticks=6, showgrid=False)
    return fig


def render_overview(user: dict, farm: dict):
    now = datetime.datetime.now()
    greeting = "Good morning" if now.hour < 12 else ("Good afternoon" if now.hour < 17 else "Good evening")
    first_name = (user["full_name"] or "there").split()[0]
    st.html(f"""
    <div class="ki-page-header">
        <div class="ki-page-header__lead">
            <div class="ki-page-eyebrow">{icon('calendar', 14)}<span>{now.strftime('%A, %d %B')}</span></div>
            <h1 class="ki-page-title">{greeting}, {esc(first_name)}</h1>
            <div class="ki-greeting-meta ki-num">
                <span>{icon('sprout', 14)}{esc(str(farm.get('farm_name', 'My Farm')))}</span>
                <span>{icon('map-pin', 14)}{esc(str(farm.get('district', '')))}, {esc(str(farm.get('state', '')))}</span>
                <span>{icon('layout-dashboard', 14)}{float(farm.get('acreage', 0) or 0):.1f} acres · {esc(str(farm.get('soil_type', '')))}</span>
            </div>
        </div>
    </div>
    """)

    # ---------------- Highlights (real market data) ----------------
    with st.spinner("Loading market highlights..."):
        snap = market_snapshot(farm)

    st.html(f'<div class="ki-section-title">Today\'s highlights'
            f'{"<span>" + esc(snap["crop"]) + " · " + esc(snap["market"]) + "</span>" if snap.get("status") == "SUCCESS" else ""}</div>')
    if snap["status"] == "SUCCESS":
        fc = snap["fc"]
        lat_p = fc["latest_observed_price"]
        p7 = fc["predictions"].get("7_day", {}).get("predicted_price_kg", lat_p)
        d7 = p7 - lat_p
        shift = snap["shift"]
        h1, h2, h3, h4 = st.container(key="tiles_overview").columns(4)
        with h1:
            st.html(kpi_card(
                "Market price", unit(count(lat_p, 2, "₹", key="ov_price"), "/kg"),
                f"{esc(snap['market'])} · {fmt_date(fc['latest_observed_date'])}", "neutral", "chart-line",
                spark_uri=sparkline_uri(snap["daily"].iloc[-45:].tolist(), COLORS["forest"])))
        with h2:
            st.html(kpi_card(
                "7-day outlook", unit(count(p7, 2, "₹", key="ov_p7"), "/kg"),
                f"{d7:+.2f}/kg · {d7 / lat_p * 100 if lat_p else 0:+.1f}%",
                "positive" if d7 >= 0 else "risk", "trending-up" if d7 >= 0 else "trending-down"))
        with h3:
            if shift.get("status") == "SUCCESS":
                detected = shift["detected"]
                st.html(kpi_card(
                    "Trend signal", unit(count(shift["slope_variance_pct"], 1, key="ov_shift", signed=True), "%"),
                    "Pattern shift detected" if detected else ("Within normal swings" if shift.get("within_noise") else "Trend stable"),
                    "warning" if detected else ("neutral" if shift.get("within_noise") else "positive"), "activity"))
            else:
                st.html(kpi_card("Trend signal", "—", "Not enough history", "neutral", "activity"))
        with h4:
            veh = list(DEFAULT_VEHICLE_CONFIGS.keys())[0]
            mandi = cached_mandi_table(snap["crop"], 500.0, farm.get("latitude", 12.7209), farm.get("longitude", 77.2799), veh)
            best = mandi.get("best_mandi")
            if best:
                st.html(kpi_card(
                    "Best net mandi", count(best["net_proceeds"], 0, "₹", key="ov_mandi"),
                    f"{esc(best['mandi'])} · 500 kg, after freight & fees", "positive", "award"))
            else:
                st.html(kpi_card("Best net mandi", "—", "No mandi prices for this crop", "neutral", "award"))
    elif snap["status"] == "NO_ARCHIVE":
        st.html(empty_state("database", "Market highlights need the price archive",
                            "Add the 2023–2026 parquet files to <code>data/historical_parquet/parquet</code> or set <code>KRISHI_PARQUET_DIR</code>."))
    else:
        st.html(empty_state("inbox", "No market history for your primary crop",
                            f"{esc(snap.get('crop', 'This crop'))} has too few price records in your state to summarise."))

    # ---------------- Weather + farm ----------------
    with st.spinner("Loading farm weather..."):
        wx = get_farm_weather(farm.get("latitude", 12.7209), farm.get("longitude", 77.2799))

    col_wx, col_side = st.columns([1.05, 1])
    with col_wx:
        with st.container(border=True, key="card_weather"):
            if wx:
                st.html(weather_card_html(wx, f"{farm.get('district', '')}, {farm.get('state', '')}"))
            else:
                st.html(card_title("cloud-sun", "Weather"))
                st.html(empty_state("cloud", "Weather is unavailable",
                                    "Open-Meteo could not be reached. It will retry automatically on your next visit."))
    with col_side:
        if wx:
            with st.container(border=True, key="card_hourly"):
                st.html(card_title("thermometer", "Next 24 hours", "Temperature and chance of rain"))
                st.plotly_chart(hourly_figure(wx), theme=None, config=PLOTLY_CONFIG, key="ov_hourly")
        with st.container(border=True, key="card_farm"):
            st.html(card_title("sprout", "Farm profile"))
            st.html(stat_list([
                ("Holding", f"{float(farm.get('acreage', 0) or 0):.1f} acres", None),
                ("Soil type", esc(str(farm.get("soil_type", "—"))), None),
                ("Primary crops", esc(str(farm.get("primary_crops", "—"))), None),
                ("Irrigation", esc(str(farm.get("irrigation_source", "—"))), None),
                ("Location", f"{esc(str(farm.get('village', '')))}, {esc(str(farm.get('district', '')))}", None),
            ]))

    # ---------------- Activity + quick actions ----------------
    col_act, col_qa = st.columns([1.5, 1])
    with col_act:
        with st.container(border=True, key="card_recent"):
            st.html(card_title("history", "Recent AI predictions", "Saved to your private reports"))
            user_preds = get_user_predictions(user["id"])
            if user_preds:
                rows = "".join(
                    f"""<div class="ki-row" style="justify-content:flex-start;">
                        <span class="ki-row-icon">{icon('file-text', 16)}</span>
                        <div style="min-width:0; flex:1;">
                            <div class="ki-row-title">{esc(p['title'])}</div>
                            <div class="ki-row-meta ki-num">{esc(p['module_name'])} · {p['created_at'][:16].replace('T', ' ')}</div>
                        </div>
                    </div>"""
                    for p in user_preds[:5]
                )
                st.html(f"<div>{rows}</div>")
            else:
                st.html(empty_state("inbox", "No predictions yet",
                                    "Saved fertilizer plans and market analyses will appear here."))
    with col_qa:
        with st.container(border=True, key="card_quick_actions"):
            st.html(card_title("zap", "Quick actions"))
            for key, label, _, target in QUICK_ACTIONS:
                if st.button(label, key=key, width="stretch"):
                    go_to(target)


# ==============================================================================
# PRICE FORECAST: TREND-SHIFT CALIBRATION HELPERS
# ==============================================================================
LOOKBACK_DAYS = {"1M": 31, "3M": 92, "6M": 183, "1Y": 366, "All": None}


def shift_banner_html(shift: dict, recal_on: bool) -> str:
    """Slim, non-intrusive status bar for the automatic pattern-change scan."""
    if shift.get("status") != "SUCCESS":
        tone, ic = "neutral", "info"
        title, meta = shift.get("headline", "Trend-shift scan unavailable"), shift.get("message", "")
        right = ""
    else:
        bw = shift["baseline_window"]
        level_part = f"level {shift['level_shift_pct']:+.1f}% vs {bw}-session moving average"
        if shift["detected"]:
            tone, ic = "warning", "activity"
            parts = [
                f"{shift['severity'].capitalize()} signal",
                f"recent {shift['recent_window']}-session slope {shift['recent_slope_per_obs']:+.2f} vs "
                f"historical {shift['baseline_slope_per_obs']:+.2f} ₹/kg per session",
                level_part,
            ]
            if shift.get("onset_date"):
                parts.append(f"onset ≈ {fmt_date(shift['onset_date'])}")
            meta = " · ".join(parts)
            right = (badge("Recalibration active", "positive", "refresh-cw") if recal_on
                     else badge("Recalibration recommended", "warning"))
        elif shift.get("within_noise"):
            tone, ic = "neutral", "activity"
            meta = (f"Above the ±{shift['slope_threshold_pct']:.0f}% threshold, but a typical swing for this market "
                    f"({shift['slope_variance_z']:+.2f}σ against its last {shift['reference_sessions']} sessions) · {level_part}")
            right = badge("Recalibration active", "positive", "refresh-cw") if recal_on else ""
        else:
            tone, ic = "positive", "circle-check"
            meta = f"Within the ±{shift['slope_threshold_pct']:.0f}% threshold · {level_part}"
            right = badge("Recalibration active", "positive", "refresh-cw") if recal_on else ""
        title = shift["headline"]

    color = TONES[tone]
    return f"""
    <div class="ki-banner" style="--tone:{color}; --tone-soft:{hex_alpha(color, 0.06)}; --tone-border:{hex_alpha(color, 0.25)};">
        <span class="ki-banner-icon">{icon(ic, 16)}</span>
        <div class="ki-banner-text">
            <span class="ki-banner-title ki-num">{title}</span>
            <span class="ki-banner-meta ki-num">{meta}</span>
        </div>
        {right}
    </div>"""


def build_forecast_figure(df_hist_series, target_market, latest_date, latest_price,
                          base_fc, eff_fc, recal_on, overlay_on, shift, lookback):
    fig = go.Figure()
    last_obs = pd.to_datetime(latest_date)
    window_days = LOOKBACK_DAYS.get(lookback)
    start = last_obs - pd.Timedelta(days=window_days) if window_days else None

    # Observed prices - deep forest for the modelled market, quieter tones for comparisons
    hist_tints = [COLORS["historical"], COLORS["text_secondary"], COLORS["sage"], COLORS["warning"], COLORS["text_muted"]]
    groups = sorted(df_hist_series.groupby("Market"), key=lambda kv: (kv[0] != target_market, kv[0]))
    for i, (m_name, g) in enumerate(groups):
        g = g.sort_values("date")
        if start is not None:
            g = g[g["date"] >= start]
        primary = i == 0
        fig.add_trace(go.Scatter(
            x=g["date"], y=g["modal_price_kg"], mode="lines",
            name=f"{m_name} · observed",
            line=dict(color=hist_tints[i % len(hist_tints)], width=1.75 if primary else 1.25),
            opacity=1.0 if primary else 0.85,
            hovertemplate="₹%{y:,.2f}/kg",
        ))

    fx = [last_obs] + list(pd.to_datetime(eff_fc["Arrival_Date"]))
    fy = [latest_price] + list(eff_fc["predicted_modal_price_kg"])
    fu = [latest_price] + list(eff_fc["confidence_upper_kg"])
    fl = [latest_price] + list(eff_fc["confidence_lower_kg"])

    fig.add_trace(go.Scatter(
        x=fx + fx[::-1], y=fu + fl[::-1], fill="toself",
        fillcolor=hex_alpha(COLORS["forecast"], 0.12), line=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip", name="90% confidence interval",
    ))

    if recal_on and overlay_on:
        fig.add_trace(go.Scatter(
            x=fx, y=[latest_price] + list(base_fc["predicted_modal_price_kg"]),
            mode="lines", name="Original forecast (unadjusted)",
            line=dict(color=COLORS["original"], width=2, dash="dot"),
            hovertemplate="₹%{y:,.2f}/kg",
        ))

    fig.add_trace(go.Scatter(
        x=fx, y=fy, mode="lines+markers",
        name="AI forecast (recalibrated)" if recal_on else "AI forecast",
        line=dict(color=COLORS["forecast"], width=2.25, dash="dash"),
        marker=dict(size=4, color=COLORS["forecast"]),
        hovertemplate="₹%{y:,.2f}/kg",
    ))

    if shift.get("detected") and shift.get("onset_date"):
        onset = pd.to_datetime(shift["onset_date"])
        fig.add_vrect(x0=onset, x1=last_obs, fillcolor=COLORS["warning"], opacity=0.08, line_width=0, layer="below")
        fig.add_annotation(
            x=onset, y=1, xref="x", yref="paper", text="Regime shift", showarrow=False,
            xanchor="left", yanchor="top", xshift=6, font=dict(color=COLORS["warning"], size=11),
        )

    fig.add_shape(type="line", x0=last_obs, x1=last_obs, y0=0, y1=1, xref="x", yref="paper",
                  line=dict(color=COLORS["border_strong"], width=1, dash="dot"))
    fig.add_annotation(x=last_obs, y=0, xref="x", yref="paper", text="Forecast", showarrow=False,
                       xanchor="left", yanchor="bottom", xshift=6, yshift=4, font=dict(color=COLORS["forecast"], size=11))

    style_figure(fig, height=420)
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0),
        margin=dict(l=4, r=4, t=12, b=4),
    )
    fig.update_yaxes(title_text="Wholesale price (₹/kg)", tickprefix="₹", tickformat=",.0f")
    fig.update_xaxes(showgrid=False, showspikes=True, spikecolor=COLORS["border_strong"], spikethickness=1,
                     spikedash="dot", spikemode="across")
    return fig


def apply_trend_settings(daily_series, fc_output):
    """Applies the shared Trend Shift recalibration to a forecast. Returns (frame, predictions, calibration)."""
    base_fc = fc_output["forecast_series"]
    if st.session_state.ts_recal:
        adjusted, calib = recalibrate_forecast(daily_series, base_fc, st.session_state.ts_sensitivity / 100.0)
        return adjusted, predictions_from_forecast(adjusted), calib
    return base_fc, fc_output.get("predictions", {}), None


def render_price_forecast(farm: dict):
    st.html(page_header(
        "chart-line", "Price Forecast",
        "Four years of APMC arrivals, a RandomForest lag model and storage-versus-spoilage economics "
        "for the sell decision. Trend Shift adjustments apply here automatically.", eyebrow="Markets"
    ))

    if not historical_data_available():
        st.html(empty_state(
            "database", "Historical price archive not found",
            "Add the 2023–2026 parquet files to <code>data/historical_parquet/parquet</code>, or set the "
            "<code>KRISHI_PARQUET_DIR</code> environment variable to the folder that contains them."
        ))
        return

    farm_state = farm.get("state", "Karnataka")
    f_meta = cached_filter_values("Tomato", farm_state)

    with st.container(border=True, key="card_pf_scope"):
        st.html(card_title("sliders-horizontal", "Market scope", "Commodity, geography and comparison markets to model."))
        c_pf1, c_pf2, c_pf3, c_pf4 = st.columns(4)
        with c_pf1:
            pf_crop = st.selectbox("Crop", f_meta["commodities"], index=f_meta["commodities"].index("Tomato") if "Tomato" in f_meta["commodities"] else 0)
        with c_pf2:
            st_opts = ["All States"] + f_meta["states"]
            pf_state = st.selectbox("State", st_opts, index=st_opts.index(farm_state) if farm_state in st_opts else 0)
        with c_pf3:
            sub_meta = cached_filter_values(pf_crop, pf_state)
            dst_opts = ["All Districts"] + sub_meta["districts"]
            pf_dist = st.selectbox("District", dst_opts, index=0)
        with c_pf4:
            mkt_meta = cached_filter_values(pf_crop, pf_state, pf_dist)
            m_opts = ["All Markets"] + mkt_meta["markets"]
            pf_market = st.selectbox("Market", m_opts, index=0)

        c_pf5, c_pf6 = st.columns([2, 1])
        with c_pf5:
            # Default to the farm's home market when it trades this crop, else the first market
            home = [m for m in (farm.get("district"), farm.get("village")) if m and m in mkt_meta["markets"]]
            pf_comp = st.multiselect("Overlay comparison markets", mkt_meta["markets"], default=home[:1] or mkt_meta["markets"][:1])
        with c_pf6:
            pf_horizon = st.selectbox("Forecast horizon", [3, 7, 14], index=1, format_func=lambda x: f"{x} days ahead")

    # The selected market is always queried, so it can be modelled even when it is not in the overlay list
    target_market = pf_market if pf_market != "All Markets" else None
    query_set = set(pf_comp) | ({target_market} if target_market else set())
    query_markets = tuple(sorted(query_set)) if query_set else None
    if target_market:
        scope_label = target_market
    elif len(pf_comp) == 1:
        scope_label = pf_comp[0]
    elif pf_comp:
        scope_label = "Average of " + ", ".join(pf_comp[:3]) + ("…" if len(pf_comp) > 3 else "")
    else:
        scope_label = f"All markets · {pf_dist if pf_dist != 'All Districts' else pf_state}"

    with st.spinner("Scanning the price archive and training the forecast model..."):
        df_hist_series = cached_price_history(pf_crop, pf_state, pf_dist, query_markets)
        if df_hist_series.empty:
            st.html(empty_state("inbox", "No price history for this selection",
                                "Try a different market, district or commodity."))
            return
        fc_output, df_target = cached_forecast(pf_crop, pf_state, pf_dist, query_markets, target_market)

    if fc_output.get("status") != "SUCCESS":
        st.html(empty_state("info", "Not enough observations to forecast", esc(fc_output.get("message", ""))))
        return

    daily_series = to_daily_series(df_target)
    ss = st.session_state
    shift = run_shift(daily_series)
    recal_on, overlay_on = bool(ss.ts_recal), bool(ss.ts_overlay)
    base_fc = fc_output["forecast_series"]
    eff_fc, eff_preds, _ = apply_trend_settings(daily_series, fc_output)

    # ---------------- KPI row ----------------
    lat_p = fc_output.get("latest_observed_price", float(df_hist_series["modal_price_kg"].iloc[-1]))
    mae_v = fc_output.get("metrics", {}).get("mae", 1.5)
    base_preds = fc_output.get("predictions", {})

    k1, k2, k3, k4, k5 = st.container(key="tiles_forecast").columns(5)
    with k1:
        st.html(kpi_card("Latest price", unit(count(lat_p, 2, "₹", key="pf_latest"), "/kg"),
                         fmt_date(fc_output.get("latest_observed_date", "")), "neutral", "calendar"))
    for col, h in zip((k2, k3, k4), (3, 7, 14)):
        p = eff_preds.get(f"{h}_day", {}).get("predicted_price_kg", lat_p)
        delta = p - lat_p
        pct = delta / lat_p * 100 if lat_p else 0.0
        sub = f"{delta:+.2f}/kg · {pct:+.1f}%"
        tag = ""
        if recal_on:
            base_p = base_preds.get(f"{h}_day", {}).get("predicted_price_kg", lat_p)
            sub += f'<div class="ki-kpi-base">Baseline ₹{base_p:.2f}</div>'
            tag = '<span class="ki-kpi-dot" title="Adjusted in Trend Shift"></span>'
        with col:
            st.html(kpi_card(f"{h}-day forecast", unit(count(p, 2, "₹", key=f"pf_p{h}"), "/kg"), sub,
                             "positive" if delta >= 0 else "risk",
                             "trending-up" if delta >= 0 else "trending-down",
                             highlight=(h == pf_horizon), tag_html=tag))
    with k5:
        st.html(kpi_card("Model error", unit(count(mae_v, 2, "±₹", key="pf_mae"), "/kg"),
                         "MAE, out-of-time test", "neutral", "target"))

    # ---------------- Pattern status, managed on the Trend Shift page ----------------
    b_left, b_right = st.columns([5, 1.15], vertical_alignment="center")
    with b_left:
        st.html(shift_banner_html(shift, recal_on))
    with b_right:
        if st.button("Adjust in Trend Shift", key="pf_open_ts", width="stretch"):
            go_to("Trend Shift")

    # ---------------- Forecast chart ----------------
    with st.container(border=True, key="card_forecast_chart"):
        h_left, h_right = st.columns([2, 1], vertical_alignment="center")
        with h_left:
            st.html(card_title("chart-line", f"{esc(pf_crop)} price history & forecast", esc(scope_label)))
        with h_right:
            lookback = st.segmented_control(
                "History window", list(LOOKBACK_DAYS.keys()), default="6M",
                key="pf_lookback", label_visibility="collapsed"
            ) or "6M"
        fig_fc = build_forecast_figure(
            df_hist_series, target_market or (pf_comp[0] if pf_comp else None),
            fc_output["latest_observed_date"], lat_p, base_fc, eff_fc,
            recal_on, overlay_on, shift, lookback
        )
        st.plotly_chart(fig_fc, theme=None, config=PLOTLY_CONFIG, key="pf_chart")

    # ---------------- Sell now vs wait ----------------
    with st.container(border=True, key="card_sell"):
        source_badge = (badge("Using recalibrated forecast", "positive", "refresh-cw") if recal_on
                        else badge("Using baseline forecast", "neutral"))
        st.html(card_title("scale", "Sell now or wait",
                           "Deterministic storage, spoilage and fee economics at the selected horizon.",
                           right_html=source_badge))

        c_dec1, c_dec2 = st.columns([1, 1.25])
        quantity = farm.get("acreage", 2.0) * 200.0
        with c_dec1:
            t_pred_price = eff_preds.get(f"{pf_horizon}_day", {}).get("predicted_price_kg", lat_p)
            st_cost = st.number_input("Daily storage cost (₹/kg/day)", value=0.15, step=0.05)
            spoil_pct = st.slider("Expected spoilage & weight loss (%)", 0.0, 20.0, 3.5 if pf_horizon == 7 else (1.5 if pf_horizon == 3 else 7.0), step=0.5)
            st.html(stat_list([
                (f"Forecast price in {pf_horizon} days", f"₹{t_pred_price:.2f}/kg", None),
                ("Current price", f"₹{lat_p:.2f}/kg", None),
                ("Quantity modelled", f"{quantity:,.0f} kg", None),
            ]))

        adv_res = evaluate_sell_timing(
            crop_name=pf_crop,
            quantity_kg=quantity,
            current_price_kg=lat_p,
            predicted_future_price_kg=t_pred_price,
            horizon_days=pf_horizon,
            daily_storage_cost_per_kg=st_cost,
            spoilage_pct=spoil_pct,
            forecast_mae=mae_v
        )

        with c_dec2:
            c = adv_res["badge_color"]
            diff = adv_res["net_difference"]
            now_html = count(adv_res["current_net_proceeds"], 0, "₹", key="sell_now")
            later_html = count(adv_res["future_net_proceeds"], 0, "₹", key="sell_later")
            diff_html = count(diff, 0, "₹", key="sell_diff", signed=True)
            st.html(f"""
            <div class="ki-decision">
                <div class="ki-eyebrow">Recommendation</div>
                <div class="ki-decision-title" style="color:{c};">{adv_res['recommendation'].title()}</div>
                <div class="ki-text">{adv_res['rationale']}</div>
                <div class="ki-decision-grid ki-num">
                    <div><div class="ki-eyebrow">Net if sold now</div><div class="ki-decision-num">{now_html}</div></div>
                    <div><div class="ki-eyebrow">Net after {pf_horizon} days</div><div class="ki-decision-num">{later_html}</div></div>
                    <div><div class="ki-eyebrow">Difference</div><div class="ki-decision-num" style="color:{COLORS['positive'] if diff >= 0 else COLORS['risk']};">{diff_html}</div></div>
                </div>
                <div class="ki-decision-action">{icon('arrow-right', 15)}<span><strong>Action</strong> · {adv_res['strategy']}</span></div>
            </div>
            """)


# ==============================================================================
# TREND SHIFT (standalone)
# ==============================================================================
def pattern_figure(daily: pd.Series, shift: dict, recent: int, baseline: int) -> go.Figure:
    """Observed prices with the historical trend, its continuation, and the recent trend."""
    lines = trend_lines(daily, recent, baseline)
    window_n = recent + baseline + 30
    s = daily.iloc[-window_n:]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name="Observed price",
                             line=dict(color=COLORS["historical"], width=1.5), hovertemplate="₹%{y:,.2f}/kg"))
    if lines:
        ma = lines["moving_average"].iloc[-window_n:]
        fig.add_trace(go.Scatter(x=ma.index, y=ma.values, mode="lines",
                                 name=f"Moving average ({max(5, baseline // 2)} sessions)",
                                 line=dict(color=COLORS["sage"], width=2), hovertemplate="₹%{y:,.2f}/kg"))
        split = lines["baseline_split"]
        bd, bf = lines["baseline_dates"], lines["baseline_fit"]
        fig.add_trace(go.Scatter(x=bd[:split], y=bf[:split], mode="lines", name="Historical trend",
                                 line=dict(color=COLORS["forest"], width=2.25), hovertemplate="₹%{y:,.2f}/kg"))
        fig.add_trace(go.Scatter(x=bd[split - 1:], y=bf[split - 1:], mode="lines", name="Historical trend, continued",
                                 line=dict(color=COLORS["forest"], width=2, dash="dot"), hovertemplate="₹%{y:,.2f}/kg"))
        fig.add_trace(go.Scatter(x=lines["recent_dates"], y=lines["recent_fit"], mode="lines", name="Recent trend",
                                 line=dict(color=COLORS["warning"], width=3), hovertemplate="₹%{y:,.2f}/kg"))
    if shift.get("detected") and shift.get("onset_date"):
        fig.add_vrect(x0=pd.to_datetime(shift["onset_date"]), x1=s.index[-1], fillcolor=COLORS["warning"],
                      opacity=0.08, line_width=0, layer="below")
    style_figure(fig, height=360)
    fig.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="top", y=-0.14, x=0))
    fig.update_yaxes(tickprefix="₹", tickformat=",.0f")
    fig.update_xaxes(showgrid=False)
    return fig


def comparison_figure(daily: pd.Series, base_fc, adj_fc, recal_on: bool, overlay_on: bool,
                      latest_date, latest_price) -> go.Figure:
    tail = daily.iloc[-30:]
    last = pd.to_datetime(latest_date)
    fx = [last] + list(pd.to_datetime(adj_fc["Arrival_Date"]))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tail.index, y=tail.values, mode="lines", name="Observed",
                             line=dict(color=COLORS["historical"], width=1.5), hovertemplate="₹%{y:,.2f}/kg"))
    fu = [latest_price] + list(adj_fc["confidence_upper_kg"])
    fl = [latest_price] + list(adj_fc["confidence_lower_kg"])
    fig.add_trace(go.Scatter(x=fx + fx[::-1], y=fu + fl[::-1], fill="toself", hoverinfo="skip",
                             fillcolor=hex_alpha(COLORS["forecast"], 0.12), line=dict(color="rgba(0,0,0,0)"),
                             name="90% confidence interval"))
    if recal_on and overlay_on:
        fig.add_trace(go.Scatter(x=fx, y=[latest_price] + list(base_fc["predicted_modal_price_kg"]), mode="lines",
                                 name="Original prediction", line=dict(color=COLORS["original"], width=2, dash="dot"),
                                 hovertemplate="₹%{y:,.2f}/kg"))
    fig.add_trace(go.Scatter(x=fx, y=[latest_price] + list(adj_fc["predicted_modal_price_kg"]), mode="lines+markers",
                             name="Adjusted prediction" if recal_on else "Prediction",
                             line=dict(color=COLORS["forecast"], width=2.25, dash="dash"), marker=dict(size=4),
                             hovertemplate="₹%{y:,.2f}/kg"))
    fig.add_shape(type="line", x0=last, x1=last, y0=0, y1=1, xref="x", yref="paper",
                  line=dict(color=COLORS["border_strong"], width=1, dash="dot"))
    style_figure(fig, height=300)
    fig.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="top", y=-0.16, x=0))
    fig.update_yaxes(tickprefix="₹", tickformat=",.0f")
    fig.update_xaxes(showgrid=False)
    return fig


def history_figure(hist: pd.DataFrame, threshold: float) -> go.Figure:
    fig = go.Figure()
    fig.add_hrect(y0=-threshold, y1=threshold, fillcolor=COLORS["grid"], opacity=0.7, line_width=0, layer="below")
    fig.add_trace(go.Scatter(x=hist["date"], y=hist["slope_variance_pct"], mode="lines", name="Slope variance",
                             line=dict(color=COLORS["forest"], width=1.5), hovertemplate="%{y:+.1f}%"))
    flagged = hist[hist["detected"]]
    fig.add_trace(go.Scatter(x=flagged["date"], y=flagged["slope_variance_pct"], mode="markers", name="Shift flagged",
                             marker=dict(color=COLORS["warning"], size=6), hovertemplate="%{y:+.1f}% · flagged"))
    for y in (threshold, -threshold):
        fig.add_hline(y=y, line=dict(color=COLORS["warning"], width=1, dash="dot"))
    style_figure(fig, height=240)
    fig.update_layout(hovermode="x unified", showlegend=False)
    fig.update_yaxes(ticksuffix="%", zeroline=True, zerolinecolor=COLORS["border_strong"])
    fig.update_xaxes(showgrid=False)
    return fig


def render_trend_shift(farm: dict):
    st.html(page_header(
        "activity", "Trend Shift",
        "Spots when recent prices break from their historical pattern, then re-weights predictions toward "
        "the new pattern. Adjustments made here also apply to Price Forecast.", eyebrow="Markets"))

    if not historical_data_available():
        st.html(empty_state("database", "Historical price archive not found",
                            "Add the 2023–2026 parquet files to <code>data/historical_parquet/parquet</code> or set <code>KRISHI_PARQUET_DIR</code>."))
        return

    farm_state = farm.get("state", "Karnataka")
    f_meta = cached_filter_values("Tomato", farm_state)
    with st.container(border=True, key="card_ts_scope"):
        st.html(card_title("sliders-horizontal", "Market & detection settings"))
        c1, c2, c3 = st.columns(3)
        with c1:
            crops = f_meta["commodities"]
            primary = (farm.get("primary_crops") or "Tomato").split(",")[0].strip()
            default_idx = crops.index(primary) if primary in crops else (crops.index("Tomato") if "Tomato" in crops else 0)
            ts_crop = st.selectbox("Crop", crops, index=default_idx, key="tsp_crop")
        with c2:
            states = f_meta["states"]
            ts_state = st.selectbox("State", states, index=states.index(farm_state) if farm_state in states else 0, key="tsp_state")
        with c3:
            markets = cached_filter_values(ts_crop, ts_state, "All Districts")["markets"]
            home = [m for m in (farm.get("district"), farm.get("village")) if m and m in markets]
            if markets:
                ts_market = st.selectbox("Market", markets, index=markets.index(home[0]) if home else 0, key="tsp_market")
            else:
                st.selectbox("Market", ["No markets"], disabled=True, key="tsp_market_none")
                ts_market = None
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.selectbox("Recent window (sessions)", [7, 14, 21, 30], key="ts_recent",
                         help="How many of the latest trading sessions count as the current pattern.")
        with d2:
            st.selectbox("Historical window (sessions)", [30, 60, 90, 120], key="ts_baseline",
                         help="The sessions before the recent window that define the established pattern.")
        with d3:
            st.slider("Detection threshold", 5, 30, step=1, key="ts_threshold", format="±%d%%",
                      help="Slope variance must exceed this to count as a pattern shift.")
        with d4:
            st.selectbox("Significance", [0.0, 1.5, 2.0, 2.5], key="ts_signif",
                         format_func=lambda z: "Off (threshold only)" if not z else f"{z:g}σ vs this market's history",
                         help="Volatile crops cross a fixed % threshold all the time. With significance on, the "
                              "slope variance must also be unusual compared with this market's last 250 sessions.")

    if not ts_market:
        st.html(empty_state("inbox", "No markets for this crop", "Choose another crop or state."))
        return

    ss = st.session_state
    with st.spinner("Loading price history..."):
        fc_output, df_target = cached_forecast(ts_crop, ts_state, "All Districts", (ts_market,), None)
    if fc_output.get("status") != "SUCCESS":
        st.html(empty_state("info", "Not enough history for this market", esc(fc_output.get("message", ""))))
        return
    daily = to_daily_series(df_target)
    shift = run_shift(daily)
    if shift.get("status") != "SUCCESS":
        st.html(empty_state("info", "Not enough history to scan", esc(shift.get("message", ""))))
        return

    st.html(shift_banner_html(shift, bool(ss.ts_recal)))

    slope_flag = shift["primary_signal"] == "slope"
    sv_z = shift.get("slope_variance_z")
    sv_sub = f"Threshold ±{shift['slope_threshold_pct']:.0f}%" + (f" · {sv_z:+.2f}σ vs history" if sv_z is not None else "")
    t1, t2, t3, t4 = st.container(key="tiles_trendshift").columns(4)
    with t1:
        st.html(kpi_card("Slope variance", unit(count(shift["slope_variance_pct"], 1, key="ts_sv", signed=True), "%"),
                         sv_sub, "warning" if slope_flag else ("neutral" if shift.get("within_noise") else "positive"), "activity"))
    with t2:
        st.html(kpi_card(f"Level vs {shift['baseline_window']}-session average",
                         unit(count(shift["level_shift_pct"], 1, key="ts_lv", signed=True), "%"),
                         f"z-score {shift['level_z']:+.2f}", "warning" if abs(shift["level_z"]) >= 2 else "neutral", "gauge"))
    with t3:
        st.html(kpi_card("Recent slope", unit(count(shift["recent_slope_per_obs"], 2, "₹", key="ts_rs", signed=True), "/kg per session"),
                         f"Last {shift['recent_window']} sessions", "neutral",
                         "trending-up" if shift["recent_slope_per_obs"] >= 0 else "trending-down"))
    with t4:
        st.html(kpi_card("Historical slope", unit(count(shift["baseline_slope_per_obs"], 2, "₹", key="ts_hs", signed=True), "/kg per session"),
                         f"Previous {shift['baseline_window']} sessions", "neutral",
                         "trending-up" if shift["baseline_slope_per_obs"] >= 0 else "trending-down"))

    col_chart, col_panel = st.columns([2.45, 1])
    with col_panel:
        with st.container(border=True, key="card_ts_calibration"):
            st.html(card_title("sliders-horizontal", "Adjust predictions",
                               "Weight recent sessions more heavily so predictions follow the new pattern."))
            recal_on = st.toggle("Adaptive recalibration", key="ts_recal",
                                 help="Blends a damped exponential-smoothing projection of recent prices into the AI forecast.")
            st.slider("Recency bias", 0, 100, step=5, key="ts_sensitivity", format="%d%%", disabled=not recal_on,
                      help="How strongly predictions react to the recent pattern.")
            st.html("""<div class="ki-scale-labels"><span>Conservative<br><em>Historical weight</em></span>
            <span style="text-align:right;">Aggressive<br><em>Recent trend weight</em></span></div>""")
            overlay_on = st.toggle("Comparison overlay", key="ts_overlay", disabled=not recal_on,
                                   help="Show the original prediction as a dotted line.")
            readout = st.empty()
    with col_chart:
        with st.container(border=True, key="card_ts_pattern"):
            st.html(card_title("chart-line", "What changed",
                               f"{esc(ts_crop)} · {esc(ts_market)} · the recent trend against the established one"))
            st.plotly_chart(pattern_figure(daily, shift, ss.ts_recent, ss.ts_baseline),
                            theme=None, config=PLOTLY_CONFIG, key="ts_pattern")

    base_fc = fc_output["forecast_series"]
    adj_fc, _, calib = apply_trend_settings(daily, fc_output)
    if calib and calib.get("applied"):
        adj = calib["final_adjustment_kg"]
        adj_html = count(adj, 2, key="ts_adj", signed=True)
        adj_color = COLORS["positive"] if adj >= 0 else COLORS["risk"]
        params_html = stat_list([
            ("Recent-trend weight", f"{calib['blend'] * 100:.0f}%", None),
            ("Smoothing α", f"{calib['alpha']:.2f}", None),
            ("Trend damping φ", f"{calib['phi']:.2f}", None),
        ], compact=True)
        readout.html(f"""
        <div class="ki-readout">
            <div class="ki-eyebrow">14-day adjustment</div>
            <div class="ki-readout-value ki-num" style="color:{adj_color};">{adj_html} <span class="ki-unit">₹/kg</span></div>
            <div class="ki-readout-sub ki-num">{calib['final_adjustment_pct']:+.1f}% vs original prediction</div>
            {params_html}
        </div>""")
    else:
        readout.html('<div class="ki-hint">Recalibration is off. Predictions use the model as trained.</div>')

    col_cmp, col_tbl = st.columns([1.5, 1])
    with col_cmp:
        with st.container(border=True, key="card_ts_compare"):
            st.html(card_title("target", "Next 14 days", "Original vs adjusted prediction"))
            st.plotly_chart(comparison_figure(daily, base_fc, adj_fc, recal_on, overlay_on,
                                              fc_output["latest_observed_date"], fc_output["latest_observed_price"]),
                            theme=None, config=PLOTLY_CONFIG, key="ts_compare")
    with col_tbl:
        with st.container(border=True, key="card_ts_table"):
            st.html(card_title("calendar", "Day by day", "₹/kg"))
            table = pd.DataFrame({
                "Date": pd.to_datetime(adj_fc["Arrival_Date"]).dt.strftime("%d %b"),
                "Original": base_fc["predicted_modal_price_kg"].round(2).values,
                "Adjusted": adj_fc["predicted_modal_price_kg"].round(2).values,
            })
            table["Change"] = (table["Adjusted"] - table["Original"]).round(2)
            st.dataframe(table, hide_index=True, height=300, column_config={
                "Original": st.column_config.NumberColumn(format="%.2f"),
                "Adjusted": st.column_config.NumberColumn(format="%.2f"),
                "Change": st.column_config.NumberColumn(format="%+.2f"),
            })

    with st.container(border=True, key="card_ts_history"):
        hist = cached_shift_history(ts_crop, ts_state, ts_market, ss.ts_recent, ss.ts_baseline, ss.ts_threshold, ss.ts_signif)
        n_flag = int(hist["detected"].sum()) if not hist.empty else 0
        st.html(card_title("history", "Signal history",
                           f"Shift flagged on {n_flag} of the last {len(hist)} sessions · shaded band is the ±{ss.ts_threshold}% threshold"))
        if hist.empty:
            st.html(empty_state("info", "Not enough history", "The detector needs more sessions for this market."))
        else:
            st.plotly_chart(history_figure(hist, ss.ts_threshold), theme=None, config=PLOTLY_CONFIG, key="ts_history")


# ==============================================================================
# BUYER NETWORK (farmers)
# ==============================================================================
REQUEST_TONES = {"pending": "warning", "accepted": "positive", "declined": "risk", "withdrawn": "neutral"}


def flash(text: str):
    """Message shown as a toast after the next rerun."""
    st.session_state["flash"] = text


def buyer_row_html(m: dict) -> str:
    industrial = m["buyer_type"] in ("Food Processor", "Exporter")
    badges = badge(m["buyer_type"], "info", "factory" if industrial else "store")
    if m["is_local"]:
        badges += " " + badge("Local", "positive", "map-pin")
    if m["is_demo"]:
        badges += " " + badge("Demo listing", "neutral")
    fair = m.get("fairness")
    fair_html = badge(fair["status"].title(), color=fair["color"]) if fair else ""
    reasons = " ".join(badge(r, "risk", "x") for r in m["reasons"])
    rng = f"{m['min_qty_kg']:,.0f}–{m['max_qty_kg']:,.0f} kg"
    transport = "Buyer collects" if m["buyer_collects"] else f"You deliver · freight {money(m['transport_cost'], 0)}"
    notes = f'<div class="ki-row-body">{esc(m["notes"])}</div>' if m.get("notes") else ""
    muted = " ki-buyer--muted" if not m["eligible"] else ""
    return f"""
    <div class="ki-buyer{muted}">
        <div class="ki-buyer-head"><span class="ki-buyer-name">{esc(m['business_name'])}</span>{badges}</div>
        <div class="ki-row-meta ki-num">{esc(m['location_label'])} · {m['distance_km']:,.0f} km · {transport} · {esc(m['payment_terms'])}</div>
        <div class="ki-buyer-stats ki-num">
            <div><div class="ki-eyebrow">Quote · {esc(m['grade'])}</div><div class="ki-buyer-num">₹{m['price_per_kg']:.2f}<span class="ki-unit">/kg</span></div></div>
            <div><div class="ki-eyebrow">Can take</div><div class="ki-buyer-num">{m['sellable_kg']:,.0f}<span class="ki-unit">kg</span></div><div class="ki-row-meta">{rng}</div></div>
            <div><div class="ki-eyebrow">You take home</div><div class="ki-buyer-num">{money(m['net_value'], 0)}</div><div class="ki-row-meta">{money(m['net_per_kg'])}/kg net</div></div>
        </div>
        <div class="ki-buyer-foot">{fair_html} {reasons}</div>
        {notes}
    </div>"""


def render_buyer_network(user: dict, farm: dict):
    st.html(page_header(
        "store", "Buyer Network",
        "Local dealers and agro-industries post what they want to buy. Describe your lot to see who pays you "
        "the most after transport, then send a request.", eyebrow="Markets"))

    commodities = quoted_commodities()
    if not commodities:
        st.html(empty_state("store", "No buyers are quoting yet",
                            "When dealers and industries publish quotations, they will appear here."))
        return

    farm_crops = [c.strip() for c in (farm.get("primary_crops") or "").split(",") if c.strip()]
    crop_opts = sorted(set(commodities) | set(farm_crops))
    default_crop = next((c for c in farm_crops if c in commodities), commodities[0])
    veh_opts = list(DEFAULT_VEHICLE_CONFIGS.keys())

    with st.container(border=True, key="card_bn_lot"):
        st.html(card_title("package", "Your lot", "What you want to sell"))
        c1, c2, c3, c4, c5 = st.columns([1.1, 1, 1, 1.3, 1.3])
        with c1:
            crop = st.selectbox("Crop", crop_opts, index=crop_opts.index(default_crop), key="bn_crop")
        with c2:
            qty = st.number_input("Quantity (kg)", min_value=50.0, max_value=100000.0,
                                  value=float(round((farm.get("acreage") or 2.5) * 200, -1)), step=50.0, key="bn_qty")
        with c3:
            grade = st.selectbox("Grade", FARMER_GRADES, key="bn_grade")
        with c4:
            veh = st.selectbox("Your vehicle (if you deliver)", veh_opts, key="bn_vehicle")
        with c5:
            max_km = st.slider("Search radius", 10, 600, 200, step=10, format="%d km", key="bn_radius")

    farm_state = farm.get("state", "Karnataka")
    fair = cached_fair_price(crop, farm_state)
    matches = match_buyers(list_open_quotations(crop), qty, grade,
                           farm.get("latitude", 12.7209), farm.get("longitude", 77.2799),
                           DEFAULT_VEHICLE_CONFIGS[veh], fair, max_km)
    eligible = [m for m in matches if m["eligible"]]
    my_requests = list_farmer_requests(user["id"])
    open_req = {r["quotation_id"]: r for r in my_requests if r["status"] in ("pending", "accepted")}

    t1, t2, t3, t4 = st.container(key="tiles_buyers").columns(4)
    with t1:
        st.html(kpi_card("Matching buyers", count(len(eligible), 0, key="bn_n"),
                         f"of {len(matches)} quoting for {esc(crop)}", "positive" if eligible else "neutral", "users"))
    with t2:
        if eligible:
            st.html(kpi_card("Best take-home", unit(count(eligible[0]["net_per_kg"], 2, "₹", key="bn_best"), "/kg"),
                             esc(eligible[0]["business_name"]), "positive", "award"))
        else:
            st.html(kpi_card("Best take-home", "—", "No buyer fits this lot yet", "neutral", "award"))
    with t3:
        n_local = sum(1 for m in eligible if m["is_local"])
        st.html(kpi_card("Local buyers", count(n_local, 0, key="bn_local"),
                         f"Within {LOCAL_RADIUS_KM:.0f} km of your farm", "neutral", "map-pin"))
    with t4:
        fair_value = unit(count(fair, 2, "₹", key="bn_fair"), "/kg") if fair else "—"
        st.html(kpi_card("Fair mandi price", fair_value, "APMC benchmark used to rate quotes", "neutral", "scale"))

    col_list, col_side = st.columns([1.7, 1])
    with col_list:
        with st.container(border=True, key="card_bn_buyers"):
            st.html(card_title("users", "Ranked buyers", "Sorted by what you take home per kg, after freight"))
            if not matches:
                st.html(empty_state("inbox", f"No quotations for {esc(crop)}",
                                    "Try another crop, or check back when more buyers have posted."))
            for m in matches:
                r1, r2 = st.columns([3.4, 1], vertical_alignment="center")
                with r1:
                    st.html(buyer_row_html(m))
                with r2:
                    existing = open_req.get(m["id"])
                    if existing:
                        status_badge = badge("Request " + existing["status"], REQUEST_TONES[existing["status"]])
                        st.html(f'<div style="text-align:right;">{status_badge}</div>')
                    elif m["eligible"]:
                        with st.popover("Connect", width="stretch"):
                            with st.form(key=f"bn_form_{m['id']}", border=False):
                                st.html(card_title("send", f"Request to {esc(m['business_name'])}"))
                                r_qty = st.number_input("Quantity (kg)", min_value=max(1.0, float(m["min_qty_kg"])),
                                                        max_value=float(m["max_qty_kg"]), value=float(m["sellable_kg"]), step=50.0)
                                r_price = st.number_input("Your price (₹/kg)", min_value=0.5, value=float(m["price_per_kg"]), step=0.5)
                                r_msg = st.text_area("Message", placeholder="Harvest date, variety, packing...", height=80)
                                if st.form_submit_button("Send request", type="primary", width="stretch"):
                                    ok, msg = create_connection_request(m["id"], user["id"], r_qty, r_price, r_msg)
                                    flash(msg)
                                    st.rerun()
                st.html('<div class="ki-sep-line"></div>')

    with col_side:
        with st.container(border=True, key="card_bn_map"):
            st.html(card_title("map-pin", "Buyers near you", "Your farm and quoting buyers"))
            pts = [{"lat": farm.get("latitude", 12.7209), "lon": farm.get("longitude", 77.2799),
                    "color": COLORS["forest"], "size": 3500}]
            pts += [{"lat": m["latitude"], "lon": m["longitude"],
                     "color": COLORS["accent"] if m["eligible"] else COLORS["sage"], "size": 2500} for m in matches]
            st.map(pd.DataFrame(pts), latitude="lat", longitude="lon", color="color", size="size", height=280)
            legend = (f'{icon("circle-dot", 12, COLORS["forest"])} Your farm &nbsp; '
                      f'{icon("circle-dot", 12, COLORS["accent"])} Match &nbsp; '
                      f'{icon("circle-dot", 12, COLORS["sage"])} Not a match')
            st.html(f'<div class="ki-row-meta" style="margin-top:8px;">{legend}</div>')

        with st.container(border=True, key="card_bn_requests"):
            st.html(card_title("send", "Your requests", "Contact details appear once a buyer accepts"))
            if not my_requests:
                st.html('<div class="ki-hint">No requests yet. Use Connect on a buyer to send one.</div>')
            for r in my_requests[:8]:
                contact = (f'<div class="ki-row-body">{icon("phone", 13)} {esc(r["buyer_phone"])}</div>'
                           if r.get("buyer_phone") else "")
                status_badge = badge(r["status"].capitalize(), REQUEST_TONES.get(r["status"], "neutral"))
                st.html(f"""
                <div class="ki-row" style="align-items:flex-start;">
                    <div style="min-width:0;">
                        <div class="ki-row-title">{esc(r['business_name'])}</div>
                        <div class="ki-row-meta ki-num">{esc(r['commodity'])} · {r['quantity_kg']:,.0f} kg at ₹{r['asking_price_kg']:.2f}/kg · {r['created_at'][:10]}</div>
                        {contact}
                    </div>
                    {status_badge}
                </div>""")
                if r["status"] == "pending":
                    if st.button("Withdraw", key=f"bn_wd_{r['id']}"):
                        withdraw_request(r["id"], user["id"])
                        flash("Request withdrawn.")
                        st.rerun()


# ==============================================================================
# BUYER DESK (dealers & industries)
# ==============================================================================
def render_business_form(user: dict, profile: Optional[dict]):
    locations = location_options()
    labels = sorted(locations)
    current = (profile or {}).get("location_label") or "Bangalore, Karnataka"
    if current not in labels:
        labels = [current] + labels
    with st.container(border=True, key="card_business"):
        st.html(card_title("store", "Business profile", "Farmers see this next to your quotations"))
        name = st.text_input("Business name", value=(profile or {}).get("business_name", ""), key="bp_name")
        b1, b2 = st.columns(2)
        with b1:
            type_idx = BUYER_TYPES.index(profile["buyer_type"]) if profile and profile["buyer_type"] in BUYER_TYPES else 0
            btype = st.selectbox("Buyer type", BUYER_TYPES, index=type_idx, key="bp_type")
        with b2:
            loc = st.selectbox("Location", labels, index=labels.index(current), key="bp_loc",
                               help="Used to compute road distance and freight to farmers.")
        phone = st.text_input("Business phone", value=(profile or {}).get("phone") or user.get("phone") or "", key="bp_phone",
                              help="Shared with a farmer only after you accept their request.")
        desc = st.text_area("What you buy", value=(profile or {}).get("description") or "", height=80, key="bp_desc")
        if st.button("Save profile", type="primary", key="bp_save"):
            if loc in locations:
                lat, lon = locations[loc]
            else:
                lat, lon = (profile or {}).get("latitude"), (profile or {}).get("longitude")
            ok, msg = upsert_buyer_profile(user["id"], {
                "business_name": name, "buyer_type": btype, "location_label": loc,
                "latitude": lat, "longitude": lon, "phone": phone, "description": desc,
            })
            if ok:
                flash(msg)
                st.rerun()
            st.error(msg)


def render_buyer_onboarding(user: dict):
    st.html(page_header("store", "Set up your buyer profile",
                        "Tell farmers who you are and where you buy. You can post quotations right after.",
                        eyebrow="Buyer desk"))
    _, mid, _ = st.columns([0.2, 1, 0.2])
    with mid:
        render_business_form(user, None)


def render_buyer_requests(user: dict, profile: dict):
    st.html(page_header("inbox", "Requests",
                        "Farmers who want to sell to you. Accepting shares contact details on both sides.",
                        eyebrow="Buyer desk"))
    reqs = list_buyer_requests(profile["id"])
    quotes = list_buyer_quotations(profile["id"])
    pending = [r for r in reqs if r["status"] == "pending"]
    t1, t2, t3, t4 = st.container(key="tiles_brequests").columns(4)
    with t1:
        st.html(kpi_card("Open quotations", count(sum(1 for q in quotes if q["status"] == "open"), 0, key="br_q"),
                         f"{len(quotes)} published in total", "neutral", "file-text"))
    with t2:
        st.html(kpi_card("Pending requests", count(len(pending), 0, key="br_p"), "Waiting for your answer",
                         "warning" if pending else "neutral", "inbox"))
    with t3:
        st.html(kpi_card("Accepted", count(sum(1 for r in reqs if r["status"] == "accepted"), 0, key="br_a"),
                         "Contacts shared", "positive", "check"))
    with t4:
        st.html(kpi_card("Volume offered", unit(count(sum(r["quantity_kg"] for r in pending), 0, key="br_v"), "kg"),
                         "Across pending requests", "neutral", "package"))

    with st.container(border=True, key="card_br_list"):
        st.html(card_title("users", "Incoming requests"))
        if not reqs:
            st.html(empty_state("inbox", "No requests yet",
                                "Farmers see your open quotations in their Buyer Network and can send requests."))
        for r in reqs:
            dist = ""
            if r.get("farm_lat") is not None:
                km, _ = estimate_road_distance_demo(profile["latitude"], profile["longitude"], r["farm_lat"], r["farm_lon"])
                dist = f" · {km:,.0f} km from you"
            vs_quote = money(r["asking_price_kg"] - r["price_per_kg"], 2, signed=True)
            contact = (f'<div class="ki-row-body">{icon("phone", 13)} {esc(r["farmer_phone"])}</div>'
                       if r.get("farmer_phone") else "")
            message = (f'<div class="ki-quote" style="margin-top:8px; padding:10px 12px;">{esc(r["message"])}</div>'
                       if r.get("message") else "")
            status_badge = badge(r["status"].capitalize(), REQUEST_TONES.get(r["status"], "neutral"))
            place = f"{esc(str(r.get('farm_name') or ''))} · {esc(str(r.get('village') or ''))}, {esc(str(r.get('district') or ''))}"
            r1, r2 = st.columns([3.4, 1], vertical_alignment="center")
            with r1:
                st.html(f"""
                <div class="ki-buyer">
                    <div class="ki-buyer-head"><span class="ki-buyer-name">{esc(r['farmer_name'])}</span>{status_badge}</div>
                    <div class="ki-row-meta ki-num">{place}{dist}</div>
                    <div class="ki-buyer-stats ki-num">
                        <div><div class="ki-eyebrow">Crop</div><div class="ki-buyer-num">{esc(r['commodity'])}</div></div>
                        <div><div class="ki-eyebrow">Quantity</div><div class="ki-buyer-num">{r['quantity_kg']:,.0f}<span class="ki-unit">kg</span></div></div>
                        <div><div class="ki-eyebrow">Asking</div><div class="ki-buyer-num">₹{r['asking_price_kg']:.2f}<span class="ki-unit">/kg</span></div>
                            <div class="ki-row-meta">{vs_quote} vs your ₹{r['price_per_kg']:.2f}</div></div>
                    </div>
                    {contact}{message}
                </div>""")
            with r2:
                if r["status"] == "pending":
                    if st.button("Accept", key=f"br_acc_{r['id']}", type="primary", width="stretch"):
                        respond_to_request(r["id"], profile["id"], True)
                        flash("Request accepted. Contact details are now shared.")
                        st.rerun()
                    if st.button("Decline", key=f"br_dec_{r['id']}", width="stretch"):
                        respond_to_request(r["id"], profile["id"], False)
                        flash("Request declined.")
                        st.rerun()
            st.html('<div class="ki-sep-line"></div>')


def render_buyer_quotations(user: dict, profile: dict):
    st.html(page_header("file-text", "Quotations",
                        "Tell farmers what you buy, at what price and in what quantity.", eyebrow="Buyer desk"))
    buyer_state = (profile.get("location_label") or "").split(",")[-1].strip() or "Karnataka"
    crops = sorted(df_market["commodity"].unique())
    col_form, col_list = st.columns([1, 1.35])
    with col_form:
        with st.container(border=True, key="card_bq_new"):
            st.html(card_title("plus", "New quotation"))
            commodity = st.selectbox("Crop", crops, index=crops.index("Tomato") if "Tomato" in crops else 0, key="bq_crop")
            g1, g2 = st.columns(2)
            with g1:
                grade = st.selectbox("Grade", GRADES, key="bq_grade")
            with g2:
                price = st.number_input("Price (₹/kg)", min_value=0.5, value=15.0, step=0.5, key="bq_price")
            q1, q2 = st.columns(2)
            with q1:
                qmin = st.number_input("Minimum (kg)", min_value=0.0, value=200.0, step=50.0, key="bq_min")
            with q2:
                qmax = st.number_input("Maximum (kg)", min_value=50.0, value=3000.0, step=50.0, key="bq_max")
            terms = st.selectbox("Payment terms", PAYMENT_TERMS, key="bq_terms")
            pickup = st.selectbox("Pickup", PICKUP_OPTIONS, key="bq_pickup")
            notes = st.text_area("Notes for farmers", placeholder="Quality, packing, timing...", height=70, key="bq_notes")

            fair = cached_fair_price(commodity, buyer_state)
            if fair:
                audit = evaluate_buyer_offer(price, max(qmax, 1.0), fair, fair * 0.88, payment_terms=terms)
                st.html(callout(
                    "scale", f"Farmers will see this quote as: {audit['status'].title()}",
                    f"Fair mandi price for {esc(commodity)} is about <span class='ki-num'>₹{fair:.2f}/kg</span> "
                    f"(APMC benchmark). Your quote is <span class='ki-num'>{audit['delta_pct']:+.1f}%</span> against farmgate parity.",
                    tone="positive" if audit["delta_pct"] >= -8 else "warning"))
            if st.button("Publish quotation", type="primary", width="stretch", key="bq_publish"):
                ok, msg = create_quotation(profile["id"], {
                    "commodity": commodity, "grade": grade, "price_per_kg": price, "min_qty_kg": qmin,
                    "max_qty_kg": qmax, "payment_terms": terms, "pickup": pickup, "notes": notes,
                })
                if ok:
                    flash(msg)
                    st.rerun()
                st.error(msg)

    with col_list:
        with st.container(border=True, key="card_bq_list"):
            quotes = list_buyer_quotations(profile["id"])
            st.html(card_title("file-text", "Your quotations", f"{len(quotes)} published"))
            if not quotes:
                st.html(empty_state("inbox", "No quotations yet", "Publish one to start receiving requests from farmers."))
            for q in quotes:
                is_open = q["status"] == "open"
                n_pend = q["pending_requests"]
                pend = f" · {n_pend} pending request{'s' if n_pend != 1 else ''}" if n_pend else ""
                state_badge = badge("Open" if is_open else "Closed", "positive" if is_open else "neutral")
                r1, r2 = st.columns([3, 1], vertical_alignment="center")
                with r1:
                    st.html(f"""
                    <div class="ki-row" style="border-bottom:none; padding:6px 0;">
                        <div style="min-width:0;">
                            <div class="ki-row-title">{esc(q['commodity'])} · ₹{q['price_per_kg']:.2f}/kg {state_badge}</div>
                            <div class="ki-row-meta ki-num">{esc(q['grade'])} · {q['min_qty_kg']:,.0f}–{q['max_qty_kg']:,.0f} kg · {esc(q['payment_terms'])} · {esc(q['pickup'])}{pend}</div>
                        </div>
                    </div>""")
                with r2:
                    if st.button("Close" if is_open else "Reopen", key=f"bq_tg_{q['id']}", width="stretch"):
                        set_quotation_status(q["id"], profile["id"], "closed" if is_open else "open")
                        flash("Quotation closed." if is_open else "Quotation reopened.")
                        st.rerun()
                st.html('<div class="ki-sep-line"></div>')


def render_buyer_settings(user: dict, profile: dict):
    st.html(page_header("store", "Business profile", "How farmers see your business, and your password.",
                        eyebrow="Account"))
    c1, c2 = st.columns([1.3, 1])
    with c1:
        render_business_form(user, profile)
    with c2:
        with st.container(border=True, key="card_bsecurity"):
            st.html(card_title("lock", "Password"))
            old_pwd = st.text_input("Current password", type="password", key="bs_old")
            new_pwd = st.text_input("New password", type="password", key="bs_new")
            new_pwd_conf = st.text_input("Confirm new password", type="password", key="bs_conf")
            if st.button("Update password", key="btn_update_pwd"):
                if new_pwd != new_pwd_conf:
                    st.error("New passwords do not match.")
                else:
                    ch_ok, ch_msg = change_user_password(user["id"], old_pwd, new_pwd)
                    if ch_ok:
                        st.success(ch_msg)
                    else:
                        st.error(ch_msg)


# ==============================================================================
# FERTILIZER ADVISOR
# ==============================================================================
def render_fertilizer(farm: dict):
    st.html(page_header("package", "Fertilizer Advisor",
                        "Crop nutrient demand against soil reserves, translated into commercial 50 kg bags and a three-stage schedule.",
                        eyebrow="Advisory"))

    c_f1, c_f2 = st.columns([1, 1.25])
    with c_f1:
        with st.container(border=True, key="card_fert_inputs"):
            st.html(card_title("sliders-horizontal", "Crop & soil test values"))
            f_crop_sel = st.selectbox("Target crop", ["Tomato", "Rice", "Maize", "Banana", "Cotton", "Potato", "Chickpea"])
            f_acres = st.number_input("Field acreage (acres)", min_value=0.5, max_value=50.0, value=farm.get("acreage", 2.0), step=0.5)
            f_sn = st.number_input("Soil available N (kg/ha)", value=60.0)
            f_sp = st.number_input("Soil available P (kg/ha)", value=35.0)
            f_sk = st.number_input("Soil available K (kg/ha)", value=45.0)

    fert_res = calculate_fertilizer_prescription(f_crop_sel, f_sn, f_sp, f_sk, f_acres)

    with c_f2:
        with st.container(border=True, key="card_fert_result"):
            st.html(card_title("package", "Commercial fertilizer requirement",
                               f'<span class="ki-num">{f_acres:.1f}</span> acres · {esc(f_crop_sel)}'))
            total_bags = sum(item["bags_50kg"] for item in fert_res["fertilizers"])
            st.html(f"""
            <div class="ki-hero" style="margin-bottom:8px;">
                <div class="ki-eyebrow">Total for this field</div>
                <div class="ki-hero-value ki-num" style="margin-bottom:0;">{count(total_bags, 1, key='fert_bags')}<span class="ki-unit">bags of 50 kg</span></div>
            </div>""")
            rows = ""
            for item in fert_res["fertilizers"]:
                qty_badge = badge(f"{item['bags_50kg']} bags · {item['total_kg']} kg", "accent")
                rows += f"""<div class="ki-row" style="align-items:flex-start;">
                    <div><div class="ki-row-title">{item['name']}</div><div class="ki-row-body">{item['purpose']}</div></div>
                    {qty_badge}
                </div>"""
            st.html(f"<div>{rows}</div>")

    demand = fert_res["nutrient_demands_kg"]
    df_sch = pd.DataFrame(fert_res["schedule"])
    c_n, c_s = st.columns([1, 1.25])
    with c_n:
        with st.container(border=True, key="card_fert_nutrients"):
            st.html(card_title("leaf", "Nutrient demand", "Total N, P and K the crop needs on this field (kg)"))
            nutrients = ["Nitrogen (N)", "Phosphorus (P)", "Potassium (K)"]
            vals = [demand["N"], demand["P"], demand["K"]]
            fig_n = go.Figure(go.Bar(
                x=vals, y=nutrients, orientation="h",
                marker=dict(color=[COLORS["forest"], COLORS["accent"], COLORS["sage"]], line=dict(width=0)),
                text=[f"{v:,.1f} kg" for v in vals], textposition="outside",
                textfont=dict(color=COLORS["text_secondary"], size=11), cliponaxis=False,
                hovertemplate="%{y}: %{x:,.1f} kg<extra></extra>", width=0.5,
            ))
            style_figure(fig_n, height=210)
            fig_n.update_xaxes(showticklabels=False, showgrid=False, range=[0, max(vals) * 1.3 if max(vals) else 1])
            fig_n.update_yaxes(autorange="reversed", showgrid=False)
            st.plotly_chart(fig_n, theme=None, config=PLOTLY_CONFIG, key="fert_nutrients")
    with c_s:
        with st.container(border=True, key="card_fert_split"):
            st.html(card_title("calendar", "Split application", "Product per stage (kg)"))
            stage_names = [s.split("(")[0].strip() for s in df_sch["stage"]]
            fig_s = go.Figure()
            for col_name, label, color in [("urea_kg", "Urea", COLORS["forest"]), ("dap_kg", "DAP", COLORS["accent"]), ("mop_kg", "MOP", COLORS["sage"])]:
                fig_s.add_trace(go.Bar(x=stage_names, y=df_sch[col_name], name=label, marker=dict(color=color, line=dict(width=0)),
                                       hovertemplate=label + ": %{y:,.1f} kg<extra></extra>"))
            style_figure(fig_s, height=210)
            fig_s.update_layout(barmode="stack", bargap=0.55, legend=dict(orientation="h", y=1.15, x=0, yanchor="bottom", traceorder="normal"),
                                margin=dict(l=4, r=4, t=28, b=4))
            fig_s.update_xaxes(showgrid=False)
            st.plotly_chart(fig_s, theme=None, config=PLOTLY_CONFIG, key="fert_split")

    with st.container(border=True, key="card_fert_schedule"):
        st.html(card_title("clipboard-list", "Application schedule"))
        df_show = df_sch[["stage", "timing", "urea_kg", "dap_kg", "mop_kg", "method"]].rename(columns={
            "stage": "Growth stage",
            "timing": "Recommended timing",
            "urea_kg": "Urea (kg)",
            "dap_kg": "DAP (kg)",
            "mop_kg": "MOP (kg)",
            "method": "Application method & guidance"
        })
        st.dataframe(df_show, hide_index=True)


# ==============================================================================
# MANDI NET PROCEEDS
# ==============================================================================
def render_mandi(farm: dict):
    st.html(page_header("truck", "Mandi Net Proceeds",
                        "Road distance, vehicle freight and APMC fees (1.5% cess + 2.0% commission), ranked by true in-hand proceeds.",
                        eyebrow="Markets"))

    with st.container(border=True, key="card_mandi_scope"):
        col_mp1, col_mp2, col_mp3 = st.columns(3)
        crop_opts = sorted(df_market['commodity'].unique())
        with col_mp1:
            m_crop = st.selectbox("Crop", crop_opts, index=crop_opts.index("Tomato") if "Tomato" in crop_opts else 0)
        with col_mp2:
            m_qty = st.number_input("Quantity to transport (kg)", min_value=100.0, max_value=20000.0, value=500.0, step=50.0)
        with col_mp3:
            m_veh = st.selectbox("Vehicle profile", list(DEFAULT_VEHICLE_CONFIGS.keys()), index=0)

    p_res = cached_mandi_table(m_crop, m_qty, farm.get("latitude", 12.7209), farm.get("longitude", 77.2799), m_veh)
    b_m = p_res["best_mandi"]
    n_m = p_res["nearest_mandi"]

    if not (b_m and n_m):
        st.html(empty_state("landmark", "No mandi prices for this crop",
                            "Choose another commodity to rank wholesale markets by net proceeds."))
        return

    net_gain = p_res["net_advantage_vs_nearest"]
    cb1, cb2, cb3 = st.columns(3)
    with cb1:
        st.html(kpi_card(
            "Highest net proceeds", count(b_m["net_proceeds"], 2, "₹", key="md_best"),
            f"{esc(b_m['mandi'])} · {money(b_m['net_price_per_kg'])}/kg net · {b_m['road_distance_km']} km",
            "positive", "award", highlight=True))
    with cb2:
        st.html(kpi_card(
            "Nearest mandi", count(n_m["net_proceeds"], 2, "₹", key="md_near"),
            f"{esc(n_m['mandi'])} · {money(n_m['net_price_per_kg'])}/kg net · {n_m['road_distance_km']} km",
            "risk" if n_m["net_proceeds"] < 0 else "neutral", "map-pin"))
    with cb3:
        st.html(kpi_card(
            "Net advantage", count(net_gain, 2, "₹", key="md_gain", signed=True),
            "Best vs nearest, after all transport expenses", "positive" if net_gain >= 0 else "risk",
            "trending-up" if net_gain >= 0 else "trending-down"))

    with st.container(border=True, key="card_mandi_top"):
        top = sorted(p_res["records"], key=lambda r: r["net_proceeds"], reverse=True)[:8]
        st.html(card_title("chart-column", "Top markets by net proceeds",
                           f"{esc(m_crop)} · {m_qty:,.0f} kg · {esc(m_veh)}"))
        names = [f"{r['mandi']} · {r['road_distance_km']:.0f} km" for r in top]
        vals = [r["net_proceeds"] for r in top]
        fig_m = go.Figure(go.Bar(
            x=vals, y=names, orientation="h",
            marker=dict(color=[COLORS["accent"]] + [COLORS["sage"]] * (len(vals) - 1), line=dict(width=0)),
            text=[money(v, 0) for v in vals], textposition="outside", cliponaxis=False,
            textfont=dict(color=COLORS["text_secondary"], size=11),
            hovertemplate="%{y}<br>Net proceeds ₹%{x:,.0f}<extra></extra>", width=0.6,
        ))
        style_figure(fig_m, height=max(220, 34 * len(vals) + 40))
        fig_m.update_yaxes(autorange="reversed", showgrid=False)
        fig_m.update_xaxes(showticklabels=False, showgrid=False,
                           range=[min(0, min(vals)) * 1.2, max(vals) * 1.22 if max(vals) > 0 else 1])
        st.plotly_chart(fig_m, theme=None, config=PLOTLY_CONFIG, key="mandi_top")

    with st.container(border=True, key="card_mandi_ledger"):
        st.html(card_title("landmark", "Ranked mandi ledger", f"{len(p_res['records'])} markets ranked by net proceeds"))
        df_m_disp = pd.DataFrame(p_res["records"])[[
            "mandi", "district", "state", "modal_price_kg", "road_distance_km",
            "gross_revenue", "transport_cost", "total_expenses", "net_proceeds", "net_price_per_kg", "suitability_badge"
        ]].rename(columns={
            "mandi": "Market",
            "district": "District",
            "state": "State",
            "modal_price_kg": "Gross modal (₹/kg)",
            "road_distance_km": "Distance (km)",
            "gross_revenue": "Gross (₹)",
            "transport_cost": "Freight (₹)",
            "total_expenses": "Fees (₹)",
            "net_proceeds": "Net proceeds (₹)",
            "net_price_per_kg": "Net realized (₹/kg)",
            "suitability_badge": "Cold-chain match"
        })
        st.dataframe(df_m_disp, height=360, hide_index=True, column_config={
            "Gross modal (₹/kg)": st.column_config.NumberColumn(format="%.2f"),
            "Distance (km)": st.column_config.NumberColumn(format="%.1f"),
            "Gross (₹)": st.column_config.NumberColumn(format="localized"),
            "Freight (₹)": st.column_config.NumberColumn(format="localized"),
            "Fees (₹)": st.column_config.NumberColumn(format="localized"),
            "Net proceeds (₹)": st.column_config.NumberColumn(format="localized"),
            "Net realized (₹/kg)": st.column_config.NumberColumn(format="%.2f"),
        })


# ==============================================================================
# FRAUD & UNFAIR OFFER DETECTOR
# ==============================================================================
def render_fraud():
    st.html(page_header("shield-check", "Offer Check",
                        "Audits a buyer's farmgate bid against fair mandi parity, quantifies the loss and drafts a counter-offer.",
                        eyebrow="Markets"))

    c_fr1, c_fr2 = st.columns([1, 1.25])
    with c_fr1:
        with st.container(border=True, key="card_fraud_inputs"):
            st.html(card_title("sliders-horizontal", "Buyer offer"))
            offered_p = st.number_input("Buyer's quoted price (₹/kg)", min_value=1.0, max_value=150.0, value=11.50, step=0.5)
            offered_q = st.number_input("Quantity in deal (kg)", min_value=100.0, max_value=25000.0, value=500.0, step=50.0)
            pay_term = st.selectbox("Payment terms", ["Immediate Cash / UPI at Weighbridge", "Payment after 7 days", "Payment after 15 days", "Unspecified Credit"])

    bench_m = 16.50
    fr_res = evaluate_buyer_offer(offered_p, offered_q, bench_m, bench_m * 0.88, payment_terms=pay_term)

    with c_fr2:
        with st.container(border=True, key="card_fraud_result"):
            st.html(card_title("shield-check", "Parity & anomaly audit",
                               right_html=badge(fr_res['status'].title(), color=fr_res['badge_color'])))

            gap = fr_res["farmer_loss_gain"]
            offer_html = count(fr_res["total_offered_proceeds"], 2, "₹", key="fr_offer")
            fair_html = count(fr_res["total_fair_proceeds"], 2, "₹", key="fr_fair")
            gap_html = count(gap, 2, "₹", key="fr_gap", signed=True)
            st.html(f"""
            <div class="ki-text">{fr_res['summary']}</div>
            <div class="ki-decision-grid ki-num" style="margin-top:16px;">
                <div><div class="ki-eyebrow">Offer value</div><div class="ki-decision-num">{offer_html}</div></div>
                <div><div class="ki-eyebrow">Fair parity</div><div class="ki-decision-num">{fair_html}</div></div>
                <div><div class="ki-eyebrow">Gap</div><div class="ki-decision-num" style="color:{COLORS['positive'] if gap >= 0 else COLORS['risk']};">{gap_html}</div></div>
            </div>
            """)

            st.html(callout(
                "lightbulb",
                f"Recommended counter-offer: <span class='ki-num'>₹{fr_res['recommended_counter_kg']:.2f}/kg</span>",
                f"Recovers <span class='ki-num'>₹{fr_res['extra_money_from_counter']:,.2f}</span> in fair proceeds.",
                tone="positive"
            ))
            st.html(f'<div class="ki-quote">{esc(fr_res["negotiation_script"])}</div>')

            if fr_res["risk_flags"]:
                flags = "".join(
                    f'<div class="ki-flag">{icon("triangle-alert", 14)}<span>{esc(flag)}</span></div>'
                    for flag in fr_res["risk_flags"]
                )
                st.html(f'<div class="ki-eyebrow" style="margin-top:16px;">Risk flags</div>{flags}')


# ==============================================================================
# REPORTS & SETTINGS
# ==============================================================================
def render_reports(user: dict):
    st.html(page_header("file-text", "Reports",
                        f"Prediction history isolated to {esc(user['full_name'])} ({esc(user['email'])}).",
                        eyebrow="Account"))

    preds = get_user_predictions(user["id"])
    with st.container(border=True, key="card_reports"):
        if preds:
            df_rep = pd.DataFrame(preds)
            st.html(card_title("history", "Saved intelligence", f"{len(df_rep)} reports",
                               right_html=badge("Tenant isolated", "positive", "lock")))
            st.dataframe(df_rep[["id", "module_name", "title", "created_at"]].rename(columns={
                "id": "Report ID",
                "module_name": "Module",
                "title": "Title / recommendation",
                "created_at": "Timestamp"
            }), hide_index=True)

            csv_data = df_rep.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download reports (CSV)",
                data=csv_data,
                file_name=f"krishi_ai_reports_{user['id']}.csv",
                mime="text/csv",
                key="btn_download_reports"
            )
        else:
            st.html(empty_state("inbox", "No saved predictions yet",
                                "Saved analyses from your modules will appear here."))


def render_settings(user: dict, farm: dict):
    st.html(page_header("settings", "Settings", "Farm profile and account security.", eyebrow="Account"))

    col_p1, col_p2 = st.columns([1, 1])

    with col_p1:
        with st.container(border=True, key="card_profile"):
            st.html(card_title("sprout", "Farm profile"))

            p_farm_name = st.text_input("Farm name", value=farm.get("farm_name", "Green Valley Agro Farm"))
            p_acreage = st.number_input("Holding acreage (acres)", value=float(farm.get("acreage", 2.5)), step=0.5)
            p_village = st.text_input("Village / town", value=farm.get("village", "Ramanagara"))
            p_district = st.text_input("District", value=farm.get("district", "Ramanagara"))
            p_state = st.text_input("State", value=farm.get("state", "Karnataka"))
            p_soil = st.selectbox("Predominant soil type", ["Red Sandy Loam", "Clay Loam", "Black Cotton Soil", "Alluvial", "Laterite"], index=0)
            p_crops = st.text_input("Primary crops", value=farm.get("primary_crops", "Tomato, Maize, Banana"))

            if st.button("Save farm profile", type="primary", key="btn_save_profile"):
                up_ok, up_msg = update_farm_profile(user["id"], {
                    "farm_name": p_farm_name,
                    "acreage": p_acreage,
                    "village": p_village,
                    "district": p_district,
                    "state": p_state,
                    "soil_type": p_soil,
                    "primary_crops": p_crops,
                    "latitude": farm.get("latitude", 12.7209),
                    "longitude": farm.get("longitude", 77.2799),
                    "irrigation_source": farm.get("irrigation_source", "Borewell Drip")
                })
                if up_ok:
                    st.success("Farm profile updated.")
                    st.session_state.current_user["farm"]["farm_name"] = p_farm_name
                    st.session_state.current_user["farm"]["acreage"] = p_acreage
                    st.session_state.current_user["farm"]["district"] = p_district
                    st.session_state.current_user["farm"]["state"] = p_state
                    st.rerun()

    with col_p2:
        with st.container(border=True, key="card_security"):
            st.html(card_title("lock", "Password"))

            old_pwd = st.text_input("Current password", type="password")
            new_pwd = st.text_input("New password", type="password")
            new_pwd_conf = st.text_input("Confirm new password", type="password")

            if st.button("Update password", key="btn_update_pwd"):
                if new_pwd != new_pwd_conf:
                    st.error("New passwords do not match.")
                else:
                    ch_ok, ch_msg = change_user_password(user["id"], old_pwd, new_pwd)
                    if ch_ok:
                        st.success(ch_msg)
                    else:
                        st.error(ch_msg)

            st.html(f'<div class="ki-row-meta ki-num" style="margin-top:20px;">Account #{user["id"]} · {esc(user["role"].capitalize())}</div>')


# ==============================================================================
# MAIN PROTECTED APPLICATION
# ==============================================================================
def render_main_application():
    user = st.session_state.current_user
    farm = user.get("farm", {})
    role = user.get("role", "farmer")
    nav = nav_for(role)
    lookup = {key: (label, ic, slug) for _, items in nav for key, label, ic, slug in items}
    section_of = {key: section for section, items in nav for key, *_ in items}
    active = st.session_state.active_nav
    if active not in lookup:
        active = st.session_state.active_nav = nav[0][1][0][0]

    profile = get_buyer_profile(user["id"]) if role == "buyer" else None
    if profile:
        # Market pages read location from a farm-shaped dict; for buyers that is their business location
        place, _, b_state = (profile["location_label"] or "").partition(",")
        farm = {**farm, "district": place.strip(), "state": b_state.strip() or farm.get("state", "Karnataka"),
                "latitude": profile["latitude"], "longitude": profile["longitude"]}
    location_text = (esc(profile["location_label"]) if profile
                     else f"{esc(str(farm.get('district', '')))}, {esc(str(farm.get('state', '')))}")

    # SIDEBAR: brand, grouped navigation, profile
    with st.sidebar:
        tagline = "Buyer desk" if role == "buyer" else "Farm intelligence"
        st.html(f"""
        <div class="ki-brand">
            <div class="ki-brand-mark">{icon('leaf', 17)}</div>
            <div><div class="ki-brand-name">Krishi AI</div><div class="ki-brand-tag">{tagline}</div></div>
        </div>
        """)
        for section, items in nav:
            if section:
                st.html(f'<div class="ki-nav-section">{section}</div>')
            for key, label, _, _ in items:
                if st.button(label, key=nav_widget_key(key), width="stretch",
                             type="primary" if active == key else "secondary"):
                    go_to(key)

        st.html('<div class="ki-sidebar-divider"></div>')
        subtitle = profile["business_name"] if profile else farm.get("farm_name", "My Farm")
        st.html(f"""
        <div class="ki-profile">
            <div class="ki-avatar">{esc(initials(user['full_name']))}</div>
            <div style="min-width:0;">
                <div class="ki-profile-name">{esc(user['full_name'])}</div>
                <div class="ki-profile-farm">{esc(str(subtitle))}</div>
            </div>
        </div>
        """)
        if st.button("Sign out", key="btn_logout", width="stretch"):
            invalidate_session(st.session_state.auth_token)
            st.session_state.auth_token = None
            st.session_state.current_user = None
            st.session_state.active_nav = "Dashboard"
            st.rerun()

    # TOP LINE (also installs the number-transition script once per session)
    nav_label, _, slug = lookup[active]
    section = section_of.get(active)
    crumb = f'<span>{section}</span><span class="ki-crumb-sep">/</span>' if section else ""
    st.html(f"""
    <div class="ki-topline">
        <div class="ki-breadcrumb">{crumb}<span class="ki-crumb-current">{nav_label}</span></div>
        <div class="ki-topline-right">
            <span class="ki-topline-date ki-num">{icon('map-pin', 14)}{location_text}</span>
            <div class="ki-avatar">{esc(initials(user['full_name']))}</div>
        </div>
    </div>
    {COUNT_UP_SCRIPT}
    """, unsafe_allow_javascript=True)

    if st.session_state.get("flash"):
        st.toast(st.session_state.pop("flash"))

    # Each page lives in its own keyed container so page switches fade in
    with st.container(key=f"page_{slug}"):
        if role == "buyer":
            if profile is None:
                render_buyer_onboarding(user)
            elif active == "Buyer Requests":
                render_buyer_requests(user, profile)
            elif active == "Buyer Quotations":
                render_buyer_quotations(user, profile)
            elif active == "Price Forecast":
                render_price_forecast(farm)
            elif active == "Trend Shift":
                render_trend_shift(farm)
            elif active == "Buyer Profile":
                render_buyer_settings(user, profile)
        elif active == "Dashboard":
            render_overview(user, farm)
        elif active == "Fertilizer Advisor":
            render_fertilizer(farm)
        elif active == "Mandi Net Proceeds":
            render_mandi(farm)
        elif active == "Price Forecast":
            render_price_forecast(farm)
        elif active == "Trend Shift":
            render_trend_shift(farm)
        elif active == "Buyer Network":
            render_buyer_network(user, farm)
        elif active == "Fraud Detector":
            render_fraud()
        elif active == "Reports":
            render_reports(user)
        elif active == "Settings":
            render_settings(user, farm)


# ==============================================================================
# MAIN ROUTING
# ==============================================================================
if not st.session_state.current_user:
    render_authentication_page()
else:
    render_main_application()

# Floating Bolna voice assistant, shared by every page (only when started via server.py)
render_voice_widget()
