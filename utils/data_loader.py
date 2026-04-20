import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import io


def load_meridian_excel(uploaded_file) -> Dict[str, pd.DataFrame]:
    """Parse a Google Meridian MMM results Excel file into structured DataFrames.

    Supports two formats:
      1. Real Meridian Looker Studio export (MediaROI, ModelFit, MediaOutcome, etc.)
      2. Simple dashboard format (media_summary, model_fit, response_curves, etc.)
    """
    xls = pd.ExcelFile(uploaded_file)
    sheet_names_lower = {s.lower().strip(): s for s in xls.sheet_names}

    if "mediaroi" in sheet_names_lower:
        raw = {s: pd.read_excel(xls, sheet_name=s) for s in xls.sheet_names}
        return _transform_meridian_export(raw)

    return _parse_simple_format(xls, sheet_names_lower)


# ---------------------------------------------------------------------------
# Real Meridian export transformation
# ---------------------------------------------------------------------------

def _transform_meridian_export(raw: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Transform native Google Meridian Looker Studio sheets into the
    normalised structure expected by the dashboard pages."""
    data: Dict[str, pd.DataFrame] = {}

    # --- model_fit from ModelDiagnostics ---------------------------------
    if "ModelDiagnostics" in raw:
        diag = raw["ModelDiagnostics"].iloc[0]
        metrics = []
        col_map = {"R Squared": "R-squared", "MAPE": "MAPE", "wMAPE": "wMAPE"}
        for src, dst in col_map.items():
            if src in diag.index:
                metrics.append({"metric": dst, "value": float(diag[src])})
        if metrics:
            data["model_fit"] = pd.DataFrame(metrics)

    # --- media_summary from MediaROI + MediaOutcome + MediaSpend ---------
    if "MediaROI" in raw:
        roi_df = raw["MediaROI"]
        all_roi = roi_df[roi_df["Analysis Period"] == "ALL"].copy().reset_index(drop=True)

        channels = all_roi["Channel"].tolist()
        spend = all_roi["Spend"].values.astype(float)
        roi_vals = all_roi["ROI"].values.astype(float)
        mroi_vals = all_roi["Marginal ROI"].values.astype(float)

        incr_rev = _get_incremental_revenue(raw, channels, spend, roi_vals)
        total_spend = spend.sum()
        total_incr = incr_rev.sum()

        pct_spend, pct_rev = _get_shares(raw, channels, spend, incr_rev)

        media_summary = pd.DataFrame({
            "channel": channels,
            "spend": spend,
            "roi": roi_vals,
            "roi_lower_ci": all_roi["ROI CI Low"].values.astype(float),
            "roi_upper_ci": all_roi["ROI CI High"].values.astype(float),
            "marginal_roi": mroi_vals,
            "incremental_revenue": incr_rev,
            "pct_spend": pct_spend,
            "pct_incremental_revenue": pct_rev,
            "effectiveness": pct_rev,
        })

        data["media_summary"] = media_summary
        data["roi_summary"] = media_summary.copy()

    # --- weekly_decomposition from ModelFit + MediaOutcome ---------------
    if "ModelFit" in raw:
        mf = raw["ModelFit"]
        decomp = pd.DataFrame({
            "date": pd.to_datetime(mf["Time"]),
            "baseline": mf["Baseline"].values.astype(float),
            "total_predicted": mf["Expected"].values.astype(float),
            "total_actual": mf["Actual"].values.astype(float),
        })

        if "expected_ci_low" not in decomp.columns:
            decomp["expected_ci_low"] = mf["Expected CI Low"].values.astype(float)
            decomp["expected_ci_high"] = mf["Expected CI High"].values.astype(float)

        if "media_summary" in data and "MediaOutcome" in raw:
            _add_channel_decomposition(decomp, data["media_summary"], raw["MediaOutcome"])

        data["weekly_decomposition"] = decomp

    # --- response_curves -------------------------------------------------
    if "response_curves" in raw:
        rc_all = _build_response_curves(raw, data.get("media_summary"))
        if rc_all is not None:
            data["response_curves"] = rc_all

    # --- optimal_frequency from reach-frequency optimisation -------------
    if "rf_opt_results" in raw:
        rf = raw["rf_opt_results"]
        all_rf = rf[rf["Group ID"].str.contains(":ALL", na=False)].copy()
        if len(all_rf) > 0:
            data["optimal_frequency"] = pd.DataFrame({
                "channel": all_rf["Channel"].values,
                "current_frequency": np.ones(len(all_rf)),
                "optimal_frequency": all_rf["Optimal Avg Frequency"].values.astype(float),
                "current_reach": np.zeros(len(all_rf), dtype=int),
                "saturation_point": all_rf["Optimal Impression Effectiveness"].values.astype(float)
                    if "Optimal Impression Effectiveness" in all_rf.columns
                    else np.zeros(len(all_rf)),
            })

    # --- budget optimisation results (raw, for reference) ----------------
    for key in ("budget_opt_results", "budget_opt_specs"):
        if key in raw:
            data[key] = raw[key]

    return data


def _get_incremental_revenue(
    raw: Dict[str, pd.DataFrame],
    channels: list,
    spend: np.ndarray,
    roi: np.ndarray,
) -> np.ndarray:
    """Prefer MediaOutcome incremental revenue, fall back to spend * ROI."""
    if "MediaOutcome" in raw:
        outcome = raw["MediaOutcome"]
        all_out = outcome[
            (outcome["Analysis Period"] == "ALL") & (outcome["Channel"] != "baseline")
            & (outcome["Channel"] != "All Channels")
        ]
        outcome_map = dict(zip(all_out["Channel"], all_out["Incremental Outcome"].astype(float)))
        mapped = np.array([outcome_map.get(ch, s * r) for ch, s, r in zip(channels, spend, roi)])
        return mapped
    return spend * roi


def _get_shares(
    raw: Dict[str, pd.DataFrame],
    channels: list,
    spend: np.ndarray,
    incr_rev: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return (pct_spend, pct_incremental_revenue) arrays in 0-100 scale."""
    total_spend = spend.sum()
    total_rev = incr_rev.sum()
    default_pct_spend = spend / total_spend * 100 if total_spend else np.zeros_like(spend)
    default_pct_rev = incr_rev / total_rev * 100 if total_rev else np.zeros_like(incr_rev)

    if "MediaSpend" not in raw:
        return default_pct_spend, default_pct_rev

    ms = raw["MediaSpend"]
    all_ms = ms[ms["Analysis Period"] == "ALL"]

    spend_share_map = dict(zip(
        all_ms.loc[all_ms["Label"] == "Spend Share", "Channel"],
        all_ms.loc[all_ms["Label"] == "Spend Share", "Share Value"].astype(float),
    ))
    rev_share_map = dict(zip(
        all_ms.loc[all_ms["Label"] == "Revenue Share", "Channel"],
        all_ms.loc[all_ms["Label"] == "Revenue Share", "Share Value"].astype(float),
    ))

    pct_spend = np.array([spend_share_map.get(ch, d / 100) * 100
                          for ch, d in zip(channels, default_pct_spend)])
    pct_rev = np.array([rev_share_map.get(ch, d / 100) * 100
                        for ch, d in zip(channels, default_pct_rev)])
    return pct_spend, pct_rev


def _add_channel_decomposition(
    decomp: pd.DataFrame,
    media_summary: pd.DataFrame,
    media_outcome_raw: pd.DataFrame,
) -> None:
    """Add per-channel columns to decomp by distributing media effect using
    each channel's contribution share from MediaOutcome."""
    all_out = media_outcome_raw[
        (media_outcome_raw["Analysis Period"] == "ALL")
        & (media_outcome_raw["Channel"] != "baseline")
        & (media_outcome_raw["Channel"] != "All Channels")
    ]
    total_media = all_out["Incremental Outcome"].sum()
    if total_media <= 0:
        return

    media_effect = (decomp["total_predicted"] - decomp["baseline"]).clip(lower=0)
    for _, row in all_out.iterrows():
        share = row["Incremental Outcome"] / total_media
        decomp[row["Channel"]] = media_effect * share


def _build_response_curves(
    raw: Dict[str, pd.DataFrame],
    media_summary: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    """Build response_curves DataFrame from the Meridian response_curves sheet."""
    if "response_curves" not in raw:
        return None

    rc = raw["response_curves"]
    all_rc = rc[rc["Group ID"].str.contains(":ALL", na=False)].copy()
    if len(all_rc) == 0:
        return None

    all_rc = all_rc.rename(columns={
        "Channel": "channel",
        "Spend": "spend_level",
        "Incremental Outcome": "incremental_revenue",
    })
    all_rc = all_rc[["channel", "spend_level", "incremental_revenue"]].copy()

    if media_summary is not None:
        spend_map = dict(zip(media_summary["channel"], media_summary["spend"]))
        rev_map = dict(zip(media_summary["channel"], media_summary["incremental_revenue"]))
        all_rc["current_spend"] = all_rc["channel"].map(spend_map)
        all_rc["current_revenue"] = all_rc["channel"].map(rev_map)
    else:
        all_rc["current_spend"] = 0.0
        all_rc["current_revenue"] = 0.0

    return all_rc.dropna(subset=["current_spend", "current_revenue"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Simple / legacy format parser
# ---------------------------------------------------------------------------

def _parse_simple_format(
    xls: pd.ExcelFile,
    sheet_names_lower: Dict[str, str],
) -> Dict[str, pd.DataFrame]:
    """Fall-back parser for simple dashboard-format Excel files."""
    data: Dict[str, pd.DataFrame] = {}

    sheet_map = {
        "media_summary": ["media_summary", "summary", "mediasummary", "media summary", "channel_summary"],
        "model_fit": ["model_fit", "modelfit", "model fit", "fit_statistics", "diagnostics"],
        "response_curves": ["response_curves", "response curves", "responsecurves", "saturation", "diminishing_returns"],
        "weekly_decomposition": ["weekly_decomposition", "decomposition", "weekly decomposition", "sales_decomposition", "contribution"],
        "roi_summary": ["roi_summary", "roi", "roi summary", "roisummary", "return_on_investment"],
        "optimal_frequency": ["optimal_frequency", "optimal frequency", "frequency", "optimal_analysis"],
        "raw_data": ["raw_data", "raw data", "input_data", "input data", "rawdata"],
    }

    available = [s.lower().strip() for s in xls.sheet_names]

    for key, possible_names in sheet_map.items():
        for name in possible_names:
            if name in available:
                idx = available.index(name)
                data[key] = pd.read_excel(xls, sheet_name=xls.sheet_names[idx])
                break

    for sheet_name in xls.sheet_names:
        normalized = sheet_name.lower().strip()
        already_loaded = any(normalized in names for names in sheet_map.values())
        if not already_loaded and normalized not in [v for vals in sheet_map.values() for v in vals]:
            data[sheet_name] = pd.read_excel(xls, sheet_name=sheet_name)

    return data


# ---------------------------------------------------------------------------
# Sample data generation (unchanged)
# ---------------------------------------------------------------------------

def generate_sample_data() -> Dict[str, pd.DataFrame]:
    """Generate realistic sample data mimicking Google Meridian MMM outputs."""
    np.random.seed(42)

    channels = [
        "Google Search", "Google PMax", "Meta (Facebook)", "Meta (Instagram)",
        "TikTok", "YouTube", "Display & Video 360", "Email Marketing",
        "Affiliate", "TV (Linear)", "Radio", "OOH"
    ]

    spend = np.array([
        450000, 380000, 520000, 280000, 150000, 320000, 180000,
        45000, 95000, 600000, 120000, 200000
    ])
    roi = np.array([3.2, 2.8, 2.5, 2.1, 3.8, 1.9, 1.5, 5.2, 4.1, 1.3, 1.1, 0.9])
    mroi = roi * np.random.uniform(0.4, 0.8, len(channels))
    incremental_revenue = spend * roi
    effectiveness = incremental_revenue / incremental_revenue.sum() * 100

    roi_lower = roi * 0.7
    roi_upper = roi * 1.35
    mroi_lower = mroi * 0.65
    mroi_upper = mroi * 1.4

    cpas = spend / (incremental_revenue / np.random.uniform(50, 200, len(channels)))

    media_summary = pd.DataFrame({
        "channel": channels,
        "spend": spend,
        "roi": roi,
        "roi_lower_ci": roi_lower,
        "roi_upper_ci": roi_upper,
        "marginal_roi": mroi,
        "mroi_lower_ci": mroi_lower,
        "mroi_upper_ci": mroi_upper,
        "incremental_revenue": incremental_revenue,
        "pct_spend": spend / spend.sum() * 100,
        "pct_incremental_revenue": effectiveness,
        "effectiveness": effectiveness,
        "cpa": cpas,
    })

    model_fit = pd.DataFrame({
        "metric": ["R-squared", "MAPE", "wMAPE", "NRMSE", "DW Statistic"],
        "value": [0.94, 0.062, 0.055, 0.078, 1.87],
    })

    weeks = pd.date_range("2024-01-01", periods=104, freq="W-MON")
    decomp_data = {"date": weeks}
    base_sales = 800000 + 50000 * np.sin(np.linspace(0, 4 * np.pi, 104)) + np.random.normal(0, 20000, 104)
    decomp_data["baseline"] = base_sales
    decomp_data["promotions"] = np.random.uniform(30000, 120000, 104)
    decomp_data["seasonality"] = 60000 * np.sin(np.linspace(0, 4 * np.pi, 104)) + 60000

    for i, ch in enumerate(channels):
        channel_contrib = spend[i] / 52 * roi[i] * np.random.uniform(0.6, 1.4, 104)
        channel_contrib *= (1 + 0.3 * np.sin(np.linspace(0, 4 * np.pi, 104) + i))
        decomp_data[ch] = np.maximum(channel_contrib, 0)

    decomp_data["total_predicted"] = base_sales + decomp_data["promotions"] + decomp_data["seasonality"]
    for ch in channels:
        decomp_data["total_predicted"] = decomp_data["total_predicted"] + decomp_data[ch]
    decomp_data["total_actual"] = decomp_data["total_predicted"] * np.random.uniform(0.96, 1.04, 104)

    weekly_decomposition = pd.DataFrame(decomp_data)

    response_curves = []
    for i, ch in enumerate(channels):
        max_spend = spend[i] * 3
        spend_range = np.linspace(0, max_spend, 100)

        half_saturation = spend[i] * np.random.uniform(0.6, 1.2)
        slope = roi[i] * half_saturation
        response = slope * spend_range / (half_saturation + spend_range)

        response_curves.append(pd.DataFrame({
            "channel": ch,
            "spend_level": spend_range,
            "incremental_revenue": response,
            "current_spend": spend[i],
            "current_revenue": slope * spend[i] / (half_saturation + spend[i]),
        }))
    response_curves_df = pd.concat(response_curves, ignore_index=True)

    roi_summary = pd.DataFrame({
        "channel": channels,
        "roi": roi,
        "roi_lower_ci": roi_lower,
        "roi_upper_ci": roi_upper,
        "marginal_roi": mroi,
        "mroi_lower_ci": mroi_lower,
        "mroi_upper_ci": mroi_upper,
        "spend": spend,
        "incremental_revenue": incremental_revenue,
        "pct_of_total_spend": spend / spend.sum() * 100,
        "pct_of_incremental_revenue": effectiveness,
    })

    optimal_freq = pd.DataFrame({
        "channel": [c for c in channels if c not in ["Email Marketing", "Affiliate"]],
        "current_frequency": np.random.uniform(1.5, 8.0, len(channels) - 2),
        "optimal_frequency": np.random.uniform(2.0, 6.0, len(channels) - 2),
        "current_reach": np.random.uniform(500000, 5000000, len(channels) - 2).astype(int),
        "saturation_point": np.random.uniform(0.5, 0.85, len(channels) - 2),
    })

    return {
        "media_summary": media_summary,
        "model_fit": model_fit,
        "response_curves": response_curves_df,
        "weekly_decomposition": weekly_decomposition,
        "roi_summary": roi_summary,
        "optimal_frequency": optimal_freq,
    }


def compute_optimizer_scenarios(
    media_summary: pd.DataFrame,
    response_curves: pd.DataFrame,
    total_budget: float,
    optimization_target: str = "revenue",
) -> pd.DataFrame:
    """Compute optimized budget allocation using response curve data."""
    channels = media_summary["channel"].tolist()
    current_spend = media_summary["spend"].values.copy()
    current_total = current_spend.sum()
    budget_ratio = total_budget / current_total

    optimized_spend = current_spend.copy()
    mroi = media_summary["marginal_roi"].values.copy()

    for _ in range(50):
        mroi_normalized = mroi / mroi.sum()
        optimized_spend = total_budget * mroi_normalized

        for i, ch in enumerate(channels):
            ch_data = response_curves[response_curves["channel"] == ch]
            if len(ch_data) > 0:
                spend_vals = ch_data["spend_level"].values
                rev_vals = ch_data["incremental_revenue"].values
                idx = np.searchsorted(spend_vals, optimized_spend[i])
                idx = min(idx, len(rev_vals) - 2)
                if idx > 0:
                    local_mroi = (rev_vals[idx] - rev_vals[idx - 1]) / (spend_vals[idx] - spend_vals[idx - 1] + 1e-6)
                    mroi[i] = max(local_mroi, 0.01)

    optimized_spend = optimized_spend / optimized_spend.sum() * total_budget

    optimized_revenue = []
    for i, ch in enumerate(channels):
        ch_data = response_curves[response_curves["channel"] == ch]
        if len(ch_data) > 0:
            spend_vals = ch_data["spend_level"].values
            rev_vals = ch_data["incremental_revenue"].values
            rev = np.interp(optimized_spend[i], spend_vals, rev_vals)
            optimized_revenue.append(rev)
        else:
            optimized_revenue.append(optimized_spend[i] * media_summary.loc[i, "roi"])

    current_revenue = media_summary["incremental_revenue"].values

    return pd.DataFrame({
        "channel": channels,
        "current_spend": current_spend,
        "optimized_spend": optimized_spend,
        "spend_change": optimized_spend - current_spend,
        "spend_change_pct": (optimized_spend - current_spend) / (current_spend + 1e-6) * 100,
        "current_revenue": current_revenue,
        "optimized_revenue": optimized_revenue,
        "revenue_change": np.array(optimized_revenue) - current_revenue,
        "current_roi": current_revenue / (current_spend + 1e-6),
        "optimized_roi": np.array(optimized_revenue) / (optimized_spend + 1e-6),
    })
