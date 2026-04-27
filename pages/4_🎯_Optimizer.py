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

# ── Scoped styling for a cleaner, denser left panel ──
st.markdown(
    """
    <style>
      /* Reduce vertical gaps inside the config panel */
      div[data-testid="stVerticalBlockBorderWrapper"] .stMarkdown { margin-bottom: 0.15rem; }
      div[data-testid="stVerticalBlockBorderWrapper"] hr { margin: 0.5rem 0; }
      /* Compact section label */
      .cfg-label { color:#64748B; font-size:0.72rem; font-weight:600;
                   text-transform:uppercase; letter-spacing:0.04em; margin-bottom:0.25rem; }
      .cfg-value { color:#1E293B; font-size:0.9rem; font-weight:500; }
      /* Slider labels smaller */
      div[data-testid="stVerticalBlockBorderWrapper"] .stSlider label { font-size:0.82rem !important; }
      /* Primary optimise button */
      .stButton > button[kind="primary"] { background:#F56565; border-color:#F56565; }
      .stButton > button[kind="primary"]:hover { background:#E53E3E; border-color:#E53E3E; }
      /* Scenario tab buttons */
      .sc-tab-row .stButton > button { border-radius:8px 8px 0 0; border-bottom:none; }
      /* Compact quick-select pill buttons (target by stable key-class) */
      [class*="st-key-_lq_"] button,
      [class*="st-key-_lqapply"] button {
          padding: 0.3rem 0.4rem !important;
          font-size: 0.78rem !important;
          line-height: 1.1 !important;
          white-space: nowrap !important;
          min-height: 0 !important;
          border-radius: 6px !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

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
spend_by_channel = {c: float(s) for c, s in zip(channels, current_spend)}

spec_min_map, spec_max_map = {}, {}
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


def _wl(d):
    return f"w{d.isocalendar()[1]:02d} {d.year}"


def _slider_range(ch, pct):
    """Return (lo, hi, min, max) bounds for a channel slider at the given ± pct."""
    cs = spend_by_channel[ch]
    abs_max = float(spec_max_map.get(ch, cs * 3))
    slider_max = max(abs_max, cs * 2, 1.0)
    if pct == 0:
        lo, hi = cs, cs
    elif pct >= 100:
        lo = float(spec_min_map.get(ch, 0))
        hi = abs_max
    else:
        lo = max(cs * (1 - pct / 100), 0.0)
        hi = min(cs * (1 + pct / 100), slider_max)
    return float(lo), float(hi), 0.0, float(slider_max)


if "_opt_scenarios" not in st.session_state:
    st.session_state["_opt_scenarios"] = []
if "_opt_active_idx" not in st.session_state:
    st.session_state["_opt_active_idx"] = None


# ══════════════════════════════════════════════════════════════
#  OPTIMIZATION ENGINE
# ══════════════════════════════════════════════════════════════

def _run_optimization(sc):
    ms, rc = media, response
    total_budget = sc["budget"]
    sel_ch = sc.get("selected_channels", channels)
    fms = ms[ms["channel"].isin(sel_ch)].reset_index(drop=True)
    fs = fms["spend"].values.astype(float)

    if sc["mode"] == "Reference scenario":
        return pd.DataFrame({
            "channel": fms["channel"], "current_spend": fs,
            "optimized_spend": fs.copy(), "spend_change": np.zeros(len(fms)),
            "spend_change_pct": np.zeros(len(fms)),
            "current_revenue": fms["incremental_revenue"].values.astype(float),
            "optimized_revenue": fms["incremental_revenue"].values.astype(float).copy(),
            "revenue_change": np.zeros(len(fms)),
            "current_roi": fms["roi"].values.astype(float),
            "optimized_roi": fms["roi"].values.astype(float).copy(),
        })

    if (budget_opt is not None
            and abs(total_budget - current_total) / max(current_total, 1) < 0.01
            and "Group ID" in budget_opt.columns):
        oa = budget_opt[budget_opt["Group ID"].str.contains(":ALL", na=False)].copy()
        if len(oa) >= len(sel_ch):
            osm = dict(zip(oa["Channel"], oa["Optimal Spend"].astype(float)))
            orm = dict(zip(oa["Channel"], oa["Optimal ROI"].astype(float)))
            os_ = np.array([osm.get(c, s) for c, s in zip(sel_ch, fs)])
            or_ = np.array([orm.get(c, r) for c, r in zip(sel_ch, fms["roi"].values)])
            orv = os_ * or_
            return pd.DataFrame({
                "channel": sel_ch, "current_spend": fs,
                "optimized_spend": os_, "spend_change": os_ - fs,
                "spend_change_pct": (os_ - fs) / (fs + 1e-6) * 100,
                "current_revenue": fms["incremental_revenue"].values.astype(float),
                "optimized_revenue": orv,
                "revenue_change": orv - fms["incremental_revenue"].values.astype(float),
                "current_roi": fms["roi"].values.astype(float), "optimized_roi": or_,
            })

    if rc is not None:
        frc = rc[rc["channel"].isin(sel_ch)]
        if len(frc) > 0:
            return compute_optimizer_scenarios(fms, frc, total_budget)

    mroi = fms["marginal_roi"].values if "marginal_roi" in fms.columns else fms["roi"].values
    mn = mroi / mroi.sum() if mroi.sum() > 0 else np.ones(len(mroi)) / len(mroi)
    os_ = total_budget * mn
    return pd.DataFrame({
        "channel": fms["channel"], "current_spend": fms["spend"],
        "optimized_spend": os_, "spend_change": os_ - fms["spend"].values,
        "spend_change_pct": (os_ - fms["spend"].values) / (fms["spend"].values + 1e-6) * 100,
        "current_revenue": fms["incremental_revenue"],
        "optimized_revenue": os_ * fms["roi"].values,
        "revenue_change": os_ * fms["roi"].values - fms["incremental_revenue"].values,
        "current_roi": fms["roi"], "optimized_roi": fms["roi"],
    })


# ══════════════════════════════════════════════════════════════
#  DIALOG — create new scenario
# ══════════════════════════════════════════════════════════════

@st.dialog("New Scenario", width="large")
def _new_scenario_dialog():
    existing = st.session_state.get("_opt_scenarios", [])
    copy_src = st.session_state.get("_opt_copy_from")

    c1, c2 = st.columns([2, 1])
    with c1:
        dn = f"{copy_src['name']} (copy)" if copy_src else f"Scenario {len(existing) + 1}"
        name = st.text_input("Scenario name", value=dn, key="_dn")
    with c2:
        stype = st.radio(
            "Type",
            ["New", "Copy own", "Copy public"],
            horizontal=True, key="_dt",
            index=1 if copy_src else 0,
        )
    if stype == "Copy own" and len(existing) > 0 and copy_src is None:
        si = st.selectbox("Copy from", range(len(existing)),
                          format_func=lambda i: existing[i]["name"], key="_dcs")
        copy_src = existing[si]
    elif stype == "Copy public":
        st.caption("No public scenarios available yet.")
    pf = copy_src

    st.markdown("**Optimization mode**")
    modes = ["Budget optimization", "Total sales target",
             "Incremental sales target", "Reference scenario", "Target ROI"]
    dm = modes.index(pf["mode"]) if pf and pf.get("mode") in modes else 0
    mode = st.radio("Mode", modes, index=dm, horizontal=True, key="_dm",
                    label_visibility="collapsed")
    tr = None
    if mode == "Budget optimization":
        budget = st.number_input("Budget ($)", value=float(pf["budget"] if pf else current_total),
                                 step=10000.0, format="%.0f", key="_db")
    elif mode in ("Total sales target", "Incremental sales target"):
        cr = float(media["incremental_revenue"].sum())
        tv = st.number_input("Target ($)", value=float(pf.get("budget", cr * 1.1) if pf else cr * 1.1),
                             step=50000.0, format="%.0f", key="_dtv")
        budget = current_total * (tv / cr) if cr > 0 else current_total
    elif mode == "Target ROI":
        tr = st.number_input("Target ROI (x)", value=float(pf.get("target_roi", 1.5) if pf else 1.5),
                             step=0.1, format="%.2f", key="_dtr")
        budget = current_total
    else:
        budget = current_total

    t1, t2 = st.columns(2)
    with t1:
        ps = st.date_input("Start", value=pf.get("period_start", _data_min) if pf else _data_min,
                           min_value=_data_min, max_value=_data_max, key="_dps")
    with t2:
        pe = st.date_input("End", value=pf.get("period_end", _data_max) if pf else _data_max,
                           min_value=_data_min, max_value=_data_max, key="_dpe")
    dw = max(1, (pe - ps).days // 7)
    st.caption(f"{_wl(ps)} — {_wl(pe)}  ·  {dw} weeks")

    dch = pf.get("selected_channels", channels) if pf else channels
    sel_ch = st.multiselect("Advertising channels", channels, default=dch, key="_dch")

    if st.button("Create scenario", use_container_width=True, type="primary", key="_dcreate"):
        sc = {
            "name": name, "mode": mode, "budget": budget,
            "period_start": ps, "period_end": pe, "n_weeks": dw,
            "selected_channels": sel_ch, "result": None,
            "ref_start": ps - timedelta(weeks=52),
            "ref_end": pe - timedelta(weeks=52),
            "target_roi": tr,
        }
        st.session_state["_opt_scenarios"].append(sc)
        st.session_state["_opt_active_idx"] = len(st.session_state["_opt_scenarios"]) - 1
        st.session_state.pop("_opt_copy_from", None)
        st.rerun()


# ══════════════════════════════════════════════════════════════
#  PAGE HEADER + SCENARIO TABS
# ══════════════════════════════════════════════════════════════

page_header("Media optimizer", "Configure a scenario, then optimise budget allocation across channels.")

scenarios = st.session_state["_opt_scenarios"]
active_idx = st.session_state["_opt_active_idx"]

# Apply pending quick-selection BEFORE any slider renders
if "_apply_pct" in st.session_state and active_idx is not None and active_idx < len(scenarios):
    _pct = st.session_state.pop("_apply_pct")
    _sc = scenarios[active_idx]
    for _ch in _sc.get("selected_channels", channels):
        _lo, _hi, _mn, _mx = _slider_range(_ch, _pct)
        st.session_state[f"_lrng_{_ch}"] = (_lo, _hi)

n_sc = len(scenarios)

# Scenario tabs (horizontal)
st.markdown('<div class="sc-tab-row">', unsafe_allow_html=True)
tab_cols = st.columns(max(n_sc + 1, 2))
for i in range(n_sc):
    with tab_cols[i]:
        is_act = (i == active_idx)
        if st.button(
            scenarios[i]["name"],
            key=f"_tab_{i}",
            use_container_width=True,
            type="primary" if is_act else "secondary",
        ):
            st.session_state["_opt_active_idx"] = i
            st.rerun()
with tab_cols[n_sc]:
    if st.button("➕ New", key="_tab_add", use_container_width=True):
        st.session_state.pop("_opt_copy_from", None)
        _new_scenario_dialog()
st.markdown("</div>", unsafe_allow_html=True)

if n_sc == 0:
    st.markdown(
        "<div style='text-align:center; padding:4rem 0; color:#94A3B8;'>"
        "<p style='font-size:1rem; color:#64748B;'>No scenarios yet. "
        "Click <b>➕ New</b> to create one.</p></div>",
        unsafe_allow_html=True,
    )
    st.stop()

if active_idx is None or active_idx >= n_sc:
    st.session_state["_opt_active_idx"] = 0
    active_idx = 0

sc = scenarios[active_idx]

# ══════════════════════════════════════════════════════════════
#  TWO-PANEL LAYOUT  (1 : 2  — more room for charts)
# ══════════════════════════════════════════════════════════════

left_col, right_col = st.columns([1, 2], gap="large")

# ─────────────────────────────────────────────────────────────
#  LEFT PANEL — scenario config
# ─────────────────────────────────────────────────────────────
with left_col:
    with st.container(border=True):
        # Name + action icons
        h1, h2, h3 = st.columns([4, 1, 1])
        with h1:
            new_name = st.text_input(
                "Scenario", value=sc["name"], key=f"_nm_{active_idx}",
                label_visibility="collapsed",
            )
            if new_name != sc["name"]:
                sc["name"] = new_name
        with h2:
            if st.button("📋", key="_sc_copy", help="Duplicate scenario", use_container_width=True):
                st.session_state["_opt_copy_from"] = sc
                _new_scenario_dialog()
        with h3:
            if st.button("🗑", key="_sc_del", help="Delete scenario", use_container_width=True):
                scenarios.pop(active_idx)
                st.session_state["_opt_active_idx"] = max(0, active_idx - 1) if scenarios else None
                st.rerun()

    # Time & budget
    with st.container(border=True):
        st.markdown('<div class="cfg-label">Time period to optimize</div>', unsafe_allow_html=True)
        tp1, tp2 = st.columns(2)
        with tp1:
            ps = st.date_input("Start", value=sc["period_start"], min_value=_data_min,
                               max_value=_data_max, key="_lps", label_visibility="collapsed")
        with tp2:
            pe = st.date_input("End", value=sc["period_end"], min_value=_data_min,
                               max_value=_data_max, key="_lpe", label_visibility="collapsed")
        sc["period_start"], sc["period_end"] = ps, pe
        dw = max(1, (pe - ps).days // 7)
        sc["n_weeks"] = dw
        st.markdown(
            f'<div class="cfg-value" style="color:#4A6CF7;">📅 {_wl(ps)} → {_wl(pe)}  '
            f'<span style="color:#64748B;">({dw} weeks)</span></div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="cfg-label" style="margin-top:0.75rem;">Budget</div>',
                    unsafe_allow_html=True)
        new_budget = st.number_input(
            "Budget", value=float(sc["budget"]), step=10000.0, format="%.0f",
            key="_lbudget", label_visibility="collapsed",
        )
        sc["budget"] = new_budget

        ref_s = sc.get("ref_start", ps - timedelta(weeks=52))
        ref_e = sc.get("ref_end", pe - timedelta(weeks=52))
        st.caption(f"Reference period: {_wl(ref_s)} → {_wl(ref_e)}")

    # Channel budget boundaries
    with st.container(border=True):
        st.markdown('<div class="cfg-label">Channel budget boundaries</div>',
                    unsafe_allow_html=True)
        st.caption("Apply a quick range to all channels:")

        pct_rows = [
            [("Fix", 0), ("± 5%", 5), ("± 10%", 10)],
            [("± 20%", 20), ("± 30%", 30), ("Full", 100)],
        ]
        for row in pct_rows:
            qc = st.columns(3, gap="small")
            for i, (lbl, pv) in enumerate(row):
                with qc[i]:
                    if st.button(lbl, key=f"_lq_{pv}", use_container_width=True):
                        st.session_state["_apply_pct"] = pv
                        st.rerun()

        cpc1, cpc2 = st.columns([2, 1])
        with cpc1:
            custom_pct = st.number_input(
                "Custom ± %", min_value=0, max_value=200, value=0,
                key="_lcpct", label_visibility="collapsed", placeholder="Custom %",
            )
        with cpc2:
            if st.button("Apply", key="_lqapply", use_container_width=True):
                st.session_state["_apply_pct"] = int(custom_pct)
                st.rerun()

        st.markdown("")  # small spacer

        # Channel selection
        sel_ch = sc.get("selected_channels", channels)
        sa_col, da_col = st.columns(2)
        with sa_col:
            if st.button("Select all", key="_lsall", use_container_width=True):
                sc["selected_channels"] = channels
                st.rerun()
        with da_col:
            if st.button("Clear all", key="_ldall", use_container_width=True):
                sc["selected_channels"] = []
                st.rerun()

        if len(sel_ch) == 0:
            st.caption("No channels selected.")
        else:
            st.caption(f"{len(sel_ch)} of {len(channels)} channels")

        # Sliders — values come from session_state keys set by quick-select
        bounds = {}
        for ch in sel_ch:
            key = f"_lrng_{ch}"
            if key not in st.session_state:
                lo, hi, _, _ = _slider_range(ch, 0)
                st.session_state[key] = (lo, hi)
            _, _, smn, smx = _slider_range(ch, 100)
            rng = st.slider(
                ch, min_value=smn, max_value=smx,
                format="$%.0f", key=key,
            )
            bounds[ch] = (rng[0], rng[1])
        sc["channel_bounds"] = bounds

    # Optimize buttons
    ob1, ob2 = st.columns([1, 2])
    with ob1:
        if st.button("Optimise all", key="_loptall", use_container_width=True):
            for s in scenarios:
                s["result"] = _run_optimization(s)
            st.rerun()
    with ob2:
        valid = len(sel_ch) > 0 and sc["budget"] > 0
        if st.button(
            "Optimise!", key="_lopt", use_container_width=True,
            type="primary", disabled=not valid,
        ):
            sc["result"] = _run_optimization(sc)
            st.rerun()


# ─────────────────────────────────────────────────────────────
#  RIGHT PANEL — results
# ─────────────────────────────────────────────────────────────
with right_col:
    result = sc.get("result")

    t_charts, t_table, t_ts, t_rc = st.tabs([
        "Result charts", "Result table", "Timeseries", "Response curves",
    ])

    if result is None:
        with t_charts:
            st.markdown(
                "<div style='text-align:center; padding:5rem 0; color:#94A3B8;'>"
                "<div style='font-size:3rem; margin-bottom:0.5rem;'>📊</div>"
                "<p style='font-size:1rem; color:#64748B;'>Configure the scenario on the left "
                "and click <b>Optimise!</b> to see results.</p></div>",
                unsafe_allow_html=True,
            )
        with t_table:
            st.caption("Run the optimiser to see the result table.")
        with t_ts:
            st.caption("Run the optimiser to see the time series view.")
        with t_rc:
            st.caption("Run the optimiser to see response curves.")
    else:
        total_budget = sc["budget"]
        sel_channels = sc["selected_channels"]

        curr_rev = float(result["current_revenue"].sum())
        opt_rev = float(result["optimized_revenue"].sum())
        uplift = opt_rev - curr_rev
        uplift_pct = uplift / curr_rev * 100 if curr_rev > 0 else 0
        fs_sum = float(result["current_spend"].sum())
        os_sum = float(result["optimized_spend"].sum())
        opt_roi = opt_rev / os_sum if os_sum > 0 else 0
        cur_roi = curr_rev / fs_sum if fs_sum > 0 else 0

        with t_charts:
            k = st.columns(4)
            k[0].metric("Current revenue", format_currency(curr_rev))
            k[1].metric("Optimised revenue", format_currency(opt_rev))
            k[2].metric("Uplift", format_currency(uplift), f"{uplift_pct:+.1f}%")
            k[3].metric("Optimised ROI", f"{opt_roi:.2f}x", f"{(opt_roi - cur_roi):+.2f}x")
            layout = {**CHART_LAYOUT, "margin": dict(l=20, r=80, t=30, b=40)}
            st.markdown("##### Budget allocation — current vs optimised")
            sr = result.sort_values("optimized_spend", ascending=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(y=sr["channel"], x=sr["current_spend"], name="Current",
                                 orientation="h", marker=dict(color="#CBD5E1"),
                                 text=[format_currency(v) for v in sr["current_spend"]],
                                 textposition="outside", textfont=dict(size=10)))
            fig.add_trace(go.Bar(y=sr["channel"], x=sr["optimized_spend"], name="Optimised",
                                 orientation="h", marker=dict(color="#4A6CF7"),
                                 text=[format_currency(v) for v in sr["optimized_spend"]],
                                 textposition="outside", textfont=dict(size=10)))
            fig.update_layout(**layout, barmode="group",
                              height=max(480, len(sel_channels) * 46),
                              xaxis_title="Spend ($)",
                            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("##### Share of spend")
            c1, c2 = st.columns(2)
            with c1:
                fp1 = go.Figure(data=[go.Pie(
                    labels=result["channel"], values=result["current_spend"], hole=0.55,
                    marker=dict(colors=COLORS[:len(result)]),
                    textinfo="percent", textfont=dict(size=11),
                )])
                fp1.update_layout(**layout, title="Current", height=400,
                                  margin=dict(l=10, r=10, t=50, b=10))
                st.plotly_chart(fp1, use_container_width=True)
            with c2:
                fp2 = go.Figure(data=[go.Pie(
                    labels=result["channel"], values=result["optimized_spend"], hole=0.55,
                    marker=dict(colors=COLORS[:len(result)]),
                    textinfo="percent", textfont=dict(size=11),
                )])
                fp2.update_layout(**layout, title="Optimised", height=400,
                                  margin=dict(l=10, r=10, t=50, b=10))
                st.plotly_chart(fp2, use_container_width=True)

        with t_table:
            disp = result.copy()
            disp["current_share"] = disp["current_spend"] / disp["current_spend"].sum() * 100
            disp["opt_share"] = disp["optimized_spend"] / disp["optimized_spend"].sum() * 100
            disp = disp.rename(columns={
                "channel": "Channel", "current_spend": "Current Spend",
                "optimized_spend": "Optimised Spend", "spend_change": "Δ Spend ($)",
                "spend_change_pct": "Δ Spend (%)", "current_revenue": "Current Revenue",
                "optimized_revenue": "Optimised Revenue", "revenue_change": "Δ Revenue",
                "current_roi": "Current ROI", "optimized_roi": "Optimised ROI",
                "current_share": "Current %", "opt_share": "Optimised %",
            })
            st.dataframe(disp, use_container_width=True, hide_index=True, height=420)

            ic, dc = st.columns(2)
            with ic:
                inc = result[result["spend_change"] > 1].sort_values("spend_change", ascending=False)
                st.markdown(
                    '<div style="background:#F0FFF4; border:1px solid #C6F6D5; '
                    'border-radius:10px; padding:1rem;">'
                    '<h5 style="color:#276749;margin-top:0;margin-bottom:0.5rem;">↑ Increase</h5>',
                    unsafe_allow_html=True)
                for _, r in inc.iterrows():
                    st.markdown(f"**{r['channel']}**: {format_currency(r['current_spend'])} → "
                                f"{format_currency(r['optimized_spend'])} ({r['spend_change_pct']:+.0f}%)")
                if len(inc) == 0:
                    st.markdown("*None*")
                st.markdown("</div>", unsafe_allow_html=True)
            with dc:
                dec_df = result[result["spend_change"] < -1].sort_values("spend_change")
                st.markdown(
                    '<div style="background:#FFF5F5; border:1px solid #FED7D7; '
                    'border-radius:10px; padding:1rem;">'
                    '<h5 style="color:#9B2C2C;margin-top:0;margin-bottom:0.5rem;">↓ Decrease</h5>',
                    unsafe_allow_html=True)
                for _, r in dec_df.iterrows():
                    st.markdown(f"**{r['channel']}**: {format_currency(r['current_spend'])} → "
                                f"{format_currency(r['optimized_spend'])} ({r['spend_change_pct']:+.0f}%)")
                if len(dec_df) == 0:
                    st.markdown("*None*")
                st.markdown("</div>", unsafe_allow_html=True)

            st.download_button("Export CSV", disp.to_csv(index=False),
                               "optimisation_plan.csv", "text/csv")

        with t_ts:
            st.markdown("##### Weekly budget pacing")
            pw = st.slider("Planning weeks", 4, 52, sc.get("n_weeks", 12), key="_wpace")
            if decomp is not None and len(decomp) >= pw:
                bl = decomp["baseline"].values[:pw]
                si = bl / bl.mean() if bl.mean() > 0 else np.ones(pw)
            else:
                si = 1 + 0.15 * np.sin(2 * np.pi * np.arange(pw) / 52)

            rows = []
            for _, r in result.iterrows():
                wb = r["optimized_spend"] / 52
                for w in range(pw):
                    rows.append({"week": w + 1, "channel": r["channel"], "spend": wb * si[w]})
            wpiv = pd.DataFrame(rows).pivot(index="week", columns="channel", values="spend")
            fwk = go.Figure()
            for i, ch in enumerate(result["channel"]):
                if ch in wpiv.columns:
                    fwk.add_trace(go.Bar(x=wpiv.index, y=wpiv[ch], name=ch,
                                         marker=dict(color=COLORS[i % len(COLORS)])))
            fwk.update_layout(**CHART_LAYOUT, barmode="stack",
                              xaxis_title="Week", yaxis_title="Spend ($)", height=480)
            st.plotly_chart(fwk, use_container_width=True)

        with t_rc:
            if response is not None:
                avail = [ch for ch in response["channel"].unique().tolist() if ch in sel_channels]
                sel = st.multiselect("Channels", avail, default=avail[:4], key="_rcsel")
                if sel:
                    osm = dict(zip(result["channel"], result["optimized_spend"]))
                    frc = go.Figure()
                    for i, ch in enumerate(sel):
                        cd = response[response["channel"] == ch]
                        clr = COLORS[i % len(COLORS)]
                        frc.add_trace(go.Scatter(
                            x=cd["spend_level"], y=cd["incremental_revenue"],
                            mode="lines", name=ch, line=dict(color=clr, width=2.5)))
                        cs_v = float(cd["current_spend"].iloc[0])
                        cr_v = float(cd["current_revenue"].iloc[0])
                        frc.add_trace(go.Scatter(
                            x=[cs_v], y=[cr_v], mode="markers", showlegend=False,
                            marker=dict(size=12, color=clr, symbol="diamond",
                                        line=dict(width=2, color="white"))))
                        os_v = osm.get(ch, cs_v)
                        or_v = float(np.interp(os_v, cd["spend_level"], cd["incremental_revenue"]))
                        frc.add_trace(go.Scatter(
                            x=[os_v], y=[or_v], mode="markers", showlegend=False,
                            marker=dict(size=12, color=clr, symbol="circle",
                                        line=dict(width=2, color="white"))))
                    frc.update_layout(**CHART_LAYOUT, xaxis_title="Spend ($)",
                                      yaxis_title="Incremental revenue ($)", height=520)
                    st.plotly_chart(frc, use_container_width=True)
            else:
                st.info("Response curve data not available.")
