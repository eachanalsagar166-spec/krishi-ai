"""
Trend-Shift Calibration engine for the price forecasting view.

1. detect_trend_shift()
   Compares the most recent observations against the preceding historical
   window. Two signals are measured:
     - Slope variance: the gap between the recent OLS slope and the historical
       slope, expressed as the extra % price change it implies over the recent
       window (relative to the historical moving average).
     - Level shift: how far the recent mean sits from the historical moving
       average, in % and in historical standard deviations (z).
   A pattern shift is flagged when either signal crosses its threshold. The
   most likely onset of the new regime is located with a two-segment
   piecewise-linear fit (a Chow-style structural break search).

2. recalibrate_forecast()
   Realigns a baseline forecast toward a damped Holt exponential-smoothing
   projection fitted on recent history. `sensitivity` (0..1) moves the model
   from Conservative (historical weight: slow smoothing, heavily damped trend,
   small blend) to Aggressive (recent trend weight: fast smoothing, persistent
   trend, large blend).
"""
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

DEFAULT_RECENT_WINDOW = 14
DEFAULT_BASELINE_WINDOW = 60
DEFAULT_SLOPE_THRESHOLD_PCT = 10.0
DEFAULT_LEVEL_Z_THRESHOLD = 2.0
DEFAULT_FIT_WINDOW = 120
DEFAULT_SIGNIFICANCE_Z = 2.0       # slope variance must be this many std devs from its own history
DEFAULT_REFERENCE_SESSIONS = 250   # history used to judge what a "normal" swing is


def to_daily_series(df_raw: pd.DataFrame, date_col: str = "Arrival_Date",
                    value_col: str = "modal_price_kg") -> pd.Series:
    """Collapses a (possibly multi-market) price frame into one mean price per date."""
    if df_raw is None or df_raw.empty:
        return pd.Series(dtype=float)
    df = df_raw[[date_col, value_col]].dropna()
    dates = pd.to_datetime(df[date_col], errors="coerce")
    s = df[value_col].groupby(dates).mean().sort_index()
    s = s[s.index.notna()].astype(float)
    s.index.name = "date"
    return s


def _ols_slope(values: np.ndarray) -> float:
    """Least-squares slope per observation step."""
    y = np.asarray(values, dtype=float)
    if len(y) < 2:
        return 0.0
    x = np.arange(len(y), dtype=float)
    x -= x.mean()
    denom = float((x ** 2).sum())
    return float((x * (y - y.mean())).sum() / denom) if denom > 0 else 0.0


def _linear_sse(y: np.ndarray) -> float:
    if len(y) < 2:
        return 0.0
    x = np.arange(len(y), dtype=float)
    slope = _ols_slope(y)
    intercept = y.mean() - slope * x.mean()
    resid = y - (intercept + slope * x)
    return float((resid ** 2).sum())


def _rolling_slopes(y: np.ndarray, window: int) -> np.ndarray:
    """OLS slope of every `window`-long run of y; element j covers y[j:j+window]."""
    x = np.arange(window, dtype=float) - (window - 1) / 2.0
    kernel = x / float((x ** 2).sum())
    return np.convolve(y, kernel[::-1], mode="valid")


def slope_variance_series(values, recent_window: int = DEFAULT_RECENT_WINDOW,
                          baseline_window: int = DEFAULT_BASELINE_WINDOW) -> np.ndarray:
    """
    Slope variance (%) as of every observation that has a full recent and
    baseline window behind it (vectorised; the last element is "now").
    """
    y = np.asarray(values, dtype=float)
    r, b = recent_window, baseline_window
    if len(y) < r + b:
        return np.array([])
    rs, bs = _rolling_slopes(y, r), _rolling_slopes(y, b)
    bm = np.convolve(y, np.ones(b) / b, mode="valid")
    ends = np.arange(r + b, len(y) + 1)
    scale = np.maximum(np.abs(bm[ends - r - b]), 1e-6)
    return (rs[ends - r] - bs[ends - r - b]) * r / scale * 100.0


def _locate_break(y: np.ndarray, min_segment: int = 5, search_last: Optional[int] = None) -> Optional[int]:
    """
    Index that best splits `y` into two independent linear trends (minimum
    combined SSE). Only splits within the last `search_last` points are tried,
    so the onset stays tied to the recent regime.
    """
    n = len(y)
    if n < 2 * min_segment:
        return None
    lo = min_segment if search_last is None else max(min_segment, n - search_last)
    hi = n - min_segment
    best_k, best_sse = None, np.inf
    for k in range(lo, hi + 1):
        sse = _linear_sse(y[:k]) + _linear_sse(y[k:])
        if sse < best_sse:
            best_k, best_sse = k, sse
    return best_k


def detect_trend_shift(
    series: pd.Series,
    recent_window: int = DEFAULT_RECENT_WINDOW,
    baseline_window: int = DEFAULT_BASELINE_WINDOW,
    slope_threshold_pct: float = DEFAULT_SLOPE_THRESHOLD_PCT,
    level_z_threshold: float = DEFAULT_LEVEL_Z_THRESHOLD,
    locate_onset: bool = True,
    significance_z: Optional[float] = DEFAULT_SIGNIFICANCE_Z,
    reference_sessions: int = DEFAULT_REFERENCE_SESSIONS,
) -> Dict[str, Any]:
    """
    Flags a structural break / slope deviation in the latest observations.

    A slope shift needs two things: the slope variance must exceed
    `slope_threshold_pct`, and (unless `significance_z` is None or 0) it must
    be unusual for this market, i.e. at least `significance_z` standard
    deviations from the slope variances seen over the previous
    `reference_sessions`. Volatile crops swing past a fixed % threshold
    constantly; the second test keeps the flag for genuine breaks.

    `series` is a date-indexed price series (one value per observation).
    Returns a dict with `detected`, `severity` ("stable" | "moderate" | "strong"),
    `direction` ("up" | "down" | "flat"), the measured signals and a headline.
    """
    s = pd.Series(series).dropna().astype(float)
    n = len(s)
    min_baseline = max(14, baseline_window // 3)
    if n < recent_window + min_baseline:
        return {
            "status": "INSUFFICIENT_DATA",
            "detected": False,
            "severity": "stable",
            "direction": "flat",
            "headline": "Trend-shift scan needs more history",
            "message": f"Only {n} observations available; at least {recent_window + min_baseline} are needed.",
            "observations": n,
        }

    recent = s.iloc[-recent_window:]
    baseline = s.iloc[max(0, n - recent_window - baseline_window):n - recent_window]

    hist_ma = float(baseline.mean())
    hist_std = float(baseline.std(ddof=1)) if len(baseline) > 1 else 0.0
    scale = max(abs(hist_ma), 1e-6)

    recent_slope = _ols_slope(recent.values)
    baseline_slope = _ols_slope(baseline.values)

    # Extra % move the recent slope implies over the recent window vs the historical slope
    slope_variance_pct = (recent_slope - baseline_slope) * recent_window / scale * 100.0
    recent_mean = float(recent.mean())
    level_shift_pct = (recent_mean - hist_ma) / scale * 100.0
    level_z = (recent_mean - hist_ma) / hist_std if hist_std > 1e-9 else 0.0

    # How unusual is this slope variance for this market?
    slope_variance_z = None
    history_sv = slope_variance_series(s.values, recent_window, baseline_window)
    if len(history_sv) > recent_window + 20:
        ref = history_sv[max(0, len(history_sv) - 1 - recent_window - reference_sessions):len(history_sv) - 1 - recent_window]
        ref_std = float(np.std(ref, ddof=1)) if len(ref) >= 20 else 0.0
        if ref_std > 1e-9:
            slope_variance_z = (slope_variance_pct - float(np.mean(ref))) / ref_std

    above_threshold = abs(slope_variance_pct) >= slope_threshold_pct
    gate_on = bool(significance_z) and slope_variance_z is not None
    significant = (not gate_on) or abs(slope_variance_z) >= significance_z
    slope_hit = above_threshold and significant
    within_noise = above_threshold and not significant
    level_hit = abs(level_z) >= level_z_threshold
    detected = bool(slope_hit or level_hit)

    strong = (slope_hit and abs(slope_variance_pct) >= 2 * slope_threshold_pct) or abs(level_z) >= 1.5 * level_z_threshold
    severity = "strong" if (detected and strong) else ("moderate" if detected else "stable")

    driver = slope_variance_pct if (slope_hit or not level_hit) else level_shift_pct
    direction = "up" if driver > 0.05 else ("down" if driver < -0.05 else "flat")

    onset_date = None
    if detected and locate_onset:
        window = s.iloc[max(0, n - recent_window - baseline_window):]
        k = _locate_break(window.values, min_segment=5, search_last=2 * recent_window)
        if k is not None:
            onset_date = window.index[k]

    if detected and slope_hit:
        headline = f"Pattern Shift Detected: {slope_variance_pct:+.1f}% slope variance"
    elif detected:
        headline = f"Pattern Shift Detected: {level_shift_pct:+.1f}% level shift vs moving average"
    elif within_noise:
        headline = f"Within normal swings: {slope_variance_pct:+.1f}% slope variance"
    else:
        headline = f"Trend stable: {slope_variance_pct:+.1f}% slope variance"

    return {
        "status": "SUCCESS",
        "detected": detected,
        "severity": severity,
        "direction": direction,
        "primary_signal": "slope" if slope_hit else ("level" if level_hit else None),
        "headline": headline,
        "slope_variance_pct": round(slope_variance_pct, 2),
        "slope_variance_z": round(slope_variance_z, 2) if slope_variance_z is not None else None,
        "significance_z": significance_z if gate_on else None,
        "within_noise": within_noise,
        "reference_sessions": reference_sessions,
        "level_shift_pct": round(level_shift_pct, 2),
        "level_z": round(level_z, 2),
        "recent_slope_per_obs": round(recent_slope, 4),
        "baseline_slope_per_obs": round(baseline_slope, 4),
        "recent_mean": round(recent_mean, 2),
        "historical_ma": round(hist_ma, 2),
        "slope_threshold_pct": slope_threshold_pct,
        "level_z_threshold": level_z_threshold,
        "recent_window": recent_window,
        "baseline_window": len(baseline),
        "onset_date": onset_date.strftime("%Y-%m-%d") if onset_date is not None else None,
        "latest_date": s.index[-1].strftime("%Y-%m-%d") if hasattr(s.index[-1], "strftime") else str(s.index[-1]),
        "observations": n,
    }


def shift_signal_history(
    series: pd.Series,
    recent_window: int = DEFAULT_RECENT_WINDOW,
    baseline_window: int = DEFAULT_BASELINE_WINDOW,
    slope_threshold_pct: float = DEFAULT_SLOPE_THRESHOLD_PCT,
    level_z_threshold: float = DEFAULT_LEVEL_Z_THRESHOLD,
    sessions: int = 180,
    significance_z: Optional[float] = DEFAULT_SIGNIFICANCE_Z,
) -> pd.DataFrame:
    """
    Re-runs the detector as of each of the last `sessions` observations, so the
    page can show when pattern shifts were flagged historically.
    Columns: date, slope_variance_pct, level_shift_pct, level_z, detected.
    """
    s = pd.Series(series).dropna().astype(float)
    n = len(s)
    first_end = max(recent_window + max(14, baseline_window // 3), n - sessions + 1)
    rows = []
    for end in range(first_end, n + 1):
        res = detect_trend_shift(s.iloc[:end], recent_window, baseline_window,
                                 slope_threshold_pct, level_z_threshold, locate_onset=False,
                                 significance_z=significance_z)
        if res.get("status") != "SUCCESS":
            continue
        rows.append({
            "date": s.index[end - 1],
            "slope_variance_pct": res["slope_variance_pct"],
            "level_shift_pct": res["level_shift_pct"],
            "level_z": res["level_z"],
            "detected": res["detected"],
        })
    return pd.DataFrame(rows, columns=["date", "slope_variance_pct", "level_shift_pct", "level_z", "detected"])


def trend_lines(series: pd.Series, recent_window: int = DEFAULT_RECENT_WINDOW,
                baseline_window: int = DEFAULT_BASELINE_WINDOW) -> Dict[str, Any]:
    """
    Least-squares trend lines for the historical (baseline) window and the
    recent window, plus the baseline line extended across the recent window so
    the page can show where prices would be if the old pattern had continued.
    """
    s = pd.Series(series).dropna().astype(float)
    n = len(s)
    if n < recent_window + 3:
        return {}
    b_start = max(0, n - recent_window - baseline_window)
    baseline = s.iloc[b_start:n - recent_window]
    recent = s.iloc[n - recent_window:]

    def fit(seg: pd.Series):
        y = seg.values
        x = np.arange(len(y), dtype=float)
        slope = _ols_slope(y)
        intercept = float(y.mean() - slope * x.mean())
        return slope, intercept

    b_slope, b_int = fit(baseline)
    r_slope, r_int = fit(recent)
    b_x = np.arange(n - b_start, dtype=float)  # baseline window + its extension over the recent window
    return {
        "baseline_dates": list(s.index[b_start:]),
        "baseline_fit": list(b_int + b_slope * b_x),
        "baseline_split": len(baseline),  # first index of the extension
        "recent_dates": list(recent.index),
        "recent_fit": list(r_int + r_slope * np.arange(len(recent), dtype=float)),
        "moving_average": s.rolling(max(5, baseline_window // 2), min_periods=3).mean(),
    }


def recency_parameters(sensitivity: float) -> Dict[str, float]:
    """
    Maps the 0..1 recency-bias control to smoothing parameters.
      alpha - level smoothing (higher = recent observations dominate)
      beta  - trend smoothing (higher = trend reacts faster)
      phi   - trend damping (higher = trend persists further into the horizon)
      blend - share of the recency-weighted projection in the final forecast
    """
    s = float(np.clip(sensitivity, 0.0, 1.0))
    return {
        "alpha": round(0.10 + 0.55 * s, 3),
        "beta": round(0.02 + 0.18 * s, 3),
        "phi": round(0.80 + 0.15 * s, 3),
        "blend": round(0.15 + 0.70 * s, 3),
    }


def holt_damped_state(values: np.ndarray, alpha: float, beta: float, phi: float) -> Tuple[float, float]:
    """Final (level, trend) of damped Holt linear exponential smoothing."""
    y = np.asarray(values, dtype=float)
    if len(y) == 0:
        return 0.0, 0.0
    level = y[0]
    trend = float(np.mean(np.diff(y[:8]))) if len(y) > 1 else 0.0
    for t in range(1, len(y)):
        prev_level = level
        level = alpha * y[t] + (1 - alpha) * (prev_level + phi * trend)
        trend = beta * (level - prev_level) + (1 - beta) * phi * trend
    return float(level), float(trend)


def recalibrate_forecast(
    series: pd.Series,
    forecast_df: pd.DataFrame,
    sensitivity: float = 0.5,
    fit_window: int = DEFAULT_FIT_WINDOW,
    price_floor: float = 1.0,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Blends the baseline forecast with a recency-weighted damped-Holt projection.

    `forecast_df` needs `predicted_modal_price_kg`, `confidence_upper_kg` and
    `confidence_lower_kg` (one row per forecast step). Returns the adjusted
    frame (same columns plus `original_predicted_kg` and `adjustment_kg`) and
    a summary of the calibration.
    """
    params = recency_parameters(sensitivity)
    out = forecast_df.copy().reset_index(drop=True)
    base = out["predicted_modal_price_kg"].to_numpy(dtype=float)

    hist = pd.Series(series).dropna().astype(float).iloc[-fit_window:]
    if len(hist) < 5 or len(base) == 0:
        out["original_predicted_kg"] = base
        out["adjustment_kg"] = 0.0
        return out, {**params, "sensitivity": float(sensitivity), "applied": False,
                     "final_adjustment_kg": 0.0, "final_adjustment_pct": 0.0}

    level, trend = holt_damped_state(hist.values, params["alpha"], params["beta"], params["phi"])
    steps = np.arange(1, len(base) + 1)
    trend_move = np.cumsum(params["phi"] ** steps) * trend

    # Guard rail: the extrapolated trend may not outrun a 2-sigma random-walk
    # envelope of recent day-to-day moves (robust sigma via MAD).
    diffs = np.diff(hist.values)
    sigma = 1.4826 * float(np.median(np.abs(diffs - np.median(diffs)))) if len(diffs) > 2 else 0.0
    if sigma > 0:
        envelope = 2.0 * sigma * np.sqrt(steps)
        trend_move = np.clip(trend_move, -envelope, envelope)
    recency_path = level + trend_move

    w = params["blend"]
    adjusted = np.maximum(price_floor, (1 - w) * base + w * recency_path)

    # Keep the original band width, widened slightly for the extra model uncertainty
    widen = 1.0 + 0.25 * w
    upper_half = np.maximum(0.0, out["confidence_upper_kg"].to_numpy(dtype=float) - base) * widen
    lower_half = np.maximum(0.0, base - out["confidence_lower_kg"].to_numpy(dtype=float)) * widen

    out["original_predicted_kg"] = base
    out["predicted_modal_price_kg"] = np.round(adjusted, 2)
    out["confidence_upper_kg"] = np.round(adjusted + upper_half, 2)
    out["confidence_lower_kg"] = np.round(np.maximum(price_floor, adjusted - lower_half), 2)
    out["adjustment_kg"] = np.round(adjusted - base, 2)

    final_adj = float(adjusted[-1] - base[-1])
    final_pct = final_adj / base[-1] * 100.0 if base[-1] else 0.0
    return out, {
        **params,
        "sensitivity": float(sensitivity),
        "applied": True,
        "smoothed_level_kg": round(level, 2),
        "smoothed_trend_per_obs": round(trend, 4),
        "final_adjustment_kg": round(final_adj, 2),
        "final_adjustment_pct": round(final_pct, 2),
    }


def predictions_from_forecast(forecast_df: pd.DataFrame, horizons=(3, 7, 14)) -> Dict[str, Dict[str, Any]]:
    """Rebuilds the `{h}_day` prediction dict (same shape as train_and_forecast_price)."""
    preds = {}
    for h in horizons:
        if h <= len(forecast_df):
            row = forecast_df.iloc[h - 1]
            preds[f"{h}_day"] = {
                "horizon_days": h,
                "target_date": row["Arrival_Date"],
                "predicted_price_kg": float(row["predicted_modal_price_kg"]),
                "confidence_lower_kg": float(row["confidence_lower_kg"]),
                "confidence_upper_kg": float(row["confidence_upper_kg"]),
            }
    return preds
