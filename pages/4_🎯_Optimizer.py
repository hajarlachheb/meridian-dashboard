import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
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
    specs_all = budget_specs[budget_specs["Analysis Period"] == "ALL"] if "Analysis Period" in budget_specs.columns else budget_specs
    if "Channel Spend Min" in specs_all.columns:
        spec_min_map = dict(zip(specs_all["Channel"], specs_all["Channel Spend Min"].astype(float)))
    if "Channel Spend Max" in specs_all.columns:
        spec_max_map = dict(zip(specs_all["Channel"], specs_all["Channel Spend Max"].astype(float)))


def _fallback_optimize(ms, rc, budget):
    if rc is not None:
        return compute_optimizer_scenarios(ms, rc, budget)
    mroi = ms["marginal_roi"].values if "marginal_roi" in ms.columns else ms["roi"].values
    mroi_n = mroi / mroi.sum()
    opt_s = budget * mroi_n
    return pd.DataFrame({
        "channel": ms["channel"], "current_spend": ms["spend"],
        "optimized_spend": opt_s,
        "spend_change": opt_s - ms["spend"].values,
        "spend_change_pct": (opt_s - ms["spend"].values) / (ms["spend"].values + 1e-6) * 100,
        "current_revenue": ms["incremental_revenue"],
        "optimized_revenue": opt_s * ms["roi"].values,
        "revenue_change": opt_s * ms["roi"].values - ms["incremental_revenue"].values,
        "current_roi": ms["roi"], "optimized_roi": ms["roi"],
    })


page_header("Media Optimizer", "Build scenarios, optimise budget allocation, and forecast sales across channels")

show_results = st.session_state.get("_opt_show_results", False)


# ── STEP 1 — CREATE SCENARIO ──

st.markdown(
    "<div style='display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;'>"
    "<div style='width:30px;height:30px;border-radius:50%;background:#4A6CF7;"
    "display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:0.85rem;'>1</div>"
    "<span style='color:#1E293B;font-size:1.05rem;font-weight:600;'>Create Scenario</span>"
    "</div>",
    unsafe_allow_html=True,
)

cfg_cols = st.columns([2, 2, 2, 1])

with cfg_cols[0]:
    opt_mode = st.radio(
        "Optimization mode",
        ["Budget optimization", "Total sales target", "Incremental sales target",
         "Reference scenario", "Target ROI"],
        horizontal=False,
        help="Budget optimization = maximise sales for a fixed budget. "
             "Sales targets = find budget to hit a goal. "
             "Reference = replay current plan.",
    )

with cfg_cols[1]:
    if decomp is not None and "date" in decomp.columns:
        min_date = decomp["date"].min().date()
        max_date = decomp["date"].max().date()
    else:
        from datetime import date
        min_date = date(2023, 1, 2)
        max_date = date(2025, 8, 25)
    period = st.date_input(
        "Time period to optimise",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

with cfg_cols[2]:
    if opt_mode == "Budget optimization":
        total_budget = st.number_input(
            "Budget ($)", value=current_total, step=10000.0, format="%.0f",
        )
    elif opt_mode in ("Total sales target", "Incremental sales target"):
        current_rev = float(media["incremental_revenue"].sum())
        target_label = "Total sales target ($)" if opt_mode == "Total sales target" else "Incremental sales target ($)"
        target_rev = st.number_input(target_label, value=current_rev * 1.1, step=50000.0, format="%.0f")
        total_budget = current_total * (target_rev / current_rev) if current_rev > 0 else current_total
    elif opt_mode == "Target ROI":
        target_roi_val = st.number_input("Target ROI (x)", value=1.5, step=0.1, format="%.2f")
        total_budget = current_total
    else:
        total_budget = current_total

with cfg_cols[3]:
    st.markdown("<br>", unsafe_allow_html=True)
    budget_change_pct = (total_budget - current_total) / current_total * 100 if current_total > 0 else 0
    change_color = "#48BB78" if budget_change_pct >= 0 else "#F56565"
    st.markdown(
        f"<div style='text-align:center; padding:0.3rem;'>"
        f"<span style='color:#94A3B8; font-size:0.75rem;'>vs. current</span><br>"
        f"<strong style='color:{change_color}; font-size:1.4rem;'>{budget_change_pct:+.1f}%</strong></div>",
        unsafe_allow_html=True,
    )

st.markdown("---")


# ── CHANNEL BOUNDARIES ──

is_reference = opt_mode == "Reference scenario"

if not is_reference:
    st.markdown("##### Apply quick selection to all")

    q_cols = st.columns([1, 1, 1, 1, 1, 1, 0.3, 1, 0.3, 1])
    with q_cols[0]:
        if st.button("Reset", use_container_width=True):
            st.session_state["_qpct"] = 0
    with q_cols[1]:
        if st.button("±5%", use_container_width=True):
            st.session_state["_qpct"] = 5
    with q_cols[2]:
        if st.button("±10%", use_container_width=True):
            st.session_state["_qpct"] = 10
    with q_cols[3]:
        if st.button("±20%", use_container_width=True):
            st.session_state["_qpct"] = 20
    with q_cols[4]:
        if st.button("±30%", use_container_width=True):
            st.session_state["_qpct"] = 30
    with q_cols[5]:
        if st.button("Full Range", use_container_width=True):
            st.session_state["_qpct"] = 100
    with q_cols[7]:
        custom_pct = st.number_input("±%", min_value=0, max_value=200, value=0,
                                     label_visibility="collapsed", key="_custom_pct_input")
    with q_cols[9]:
        if st.button("Apply", use_container_width=True):
            st.session_state["_qpct"] = custom_pct

    global_pct = st.session_state.get("_qpct", 0)

    st.markdown("---")
    st.markdown("##### Media investment budget boundaries")

    header_cols = st.columns([3, 2, 4, 2, 2])
    header_cols[0].markdown("<span style='color:#64748B; font-size:0.8rem; font-weight:600;'>Channel</span>", unsafe_allow_html=True)
    header_cols[1].markdown("<span style='color:#64748B; font-size:0.8rem; font-weight:600;'>Min ($)</span>", unsafe_allow_html=True)
    header_cols[2].markdown("<span style='color:#64748B; font-size:0.8rem; font-weight:600;'>Budget Range</span>", unsafe_allow_html=True)
    header_cols[3].markdown("<span style='color:#64748B; font-size:0.8rem; font-weight:600;'>Max ($)</span>", unsafe_allow_html=True)
    header_cols[4].markdown("<span style='color:#64748B; font-size:0.8rem; font-weight:600;'>Mode</span>", unsafe_allow_html=True)

    channel_bounds = {}

    for idx, ch in enumerate(channels):
        cs = float(current_spend[idx])
        abs_max = float(spec_max_map.get(ch, cs * 3))

        if global_pct == 0:
            def_lo = cs
            def_hi = cs
        elif global_pct >= 100:
            def_lo = float(spec_min_map.get(ch, 0))
            def_hi = abs_max
        else:
            def_lo = max(cs * (1 - global_pct / 100), 0)
            def_hi = cs * (1 + global_pct / 100)

        row = st.columns([3, 2, 4, 2, 2])

        with row[0]:
            st.markdown(
                f"<div style='padding-top:0.45rem;'>"
                f"<span style='color:#1E293B; font-size:0.9rem;'>{ch}</span><br>"
                f"<span style='color:#94A3B8; font-size:0.7rem;'>Current: {format_currency(cs)}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with row[1]:
            lo = st.number_input("min", value=float(int(def_lo)), step=1000.0, format="%.0f",
                                 label_visibility="collapsed", key=f"lo_{ch}")

        with row[2]:
            slider_max = max(abs_max, cs * 2, 1)
            rng = st.slider(
                "rng", min_value=0.0, max_value=float(slider_max),
                value=(float(lo), float(min(def_hi, slider_max))),
                format="$%.0f", label_visibility="collapsed", key=f"rng_{ch}",
            )

        with row[3]:
            hi = st.number_input("max", value=float(int(rng[1])), step=1000.0, format="%.0f",
                                 label_visibility="collapsed", key=f"hi_{ch}")

        with row[4]:
            mode = st.radio("m", ["Range", "Single", "Full"],
                            horizontal=True, label_visibility="collapsed", key=f"mode_{ch}")
            if mode == "Single":
                lo = cs
                hi = cs
            elif mode == "Full":
                lo = float(spec_min_map.get(ch, 0))
                hi = abs_max

        channel_bounds[ch] = (lo, hi)

else:
    channel_bounds = {ch: (float(cs), float(cs)) for ch, cs in zip(channels, current_spend)}

st.markdown("---")


# ── COMPUTE BUTTON ──

_, btn_col, _ = st.columns([2, 3, 2])
with btn_col:
    st.markdown(
        "<style>"
        "#opt_run_btn > button {"
        "  background: #4A6CF7 !important; color: white !important;"
        "  font-size: 1.05rem !important; padding: 0.7rem 2rem !important;"
        "  border-radius: 10px !important; border: none !important;"
        "}"
        "#opt_run_btn > button:hover {"
        "  background: #3B5DE7 !important;"
        "  box-shadow: 0 4px 14px rgba(74,108,247,0.3) !important;"
        "}"
        "</style>",
        unsafe_allow_html=True,
    )
    run_clicked = st.button("Compute Optimisation", use_container_width=True, key="opt_run_btn")
    if run_clicked:
        st.session_state["_opt_show_results"] = True
        show_results = True

if not show_results:
    st.markdown(
        "<div style='text-align:center; padding:3rem 0; color:#94A3B8;'>"
        "<p style='font-size:1rem;'>Configure your scenario above, then click <b>Compute Optimisation</b> to see results.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()


# ── STEP 2 — RESULTS ──

st.markdown("---")
st.markdown(
    "<div style='display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;'>"
    "<div style='width:30px;height:30px;border-radius:50%;background:#48BB78;"
    "display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:0.85rem;'>2</div>"
    "<span style='color:#1E293B;font-size:1.05rem;font-weight:600;'>Optimisation Results</span>"
    "</div>",
    unsafe_allow_html=True,
)

if is_reference:
    result = pd.DataFrame({
        "channel": channels,
        "current_spend": current_spend,
        "optimized_spend": current_spend.copy(),
        "spend_change": np.zeros(len(channels)),
        "spend_change_pct": np.zeros(len(channels)),
        "current_revenue": media["incremental_revenue"].values.astype(float),
        "optimized_revenue": media["incremental_revenue"].values.astype(float).copy(),
        "revenue_change": np.zeros(len(channels)),
        "current_roi": media["roi"].values.astype(float),
        "optimized_roi": media["roi"].values.astype(float).copy(),
    })
elif (budget_opt is not None
      and abs(total_budget - current_total) / max(current_total, 1) < 0.01
      and "Group ID" in budget_opt.columns):
    opt_all = budget_opt[budget_opt["Group ID"].str.contains(":ALL", na=False)].copy()
    if len(opt_all) >= len(channels):
        osm = dict(zip(opt_all["Channel"], opt_all["Optimal Spend"].astype(float)))
        orm = dict(zip(opt_all["Channel"], opt_all["Optimal ROI"].astype(float)))
        opt_s = np.array([osm.get(ch, cs) for ch, cs in zip(channels, current_spend)])
        opt_r = np.array([orm.get(ch, r) for ch, r in zip(channels, media["roi"].values)])
        opt_rev = opt_s * opt_r
        result = pd.DataFrame({
            "channel": channels, "current_spend": current_spend,
            "optimized_spend": opt_s, "spend_change": opt_s - current_spend,
            "spend_change_pct": (opt_s - current_spend) / (current_spend + 1e-6) * 100,
            "current_revenue": media["incremental_revenue"].values.astype(float),
            "optimized_revenue": opt_rev,
            "revenue_change": opt_rev - media["incremental_revenue"].values.astype(float),
            "current_roi": media["roi"].values.astype(float), "optimized_roi": opt_r,
        })
    else:
        result = _fallback_optimize(media, response, total_budget)
else:
    result = _fallback_optimize(media, response, total_budget)


# ── KPI ROW ──

curr_rev_total = float(result["current_revenue"].sum())
opt_rev_total = float(result["optimized_revenue"].sum())
uplift = opt_rev_total - curr_rev_total
uplift_pct = uplift / curr_rev_total * 100 if curr_rev_total > 0 else 0

k = st.columns(5)
k[0].metric("Current Revenue", format_currency(curr_rev_total))
k[1].metric("Optimised Revenue", format_currency(opt_rev_total))
k[2].metric("Revenue Uplift", format_currency(uplift), f"{uplift_pct:+.1f}%")
opt_roi_total = opt_rev_total / total_budget if total_budget > 0 else 0
cur_roi_total = curr_rev_total / current_total if current_total > 0 else 0
k[3].metric("Optimised ROI", f"{opt_roi_total:.2f}x", f"{(opt_roi_total - cur_roi_total):+.2f}x")
n_up = int((result["spend_change"] > 1).sum())
n_dn = int((result["spend_change"] < -1).sum())
k[4].metric("Reallocation", f"{n_up} ↑  {n_dn} ↓")

st.markdown("---")


# ── RESULT TABS ──

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
                      height=max(440, len(channels) * 40), xaxis_title="Spend ($)")
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
                           height=max(400, len(channels) * 34), xaxis_title="ROI")
        st.plotly_chart(fig2, use_container_width=True)
    with c2:
        st.markdown("##### Budget Change")
        sc = result.sort_values("spend_change", ascending=False)
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=sc["channel"], y=sc["spend_change"],
            marker=dict(color=["#48BB78" if v > 0 else "#F56565" for v in sc["spend_change"]], opacity=0.85),
            text=[f"{v:+,.0f}" for v in sc["spend_change"]], textposition="outside",
            textfont=dict(size=9, color="#334155"),
        ))
        fig3.update_layout(**CHART_LAYOUT, height=max(400, len(channels) * 34),
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
        dec = result[result["spend_change"] < -1].sort_values("spend_change")
        st.markdown(
            '<div style="background:#FFF5F5; border:1px solid #FED7D7; '
            'border-radius:10px; padding:1rem;">'
            '<h4 style="color:#9B2C2C;margin-top:0;">Decrease Budget</h4>',
            unsafe_allow_html=True,
        )
        for _, r in dec.iterrows():
            st.markdown(f"**{r['channel']}**: {format_currency(r['current_spend'])} → "
                        f"{format_currency(r['optimized_spend'])} ({r['spend_change_pct']:+.0f}%)")
        if len(dec) == 0:
            st.markdown("*No decreases*")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.download_button("Export CSV", disp.to_csv(index=False), "optimisation_plan.csv", "text/csv")


with t_ts:
    st.markdown("#### Weekly Budget Pacing")
    st.markdown("<p style='color:#64748B;'>Budget per channel per week, adjusted for demand seasonality.</p>",
                unsafe_allow_html=True)

    n_weeks = st.slider("Planning weeks", 4, 52, 12, key="wpace")

    if decomp is not None and len(decomp) >= n_weeks:
        bl = decomp["baseline"].values[:n_weeks]
        si = bl / bl.mean() if bl.mean() > 0 else np.ones(n_weeks)
    else:
        si = 1 + 0.15 * np.sin(2 * np.pi * np.arange(n_weeks) / 52)

    rows = []
    for _, r in result.iterrows():
        wb = r["optimized_spend"] / 52
        for w in range(n_weeks):
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
    fsi.add_trace(go.Scatter(x=list(range(1, n_weeks + 1)), y=si, mode="lines+markers",
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
        avail = response["channel"].unique().tolist()
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
    base = float(decomp["baseline"].sum()) if decomp is not None else curr_rev_total * 0.6

    labels = ["Base Sales"] + list(result["channel"])
    c_vals = [base] + list(result["current_revenue"])
    o_vals = [base] + list(result["optimized_revenue"])
    dec_colors = ["#94A3B8"] + COLORS[:len(result)]

    d1, d2 = st.columns(2)
    with d1:
        fd1 = go.Figure(data=[go.Pie(labels=labels, values=c_vals, hole=0.5,
                                     marker=dict(colors=dec_colors), textinfo="label+percent",
                                     textfont=dict(size=9))])
        fd1.update_layout(**CHART_LAYOUT, title=f"Current — {format_currency(base + curr_rev_total)}", height=410)
        st.plotly_chart(fd1, use_container_width=True)
    with d2:
        fd2 = go.Figure(data=[go.Pie(labels=labels, values=o_vals, hole=0.5,
                                     marker=dict(colors=dec_colors), textinfo="label+percent",
                                     textfont=dict(size=9))])
        fd2.update_layout(**CHART_LAYOUT, title=f"Optimised — {format_currency(base + opt_rev_total)}", height=410)
        st.plotly_chart(fd2, use_container_width=True)

    st.markdown("##### Revenue Waterfall: Current → Optimised")
    wf_labels = ["Current"]
    wf_vals = [base + curr_rev_total]
    wf_measures = ["absolute"]
    for _, r in result.sort_values("revenue_change", ascending=False).iterrows():
        if abs(r["revenue_change"]) > 100:
            wf_labels.append(r["channel"])
            wf_vals.append(r["revenue_change"])
            wf_measures.append("relative")
    wf_labels.append("Optimised")
    wf_vals.append(base + opt_rev_total)
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
