# 🌿 Krishi AI – Intelligent Farming Decision System
> **Commercial-Grade AgriTech SaaS Platform: Predictive AI, Mandi Logistics, Multi-Market Arbitrage & Fraud Defense**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-2D6A4F?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit 1.50+](https://img.shields.io/badge/Streamlit-1.50%2B-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![DuckDB](https://img.shields.io/badge/DuckDB-Parquet%20Analytics-FFF000?logo=duckdb&logoColor=black)](https://duckdb.org/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-ML%20Pipelines-F7931E?logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![OpenRouteService](https://img.shields.io/badge/ORS-Road%20Matrix%20Routing-059669)](https://openrouteservice.org/)
[![Security](https://img.shields.io/badge/Security-bcrypt%20%7C%20Rate--Limited%20%7C%20Isolated-0F172A)](https://github.com)

---

## 📌 Executive Summary

Smallholder and commercial farmers across India face systemic challenges: suboptimal crop choices, lack of mandi price visibility, expensive road transport, and predatory buyer quotes.

**Krishi AI** solves this with an end-to-end intelligence suite:
1. **Fertilizer Advisory & Farm Overview**: Urea/DAP/MOP 50 kg bag prescriptions with a split schedule, plus an overview with live farm weather (Open-Meteo, no API key) and market highlights for the primary crop. The crop, soil and yield models remain in `modules/` and `models/` but are no longer exposed in the app.
2. **Logistics & Net Proceeds Engine**: Real road routing (OpenRouteService) evaluating 2,733 wholesale mandis. Deducts freight, APMC cess (1.5%), commission agent fees (2.0%), and handling to rank markets by **True In-Hand Net Profit** (revealing up to ₹9,600+ net arbitrage over local mandis).
3. **DuckDB 4-Year Price Forecasting**: Sub-second lazy scans over multi-year agricultural parquet archives with lag-feature time-series regression for 3/7/14-day price forecasting, plus **Trend-Shift Calibration**: automatic pattern-change detection (slope variance vs the historical moving average) and recency-weighted recalibration with a live comparison overlay.
4. **Deterministic Sell Advisor**: Financial model factoring in storage costs and spoilage degradation to recommend **Sell Now**, **Wait**, or **Split Delivery**.
5. **Anti-Fraud Parity**: Predatory buyer quote anomaly detection, farmer loss quantification, and auto-generated counter-negotiation scripts citing official APMC rates.
6. **Enterprise Authentication**: Argon2id/bcrypt password hashing, rate-limited login throttling, and private tenant data isolation.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Client ["Client Interface (Streamlit SaaS)"]
        UI["Premium Light UI<br/>(Forest & Sage Palette)"]
    end

    subgraph Auth ["Security & Tenancy"]
        AUTH_DB["SQLite User & Farm DB<br/>(bcrypt Cost 12 • Rate Limiting)"]
    end

    subgraph Agronomy ["Agronomic Intelligence"]
        CROP_ML["Crop Recommendation RF Classifier<br/>(NPK, Temp, Humidity, pH, Rainfall)"]
        SOIL_ENG["Soil Health Index & NPK Deficit"]
        YIELD_ML["Harvest Volume Regressor"]
    end

    subgraph Logistics ["Market Logistics & Arbitrage"]
        ORS["OpenRouteService Matrix Engine<br/>(Distance, Duration, Circuity Factor)"]
        TRANS["Cold-Chain vs Normal Freight Model"]
        MANDI_PROC["Net Proceeds Calculator<br/>(Gross Price - Cess - Freight - Labor)"]
    end

    subgraph Forecasting ["Predictive Time Series"]
        DUCK["DuckDB Parquet Lazy Scanner<br/>(2023-2026 Historical Timeseries)"]
        FORECAST_ML["Lag Feature Regressor (t-1, t-7, t-14, t-30)"]
        SELL_OPT["Financial Sell Now vs Wait Engine"]
    end

    subgraph Defense ["Fair Price Defense"]
        FRAUD["Predatory Bid Anomaly Detector"]
        COUNTER["Counter-Offer Script Generator"]
    end

    UI --> AUTH_DB
    UI --> CROP_ML & SOIL_ENG & YIELD_ML
    UI --> ORS & TRANS & MANDI_PROC
    UI --> DUCK & FORECAST_ML & SELL_OPT
    UI --> FRAUD & COUNTER
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10 – 3.14 (64-bit)
- Git

### 2. Clone Repository & Setup
```bash
# Clone the repository
git clone https://github.com/supreethhegde4-dev/krishi-ai.git
cd krishi-ai

# Install dependencies
python -m pip install -r requirements.txt
```

### 3. Launch Application
On Windows, double-click **`run_app.bat`** (it creates `.venv` and installs requirements on first run), or from the project folder:
```bash
.venv\Scripts\python -m streamlit run server.py --server.port 8501
```
Open **`http://localhost:8501`** in your browser. (Plain `streamlit run …` only works if Streamlit is installed for your system Python.)

`server.py` runs the app together with its server-side routes (the Bolna voice assistant). `streamlit run app.py` still works, without the call button.

### 4. Voice Assistant (Bolna AI)
A floating call button (bottom-right on every page) opens **Call me**: the visitor enters a mobile number and the Bolna agent phones them (`POST /api/bolna-call` → Bolna `POST /call`). **Talk in the browser instead** starts a live web call through the Bolna Web Call SDK (`POST /api/bolna-session`).

**Setup:** copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (git-ignored), paste your key, and restart the app. Environment variables with the same names take priority over the file.

| Setting | Required | Purpose |
| :--- | :--- | :--- |
| `BOLNA_API_KEY` | Yes | Your Bolna API key (`bn-…`). Read only on the server; never sent to the browser. |
| `BOLNA_AGENT_ID` | No | Agent to call. Defaults to `9ae02706-b806-46dc-b146-0efbdd6389d6`. |
| `BOLNA_FROM_NUMBER` | No | Caller number bought in your Bolna account (E.164). Bolna's default number is used if unset. |
| `BOLNA_CALL_COUNTRY_CODES` | No | Country codes **Call me** may dial (default `+91`; Indian numbers must be 10-digit mobiles). |
| `BOLNA_SESSION_ENDPOINT` / `BOLNA_CALL_ENDPOINT` | No | Overrides for Bolna's endpoints. |
| `KRISHI_VOICE_SECRET` | No | Signs page tokens. Set it when running several server processes; otherwise a random per-process secret is used. |

Both routes only answer same-origin requests carrying a short-lived token signed by the server. **Call me** allows 3 requests per visitor per 15 minutes and 2 calls per number per 30 minutes; browser sessions allow 5 per visitor per 10 minutes. The Web Call SDK (v3.0.1) loads from jsDelivr with a subresource-integrity hash.

---

## 🔑 Demo Access Credentials

The platform includes pre-seeded demonstration accounts for instant 1-click evaluation:

| Role | Email | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **🧑‍🌾 Demo Farmer** | `farmer@krishiai.com` | `Password@123` | 5-Acre Tomato Enterprise (Ramanagara, Karnataka) |
| **🛡️ Demo Administrator** | `admin@krishiai.com` | `Admin@123` | System Analytics, APMC Mandi Oversight |

---

## 📊 Modules & Verification

Run the comprehensive automated test suites:

```bash
# 1. Run Authentication & SaaS Redesign Verification
python tests/test_auth_and_redesign.py

# 2. Run End-to-End Agronomic & Logistics Verification
python tests/test_end_to_end.py

# 3. Run Trend-Shift Calibration Verification (synthetic data, no archive needed)
python tests/test_trend_shift.py

# 4. Run Buyer Network and Voice Assistant route checks (temp DB / mocked Bolna)
python tests/test_buyer_network.py
python tests/test_voice_assistant.py
```

The suites run 49 verification tests. The forecasting tests need the 2023–2026 parquet archive in `data/historical_parquet/parquet`; set `KRISHI_PARQUET_DIR` to use a folder elsewhere.

---

## 📄 License
MIT License. Built for the Intelligent Analytics and Predictive AI AgriTech Buildathon.
