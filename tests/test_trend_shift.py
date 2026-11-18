"""
Test Suite for the Trend-Shift Calibration engine (modules/trend_shift.py).
Uses synthetic series only, so it runs without the parquet archive.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from modules.trend_shift import (
    to_daily_series, detect_trend_shift, recalibrate_forecast,
    recency_parameters, predictions_from_forecast, shift_signal_history, trend_lines
)


def make_series(values, start="2025-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="D")
    return pd.Series(np.asarray(values, dtype=float), index=idx)


def make_forecast(last_date, base_price, steps=14, band=2.0):
    dates = pd.date_range(pd.Timestamp(last_date) + pd.Timedelta(days=1), periods=steps, freq="D")
    preds = np.full(steps, base_price)
    return pd.DataFrame({
        "Arrival_Date": dates.strftime("%Y-%m-%d"),
        "predicted_modal_price_kg": preds,
        "confidence_upper_kg": preds + band,
        "confidence_lower_kg": preds - band,
    })


def run_tests():
    print("=" * 65)
    print("RUNNING TREND-SHIFT CALIBRATION VERIFICATION")
    print("=" * 65)
    rng = np.random.default_rng(7)

    # 1. Stable series -> no shift
    print("\n[Test 1] Stable series is not flagged...")
    flat = make_series(20 + rng.normal(0, 0.3, 120))
    res = detect_trend_shift(flat)
    assert res["status"] == "SUCCESS"
    assert not res["detected"], res
    assert res["severity"] == "stable"
    assert res["headline"].startswith("Trend stable")
    print(f"  -> PASS: {res['headline']}")

    # 2. Flat history then a sharp recent rally -> upward slope shift with onset in the rally
    print("\n[Test 2] Recent rally is flagged as an upward pattern shift...")
    rally = np.concatenate([20 + rng.normal(0, 0.3, 100), 20 + np.arange(1, 15) * 0.6])
    s_rally = make_series(rally)
    res = detect_trend_shift(s_rally)
    assert res["detected"] and res["direction"] == "up", res
    assert res["slope_variance_pct"] > res["slope_threshold_pct"]
    assert res["headline"].startswith("Pattern Shift Detected: +")
    onset = pd.Timestamp(res["onset_date"])
    assert onset >= s_rally.index[-25], f"Onset {onset} should sit near the rally"
    print(f"  -> PASS: {res['headline']} ({res['severity']}), onset {res['onset_date']}")

    # 3. Recent slump -> downward shift
    print("\n[Test 3] Recent slump is flagged as a downward pattern shift...")
    slump = np.concatenate([20 + rng.normal(0, 0.3, 100), 20 - np.arange(1, 15) * 0.6])
    res = detect_trend_shift(make_series(slump))
    assert res["detected"] and res["direction"] == "down", res
    assert res["slope_variance_pct"] < 0
    print(f"  -> PASS: {res['headline']}")

    # 4. Short history -> graceful insufficient-data result
    print("\n[Test 4] Short history returns INSUFFICIENT_DATA...")
    res = detect_trend_shift(make_series([10, 11, 12, 11, 10]))
    assert res["status"] == "INSUFFICIENT_DATA" and not res["detected"]
    print(f"  -> PASS: {res['message']}")

    # 5. Recency parameters are monotonic from conservative to aggressive
    print("\n[Test 5] Recency parameters scale with sensitivity...")
    lo, hi = recency_parameters(0.0), recency_parameters(1.0)
    for k in ("alpha", "beta", "phi", "blend"):
        assert lo[k] < hi[k], k
    assert recency_parameters(-1) == lo and recency_parameters(5) == hi
    print(f"  -> PASS: conservative {lo} -> aggressive {hi}")

    # 6. Recalibration pulls a stale baseline toward the recent trend, more so when aggressive
    print("\n[Test 6] Recalibration realigns a stale forecast with the rally...")
    base_fc = make_forecast(s_rally.index[-1], base_price=20.0)
    cons, meta_c = recalibrate_forecast(s_rally, base_fc, sensitivity=0.0)
    aggr, meta_a = recalibrate_forecast(s_rally, base_fc, sensitivity=1.0)
    assert meta_c["applied"] and meta_a["applied"]
    assert 0 < meta_c["final_adjustment_kg"] < meta_a["final_adjustment_kg"], (meta_c, meta_a)
    assert (aggr["original_predicted_kg"] == base_fc["predicted_modal_price_kg"]).all()
    assert (aggr["confidence_upper_kg"] >= aggr["predicted_modal_price_kg"]).all()
    assert (aggr["confidence_lower_kg"] <= aggr["predicted_modal_price_kg"]).all()
    assert not aggr.isna().any().any()
    print(f"  -> PASS: 14d adjustment conservative {meta_c['final_adjustment_kg']:+.2f} vs aggressive {meta_a['final_adjustment_kg']:+.2f} ₹/kg")

    # 7. Guard rails: price floor and bounded extrapolation on a crash
    print("\n[Test 7] Price floor and trend envelope hold on a crash...")
    crash = make_series(np.concatenate([np.full(100, 5.0) + rng.normal(0, 0.1, 100), 5 - np.arange(1, 15) * 0.3]))
    adj, meta = recalibrate_forecast(crash, make_forecast(crash.index[-1], 2.0, band=1.5), sensitivity=1.0)
    assert (adj["predicted_modal_price_kg"] >= 1.0).all()
    assert (adj["confidence_lower_kg"] >= 1.0).all()
    print(f"  -> PASS: minimum adjusted price ₹{adj['predicted_modal_price_kg'].min():.2f}/kg")

    # 8. Prediction dict keeps the train_and_forecast_price shape
    print("\n[Test 8] Horizon predictions rebuilt from the adjusted frame...")
    preds = predictions_from_forecast(aggr)
    assert set(preds) == {"3_day", "7_day", "14_day"}
    assert preds["7_day"]["predicted_price_kg"] == float(aggr.iloc[6]["predicted_modal_price_kg"])
    print(f"  -> PASS: 7-day ₹{preds['7_day']['predicted_price_kg']:.2f}/kg")

    # 9. Daily aggregation averages multiple markets per date
    print("\n[Test 9] Multi-market frame collapses to one mean per date...")
    raw = pd.DataFrame({
        "Arrival_Date": ["2025-01-01", "2025-01-01", "2025-01-02"],
        "modal_price_kg": [10.0, 20.0, 12.0],
    })
    daily = to_daily_series(raw)
    assert list(daily.values) == [15.0, 12.0]
    print("  -> PASS: [10, 20] on the same date -> 15.0")

    # 10. Signal history flags the rally only near its end
    print("\n[Test 10] Signal history re-runs the detector session by session...")
    hist = shift_signal_history(s_rally, sessions=60)
    assert len(hist) == 60 and set(hist.columns) >= {"date", "slope_variance_pct", "detected"}
    assert hist["detected"].iloc[-1] and not hist["detected"].iloc[:30].any()
    print(f"  -> PASS: flagged on {int(hist['detected'].sum())} of {len(hist)} sessions, none before the rally.")

    # 11. Trend lines: recent slope is steeper than the historical one on the rally
    print("\n[Test 11] Fitted trend lines for the pattern chart...")
    lines = trend_lines(s_rally)
    rec = lines["recent_fit"]
    base = lines["baseline_fit"][:lines["baseline_split"]]
    assert (rec[-1] - rec[0]) > 5 * abs(base[-1] - base[0])
    assert len(lines["baseline_fit"]) == len(lines["baseline_dates"])
    print(f"  -> PASS: recent trend rises ₹{rec[-1] - rec[0]:.2f}, historical moves ₹{base[-1] - base[0]:+.2f}")

    # 12. Significance gate: routine swings on a volatile crop are not flagged
    print("\n[Test 12] Significance gate separates routine swings from real breaks...")
    t = np.arange(400)
    volatile = make_series(20 + 5 * np.sin(t / 9.0) + rng.normal(0, 1.0, 400))
    gated = shift_signal_history(volatile, sessions=150)
    ungated = shift_signal_history(volatile, sessions=150, significance_z=None)
    assert ungated["detected"].sum() > 3 * max(1, gated["detected"].sum()), (ungated["detected"].sum(), gated["detected"].sum())
    noisy = detect_trend_shift(volatile)
    if abs(noisy["slope_variance_pct"]) >= noisy["slope_threshold_pct"] and not noisy["detected"]:
        assert noisy["within_noise"] and noisy["headline"].startswith("Within normal swings")
    broken = make_series(np.concatenate([volatile.values, volatile.values[-1] + np.arange(1, 15) * 1.5]))
    assert detect_trend_shift(broken)["detected"], "A sharp break must still be flagged"
    print(f"  -> PASS: flagged {int(gated['detected'].sum())} of 150 sessions with the gate vs {int(ungated['detected'].sum())} without; a real break is still caught.")

    print("\n" + "=" * 65)
    print("ALL 12 TREND-SHIFT CALIBRATION TESTS PASSED")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
