import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date, timedelta
from utils.data_loader import compute_optimizer_scenarios
from utils.charts import format_currency, CHART_LAYOUT, COLORS, page_header, setup_page, sidebar_logo

st.set_page_config(page_title="Optimizer | s360 MMM", page_icon="🎯", layout="wide")
setup_page()
sidebar_logo()

data = st.session_state.data
media = data.get("media_summary")
response = data.get("response_curves")
budget_opt = data.get("budget_opt_results")
budget_specs = data.get("budget_opt_specs")
decomp = data.get("weekly_decomposition")

if media is None:
    st.info("No media data available. Please upload an Excel file.")
    st.stop()

channels = media["channel"].tolist()
current_spend = media["spend"].values.astype(float)
current_total = float(current_spend.sum())

spec_min_map = {}
spec_max_map = {}
if budget_specs is not None:
    specs_all = (
        budget_specs[budget_specs["Analysis Period"] == "ALL"]
        if "Analysis Period" in budget_specs.columns
        else budget_specs
    )
    if "Channel Spend Min" in specs_all.columns:
        spec_min_map = dict(zip(specs_all["Channel"], specs_all["Channel Spend Min"].astype(float)))
    if "Channel Spend Max" in specs_all.columns:
        spec_max_map = dict(zip(specs_all["Channel"], specs_all["Channel Spend Max"].astype(float)))

if decomp is not None and "date" in decomp.columns:
    _data_min = decomp["date"].min().date()
    _data_max = decomp["date"].max().date()
else:
    _data_min = date(2023, 1, 2)
    _data_max = date(2025, 8, 25)


def _week_label(d):
    return f"w{d.isocalendar()[1]:02d} {d.year}"


# ── Session state init ──

if "_opt_scenarios" not in st.session_state:
    st.session_state["_opt_scenarios"] = []
if "_opt_active_idx" not in st.session_state:
    st.session_state["_opt_active_idx"] = None
if "_opt_copy_from" not in st.session_state:
    st.session_state["_opt_copy_from"] = None


def _run_optimization(scenario):
    ms = media
    rc = response
    total_budget = scenario["budget"]
    sel_channels = scenario.get("selected_channels", channels)

    filtered_ms = ms[ms["channel"].isin(sel_channels)].reset_index(drop=True)
    f_spend = filtered_ms["spend"].values.astype(float)

    if scenario["mode"] == "Reference scenario":
        return pd.DataFrame({
            "channel": filtered_ms["channel"],
            "current_spend": f_spend,
            "optimized_spend": f_spend.copy(),
            "spend_change": np.zeros(len(filtered_ms)),
            "spend_change_pct": np.zeros(len(filtered_ms)),
            "current_revenue": filtered_ms["incremental_revenue"].values.astype(float),
            "optimized_revenue": filtered_ms["incremental_revenue"].values.astype(float).copy(),
            "revenue_change": np.zeros(len(filtered_ms)),
            "current_roi": filtered_ms["roi"].values.astype(float),
            "optimized_roi": filtered_ms["roi"].values.astype(float).copy(),
        })

    if (
        budget_opt is not None
        and abs(total_budget - current_total) / max(current_total, 1) < 0.01
        and "Group ID" in budget_opt.columns
    ):
        opt_all = budget_opt[budget_opt["Group ID"].str.contains(":ALL", na=False)].copy()
        if len(opt_all) >= len(sel_channels):
            osm = dict(zip(opt_all["Channel"], opt_all["Optimal Spend"].astype(float)))
            orm = dict(zip(opt_all["Channel"], opt_all["Optimal ROI"].astype(float)))
            opt_s = np.array([osm.get(ch, cs) for ch, cs in zip(sel_channels, f_spend)])
            opt_r = np.array([orm.get(ch, r) for ch, r in zip(sel_channels, filtered_ms["roi"].values)])
            opt_rev = opt_s * opt_r
            return pd.DataFrame({
                "channel": sel_channels, "current_spend": f_spend,
                "optimized_spend": opt_s, "spend_change": opt_s - f_spend,
                "spend_change_pct": (opt_s - f_spend) / (f_spend + 1e-6) * 100,
                "current_revenue": filtered_ms["incremental_revenue"].values.astype(float),
                "optimized_revenue": opt_rev,
                "revenue_change": opt_rev - filtered_ms["incremental_revenue"].values.astype(float),
                "current_roi": filtered_ms["roi"].values.astype(float), "optimized_roi": opt_r,
            })

    if rc is not None:
        filtered_rc = rc[rc["channel"].isin(sel_channels)]
        if len(filtered_rc) > 0:
            return compute_optimizer_scenarios(filtered_ms, filtered_rc, total_budget)

    mroi = filtered_ms["marginal_roi"].values if "marginal_roi" in filtered_ms.columns else filtered_ms["roi"].values
    mroi_n = mroi / mroi.sum()
    opt_s = total_budget * mroi_n
    return pd.DataFrame({
        "channel": filtered_ms["channel"], "current_spend": filtered_ms["spend"],
        "optimized_spend": opt_s,
        "spend_change": opt_s - filtered_ms["spend"].values,
        "spend_change_pct": (opt_s - filtered_ms["spend"].values) / (filtered_ms["spend"].values + 1e-6) * 100,
        "current_revenue": filtered_ms["incremental_revenue"],
        "optimized_revenue": opt_s * filtered_ms["roi"].values,
        "revenue_change": opt_s * filtered_ms["roi"].values - filtered_ms["incremental_revenue"].values,
        "current_roi": filtered_ms["roi"], "optimized_roi": filtered_ms["roi"],
    })


# ══════════════════════════════════════════════════════════════
#  SCENARIO CREATION DIALOG
# ══════════════════════════════════════════════════════════════

@st.dialog("Create Scenario", width="large")
def scenario_dialog():
    existing = st.session_state.get("_opt_scenarios", [])
    copy_from = st.session_state.get("_opt_copy_from")
    prefill = copy_from if copy_from else None

    # ── A. Scenario Identity ──
    st.markdown("##### Scenario Identity")
    a1, a2 = st.columns(2)
    with a1:
        default_name = f"Scenario {len(existing) + 1}"
        if prefill:
            default_name = f"{prefill['name']} (copy)"
        sc_name = st.text_input("Scenario name", value=default_name, key="_dlg_name")
    with a2:
        sc_type = st.radio(
            "Type",
            ["New scenario", "Copy own scenario", "Copy public scenario"],
            horizontal=True,
            key="_dlg_type",
        )

    if sc_type == "Copy own scenario" and len(existing) > 0 and prefill is None:
        src_idx = st.selectbox(
            "Copy from",
            range(len(existing)),
            format_func=lambda i: existing[i]["name"],
            key="_dlg_copy_src",
        )
        prefill = existing[src_idx]
    elif sc_type == "Copy public scenario":
        st.info("No public scenarios available yet.")

    st.markdown("---")

    # ── B. Optimization Mode ──
    st.markdown("##### Optimization Mode")
    b1, b2 = st.columns(2)
    modes = [
        "Budget optimization", "Total sales target",
        "Incremental sales target", "Reference scenario", "Target ROI",
    ]
    with b1:
        def_mode_idx = modes.index(prefill["mode"]) if prefill and prefill.get("mode") in modes else 0
        opt_mode = st.radio("Mode", modes, index=def_mode_idx, key="_dlg_mode")

    with b2:
        if opt_mode == "Budget optimization":
            def_budget = prefill["budget"] if prefill else current_total
            total_budget = st.number_input(
                "Budget ($)", value=float(def_budget), step=10000.0, format="%.0f", key="_dlg_budget",
            )
        elif opt_mode in ("Total sales target", "Incremental sales target"):
            cr = float(media["incremental_revenue"].sum())
            def_target = prefill.get("budget", cr * 1.1) if prefill else cr * 1.1
            label = "Total sales target ($)" if opt_mode == "Total sales target" else "Incremental sales target ($)"
            target_rev = st.number_input(label, value=float(def_target), step=50000.0, format="%.0f", key="_dlg_target")
            total_budget = current_total * (target_rev / cr) if cr > 0 else current_total
        elif opt_mode == "Target ROI":
            def_roi = prefill.get("target_roi", 1.5) if prefill else 1.5
            target_roi_val = st.number_input("Target ROI (x)", value=float(def_roi), step=0.1, format="%.2f", key="_dlg_troi")
            total_budget = current_total
        else:
            total_budget = current_total

    st.markdown("---")

    # ── C. Default Week Selection ──
    st.markdown("##### Default Week Selection")
    wk_modes = ["Number of weeks", "Calendar weeks (in order)", "Calendar weeks (match week numbers)"]
    def_wk = prefill.get("week_selection_mode", wk_modes[0]) if prefill else wk_modes[0]
    def_wk_idx = wk_modes.index(def_wk) if def_wk in wk_modes else 0
    wk_sel = st.radio("Selection method", wk_modes, index=def_wk_idx, horizontal=True, key="_dlg_wkmode")
    if wk_sel == "Number of weeks":
        n_weeks = st.number_input("Weeks", min_value=1, max_value=104,
                                  value=prefill.get("n_weeks", 4) if prefill else 4, key="_dlg_nwk")
    else:
        n_weeks = 4

    st.markdown("---")

    # ── D. Media Performance Selection ──
    st.markdown("##### Media Performance Selection")
    perf_opts = [
        "Use model performance estimates",
        "Use reference period media performance",
        "Use historical average performance",
    ]
    def_perf = prefill.get("perf_selection", perf_opts[0]) if prefill else perf_opts[0]
    def_perf_idx = perf_opts.index(def_perf) if def_perf in perf_opts else 0
    perf_sel = st.radio("Performance source", perf_opts, index=def_perf_idx, key="_dlg_perf")

    st.markdown("---")

    # ── E. Investment Forecast Selection ──
    st.markdown("##### Investment Forecast Selection")
    inv_opts = ["Use reference period investment", "Use model forecast investment"]
    def_inv = prefill.get("invest_selection", inv_opts[0]) if prefill else inv_opts[0]
    def_inv_idx = inv_opts.index(def_inv) if def_inv in inv_opts else 0
    inv_sel = st.radio("Investment source", inv_opts, index=def_inv_idx, horizontal=True, key="_dlg_inv")

    st.markdown("---")

    # ── F. Time Period to Optimize ──
    st.markdown("##### Time Period to Optimize")
    f1, f2, f3 = st.columns([2, 2, 1])
    def_ps = prefill.get("period_start", _data_min) if prefill else _data_min
    def_pe = prefill.get("period_end", _data_max) if prefill else _data_max
    with f1:
        p_start = st.date_input("Start", value=def_ps, min_value=_data_min, max_value=_data_max, key="_dlg_ps")
    with f2:
        p_end = st.date_input("End", value=def_pe, min_value=_data_min, max_value=_data_max, key="_dlg_pe")
    with f3:
        delta_wks = max(1, (p_end - p_start).days // 7)
        st.markdown(f"<br><span style='color:#64748B; font-size:0.9rem;'>{_week_label(p_start)} — {_week_label(p_end)}</span><br>"
                    f"<strong style='color:#1E293B;'>{delta_wks} weeks</strong>",
                    unsafe_allow_html=True)

    st.markdown("---")

    # ── G. Reference Time Period ──
    st.markdown("##### Reference Time Period")
    ref_modes = [
        "Use same weeks from last year",
        "Use same weeks as Time period to optimize",
        "Use most recent weeks",
        "Custom time period",
    ]
    def_rm = prefill.get("ref_mode", ref_modes[0]) if prefill else ref_modes[0]
    def_rm_idx = ref_modes.index(def_rm) if def_rm in ref_modes else 0
    ref_mode = st.radio("Reference period", ref_modes, index=def_rm_idx, key="_dlg_refmode")

    if ref_mode == "Use same weeks from last year":
        ref_start = p_start - timedelta(weeks=52)
        ref_end = p_end - timedelta(weeks=52)
    elif ref_mode == "Use same weeks as Time period to optimize":
        ref_start = p_start
        ref_end = p_end
    elif ref_mode == "Use most recent weeks":
        ref_end = _data_max
        ref_start = ref_end - timedelta(weeks=delta_wks)
    else:
        g1, g2 = st.columns(2)
        def_rs = prefill.get("ref_period_start", _data_min) if prefill else _data_min
        def_re = prefill.get("ref_period_end", _data_max) if prefill else _data_max
        with g1:
            ref_start = st.date_input("Ref start", value=def_rs, key="_dlg_rs")
        with g2:
            ref_end = st.date_input("Ref end", value=def_re, key="_dlg_re")

    ref_wks = max(1, (ref_end - ref_start).days // 7)
    st.caption(f"{_week_label(ref_start)} — {_week_label(ref_end)}  ({ref_wks} weeks)")

    st.markdown("---")

    # ── H. Dimensions ──
    st.markdown("##### Dimensions")
    h1, h2 = st.columns(2)
    with h1:
        def_ch = prefill.get("selected_channels", channels) if prefill else channels
        sel_channels = st.multiselect(
            "Advertising channel",
            channels,
            default=def_ch,
            key="_dlg_channels",
        )
        st.caption(f"{len(sel_channels)} selected")

    with h2:
        st.selectbox("Country", ["All countries"], disabled=True, key="_dlg_country",
                      help="Not available in dataset")
        st.selectbox("Customer type", ["All types"], disabled=True, key="_dlg_cust",
                      help="Not available in dataset")

    h3, h4 = st.columns(2)
    with h3:
        st.selectbox("Sales Channel", ["All channels"], disabled=True, key="_dlg_saleschan",
                      help="Not available in dataset")
        st.selectbox("Product category", ["Overall"], disabled=True, key="_dlg_prodcat",
                      help="Not available in dataset")
    with h4:
        st.selectbox("Planning group", ["Default"], disabled=True, key="_dlg_plangrp",
                      help="Not available in dataset")

    st.markdown("---")

    # ── I. Channel Boundaries ──
    if opt_mode != "Reference scenario":
        st.markdown("##### Channel Budget Boundaries")

        pct_opts = {"Reset": 0, "±5%": 5, "±10%": 10, "±20%": 20, "±30%": 30, "Full Range": 100}
        qc = st.columns(len(pct_opts))
        chosen_pct = 0
        for i, (lbl, pv) in enumerate(pct_opts.items()):
            with qc[i]:
                if st.button(lbl, use_container_width=True, key=f"_dlg_q_{pv}"):
                    chosen_pct = pv
                    st.session_state["_dlg_qpct"] = pv
        global_pct = st.session_state.get("_dlg_qpct", 0)

        channel_bounds = {}
        for idx, ch in enumerate(sel_channels):
            ch_idx = channels.index(ch)
            cs = float(current_spend[ch_idx])
            abs_max = float(spec_max_map.get(ch, cs * 3))

            if global_pct == 0:
                d_lo, d_hi = cs, cs
            elif global_pct >= 100:
                d_lo = float(spec_min_map.get(ch, 0))
                d_hi = abs_max
            else:
                d_lo = max(cs * (1 - global_pct / 100), 0)
                d_hi = cs * (1 + global_pct / 100)

            sl_max = max(abs_max, cs * 2, 1)
            rng = st.slider(
                f"{ch}  (current: {format_currency(cs)})",
                min_value=0.0, max_value=float(sl_max),
                value=(float(d_lo), float(min(d_hi, sl_max))),
                format="$%.0f", key=f"_dlg_rng_{ch}",
            )
            channel_bounds[ch] = (rng[0], rng[1])
    else:
        channel_bounds = {ch: (float(current_spend[channels.index(ch)]),
                               float(current_spend[channels.index(ch)]))
                          for ch in sel_channels}

    st.markdown("---")

    # ── FOOTER: Create & Optimize ──
    st.markdown(
        "<style>#_dlg_create > button { background:#4A6CF7 !important; color:white !important; "
        "border:none !important; font-size:1.05rem !important; padding:0.65rem !important; "
        "border-radius:10px !important; }"
        "#_dlg_create > button:hover { background:#3B5DE7 !important; }</style>",
        unsafe_allow_html=True,
    )
    if st.button("Create & Optimize", use_container_width=True, key="_dlg_create"):
        scenario = {
            "name": sc_name,
            "mode": opt_mode,
            "budget": total_budget,
            "period_start": p_start,
            "period_end": p_end,
            "ref_period_start": ref_start,
            "ref_period_end": ref_end,
            "ref_mode": ref_mode,
            "week_selection_mode": wk_sel,
            "n_weeks": n_weeks if wk_sel == "Number of weeks" else delta_wks,
            "perf_selection": perf_sel,
            "invest_selection": inv_sel,
            "selected_channels": sel_channels,
            "channel_bounds": channel_bounds,
            "target_roi": target_roi_val if opt_mode == "Target ROI" else None,
        }
        scenario["result"] = _run_optimization(scenario)
        st.session_state["_opt_scenarios"].append(scenario)
        st.session_state["_opt_active_idx"] = len(st.session_state["_opt_scenarios"]) - 1
        st.session_state["_opt_copy_from"] = None
        st.rerun()


# ══════════════════════════════════════════════════════════════
#  PAGE LAYOUT
# ══════════════════════════════════════════════════════════════

page_header("Media Optimizer", "Build scenarios, optimise budget allocation, and forecast sales")

scenarios = st.session_state.get("_opt_scenarios", [])
active_idx = st.session_state.get("_opt_active_idx")

# ── Toolbar ──
tb1, tb2, tb3 = st.columns([1.3, 1, 5])
with tb1:
    if st.button("+ Create Scenario", use_container_width=True, key="_btn_create"):
        st.session_state["_opt_copy_from"] = None
        scenario_dialog()
with tb2:
    if len(scenarios) > 0 and st.button("Refresh", use_container_width=True, key="_btn_refresh"):
        if active_idx is not None and active_idx < len(scenarios):
            sc = scenarios[active_idx]
            sc["result"] = _run_optimization(sc)
            st.rerun()

# ── Empty state ──
if len(scenarios) == 0:
    st.markdown(
        "<div style='text-align:center; padding:5rem 0; color:#94A3B8;'>"
        "<div style='font-size:3rem; margin-bottom:1rem;'>🎯</div>"
        "<p style='font-size:1.1rem; font-weight:500; color:#64748B;'>No scenarios yet</p>"
        "<p style='font-size:0.9rem;'>Click <b>+ Create Scenario</b> to get started.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

# ── Scenario cards ──
st.markdown("---")
card_cols = st.columns(min(len(scenarios), 5))
for i, sc in enumerate(scenarios):
    is_active = (i == active_idx)
    border_color = "#4A6CF7" if is_active else "#E2E8F0"
    bg = "#F0F4FF" if is_active else "#FFFFFF"
    with card_cols[i % len(card_cols)]:
        st.markdown(
            f"<div style='background:{bg}; border:2px solid {border_color}; "
            f"border-radius:10px; padding:0.8rem; margin-bottom:0.5rem; min-height:100px;'>"
            f"<strong style='color:#1E293B; font-size:0.95rem;'>{sc['name']}</strong><br>"
            f"<span style='color:#64748B; font-size:0.78rem;'>{sc['mode']}</span><br>"
            f"<span style='color:#94A3B8; font-size:0.72rem;'>"
            f"Budget: {format_currency(sc['budget'])} &middot; "
            f"{len(sc['selected_channels'])} channels</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("Select" if not is_active else "Active", key=f"_sel_{i}",
                          use_container_width=True, disabled=is_active):
                st.session_state["_opt_active_idx"] = i
                st.rerun()
        with bc2:
            if st.button("Copy", key=f"_copy_{i}", use_container_width=True):
                st.session_state["_opt_copy_from"] = sc
                scenario_dialog()

if active_idx is None or active_idx >= len(scenarios):
    st.session_state["_opt_active_idx"] = 0
    active_idx = 0

sc = scenarios[active_idx]
result = sc.get("result")
if result is None:
    result = _run_optimization(sc)
    sc["result"] = result

total_budget = sc["budget"]
sel_channels = sc["selected_channels"]


# ══════════════════════════════════════════════════════════════
#  RESULTS VIEW
# ══════════════════════════════════════════════════════════════

st.markdown("---")
st.markdown(
    f"<div style='display:flex; align-items:center; gap:0.5rem; margin-bottom:0.75rem;'>"
    f"<span style='color:#1E293B; font-size:1.1rem; font-weight:600;'>"
    f"Results: {sc['name']}</span>"
    f"<span style='background:#E2E8F0; color:#475569; font-size:0.72rem; padding:2px 8px; "
    f"border-radius:6px; font-weight:500;'>{sc['mode']}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

# ── KPI row ──
f_spend = result["current_spend"].values
curr_rev_total = float(result["current_revenue"].sum())
opt_rev_total = float(result["optimized_revenue"].sum())
uplift = opt_rev_total - curr_rev_total
uplift_pct = uplift / curr_rev_total * 100 if curr_rev_total > 0 else 0

k = st.columns(5)
k[0].metric("Current Revenue", format_currency(curr_rev_total))
k[1].metric("Optimised Revenue", format_currency(opt_rev_total))
k[2].metric("Revenue Uplift", format_currency(uplift), f"{uplift_pct:+.1f}%")
opt_roi = opt_rev_total / total_budget if total_budget > 0 else 0
cur_roi = curr_rev_total / float(f_spend.sum()) if f_spend.sum() > 0 else 0
k[3].metric("Optimised ROI", f"{opt_roi:.2f}x", f"{(opt_roi - cur_roi):+.2f}x")
n_up = int((result["spend_change"] > 1).sum())
n_dn = int((result["spend_change"] < -1).sum())
k[4].metric("Reallocation", f"{n_up} ↑  {n_dn} ↓")

st.markdown("---")

# ── Result tabs ──
t_charts, t_table, t_ts, t_rc, t_decomp = st.tabs([
    "Result Charts", "Result Table", "Weekly Pacing",
    "Response Curves", "Sales Decomposition",
])

with t_charts:
    st.markdown("#### Current vs. Optimised Budget Allocation")
    sr = result.sort_values("current_spend", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=sr["channel"], x=sr["current_spend"], name="Current",
                         orientation="h", marker=dict(color="rgba(74,108,247,0.55)")))
    fig.add_trace(go.Bar(y=sr["channel"], x=sr["optimized_spend"], name="Optimised",
                         orientation="h", marker=dict(color="rgba(72,187,120,0.55)")))
    fig.update_layout(**CHART_LAYOUT, barmode="group",
                      height=max(440, len(sel_channels) * 40), xaxis_title="Spend ($)")
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### ROI Comparison")
        sr2 = result.sort_values("optimized_roi", ascending=True)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(y=sr2["channel"], x=sr2["current_roi"], name="Current ROI",
                              orientation="h", marker=dict(color="rgba(74,108,247,0.6)")))
        fig2.add_trace(go.Bar(y=sr2["channel"], x=sr2["optimized_roi"], name="Optimised ROI",
                              orientation="h", marker=dict(color="rgba(72,187,120,0.6)")))
        fig2.add_vline(x=1.0, line=dict(color="rgba(245,101,101,0.4)", dash="dash"))
        fig2.update_layout(**CHART_LAYOUT, barmode="group",
                           height=max(400, len(sel_channels) * 34), xaxis_title="ROI")
        st.plotly_chart(fig2, use_container_width=True)
    with c2:
        st.markdown("##### Budget Change")
        sc_sort = result.sort_values("spend_change", ascending=False)
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=sc_sort["channel"], y=sc_sort["spend_change"],
            marker=dict(color=["#48BB78" if v > 0 else "#F56565" for v in sc_sort["spend_change"]], opacity=0.85),
            text=[f"{v:+,.0f}" for v in sc_sort["spend_change"]], textposition="outside",
            textfont=dict(size=9, color="#334155"),
        ))
        fig3.update_layout(**CHART_LAYOUT, height=max(400, len(sel_channels) * 34),
                           yaxis_title="Change ($)", showlegend=False)
        fig3.update_xaxes(tickangle=-45)
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("##### Allocation Split")
    p1, p2 = st.columns(2)
    with p1:
        fp1 = go.Figure(data=[go.Pie(labels=result["channel"], values=result["current_spend"],
                                     hole=0.45, marker=dict(colors=COLORS[:len(result)]),
                                     textinfo="label+percent", textfont=dict(size=9))])
        fp1.update_layout(**CHART_LAYOUT, title="Current", height=370)
        st.plotly_chart(fp1, use_container_width=True)
    with p2:
        fp2 = go.Figure(data=[go.Pie(labels=result["channel"], values=result["optimized_spend"],
                                     hole=0.45, marker=dict(colors=COLORS[:len(result)]),
                                     textinfo="label+percent", textfont=dict(size=9))])
        fp2.update_layout(**CHART_LAYOUT, title="Optimised", height=370)
        st.plotly_chart(fp2, use_container_width=True)


with t_table:
    st.markdown("#### Optimisation Details")
    disp = result.copy()
    disp["current_share"] = disp["current_spend"] / disp["current_spend"].sum() * 100
    disp["optimised_share"] = disp["optimized_spend"] / disp["optimized_spend"].sum() * 100
    disp = disp.rename(columns={
        "channel": "Channel", "current_spend": "Current Spend",
        "optimized_spend": "Optimised Spend", "spend_change": "Δ Spend ($)",
        "spend_change_pct": "Δ Spend (%)", "current_revenue": "Current Revenue",
        "optimized_revenue": "Optimised Revenue", "revenue_change": "Δ Revenue",
        "current_roi": "Current ROI", "optimized_roi": "Optimised ROI",
        "current_share": "Current %", "optimised_share": "Optimised %",
    })
    st.dataframe(disp, use_container_width=True, hide_index=True)

    ic, dc = st.columns(2)
    with ic:
        inc = result[result["spend_change"] > 1].sort_values("spend_change", ascending=False)
        st.markdown(
            '<div style="background:#F0FFF4; border:1px solid #C6F6D5; '
            'border-radius:10px; padding:1rem;">'
            '<h4 style="color:#276749;margin-top:0;">Increase Budget</h4>',
            unsafe_allow_html=True,
        )
        for _, r in inc.iterrows():
            st.markdown(f"**{r['channel']}**: {format_currency(r['current_spend'])} → "
                        f"{format_currency(r['optimized_spend'])} ({r['spend_change_pct']:+.0f}%)")
        if len(inc) == 0:
            st.markdown("*No increases*")
        st.markdown("</div>", unsafe_allow_html=True)
    with dc:
        dec_df = result[result["spend_change"] < -1].sort_values("spend_change")
        st.markdown(
            '<div style="background:#FFF5F5; border:1px solid #FED7D7; '
            'border-radius:10px; padding:1rem;">'
            '<h4 style="color:#9B2C2C;margin-top:0;">Decrease Budget</h4>',
            unsafe_allow_html=True,
        )
        for _, r in dec_df.iterrows():
            st.markdown(f"**{r['channel']}**: {format_currency(r['current_spend'])} → "
                        f"{format_currency(r['optimized_spend'])} ({r['spend_change_pct']:+.0f}%)")
        if len(dec_df) == 0:
            st.markdown("*No decreases*")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.download_button("Export CSV", disp.to_csv(index=False), "optimisation_plan.csv", "text/csv")


with t_ts:
    st.markdown("#### Weekly Budget Pacing")
    st.markdown("<p style='color:#64748B;'>Budget per channel per week, adjusted for demand seasonality.</p>",
                unsafe_allow_html=True)

    plan_weeks = st.slider("Planning weeks", 4, 52, sc.get("n_weeks", 12), key="wpace")

    if decomp is not None and len(decomp) >= plan_weeks:
        bl = decomp["baseline"].values[:plan_weeks]
        si = bl / bl.mean() if bl.mean() > 0 else np.ones(plan_weeks)
    else:
        si = 1 + 0.15 * np.sin(2 * np.pi * np.arange(plan_weeks) / 52)

    rows = []
    for _, r in result.iterrows():
        wb = r["optimized_spend"] / 52
        for w in range(plan_weeks):
            rows.append({"week": w + 1, "channel": r["channel"], "spend": wb * si[w]})
    wpiv = pd.DataFrame(rows).pivot(index="week", columns="channel", values="spend")

    fwk = go.Figure()
    for i, ch in enumerate(result["channel"]):
        if ch in wpiv.columns:
            fwk.add_trace(go.Bar(x=wpiv.index, y=wpiv[ch], name=ch,
                                 marker=dict(color=COLORS[i % len(COLORS)])))
    fwk.update_layout(**CHART_LAYOUT, barmode="stack", xaxis_title="Week",
                      yaxis_title="Spend ($)", height=470)
    st.plotly_chart(fwk, use_container_width=True)

    st.markdown("##### Seasonality Index")
    fsi = go.Figure()
    fsi.add_trace(go.Scatter(x=list(range(1, plan_weeks + 1)), y=si, mode="lines+markers",
                             marker=dict(size=5, color="#4A6CF7"), line=dict(color="#4A6CF7", width=2),
                             fill="tozeroy", fillcolor="rgba(74,108,247,0.06)"))
    fsi.add_hline(y=1.0, line=dict(color="rgba(245,101,101,0.3)", dash="dash"))
    fsi.update_layout(**CHART_LAYOUT, xaxis_title="Week", yaxis_title="Index", height=260)
    st.plotly_chart(fsi, use_container_width=True)


with t_rc:
    if response is not None:
        st.markdown("#### Response Curves")
        st.markdown("<p style='color:#64748B;'>Diamond = current spend. Circle = optimised spend.</p>",
                    unsafe_allow_html=True)
        avail = [ch for ch in response["channel"].unique().tolist() if ch in sel_channels]
        sel = st.multiselect("Channels", avail, default=avail[:4], key="rcsel")
        if sel:
            osm = dict(zip(result["channel"], result["optimized_spend"]))
            frc = go.Figure()
            for i, ch in enumerate(sel):
                cd = response[response["channel"] == ch]
                clr = COLORS[i % len(COLORS)]
                frc.add_trace(go.Scatter(x=cd["spend_level"], y=cd["incremental_revenue"],
                                         mode="lines", name=ch, line=dict(color=clr, width=2.5)))
                cs_val = float(cd["current_spend"].iloc[0])
                cr_val = float(cd["current_revenue"].iloc[0])
                frc.add_trace(go.Scatter(x=[cs_val], y=[cr_val], mode="markers", showlegend=False,
                                         marker=dict(size=13, color=clr, symbol="diamond",
                                                     line=dict(width=2, color="white"))))
                os_val = osm.get(ch, cs_val)
                or_val = float(np.interp(os_val, cd["spend_level"], cd["incremental_revenue"]))
                frc.add_trace(go.Scatter(x=[os_val], y=[or_val], mode="markers", showlegend=False,
                                         marker=dict(size=13, color=clr, symbol="circle",
                                                     line=dict(width=2, color="white"))))
            frc.update_layout(**CHART_LAYOUT, xaxis_title="Spend ($)",
                              yaxis_title="Incremental Revenue ($)", height=510)
            st.plotly_chart(frc, use_container_width=True)
    else:
        st.info("Response curve data not available.")


with t_decomp:
    st.markdown("#### Forecasted Sales Decomposition")
    st.markdown("<p style='color:#64748B;'>Base (organic) + media-driven revenue for current vs. optimised.</p>",
                unsafe_allow_html=True)
    base_val = float(decomp["baseline"].sum()) if decomp is not None else curr_rev_total * 0.6

    labels = ["Base Sales"] + list(result["channel"])
    c_vals = [base_val] + list(result["current_revenue"])
    o_vals = [base_val] + list(result["optimized_revenue"])
    dec_colors = ["#94A3B8"] + COLORS[:len(result)]

    d1, d2 = st.columns(2)
    with d1:
        fd1 = go.Figure(data=[go.Pie(labels=labels, values=c_vals, hole=0.5,
                                     marker=dict(colors=dec_colors), textinfo="label+percent",
                                     textfont=dict(size=9))])
        fd1.update_layout(**CHART_LAYOUT, title=f"Current — {format_currency(base_val + curr_rev_total)}", height=410)
        st.plotly_chart(fd1, use_container_width=True)
    with d2:
        fd2 = go.Figure(data=[go.Pie(labels=labels, values=o_vals, hole=0.5,
                                     marker=dict(colors=dec_colors), textinfo="label+percent",
                                     textfont=dict(size=9))])
        fd2.update_layout(**CHART_LAYOUT, title=f"Optimised — {format_currency(base_val + opt_rev_total)}", height=410)
        st.plotly_chart(fd2, use_container_width=True)

    st.markdown("##### Revenue Waterfall: Current → Optimised")
    wf_labels = ["Current"]
    wf_vals = [base_val + curr_rev_total]
    wf_measures = ["absolute"]
    for _, r in result.sort_values("revenue_change", ascending=False).iterrows():
        if abs(r["revenue_change"]) > 100:
            wf_labels.append(r["channel"])
            wf_vals.append(r["revenue_change"])
            wf_measures.append("relative")
    wf_labels.append("Optimised")
    wf_vals.append(base_val + opt_rev_total)
    wf_measures.append("total")

    fwf = go.Figure(go.Waterfall(
        x=wf_labels, y=wf_vals, measure=wf_measures,
        increasing=dict(marker=dict(color="#48BB78")),
        decreasing=dict(marker=dict(color="#F56565")),
        totals=dict(marker=dict(color="#4A6CF7")),
        connector=dict(line=dict(color="rgba(148,163,184,0.3)")),
        textposition="outside", texttemplate="%{y:$,.0f}",
        textfont=dict(size=9, color="#334155"),
    ))
    fwf.update_layout(**CHART_LAYOUT, yaxis_title="Revenue ($)", height=470)
    fwf.update_xaxes(tickangle=-45)
    st.plotly_chart(fwf, use_container_width=True)
