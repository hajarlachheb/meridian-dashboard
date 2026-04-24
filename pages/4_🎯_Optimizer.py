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


def _wl(d):
    return f"w{d.isocalendar()[1]:02d} {d.year}"


if "_opt_scenarios" not in st.session_state:
    st.session_state["_opt_scenarios"] = []
if "_opt_active_idx" not in st.session_state:
    st.session_state["_opt_active_idx"] = None


def _run_optimization(sc):
    ms = media
    rc = response
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
    mn = mroi / mroi.sum()
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

    st.markdown("##### Scenario Identity")
    c1, c2 = st.columns(2)
    with c1:
        dn = f"Scenario {len(existing) + 1}"
        if copy_src:
            dn = f"{copy_src['name']} (copy)"
        name = st.text_input("Name", value=dn, key="_dn")
    with c2:
        stype = st.radio("Type", ["New scenario", "Copy own scenario", "Copy public scenario"],
                         horizontal=True, key="_dt")
    if stype == "Copy own scenario" and len(existing) > 0 and copy_src is None:
        si = st.selectbox("Copy from", range(len(existing)),
                          format_func=lambda i: existing[i]["name"], key="_dcs")
        copy_src = existing[si]
    elif stype == "Copy public scenario":
        st.info("No public scenarios available yet.")
    pf = copy_src

    st.markdown("---")
    st.markdown("##### Optimization Mode")
    modes = ["Budget optimization", "Total sales target",
             "Incremental sales target", "Reference scenario", "Target ROI"]
    dm = modes.index(pf["mode"]) if pf and pf.get("mode") in modes else 0
    mode = st.radio("Mode", modes, index=dm, key="_dm")
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

    st.markdown("---")
    st.markdown("##### Time Period")
    t1, t2 = st.columns(2)
    with t1:
        ps = st.date_input("Start", value=pf.get("period_start", _data_min) if pf else _data_min,
                           min_value=_data_min, max_value=_data_max, key="_dps")
    with t2:
        pe = st.date_input("End", value=pf.get("period_end", _data_max) if pf else _data_max,
                           min_value=_data_min, max_value=_data_max, key="_dpe")
    dw = max(1, (pe - ps).days // 7)
    st.caption(f"{_wl(ps)} — {_wl(pe)}  ({dw} weeks)")

    st.markdown("---")
    st.markdown("##### Dimensions")
    dch = pf.get("selected_channels", channels) if pf else channels
    sel_ch = st.multiselect("Advertising channels", channels, default=dch, key="_dch")
    st.caption(f"{len(sel_ch)} selected")

    st.markdown(
        "<style>#_dcreate > button { background:#4A6CF7 !important; color:white !important; "
        "border:none !important; font-size:1rem !important; padding:0.6rem !important; "
        "border-radius:10px !important; }"
        "#_dcreate > button:hover { background:#3B5DE7 !important; }</style>",
        unsafe_allow_html=True,
    )
    if st.button("Create Scenario", use_container_width=True, key="_dcreate"):
        sc = {
            "name": name, "mode": mode, "budget": budget,
            "period_start": ps, "period_end": pe, "n_weeks": dw,
            "selected_channels": sel_ch, "result": None,
            "ref_start": ps - timedelta(weeks=52), "ref_end": pe - timedelta(weeks=52),
            "target_roi": tr if mode == "Target ROI" else None,
        }
        st.session_state["_opt_scenarios"].append(sc)
        st.session_state["_opt_active_idx"] = len(st.session_state["_opt_scenarios"]) - 1
        st.session_state.pop("_opt_copy_from", None)
        st.rerun()


# ══════════════════════════════════════════════════════════════
#  PAGE HEADER
# ══════════════════════════════════════════════════════════════

page_header("Media optimizer", "")

scenarios = st.session_state["_opt_scenarios"]
active_idx = st.session_state["_opt_active_idx"]

# ── Scenario tabs row ──
n_sc = len(scenarios)
tab_cols = st.columns(min(n_sc + 1, 8))
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
with tab_cols[min(n_sc, 7)]:
    if st.button("+", key="_tab_add", use_container_width=True):
        st.session_state.pop("_opt_copy_from", None)
        _new_scenario_dialog()

# ── Empty state ──
if n_sc == 0:
    st.markdown(
        "<div style='text-align:center; padding:4rem 0; color:#94A3B8;'>"
        "<p style='font-size:1rem; color:#64748B;'>No scenarios yet. "
        "Click <b>+</b> to create one.</p></div>",
        unsafe_allow_html=True,
    )
    st.stop()

if active_idx is None or active_idx >= n_sc:
    st.session_state["_opt_active_idx"] = 0
    active_idx = 0

sc = scenarios[active_idx]

# ══════════════════════════════════════════════════════════════
#  TWO-PANEL LAYOUT:  left=config  |  right=results
# ══════════════════════════════════════════════════════════════

left_col, right_col = st.columns([2, 3], gap="large")

# ─────────────────────────────────────────────────────────────
#  LEFT PANEL — scenario config (editable inline)
# ─────────────────────────────────────────────────────────────
with left_col:
    # header with action buttons
    lh1, lh2, lh3, lh4 = st.columns([3, 1, 1, 1])
    with lh1:
        new_name = st.text_input("Scenario", value=sc["name"], key="_sc_name",
                                 label_visibility="collapsed")
        if new_name != sc["name"]:
            sc["name"] = new_name
    with lh2:
        if st.button("🗑", key="_sc_del", help="Delete scenario"):
            scenarios.pop(active_idx)
            st.session_state["_opt_active_idx"] = max(0, active_idx - 1) if scenarios else None
            st.rerun()
    with lh3:
        if st.button("📋", key="_sc_copy", help="Copy scenario"):
            st.session_state["_opt_copy_from"] = sc
            _new_scenario_dialog()
    with lh4:
        if st.button("✏️", key="_sc_edit", help="Edit in dialog"):
            st.session_state["_opt_copy_from"] = sc
            _new_scenario_dialog()

    st.markdown("---")

    # Time period + budget
    tp1, tp2 = st.columns(2)
    with tp1:
        st.markdown("<span style='color:#64748B; font-size:0.78rem; font-weight:600;'>Time period to optimize</span>",
                    unsafe_allow_html=True)
        ps = st.date_input("s", value=sc["period_start"], min_value=_data_min, max_value=_data_max,
                           key="_lps", label_visibility="collapsed")
        pe = st.date_input("e", value=sc["period_end"], min_value=_data_min, max_value=_data_max,
                           key="_lpe", label_visibility="collapsed")
        sc["period_start"] = ps
        sc["period_end"] = pe
        dw = max(1, (pe - ps).days // 7)
        sc["n_weeks"] = dw
        st.caption(f"{_wl(ps)} > {_wl(pe)}")

    with tp2:
        st.markdown("<span style='color:#64748B; font-size:0.78rem; font-weight:600;'>Budget optimization</span>",
                    unsafe_allow_html=True)
        new_budget = st.number_input("b", value=float(sc["budget"]), step=10000.0, format="%.0f",
                                     key="_lbudget", label_visibility="collapsed")
        sc["budget"] = new_budget
        st.caption("$")

    ref_s = sc.get("ref_start", ps - timedelta(weeks=52))
    ref_e = sc.get("ref_end", pe - timedelta(weeks=52))
    st.markdown(
        f"<span style='color:#64748B; font-size:0.78rem;'>Reference time period: "
        f"<b>{_wl(ref_s)}</b> to <b>{_wl(ref_e)}</b></span>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Promo / Baseline scenario
    pr1, pr2 = st.columns(2)
    with pr1:
        st.markdown("<span style='color:#F56565; font-size:0.78rem; font-weight:600;'>Promo scenario</span>",
                    unsafe_allow_html=True)
        st.selectbox("p", ["Last 12 weeks..."], key="_lpromo", label_visibility="collapsed")
    with pr2:
        st.markdown("<span style='color:#48BB78; font-size:0.78rem; font-weight:600;'>Baseline scenario</span>",
                    unsafe_allow_html=True)
        st.selectbox("b", ["Last 12 weeks..."], key="_lbase", label_visibility="collapsed")

    st.markdown("---")

    # Grouping
    st.markdown("<span style='color:#64748B; font-size:0.78rem; font-weight:600;'>Grouping by</span>",
                unsafe_allow_html=True)
    st.caption("Advertising channel")

    st.markdown("---")

    # Quick selection
    st.markdown("<span style='color:#64748B; font-size:0.78rem; font-weight:600;'>Apply quick selection to all</span>",
                unsafe_allow_html=True)
    pct_labels = {"Reset": 0, "+/-5%": 5, "+/-10%": 10, "+/-20%": 20, "+/-30%": 30, "Full Range": 100}
    qc = st.columns(len(pct_labels))
    for i, (lbl, pv) in enumerate(pct_labels.items()):
        with qc[i]:
            if st.button(lbl, key=f"_lq_{pv}", use_container_width=True):
                st.session_state["_lqpct"] = pv

    qr1, qr2, qr3 = st.columns([1, 1, 1])
    with qr1:
        st.caption("+/-")
    with qr2:
        custom_pct = st.number_input("c", min_value=0, max_value=200, value=0,
                                     label_visibility="collapsed", key="_lcpct")
    with qr3:
        if st.button("Apply", key="_lqapply", use_container_width=True):
            st.session_state["_lqpct"] = custom_pct

    global_pct = st.session_state.get("_lqpct", 0)

    st.markdown("---")

    # Calendar weeks
    st.caption(f"📅  Calendar weeks")

    # Group by
    st.markdown("<span style='color:#64748B; font-size:0.78rem; font-weight:600;'>Group by</span>",
                unsafe_allow_html=True)
    st.radio("gb", ["None", "Ad platform", "Advertising channel"],
             horizontal=True, label_visibility="collapsed", key="_lgb")

    st.markdown("---")

    # Media investment budgets boundaries
    st.markdown("<span style='color:#64748B; font-size:0.78rem; font-weight:600;'>"
                "Media investment budgets boundaries</span>", unsafe_allow_html=True)

    sel_ch = sc.get("selected_channels", channels)
    sa_col, da_col = st.columns(2)
    with sa_col:
        if st.button("Select all", key="_lsall", use_container_width=True):
            sc["selected_channels"] = channels
            st.rerun()
    with da_col:
        if st.button("Deselect all", key="_ldall", use_container_width=True):
            sc["selected_channels"] = []
            st.rerun()

    bounds = {}
    for ch in sel_ch:
        ci = channels.index(ch)
        cs = float(current_spend[ci])
        am = float(spec_max_map.get(ch, cs * 3))
        if global_pct == 0:
            dl, dh = cs, cs
        elif global_pct >= 100:
            dl = float(spec_min_map.get(ch, 0))
            dh = am
        else:
            dl = max(cs * (1 - global_pct / 100), 0)
            dh = cs * (1 + global_pct / 100)
        sm = max(am, cs * 2, 1)
        rng = st.slider(
            ch, min_value=0.0, max_value=float(sm),
            value=(float(dl), float(min(dh, sm))),
            format="$%.0f", key=f"_lrng_{ch}",
        )
        bounds[ch] = (rng[0], rng[1])
    sc["channel_bounds"] = bounds

    st.caption(f"📅  Optimize: {dw} weeks")

    # Validity
    valid = len(sel_ch) > 0 and sc["budget"] > 0
    if valid:
        st.success("Scenario is valid and can be optimized.")
    else:
        st.warning("Select at least one channel and set a budget.")

    st.markdown("---")

    # Optimize buttons
    ob1, ob2 = st.columns(2)
    with ob1:
        if st.button("Optimize all", key="_loptall", use_container_width=True):
            for s in scenarios:
                s["result"] = _run_optimization(s)
            st.rerun()
    with ob2:
        st.markdown(
            "<style>#_lopt > button { background:#F56565 !important; color:white !important; "
            "border:none !important; border-radius:8px !important; font-weight:600 !important; }"
            "#_lopt > button:hover { background:#E53E3E !important; }</style>",
            unsafe_allow_html=True,
        )
        if st.button("Optimize!", key="_lopt", use_container_width=True):
            sc["result"] = _run_optimization(sc)
            st.rerun()


# ─────────────────────────────────────────────────────────────
#  RIGHT PANEL — results
# ─────────────────────────────────────────────────────────────
with right_col:
    result = sc.get("result")

    t_charts, t_table, t_ts, t_rc = st.tabs([
        "Result Charts", "Result Table", "Timeseries", "Response curves",
    ])

    if result is None:
        with t_charts:
            st.markdown(
                "<div style='text-align:center; padding:4rem 0; color:#94A3B8;'>"
                "<p style='font-size:1rem;'>No scenarios optimized or selected.</p></div>",
                unsafe_allow_html=True,
            )
        st.stop()

    total_budget = sc["budget"]
    sel_channels = sc["selected_channels"]

    # ── KPI row (above tabs) ──
    curr_rev = float(result["current_revenue"].sum())
    opt_rev = float(result["optimized_revenue"].sum())
    uplift = opt_rev - curr_rev
    uplift_pct = uplift / curr_rev * 100 if curr_rev > 0 else 0

    with t_charts:
        k = st.columns(4)
        k[0].metric("Current Revenue", format_currency(curr_rev))
        k[1].metric("Optimised Revenue", format_currency(opt_rev))
        k[2].metric("Revenue Uplift", format_currency(uplift), f"{uplift_pct:+.1f}%")
        fs = result["current_spend"].values
        opr = opt_rev / total_budget if total_budget > 0 else 0
        cr = curr_rev / float(fs.sum()) if fs.sum() > 0 else 0
        k[3].metric("Optimised ROI", f"{opr:.2f}x", f"{(opr - cr):+.2f}x")

        st.markdown("---")

        st.markdown("#### Budget Allocation")
        sr = result.sort_values("current_spend", ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(y=sr["channel"], x=sr["current_spend"], name="Current",
                             orientation="h", marker=dict(color="rgba(74,108,247,0.55)")))
        fig.add_trace(go.Bar(y=sr["channel"], x=sr["optimized_spend"], name="Optimised",
                             orientation="h", marker=dict(color="rgba(72,187,120,0.55)")))
        fig.update_layout(**CHART_LAYOUT, barmode="group",
                          height=max(380, len(sel_channels) * 36), xaxis_title="Spend ($)")
        st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            fp1 = go.Figure(data=[go.Pie(labels=result["channel"], values=result["current_spend"],
                                         hole=0.45, marker=dict(colors=COLORS[:len(result)]),
                                         textinfo="label+percent", textfont=dict(size=8))])
            fp1.update_layout(**CHART_LAYOUT, title="Current", height=320)
            st.plotly_chart(fp1, use_container_width=True)
        with c2:
            fp2 = go.Figure(data=[go.Pie(labels=result["channel"], values=result["optimized_spend"],
                                         hole=0.45, marker=dict(colors=COLORS[:len(result)]),
                                         textinfo="label+percent", textfont=dict(size=8))])
            fp2.update_layout(**CHART_LAYOUT, title="Optimised", height=320)
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
        st.dataframe(disp, use_container_width=True, hide_index=True)

        ic, dc = st.columns(2)
        with ic:
            inc = result[result["spend_change"] > 1].sort_values("spend_change", ascending=False)
            st.markdown(
                '<div style="background:#F0FFF4; border:1px solid #C6F6D5; '
                'border-radius:10px; padding:0.8rem;">'
                '<h5 style="color:#276749;margin-top:0;">Increase</h5>',
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
                'border-radius:10px; padding:0.8rem;">'
                '<h5 style="color:#9B2C2C;margin-top:0;">Decrease</h5>',
                unsafe_allow_html=True)
            for _, r in dec_df.iterrows():
                st.markdown(f"**{r['channel']}**: {format_currency(r['current_spend'])} → "
                            f"{format_currency(r['optimized_spend'])} ({r['spend_change_pct']:+.0f}%)")
            if len(dec_df) == 0:
                st.markdown("*None*")
            st.markdown("</div>", unsafe_allow_html=True)

        st.download_button("Export CSV", disp.to_csv(index=False), "optimisation_plan.csv", "text/csv")

    with t_ts:
        st.markdown("#### Weekly Budget Pacing")
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
        fwk.update_layout(**CHART_LAYOUT, barmode="stack", xaxis_title="Week",
                          yaxis_title="Spend ($)", height=420)
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
                    frc.add_trace(go.Scatter(x=cd["spend_level"], y=cd["incremental_revenue"],
                                             mode="lines", name=ch, line=dict(color=clr, width=2.5)))
                    cs_v = float(cd["current_spend"].iloc[0])
                    cr_v = float(cd["current_revenue"].iloc[0])
                    frc.add_trace(go.Scatter(x=[cs_v], y=[cr_v], mode="markers", showlegend=False,
                                             marker=dict(size=12, color=clr, symbol="diamond",
                                                         line=dict(width=2, color="white"))))
                    os_v = osm.get(ch, cs_v)
                    or_v = float(np.interp(os_v, cd["spend_level"], cd["incremental_revenue"]))
                    frc.add_trace(go.Scatter(x=[os_v], y=[or_v], mode="markers", showlegend=False,
                                             marker=dict(size=12, color=clr, symbol="circle",
                                                         line=dict(width=2, color="white"))))
                frc.update_layout(**CHART_LAYOUT, xaxis_title="Spend ($)",
                                  yaxis_title="Incremental Revenue ($)", height=460)
                st.plotly_chart(frc, use_container_width=True)
        else:
            st.info("Response curve data not available.")
